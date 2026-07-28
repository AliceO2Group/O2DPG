# CLAUDE.md — AODBcRewriter Development Handoff

## Current work state (2026-07-28) — O2-7098

**Branch:** `swenzel/O2-7098-aodbcrewriter-index-remap`.

### The bug: O2fwdtrack's match indices were reordered but not remapped

Reported by Maurice Coquet (JIRA **O2-7098**, patch proposal
[O2DPG#2418](https://github.com/AliceO2Group/O2DPG/pull/2418)): in anchored MC
AO2Ds produced since early June 2026, `O2fwdtrack.fIndexMFTTracks` and
`O2fwdtrack.fIndexFwdTracks_MatchMCHTrack` point at the wrong rows, so the MFT
leg and the MCH leg of every global muon belong to different MC particles
(`sameParticle=0`).

**Cause.** Stage 1b (added by #2370, merged 4 Jun 2026) re-sorts `O2track_iu`,
`O2mfttrack_*` and `O2fwdtrack`, but wrote each table the moment it had planned
it. `O2fwdtrack` points at `O2mfttrack` — reordered later in the same loop — and
at *itself*; neither permutation existed yet at write time, so the two columns
kept pre-reorder row numbers. They stayed in range, so every structural check
passed.

**Scope.** The corruption does *not* need the BC→collision reorder cascade.
Stage 1b re-sorts unconditionally to make the split `-1` group contiguous, so in
practice **every merged MC AO2D since 4 Jun 2026 is affected**.

**Reproduced** on `example_AOD/AO2D_pre.root`: 171 fwd tracks with an MFT match,
`sameParticle` 30 → **0** with the pre-fix code, 30 → **30** with the fix.

### What the fix does

1. **One index registry, `kIndexRefs` (Section 1).** Every `fIndex*` column and
   the table it points at, in one place, used by the rewriter, the validator and
   the drift guard alike. Referent resolution is `isTableNamed()` (`K == P` or
   `K == P_<digits>`), which — unlike the old `BeginsWith` — keeps
   `O2mfttrack_001` apart from `O2mfttrackcov`, `O2bc_001` from `O2bcflag` and
   `O2calo` from `O2calotrigger`.
2. **`buildRemaps()` (Section 3)** derives a table's complete remap list from
   that registry. The privileged "primary index + optional extras" split in
   `rewriteTable` is gone — there is one `writeTable(src, dirOut, rowOrder,
   remaps)` and every column goes through the same path. Forgetting a column is
   no longer possible; the old design *required* each stage to remember.
3. **Plan, then write (Sections 3b + 10).** Every stage now only appends a
   `TablePlan` and publishes its permutation; `processDF` writes all plans
   afterwards, when every permutation in the DF is known. This is what makes the
   forward reference (fwd→mft) and the self reference (fwd→fwd) work.
4. **Drift guard.** Any `fIndex*` branch not in `kIndexRefs` is a `[warn]` at
   rewrite time and a `[FAIL]` in the validator. Schema growth now breaks the
   test instead of silently mis-linking data.
5. **`AODBcRewriterCheckLinks()` (Section 11b)** — the check that can actually
   see this bug class; see "Testing" below.
6. **Re-sort tables stored sorted by a reference** (`findGroupingColumn` /
   `resortByGroupingColumn`, Section 8). The same family: `O2fwdtrkcl` and
   `O2trackqa_003` were coming out unsorted in every DF of two of the three
   sample files, which breaks O2's slicing the same way the split `-1` group
   did. Derived from the data, not from a list — see resolved gap 1.

Maurice's #2418 has the same shape (defer `O2fwdtrack`, remap via the MFT/Fwd
perms) and is correct; this generalises it from one table to all of them.

### Previous work state (2026-06-09): tracks' `-1` collision group split

Downstream O2 analysis (`o2-analysis-event-selection`) was crashing with:

```
[FATAL] Table Tracks_IU index fIndexCollisions has a group with index -1
        that is split by 776
```

O2's `ArrowTableSlicingCache::validateOrder` requires every `fIndexCollisions`
group in a track table — **including the `-1` "ambiguous" group** — to be one
contiguous run of rows. Two commits broke this:

- **`b11cd3de`** added a value-wise remap of tracks' `fIndexCollisions` via
  `collPerm` but left the track **rows in input order**. Since Stage 1 reorders
  `O2collision` (sort by remapped `fIndexBCs`), the remapped values no longer
  formed contiguous groups → the split. (b11cd3de made the *values* correct at
  the cost of the *grouping*; the complete fix needs **both** — reorder rows
  *and* remap values.)
- **`28b44ef`** (a colleague's attempt) then replaced the Stage 0 BC **sort**
  with an order-preserving dedup that `std::abort()`s unless the input BC table
  is already `globalBC`-sorted. That contradicts PURPOSE (a) — repairing
  *non-monotonic* BCs in merged files — so it aborted on exactly the files the
  tool exists to fix ("doesn't run to completion").

### What the current fix does

1. **Reverted only the Stage 0 change** of `28b44ef`: restored `stage0_sortBCs`
   (sort + dedup) and removed the abort. Non-monotonic merged BCs are repaired
   again, as intended.
2. **Kept `28b44ef`'s Stage 1b** (`stage1b_reorderTrackTables`, Section 9b) and
   the `fIndexTracks*` / `fIndexMFTTracks` / `fIndexFwdTracks` remaps in
   `processPasteJoinTables`. This regroup-tracks-by-remapped-`fIndexCollisions`
   mechanism is the *correct* fix for the split; it only ever failed because the
   aborting Stage 0 stopped it from running. Rewriting it from scratch was
   judged higher-risk than keeping the reviewed logic.
3. **Added validator check** `checkCollisionGroupContiguity` (Section 11):
   mirrors O2's slicing invariant — flags any `fIndexCollisions` group split
   into >1 run. Runs over every collision-grouped track table.

**Design note / cascade:** sorting BCs is unavoidable for non-monotonic input
and forces a reorder cascade **BC (Stage 0) → collisions (Stage 1) → tracks
(Stage 1b)**, propagated to paste-join children and all track references. Do
**not** re-introduce an "assert already sorted / order-preserving" Stage 0 — it
is a known dead end (see the history note in the Section 4 code comment).

### Status of the 2026-06-09 items

- ~~**UNVALIDATED on real data.**~~ Now run on `example_AOD/AO2D_pre.root`,
  `bigger/` and `bigger2/` (3–4 DFs each, up to 6M MC particles): rewrite clean,
  `AODBcRewriterValidate` and `AODBcRewriterCheckLinks` both pass. The macro is
  still interpreter-only; `.L AODBcRewriter.C+` (ACLiC) fails on missing std
  includes — pre-existing, not a regression.
- ~~**Known fragility (whack-a-mole).**~~ Resolved by `kIndexRefs` +
  `buildRemaps()` + the drift guard (see above). There is now exactly one list,
  and an entry missing from it fails the test rather than corrupting output.
- ~~**Biggest gap: no executable CI.**~~ `MC/utils/tests/` now provides one that
  needs nothing but ROOT and runs in seconds. Still open: wiring it into the
  ALICE CI job list — `.github/workflows/` has no ROOT runner, so it needs a
  line wherever `test/run_*_tests.sh` are invoked. **Confirm with the O2DPG CI
  owners rather than guessing.**

---

## Testing

```bash
${O2DPG_ROOT}/MC/utils/tests/run_aodbcrewriter_tests.sh
```

Needs only ROOT — no simulation, no O2Physics, no GRID, no committed binary
fixture. `makeTestAOD.C` builds a few-kB synthetic AO2D carrying every pathology
the tool exists to repair (non-monotonic + duplicate BCs, duplicate MC
collisions, a split `-1` track group from two sub-timeframe blocks, fwd↔MFT and
fwd→fwd matches, V0/cascade links, `fIndexSliceBCs`, mcparticle mother/daughter
links, and a link-free table for the fast-clone path).

Three independent layers, in increasing specificity:

| layer | what it sees |
|---|---|
| `AODBcRewriterValidate(out)` | structural invariants of the output alone |
| `AODBcRewriterCheckLinks(in, out)` | input vs output: no row changed what it points at |
| `testAODBcRewriter(in, out)` | named, physics-readable assertions |

**The middle layer is the one that matters for this bug class.** Everything in
`AODBcRewriterValidate` is structural, and O2-7098 was structurally perfect —
the row numbers were simply the wrong ones, and in range. Catching that requires
comparing against the input. `AODBcRewriterCheckLinks` does it without
permutation dumps or synthetic tagging: it fingerprints each row from its
non-`fIndex*` branches and compares, per table, the multiset of

```
( payload fingerprint of the row, payload fingerprint of each row it points at )
```

before and after. Dedup is handled by canonicalising the *input* side — a
referenced row that did not survive becomes the null link, which is what the
rewriter does — so a tuple present in the output but in no input row is always a
bug. The BC table is fingerprinted on `fGlobalBC` alone, because Stage 0
*redirects* references onto the surviving row rather than nulling them.

Because it needs no synthetic data, run it on real production files too:

```cpp
root -l -b -q -e '.L AODBcRewriter.C' \
     -e 'AODBcRewriterCheckLinks("AO2D_pre.root","AO2D.root")'
```

Regression-locked: against the pre-fix `master` rewriter the suite reports
`O2fwdtrack: links not preserved` and `MFT-MCH match: sameParticle=1/6`.

---

## What this tool does

`AODBcRewriter.C` is a ROOT macro that fixes structural integrity problems in
ALICE Run3 AO2D files after merging. AO2D files are ROOT files containing
`DF_*` subdirectories, each holding a set of TTrees that form a relational
schema (similar to a database). After merging two AO2D files with `hadd` or
similar tools, three problems can arise:

1. **Non-monotonic `fGlobalBC`** in the BC table — the framework requires
   strictly increasing values.
2. **Duplicate `fGlobalBC` entries** — the same bunch crossing represented by
   multiple rows.
3. **Duplicate MCCollision entries** — the same MC event appearing twice
   because it was present in both source files before merging.

Run with:
```bash
root -l -b -q 'AODBcRewriter.C("AO2D.root","AO2D_rewritten.root")'
```

---

## AO2D data model (relevant subset)

The tables form a dependency graph. Every stage of the tool processes one
level of this graph and produces a **PermMap** (`vector<Int_t>`,
`permMap[oldRow] = newRow`, -1 = row dropped) which the next stage consumes.

```
BCs (O2bc_*)                                          [Stage 0]
 │  fIndexBCs / fIndexBC
 ├─► Collisions        (O2collision_*)                [Stage 1]
 │    │  paste-join ──► McCollisionLabels (O2mccollisionlabel_*)
 │    └─► Tracks       (O2track_*, O2trackiu_*, ...)  [Stage 1]
 │         paste-join ─► McTrackLabels (O2mctracklabel_*)
 │         paste-join ─► McFwdTrackLabels, McMFTTrackLabels
 │
 └─► MCCollisions      (O2mccollision_*)              [Stage 1, deduped]
      │  fIndexMcCollisions
      ├─► HepMCXSections  (O2hepmcxsection_*)         [Stage 2]
      ├─► HepMCPdfInfos   (O2hepmcpdfinfo_*)           [Stage 2]
      └─► HepMCHeavyIons  (O2hepmcheavyion_*)          [Stage 2]
```

**Index joins** (`fIndexBCs`, `fIndexCollisions`, `fIndexMcCollisions`) are
explicit integer columns pointing to a row in another table by position.

**Paste joins** are implicit: table row N of a paste-joined table corresponds
to row N of its parent table. These tables have *no index column*. They must
be reordered to match their parent whenever the parent is reordered.

The known paste-join relationships are hardcoded in `kPasteJoins` (Section 1).
The list is authoritative — derived from `AnalysisDataModel.h` comments
("Table joined to the collision table containing the MC index", etc.) and
from the SOA `EXTENDED_TABLE` declarations for cov / extra tables:
```
O2bcflag              →  parent: O2bc_*           (BCFlags joinable with BCs)
O2mccollisionlabel    →  parent: O2collision_*    (McCollisionLabels)
O2mctracklabel        →  parent: O2track_iu (or O2track)
O2mcfwdtracklabel     →  parent: O2fwdtrack
O2mcmfttracklabel     →  parent: O2mfttrack
O2mccalolabel         →  parent: O2calo           (McCaloLabels)
O2trackcov_iu         →  parent: O2track_iu       (TracksCovIU extension)
O2trackextra          →  parent: O2track_iu       (TracksExtra  extension)
O2fwdtrackcov         →  parent: O2fwdtrack       (FwdTracksCov extension)
```
NOT in this list (despite the suffix): `O2mfttrackcov` carries its own
`fIndexMFTTracks` and is **index-linked**, not paste-joined.

A child may carry its own index columns (e.g. `O2mccollisionlabel` carries
`fIndexMcCollisions`). Those values are remapped *value-wise* through the
appropriate parent-stage permutation, but the child's row count and row
order strictly follow its paste-join parent.

---

## Code structure (11 sections)

| Section | Function(s) | Purpose |
|---------|-------------|---------|
| 1 | `PermMap`, `isBCTable`, `bcIndexBranch`, `mcCollIndexBranch`, `collIndexBranch`, `kPasteJoins`, `isPasteJoinChild`, **`kIndexRefs`**, **`isTableNamed`**, **`unregisteredIndexBranches`** | Core types, name-probe helpers, the paste-join list, and the authoritative index-reference registry |
| 2 | `ScalarTag`, `tagOf`, `byteSize`, `readAsInt`, `writeAsInt`, `BranchDesc`, `describeBranches` | Generic ROOT branch I/O over raw byte buffers |
| 3 | **`writeTable`**, `permFromRowOrder`, `remapBuffer`, `findPermFor`, **`buildRemaps`** | **Central engine**: writes any table in a given row order, remapping *every* index column it carries |
| 3b | `TablePlan` | Deferred write plan — why planning and writing are separate phases |
| 4 | `BCStage0Result`, `stage0_sortBCs` | Sort + deduplicate the BC table; produce `bcPerm` |
| 5 | `stage0_copyBCFlags` | Plan the BC flags table following BC row selection |
| 6 | `MCCollKey`, `MCCollKeyHash`, `stage1_BCindexedTables` | Plan all BC-indexed tables; deduplicate MCCollisions |
| 7 | `stage2_MCCollIndexedTables` | Plan all MCCollision-indexed tables; drop rows whose parent was deduped |
| 9b | `isCollGroupedTrackTable`, `stage1b_reorderTrackTables` | **Stage 1b**: regroup collision-grouped track tables (`O2track_iu`, `O2mfttrack`, `O2fwdtrack`) by remapped `fIndexCollisions` (`-1` sinks to a contiguous tail); publish track perms so children/references follow. Restores the O2 slicing invariant after the BC→collision reorder cascade |
| 8 | `planRemainingTables` | Paste-joined tables follow their parent's row order; everything else keeps its own |
| 9 | `copyNonTreeObjects` | Copy TMap metadata and other non-TTree objects |
| 10 | `processDF` | Orchestrates the **plan phase** then the **write phase** for one `DF_*` directory |
| 11 | `AODBcRewriterValidate` and helpers | Structural validation of an output file |
| 11b | `payloadFingerprints`, `linkTupleCounts`, **`AODBcRewriterCheckLinks`** | Input-vs-output link preservation — the check that sees the O2-7098 bug class |
| 12 | `AODBcRewriter` | Top-level entry: opens files, iterates `DF_*` dirs, preserves compression |

### `writeTable` — the central engine

```cpp
void writeTable(TTree *src, TDirectory *dirOut,
                const vector<Long64_t> &rowOrder,
                const vector<IndexRemap> &remaps);
```

- `rowOrder`: which source rows to emit and in what sequence (may be a subset
  for deduplication, or reordered for sorting)
- `remaps`: **every** index column to remap, each with its own PermMap —
  obtained from `buildRemaps(src, allPerms)` and therefore from `kIndexRefs`

There is deliberately **no privileged "primary index"** parameter any more. The
old signature took one nominated index column plus an optional list of "extras",
which meant every stage had to remember to populate the extras. Stage 1b did
not, and that is O2-7098. Do not reintroduce the distinction.

The row permutation a `rowOrder` implies is `permFromRowOrder(nSrc, rowOrder)`
(`perm[srcRow] = outRow`, -1 if dropped). Stages publish it into `allPerms`
*before* anything is written, which is what lets a table's remaps refer to
tables written later — or to itself.

The function handles both scalar branches and VLA (variable-length array)
branches generically. For VLAs it pre-scans the count branch to find the
maximum array length and allocates buffers accordingly. Input and output
branches share the same raw byte buffers; ROOT handles the VLA count
implicitly through the shared count buffer.

### The two phases in `processDF`

```
PLAN   stage0 -> stage1 -> stage2 -> stage1b -> planRemainingTables
       each appends a TablePlan and publishes its PermMap into allPerms
WRITE  for every plan: buildRemaps(src, allPerms) then writeTable(...)
       (identity row order and no remaps -> fast CloneTree instead)
```

Note `allPerms` holds **reference-remapping** semantics, not plain row
permutations: for the BC table it is `bcPerm`, where several old rows collapse
onto the surviving one, because that is what references into a deduplicated BC
table need. For `O2mccollision` a dropped duplicate maps to -1 instead — that is
the existing, deliberate behaviour (see resolved gap 7), not an oversight.

---

## MCCollision deduplication

Implemented in `stage1_BCindexedTables` when the current table begins with
`O2mccollision`.

**Key**: `MCCollKey { Long64_t newBCrow; Float_t weight; }` using `fEventWeight`.

**Important constraint**: deduplication is only enabled when `fEventWeight` is
present in the tree. If it is absent, all rows are kept (only reordered). This
is intentional: deduplicating on `newBCrow` alone would incorrectly collapse
distinct MC events that happen to share the same bunch crossing.

When a MCCollision row is dropped (PermMap entry = -1), Stage 2 propagates
the drop: any `O2hepmcxsection_*` / `O2hepmcpdfinfo_*` / `O2hepmcheavyion_*`
row whose `fIndexMcCollisions` pointed to a dropped row is also dropped.

---

## Known gaps / TODO items

These were identified during the refactor but not yet implemented:

### ~~1. Tables SORTED BY a reference into a reordered table are not re-sorted~~ (RESOLVED)

Stage 1b reorders `O2track_iu` / `O2mfttrack` / `O2fwdtrack`. Several other
tables are *stored sorted by* a reference into one of those (or into
`O2collision`). Their values were remapped but their rows left where they were,
so the ordering was destroyed:

| table | key | sorted in input? |
|---|---|---|
| `O2fwdtrkcl` | `fIndexFwdTracks` | yes |
| `O2ambiguoustrack` | `fIndexTracks` | yes |
| `O2trackqa_003` | `fIndexTracks` | yes |
| `O2v0_002`, `O2cascade_001`, `O2decay3body` | `fIndexCollisions` | yes |
| `O2mfttrackcov` | `fIndexMFTTracks` | **no** — so not an invariant there |

(measured on `example_AOD/AO2D_pre.root`.) Same failure mode as the split `-1`
group that produced the `ArrowTableSlicingCache::validateOrder` FATAL. **Not
theoretical**: on `example_AOD/AO2D_pre.root` and `bigger2/`, `O2fwdtrkcl` and
`O2trackqa_003` came out unsorted in *every* DF.

**Fix**: `findGroupingColumn` + `resortByGroupingColumn` (Section 8), driven by
the data rather than by another hardcoded list — *if `T.B` is non-decreasing in
the input and `B`'s referent gets reordered, re-sort `T` by the remapped `B`*.
Self-maintaining across schema changes, and it correctly leaves `O2mfttrackcov`
alone (its `fIndexMFTTracks` is not sorted on input, so there is no ordering to
preserve). Iterated to a fixed point, because these tables reference each other:
`O2cascade_001` is sorted by `fIndexV0s` and `O2v0_002` may itself have just
been re-sorted.

Policed by a new check in `AODBcRewriterCheckLinks`: a column sorted on input
must be sorted on output.

### ~~2. `fIndexCollisions` inside `O2mccollision` is not remapped~~ (MOOT)

Checked against three real AO2Ds (`example_AOD/`, `bigger/`, `bigger2/`):
`O2mccollision_001` carries **only** `fIndexBCs` in the current schema, so there
is nothing to remap. Should the column reappear, `kIndexRefs` now handles it
with no code change.

### 3. Deduplication key could be strengthened

The current `(newBCrow, fEventWeight)` key is a good heuristic. A more robust
key would additionally include `fImpactParameter` and/or `fGeneratorsID` if
those branches are present. Consider making the key construction a small
helper function that probes which fields are available and builds the strongest
possible key.

### ~~4. `O2mccollision` has two potential parents for paste-join lookup~~ (PARTLY RESOLVED)

Referent resolution now goes through `findPermFor` / `isTableNamed`, which
matches `P` or `P_<digits>` and, when several schema versions coexist, picks the
lexicographically smallest name **deterministically** instead of whatever the
`unordered_map` happened to yield first. Still no warning for the ambiguous
case — add one if schema-version coexistence ever becomes real.

### 5. Paste-join size-mismatch fallback is silent-ish

When a paste-joined table has a different row count from its parent (schema
drift), the tool now keeps the child's own row order — index remaps still get
applied, so nothing is left dangling — and prints a `[warn]`. The output is
still structurally inconsistent and the validator's paste-join parity check will
`[FAIL]` on it. Consider making it a hard error, or reconciling row counts.

### ~~5. No validation pass~~ (RESOLVED)

`AODBcRewriterValidate(fname)` (Section 11) now validates BC monotonicity,
MC-particle intra-table index integrity, paste-join row-count parity, and
generic `fIndex*` range against the referent table.  Call it after rewriting
to confirm output correctness.

### ~~6. fIndexArray_Mothers / fIndexSlice_Daughters not remapped~~ (RESOLVED)

This was the root cause of the O2Physics FATAL
`MC particle N has daughter with index M > MC particle table size`.
After Stage 2 reorders `O2mcparticle`, the intra-table mother/daughter indices
get remapped through the table's own permutation.

`fIndexMcParticles` in label tables (`O2mctracklabel`, `O2mcfwdtracklabel`,
`O2mcmfttracklabel`, `O2mccalolabel`) is remapped via the MC-particle
permutation.

*(Since O2-7098 both are plain `kIndexRefs` entries and need no special
casing — `buildRemaps` picks them up like any other column.)*

### ~~8. fIndexSliceBCs in O2ambiguous* not remapped after BC dedup~~ (RESOLVED)

`fIndexSliceBCs` is a SOA `SLICE_INDEX_COLUMN(BC, bc)` (header line 1029),
stored on disk as a fixed `[2]/I` `{first, last}` pair pointing into the BC
table. It appears in `O2ambiguoustrack`, `O2ambiguousmfttr`,
`O2ambiguousfwdtr` — none of which carry `fIndexBCs` and therefore none
were processed by Stage 1. After BC dedup the slice endpoints would then
point past the compacted table.

**Fix**: `bcPerm` is published into `allPerms` under the BC tree's name, so
`buildRemaps` applies it to any `fIndexSliceBCs` / `fIndexBCs` / `fIndexBC`
column it finds. Validated against `example_AOD/AO2D_pre.root`: pre-fix the
rewritten output had 7 and 19 out-of-range slice endpoints in
DF_3594457012003; post-fix the validator reports zero. `testAODBcRewriter`
also asserts the endpoints still name the same bunch crossings.

### ~~7. Paste-join row-count drift on MC-collision dedup~~ (RESOLVED)

`O2mccollisionlabel` is paste-joined to `O2collision_*` (row N ↔ row N) but
also carries `fIndexMcCollisions`. The previous code routed it through Stage
2 (because of the MC-collision index), which sorted it by new MC-collision
position and *dropped* rows whose MC collision had been deduplicated. That
left `O2mccollisionlabel` shorter than `O2collision_*` by N rows — leading
to downstream "O2collision_001 is one larger than O2mccollisionlabel" crashes.

**Fix**: `kPasteJoins` was extended to cover every joined pair from
`AnalysisDataModel.h`. Paste-join children are now *deferred* from Stage 2
to `planRemainingTables`, where they take the parent's row order and have
their own index columns remapped value-wise. Rows that lose their MC label
on dedup now correctly produce `fIndexMcCollisions == -1`, and the row count
matches the parent collision table.

The new validator catches the regression class as
`[FAIL] paste-join size mismatch: O2mccollisionlabel* has N rows but parent
 O2collision* has M`.

### ~~9. Tracks' `-1` collision group split after BC/collision reorder~~ (RESOLVED — pending validation)

See the **Current work state** section at the top for the full story. In short:
after Stage 1 reorders `O2collision`, the collision-grouped track tables must be
**reordered** (not just have their `fIndexCollisions` values remapped) so each
group — including the `-1` ambiguous group — stays one contiguous run, as O2's
`ArrowTableSlicingCache::validateOrder` requires.

**Fix:** Stage 1b (`stage1b_reorderTrackTables`, Section 9b) stable-sorts each
track table by remapped `fIndexCollisions` (`-1` to a contiguous tail) and
publishes the track perm; paste-join children follow it and every
`fIndexTracks*` reference is remapped through it. Validator check
`checkCollisionGroupContiguity` flags split groups as
`[FAIL] ... fIndexCollisions has N group(s) split into non-contiguous runs`.

**Status:** on `master` since `5597f516`, now run on real merged AO2Ds. Note
this fix is what *introduced* gap 10 below.

### ~~10. O2fwdtrack match indices reordered but not remapped (O2-7098)~~ (RESOLVED)

See the **Current work state** section at the top. Stage 1b wrote each table as
soon as it had planned it, so `O2fwdtrack`'s `fIndexMFTTracks` (pointing at a
table reordered later in the same loop) and `fIndexFwdTracks_MatchMCHTrack`
(pointing at itself) kept pre-reorder row numbers.

**Fix:** planning and writing are now separate phases, and every index column is
derived from the single `kIndexRefs` registry by `buildRemaps` instead of being
enumerated per stage.

---

## Testing checklist

Automated: `${O2DPG_ROOT}/MC/utils/tests/run_aodbcrewriter_tests.sh` (see the
**Testing** section above). Run it for any change to this tool.

When testing a real AO2D by hand:

1. Run `AODBcRewriterValidate("AO2D_rewritten.root")` (Section 11).
   It checks BC monotonicity, MC-particle intra-table integrity, paste-join
   row-count parity for every pair in `kPasteJoins`, `fIndex*` value
   ranges against the referent table, and that no `fIndex*` column is missing
   from `kIndexRefs`. Failures appear as `[FAIL] ...` lines.
2. Run `AODBcRewriterCheckLinks("AO2D_pre.root","AO2D.root")` (Section 11b).
   **Do not skip this one** — it is the only check that compares against the
   input, and therefore the only one that can see a mis-remapped index.
   Roughly 30 s for a 3-DF file with 6M MC particles.
3. Check stdout from the rewrite run itself for any `[warn]` lines — these
   indicate branches or tables that fell through to a fallback path, or an
   index column the registry does not know about.
4. If deduplication ran, verify the dropped count is as expected by comparing
   the input DF MCCollision count vs. output.

A standalone minimal validation script (kept here for reference; in practice
just call `AODBcRewriterValidate`):
```cpp
// validate.C
void validate(const char *fname) {
  TFile *f = TFile::Open(fname);
  TIter top(f->GetListOfKeys());
  while (TKey *k = (TKey*)top()) {
    if (!TString(k->GetName()).BeginsWith("DF_")) continue;
    TDirectory *d = (TDirectory*)f->Get(k->GetName());
    // check BC monotonicity
    TTree *bc = (TTree*)d->Get("O2bc_001");  // adjust suffix
    if (bc) {
      ULong64_t gbc, prev = 0; bool ok = true;
      bc->SetBranchAddress("fGlobalBC", &gbc);
      for (Long64_t i = 0; i < bc->GetEntries(); ++i) {
        bc->GetEntry(i);
        if (i > 0 && gbc <= prev) { printf("BC non-monotonic at row %lld\n", i); ok=false; }
        prev = gbc;
      }
      if (ok) printf("%s: BCs OK (%lld entries)\n", k->GetName(), bc->GetEntries());
    }
  }
}
```

---

## Data model reference

Full table schema: https://aliceo2group.github.io/analysis-framework/docs/datamodel/ao2dTables.html

Source definitions: `AliceO2/Framework/Core/include/Framework/AnalysisDataModel.h`

The upstream PR this work improves upon: https://github.com/AliceO2Group/O2DPG/pull/2317

Target file location in O2DPG: `MC/utils/AODBcRewriter.C`
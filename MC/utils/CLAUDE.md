# CLAUDE.md — AODBcRewriter Development Handoff

## Current work state (handoff — 2026-06-09)

**Branch:** `fix/aodbcrewriter-track-regroup` · **Last commit:** `8bb9d30b3c`
(committed, not yet pushed/validated).

### The bug being fixed: tracks' `-1` collision group split

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

### Not done yet / next steps for whoever picks this up

- **UNVALIDATED on real data.** Parses cleanly in cling (`.L AODBcRewriter.C`),
  but has *not* been run on a real merged AO2D, nor through the analysis task
  that crashed. The macro is interpreter-only; `.L AODBcRewriter.C+` (ACLiC)
  fails on missing std includes — pre-existing, not a regression.
  Test sequence: `AODBcRewriter("AO2D.root","out.root")` →
  `AODBcRewriterValidate("out.root")` (expect no `[FAIL]`) → then the **real**
  `o2-analysis-event-selection` on `out.root` (ground truth).
- **Known fragility (whack-a-mole):** the `fIndexTracks*` reference remap is a
  hardcoded enumeration in `processPasteJoinTables` and the validator's
  `kIndexBranchToTable`. A missed reference into a reordered track table = silent
  corruption. Longer term, *derive* index→referent relationships from the AO2D
  column-name conventions instead of enumerating.
- **Biggest gap:** there is no executable analysis-level CI for this tool, so
  regressions are only found in production with delay. Building a reproducer
  (merged AO2D that triggers the split/abort) + a CI check that runs the real
  task is the agreed top priority after this fix lands.

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
| 1 | `PermMap`, `isBCTable`, `bcIndexBranch`, `mcCollIndexBranch`, `collIndexBranch`, `kPasteJoins`, `isPasteJoinChild` | Core types, name-probe helpers, and the authoritative paste-join list |
| 2 | `ScalarTag`, `tagOf`, `byteSize`, `readAsInt`, `writeAsInt`, `BranchDesc`, `describeBranches` | Generic ROOT branch I/O over raw byte buffers |
| 3 | `rewriteTable` | **Central engine**: writes any table in a given row order, remapping one nominated index column via a PermMap |
| 4 | `BCStage0Result`, `stage0_sortBCs` | Sort + deduplicate the BC table; produce `bcPerm` |
| 5 | `stage0_copyBCFlags` | Copy BC flags table following BC row selection |
| 6 | `MCCollKey`, `MCCollKeyHash`, `stage1_BCindexedTables` | Process all BC-indexed tables; deduplicate MCCollisions |
| 7 | `stage2_MCCollIndexedTables` | Process all MCCollision-indexed tables; drop rows whose parent was deduped |
| 9b | `isCollGroupedTrackTable`, `stage1b_reorderTrackTables` | **Stage 1b**: regroup collision-grouped track tables (`O2track_iu`, `O2mfttrack`, `O2fwdtrack`) by remapped `fIndexCollisions` (`-1` sinks to a contiguous tail); publish track perms so children/references follow. Restores the O2 slicing invariant after the BC→collision reorder cascade |
| 8 | `rowOrderFromPerm`, `findPermByPrefix`, `processPasteJoinTables` | Reorder paste-joined tables to follow their parent (1:1 row count guaranteed); remap any of their own index columns value-wise (incl. `fIndexTracks*` via the Stage 1b track perms); copy unrelated tables verbatim |
| 9 | `copyNonTreeObjects` | Copy TMap metadata and other non-TTree objects |
| 10 | `processDF` | Orchestrates all stages for one `DF_*` directory |
| 11 | `AODBcRewriter` | Top-level entry: opens files, iterates `DF_*` dirs, preserves compression |

### `rewriteTable` — the central engine

```cpp
PermMap rewriteTable(TTree *src, TDirectory *dirOut,
                     const vector<Long64_t> &rowOrder,
                     const string &indexBranch,
                     const PermMap &parentPerm);
```

- `rowOrder`: which source rows to emit and in what sequence (may be a subset
  for deduplication, or reordered for sorting)
- `indexBranch`: name of the one index column to remap (e.g. `"fIndexBCs"`),
  or `""` for none
- `parentPerm`: the PermMap from the parent stage used to translate the old
  index value to a new one
- Returns `srcToOut` PermMap: `srcToOut[srcRow] = outRow`, -1 if dropped

The function handles both scalar branches and VLA (variable-length array)
branches generically. For VLAs it pre-scans the count branch to find the
maximum array length and allocates buffers accordingly. Input and output
branches share the same raw byte buffers; ROOT handles the VLA count
implicitly through the shared count buffer.

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

### 1. `fIndexCollisions` inside `O2mccollision` is not remapped

`O2mccollision` has both `fIndexBCs` (handled) and `fIndexCollisions` (linking
back to the reconstructed `O2collision` row). After Stage 1 reorders
`O2collision`, this second index in `O2mccollision` becomes stale.

**Fix**: After `stage1_BCindexedTables` runs, find `collPerm` (the PermMap for
`O2collision_*`) in `stage1Perms`, then apply a second `rewriteTable` pass on
`O2mccollision_*` to remap `fIndexCollisions` via `collPerm`. The
`ExtraRemap` mechanism in `rewriteTable` already supports this pattern.

### 2. Deduplication key could be strengthened

The current `(newBCrow, fEventWeight)` key is a good heuristic. A more robust
key would additionally include `fImpactParameter` and/or `fGeneratorsID` if
those branches are present. Consider making the key construction a small
helper function that probes which fields are available and builds the strongest
possible key.

### 3. `O2mccollision` has two potential parents for paste-join lookup

In `processDF`, the MCColl PermMap is extracted by scanning `stage1Perms` for
a name beginning with `"O2mccollision"`. If the DF contains both
`O2mccollision_000` and `O2mccollision_001` (schema version coexistence),
only the first found is used. Add a warning and handle this explicitly if it
becomes relevant.

### 4. Paste-join size-mismatch fallback is silent-ish

When a paste-joined table has a different row count from its parent (schema
drift), the tool falls back to `CloneTree(-1, "fast")` and prints a warning.
This produces a structurally inconsistent output. Consider making this a hard
error, or implement a best-effort row-count reconciliation.

### ~~5. No validation pass~~ (RESOLVED)

`AODBcRewriterValidate(fname)` (Section 11) now validates BC monotonicity,
MC-particle intra-table index integrity, paste-join row-count parity, and
generic `fIndex*` range against the referent table.  Call it after rewriting
to confirm output correctness.

### ~~6. fIndexArray_Mothers / fIndexSlice_Daughters not remapped~~ (RESOLVED)

This was the root cause of the O2Physics FATAL
`MC particle N has daughter with index M > MC particle table size`.
After Stage 2 reorders `O2mcparticle`, the intra-table mother/daughter indices
now get remapped via `ExtraRemap` in the same pass (Section 7).

`fIndexMcParticles` in label tables (`O2mctracklabel`, `O2mcfwdtracklabel`,
`O2mcmfttracklabel`, `O2mccalolabel`) is also now remapped via the MC-particle
permutation in `processPasteJoinTables` (Section 8).

### ~~8. fIndexSliceBCs in O2ambiguous* not remapped after BC dedup~~ (RESOLVED)

`fIndexSliceBCs` is a SOA `SLICE_INDEX_COLUMN(BC, bc)` (header line 1029),
stored on disk as a fixed `[2]/I` `{first, last}` pair pointing into the BC
table. It appears in `O2ambiguoustrack`, `O2ambiguousmfttr`,
`O2ambiguousfwdtr` — none of which carry `fIndexBCs` and therefore none
were processed by Stage 1. After BC dedup the slice endpoints would then
point past the compacted table.

**Fix**: `processPasteJoinTables` now also accepts the BC permutation
(passed explicitly from `processDF`) and applies it value-wise to any
`fIndexSliceBCs` / `fIndexBCs` / `fIndexBC` column it finds. Validated
against `example_AOD/AO2D_pre.root`: pre-fix the rewritten output had 7
and 19 out-of-range slice endpoints in DF_3594457012003; post-fix the
validator reports zero.

### ~~7. Paste-join row-count drift on MC-collision dedup~~ (RESOLVED)

`O2mccollisionlabel` is paste-joined to `O2collision_*` (row N ↔ row N) but
also carries `fIndexMcCollisions`. The previous code routed it through Stage
2 (because of the MC-collision index), which sorted it by new MC-collision
position and *dropped* rows whose MC collision had been deduplicated. That
left `O2mccollisionlabel` shorter than `O2collision_*` by N rows — leading
to downstream "O2collision_001 is one larger than O2mccollisionlabel" crashes.

**Fix**: `kPasteJoins` was extended to cover every joined pair from
`AnalysisDataModel.h`. Paste-join children are now *deferred* from Stage 2
to `processPasteJoinTables`, where they take the parent's row order and have
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
track table by remapped `fIndexCollisions` (`-1` to a contiguous tail), publishes
the track perm, and `processPasteJoinTables` follows it for paste-join children
and remaps every `fIndexTracks*` reference. New validator check
`checkCollisionGroupContiguity` flags split groups as
`[FAIL] ... fIndexCollisions has N group(s) split into non-contiguous runs`.

**Status:** committed on `fix/aodbcrewriter-track-regroup` (`8bb9d30b3c`), parses
in cling, **not yet run on a real merged AO2D or the failing analysis task.**

---

## Testing checklist

When testing a new AO2D:

1. Run `AODBcRewriterValidate("AO2D_rewritten.root")` (Section 11).
   It checks BC monotonicity, MC-particle intra-table integrity, paste-join
   row-count parity for every pair in `kPasteJoins`, and `fIndex*` value
   ranges against the referent table. Failures appear as `[FAIL] ...` lines.
2. Check stdout from the rewrite run itself for any `[warn]` lines — these
   indicate branches or tables that fell through to a fallback path.
3. If deduplication ran, verify the dropped count is as expected by comparing
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
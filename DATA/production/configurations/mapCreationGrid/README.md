# TPC Map Creation on the GRID

Runs the ALICE TPC space-charge distortion map creation chain on the ALICE GRID, as a two-stage
pipeline: a heavy map-creation stage (hours per slot) followed by a fast post-processing stage
(minutes per slot). Ported from the original SLURM/Lustre-based production.

The four ROOT macros this pipeline runs (`staticMapCreatorCPM.C`, `SmoothingExtrapolate.C`,
`voxResQA.C`, `TPCFastTransformInitCPM.C`) live in the main O2 repository, under
`Detectors/TPC/calibration/SpacePoints/macro/` and `GPU/TPCFastTransformation/macro/` respectively, and
install to `$O2_ROOT/share/macro/` as part of a normal O2 build -- this directory only holds the GRID
submission/orchestration layer (list discovery, manifest staging, `grid_submit.sh` wrappers, per-slot
job scripts).

## Quickstart

For a normal production on the official O2 build, with defaults left alone, only two settings usually
need changing: the bad-time-ranges list and how long each map should span. Everything else below can be
left as-is.

1. **Build the slot lists** (local, once per batch of runs):

   ```bash
   ./discoverResiduals.sh <batch_file>
   ```

   `<batch_file>` lists one run per line: `<period> <run>`, e.g. `LHC26ak 572557`.

2. **Submit stage 1 (map creation).** In `submitMapCreation.sh`, set:
   - `BAD_RANGES_NAME` — the bad-time-ranges file for this data period (keep the default if it still
     applies).
   - `SLOT_LENGTH_MIN` — how many minutes of data go into one map, e.g. `5`.
   - `JOBNAME` — any name that's unique to this submission; you'll need it again in step 3.

   Then:

   ```bash
   ./submitMapCreation.sh [path/to/lists]
   ```

   `path/to/lists` is the `./lists` directory step 1 wrote (default: `./lists` in the current directory)
   — only pass it explicitly if you're running this from a different directory than step 1.

   This takes hours per map — watch progress on alimonitor and wait for it to finish (or mostly finish)
   before continuing.

3. **Submit stage 2 (smoothing + FastTransform).** In `submitPostProcess.sh`, set `STAGE1_JOBNAME_TAG`
   to the exact `JOBNAME` used in step 2, then:

   ```bash
   ./submitPostProcess.sh
   ```

   This takes minutes per map and produces the final smoothed map, the `FT_*.root` FastTransform file,
   and QA plots.

Everything else in this document explains what the other settings do and how to debug things when they
don't go as expected — skip ahead to it only if you need to change something beyond the three above.

## Prerequisites

- A valid AliEn/JAliEn token (`alien-token-init <user>`) and `alien.py` on your `PATH`.
- `O2DPG_ROOT` set (provides `grid_submit.sh`).
- **bash ≥ 4** for the locally-run scripts (`discoverResiduals.sh`, `makeResidualLists.sh`) — they use
  `mapfile`. macOS still ships bash 3.2, so on a Mac install a newer one (`brew install bash`) and make
  sure it precedes `/bin` on your `PATH`; `#!/usr/bin/env bash` then picks it up. Note this also makes
  `set -e` stricter (an arithmetic `(( ))` evaluating to 0 aborts), which is the behaviour lxplus has.
- GNU `parallel` (used by `discoverResiduals.sh`).
- Write access to your AliEn home directory. The wrappers derive
  `alien:///alice/cern.ch/user/<initial>/<user>/MapCreation` automatically from `ALIEN_USER` (falling
  back to your local username), the same way `grid_submit.sh` derives `MY_HOMEDIR` — **no per-user edit
  needed**. Both wrappers print the resolved directory before doing anything, so check that line on your
  first run: if your laptop's local username differs from your AliEn account, `export ALIEN_USER=<your
  alien account>`, or set `MAPCREATION_ALIEN_DIR` to override the whole path. This directory only holds
  the slot manifest, the bad-time-ranges list, and the `stage1Workdir` pointer files -- not the actual
  map data (see Step 3) -- and, if `MACRO_SOURCE=alien` (see below), a staged copy of the macros.
- A `--packagespec` tag whose O2 build includes the four macros above, **or** `MACRO_SOURCE=alien` (see
  "Where the macros come from" below) if no such tag is published yet.

## Where the macros come from (`MACRO_SOURCE`)

Every payload script (`mapCreationJob.sh`, `postProcessJob.sh`) reads a
`MACRO_SOURCE` variable, substituted by its wrapper the same way as `JOBNAME_TAG`:

- **`official` (default)**: runs the macros straight from the O2 package this job's `--packagespec`
  loads (`$O2_ROOT/share/macro/<macro>.C`) — no staging or download at all. This is the same idiom
  `DATA/production/configurations/asyncCalib/createCorrectionMap.sh` already uses for the older
  `staticMapCreator.C`/`TPCFastTransformInit.C` pair. Requires `PACKAGESPEC` to resolve to an O2 build new
  enough to include `staticMapCreatorCPM.C` et al. If it doesn't, the job fails fast with a clear error
  rather than silently falling back.
- **`alien`**: stages a macro from a local path (`MACRO_LOCAL_PATH` in `submitMapCreation.sh`,
  `MACRO_LOCAL_DIR` in `submitPostProcess.sh`) to AliEn, and jobs download it
  from there instead. Use this until a `--packagespec` tag with the macros is published — point
  `MACRO_LOCAL_PATH`/`MACRO_LOCAL_DIR` at your own O2 checkout's copy of the macro(s).

## The chain, in order

```
discoverResiduals.sh   (local)     find residual files on AliEn, build per-run slot lists
        │
        ▼
submitMapCreation.sh   (submits)   STAGE 1: map creation (hours/slot)
        │                            └─ per-slot payload: mapCreationJob.sh
        ▼   (wait for jobs to finish on alimonitor)
        │
submitPostProcess.sh   (submits)   STAGE 2: smoothing + FastTransform (minutes/slot)
                                     └─ per-slot payload: postProcessJob.sh
```

Stage 1 and stage 2 are **independent GRID submissions**, not one script. If some stage-1 slots fail
or are still running, stage 2 simply skips those (see "Partial failure" below) — no need to wait for
100% of stage 1 before submitting stage 2, and a failed stage-2 subjob can be resubmitted on its own
without redoing the expensive stage-1 work for that slot.

### Step 1 — discover residual files and build slot lists (local, once per batch of runs)

```bash
./discoverResiduals.sh <batch_file> [--calib-pass cpass2_residuals]
```

`<batch_file>` is one run per line: `<period_token> <run>`, e.g.:

```
LHC26ak 572557
LHC26ak 572558
```

This queries AliEn (`/alice/data/<year>/<period>/<run>/<calib-pass>/`) for `o2tpc_residuals_*.root`
files and writes per-run slot lists under `./lists/<run>/`. Runs in parallel (`N_PARALLEL=8` in the
script). Safe to re-run; each run is independent. The period is resolved **per line**, so a batch file
may legitimately span periods; malformed rows are rejected up front rather than as one failed run
mid-batch.

**One list per run — granularity comes from `SLOT_LENGTH_MIN`, not from the catalog.** Each residual
filename carries the aggregation slot label `<firstTS>_<lastTS>_<firstTF>_<lastTF>` its reco job
assigned, and those labels are **not** a uniform grid — same-length slots are not guaranteed, and a
run's catalog can hold overlapping/nested labels at different granularities. Example (run 572266):

```
0_105425 (22 files)   105426_210851 (6)   0_210851 (35)
210852_316277 (2)     210852_421703 (45)
```

Slicing per label would give overlapping slots with wildly uneven statistics — the 2- and 6-file ones
trip `MIN_TRACKS_PER_SLICE` and come back `badCalib_` while the data that would have fixed them sits in
a sibling list. So `makeResidualLists.sh` writes **one list per run** holding every file, and you choose
the map length with `SLOT_LENGTH_MIN` at submission time. It is then uniform across runs and independent
of whatever granularity the upstream catalog happens to have.

`stageSlotsForGrid.py` cuts each run into windows of `SLOT_LENGTH_MIN` and writes **one manifest line
per window**, carrying that window's bounds and only the files whose label overlaps it. A file's
contents are always a subset of its label's range, so this selection never discards data that could
contribute, and it costs nothing — no file is opened. That matters: the macro's own per-file skip has to
*open* each out-of-window file to read its time range (~7 s each over `alien://`, at ~zero CPU), and
AliEn kills a payload whose CPU stays low for 15 min. For run 572266:

| `SLOT_LENGTH_MIN` | windows × files per subjob (of 110) |
|---|---|
| `0` (one map per run) | 1 × 110 |
| `10` | 2 × (63, 47) |
| `5` | 4 × (57, 41, 47, 45) |

A coarse-labelled file spanning several windows is deliberately kept by each of them; the macro's per-TF
`firstTFTime`/`lastTFTime` cut then decides which TFs each map actually uses, so nothing is
double-counted. That is why the per-subjob counts can sum to more than the total.

A pure overlap test is too generous at window edges, though: the aggregator's coarse labels routinely
begin 1–2 ms before a window ends, and that was enough to drag all 45 of their files into a window whose
map they contribute nothing to (run 572266 at 5 min: window 1 took 88 files to use 41). So a file is
only assigned to a window when the overlap **exceeds `OVERLAP_MARGIN_MS`** (default 1000). The cost is
bounded exactly: if a label overlaps by X ms then at most X ms of that file's data belongs here, so
skipping at X ≤ margin loses at most `margin` ms of coverage per window edge — 1 s out of 300 s. The
margin is clamped to a tenth of the window, and `stageSlotsForGrid.py` verifies that every file still
lands in at least one window, warning loudly if the margin is ever set high enough to orphan one.
With it, run 572266 at 5 min gives 57 / 41 / 47 / 45 instead of 63 / 88 / 47 / 45.

`mapCreationJob.sh` additionally *orders* each window's files by orbit distance from the window centre,
so whatever still comes along is opened last and `MAX_TRACKS_PER_SLICE` usually stops the job first.

Neither job script does any time arithmetic: both read the run and the window straight off the same
manifest line, so they cannot disagree about a slot's identity.

**Previewing the split.** The windows are decided at submission time, not at discovery, so `./lists/`
holds one file per *run*, not per window. To see how a given `SLOT_LENGTH_MIN` actually slices your
runs, run the manifest builder in preview mode — it skips the AliEn upload, so it needs no token and
re-queries nothing; add `--window-lists` to also write one plain file list per window:

```bash
./stageSlotsForGrid.py --lists-dir ./lists --manifest-name mapSlots.preview.tsv \
                       --slot-length-min 5 --preview --window-lists
ls mapSlots.preview.windows/          # one <run>.TD<w>of<W>.<firstTS>_<lastTS>.txt per window
```

`--preview` skips the upload, so it needs no token and re-queries nothing; `--window-lists` additionally
writes the per-window lists. See `./stageSlotsForGrid.py --help` for the full option list.

The window boundaries and file counts are printed as it goes, which is all you usually need. To see
*which* files a window got, add `--window-lists`. That is off by default because on a parallel
filesystem each list is a metadata round trip: on Lustre, 120 of them measured **32.8 s**, against
0.03 s for all the actual work. Pair it with `--window-dir /tmp/windows` to keep them on local disk.
`--timing` prints the read/compute/write breakdown.

The manifest itself is always written locally — one file, and the complete record of the split (one
line per window, sixth column being the comma-separated file list).

Cheap enough to compare several lengths back to back. For run 572266 (20 min):

| `SLOT_LENGTH_MIN` | windows | files per window |
|---|---|---|
| `10` | 2 | 63, 47 |
| `5` | 4 | 57, 41, 47, 45 |
| `2` | 10 | 57, 57, 63, 41, 41, 47, 47, 47, 45, 45 |

Note the counts stop falling below ~5 min: a coarse aggregation label spanning 10 minutes overlaps
*every* 2-minute window inside it, so slicing finer than the aggregator's own slot length buys time
resolution but not less I/O per job. Add `--window-lists` to a normal (non-preview) run to write the
same directory alongside the uploaded manifest, so you can check afterwards what a submission actually
used.

**`./lists/` accumulates.** A second batch discovered into the same tree does not replace the first —
it adds to it, and Step 2 by default puts *everything* under `./lists/` into the manifest. That
silently recalibrates the earlier batch from scratch at hours per slot. Either use a fresh `listsDir`
per batch, or set `RUNS_FILTER` in the Step-2 wrapper (see below).

### Step 2 — configure and submit stage 1 (map creation)

Edit the config block at the top of **`submitMapCreation.sh`**:

| Variable | Meaning |
|---|---|
| `JOBNAME` | Identifies this production. Tags the AliEn manifest (`mapSlots.<JOBNAME>.tsv`) and the small `stage1Workdir.<JOBNAME>.txt` pointer file (see Step 3) — **must be unique per submission** so concurrent/repeated productions don't clobber each other's manifest or pointer. Stage 2 needs to know this value (see Step 4). |
| `TOPWORKDIR` | Static top-level bucket under your GRID home for this job's working directory (replaces `grid_submit.sh`'s generic `selfjobs` default with something identifiable). |
| `SLOT_LENGTH_MIN` | Target length of **one map**, in minutes. Each run is cut into whole steps of this length; a trailing remainder shorter than half a step is absorbed into the last window rather than left as a runt that would fail `MIN_TRACKS_PER_SLICE`. `0` = one map per run. A 20 min run at `5` gives 4 maps, a 60 min run gives 12 — the count follows the run length instead of being fixed. |
| `PACKAGESPEC` | O2/O2DPG software tag to run under — set this to the async-reco tag matching your data. Also determines whether `MACRO_SOURCE=official` can find the macros (see "Where the macros come from" above). |
| `ASUSER` | AliEn account this job runs/is charged as, e.g. `pwg_pp` (your account must already be a member of that group) instead of your own personal account/quota. Determines both which quota pays for the job and where its `${ALIEN_JDL_OUTPUTDIR}` lands (see Step 3). Verify on alimonitor that the first job is really attributed correctly before relying on it for a big batch. |
| `MACRO_SOURCE` / `MACRO_LOCAL_PATH` | See "Where the macros come from" above. |
| `RUNS_FILTER` | Optional comma-separated run whitelist, e.g. `"572557,572558"`. Empty means every run found under `listsDir` — including runs left over from an earlier batch (see Step 1). Naming a run that has no lists is a hard error, not a silently smaller production. |
| `BAD_RANGES_NAME` | Filename of the bad-time-ranges list under `${MACRO_ALIEN_DIR}/lists/`. Period- and system-specific (the default is the PbPb26 list), so change it when the data changes. It is both the upload destination and the name each job downloads, so the two cannot drift apart. Set to `""` to disable bad-ranges filtering entirely for this submission — a deliberate opt-out (`staticMapCreatorCPM.C` treats an empty filename that way), not the same as forgetting to set it. |
| `BAD_RANGES_LOCAL` | Local path to the bad-time-ranges list, only needed if you want to (re-)upload a new one this submission. Leave empty to reuse whatever is already staged on AliEn under `BAD_RANGES_NAME` — the wrapper checks that it actually exists there before submitting anything, so a wrong `BAD_RANGES_NAME`/`ALIEN_USER` or a never-uploaded file fails fast, locally, once, instead of inside every GRID subjob. |
| `MACRO_ALIEN_DIR_BARE` | AliEn directory (no `alien://` prefix) used for staging the slot manifest and the small `stage1Workdir` pointer file (see Step 3) — and the macro too, when `MACRO_SOURCE=alien`. **Not** the actual map data, which goes to `${ALIEN_JDL_OUTPUTDIR}` instead. Only edit it here — the wrapper substitutes it into the payload script (`mapCreationJob.sh`) automatically before every submission, same mechanism as `JOBNAME_TAG`. Don't hand-edit `MACRO_ALIEN_DIR_BARE`/`MACRO_ALIEN_DIR` inside the payload scripts themselves — it's a placeholder line there, not a real per-user setting. |

**Physics/processing parameters live in a different file** — edit the config block in
**`mapCreationJob.sh`** itself (not the wrapper; these are not part of the wrapper's
placeholder-substitution mechanism, so a hand-edit here is a normal, permanent change, not something
that gets overwritten per submission):

| Variable | Meaning |
|---|---|
| `Z2XBINNING`, `Y2XBINNING` | Voxel binning along z/x and y/x. |
| `USE_SMOOTHED` | Passed through to the macro's `useSmoothed`. |
| `CREATE_SPLINE` | Leave `false` — `TPCFastTransformInitCPM.C` is invoked separately in stage 2, not from this macro. |
| `MAX_TRACKS_PER_SLICE` / `MIN_TRACKS_PER_SLICE` | Per-voxel-slice track count cap / floor. Falling short of `MIN_TRACKS_PER_SLICE` is what triggers the `badCalib_` marking (see Step 3). |
| `MAX_DEDX`, `MAX_DEDX_EXP`, `MAX_DEV_DEDX_OVER_EXP` | dE/dx-based track rejection cuts (`-1` = disabled). |
| `SKIP_EDGE_PADS` | Skip edge pads in the calibration. |
| `BAD_RANGE_SELECTION` | Which bad-time-range comment tag(s) to apply (`"ALL"` = every entry in the bad-ranges list). |
| `MAX_Z2X_CUT` | Track `tgl` cut (`SpacePointsCalibConfParam scdcalib.maxZ2X`) — real production value is `1.4`. |
| `MAX_TRACK_WORKERS` | **Set this to match your GRID job's actual allocated CPU core count** (i.e. whatever `--packagespec`/JDL gives you, commonly matching a `multicore_N` tag). Auto-detection via `hardware_concurrency()` does *not* reliably reflect the real GRID allocation — confirmed auto-detecting 32 threads on an 8-core job (4x oversubscription) once. Getting this wrong doesn't fail the job, just wastes/starves CPU. |

Note: the macro no longer reads IDC scalers from CCDB directly (`useCTPLumi`/`nScalerRanges`/`useScalerRange`
are gone from its signature) — luminosity values are joined back offline by `SmoothingExtrapolate.C` in
stage 2 instead (its own `USE_CTP_LUMI`, see Step 4).

Then:

```bash
./submitMapCreation.sh [listsDir]     # listsDir defaults to ./lists
```

This builds + uploads the slot manifest (and, if `MACRO_SOURCE=alien`, re-stages the macro) and submits
a SINGLE `grid_submit.sh --prodsplit N` production, where N is the total number of windows across all
selected runs. There is no longer one submission per time division: a subjob index identifies a
(run, window) pair on its own, because the windows are baked into the manifest.

**Local single-slot test before submitting to the GRID** (recommended — much faster feedback loop):

```bash
SUBJOBID=1 ./mapCreationJob.sh
```

Runs subjob 1's slot locally using whatever manifest/macro is already staged on AliEn.

### Step 3 — monitor and wait

Watch progress on alimonitor (job status, logs, quota).

**Where the output actually goes** (per ALICE Grid support): each slot's map is staged
directly to *that job's own* JDL-assigned output directory (`${ALIEN_JDL_OUTPUTDIR}`), **not** a fixed
path under your own AliEn home — writing multi-GB production data into personal space would need its
own separate disk-quota request on top of the CPU one, so this pipeline deliberately doesn't do that.
Concretely, for subjob N:

```
<your-job-workdir-root>/<JOBNAME>-<submission-timestamp>/<N zero-padded>/voxRes.<run>_<firstTS>_<lastTS>.TD<w>of<W>.it0.root
```

That parent directory is only known once the job actually runs and is otherwise unrecoverable later
(it includes the real submission timestamp) — so `submitMapCreation.sh` captures it the
moment it submits and uploads it as a small pointer file, `stage1Workdir.<JOBNAME>.txt`, to
your own AliEn space (negligible size — a single line of text, not the actual data). Stage 2 downloads
this pointer and reconstructs each slot's exact output location from it (see Step 4) — you shouldn't
need to look at it directly, but it's what makes stage 2 able to find stage 1's output at all.

If a slot didn't reach the minimum track-count threshold, its map is staged with a `badCalib_` prefix
instead of the normal name — that's the real production's own convention, replicated here so stage 2
knows to skip it (see below). This is expected behavior for low-statistics slots, not a failure.

You do **not** need to wait for every stage-1 subjob to finish before moving on to stage 2 — see
"Partial failure" below.

**Note**: there's no clean, human-browsable `<run>/...`-style directory tree here (unlike the real
input data's own `/alice/data/<year>/<period>/<run>/...` catalog convention) — that catalog is
populated by a centrally-run, formally-registered production system with dedicated write access, not
something reachable via a generic `grid_submit.sh` submission like this one. If you want a tidy,
reorganized view of a run's output later, that needs a separate finalize/merge step (copying out of
these per-job locations into wherever makes sense) — deliberately not built as part of this pipeline.

### Step 4 — configure and submit stage 2 (smoothing + FastTransform)

Edit the config block at the top of **`submitPostProcess.sh`**:

| Variable | Meaning |
|---|---|
| `JOBNAME` | This stage's *own* job name (just for GRID job monitoring) — **not** the same thing as `STAGE1_JOBNAME_TAG` below. |
| `STAGE1_JOBNAME_TAG` | **Must equal the `JOBNAME` stage 1 was actually submitted with** (Step 2). This is what stage 2 uses to find both the manifest and the `stage1Workdir.<tag>.txt` pointer file that tells it where stage 1's own jobs staged their maps. A mismatch here doesn't corrupt anything — the wrapper fails loudly up front if the pointer file can't be fetched (see Step 4's submission output), rather than silently producing zero output. |
| `TOPWORKDIR` | Same meaning as stage 1's. Independent value — stage 2 is its own GRID submission with its own working directory, not nested under stage 1's. |
| `PACKAGESPEC` | Same meaning as stage 1; keep in sync. Also determines whether `MACRO_SOURCE=official` can find the macros. |
| `ASUSER` | Same meaning as stage 1's — independent of what stage 1 used (stage 2's own submission). |
| `MACRO_SOURCE` / `MACRO_LOCAL_DIR` | See "Where the macros come from" above (this stage uploads all three macros at once when `MACRO_SOURCE=alien`, via `MACRO_LOCAL_DIR` rather than a single-file path). |

**Physics/processing parameters**, same as stage 1, live in the payload script
(**`postProcessJob.sh`**), not the wrapper:

| Variable | Meaning |
|---|---|
| `USE_SMOOTHED` | Should match stage 1's `USE_SMOOTHED` — selects `DO_GAUS_SMOOTH` below. |
| `DO_GAUS_SMOOTH` | Whether `SmoothingExtrapolate.C` applies Gaussian smoothing. |
| `DO_EXTRAPOLATION` | `2` = extrapolate both smoothed and raw values. |
| `A11_MAX_Z2X` | `-1` = disabled. |
| `MASK_IA11` | `0` = disabled. |
| `USE_CTP_LUMI` | Selects `TPCFastTransformInitCPM.C`'s luminosity source. `2` = CTP (matches stage 1's macro not accessing IDC scalers directly at all -- see the note at the end of Step 2). |
| `QA_DRAW_ERRORS` | `voxResQA.C` option — draw error bars. |
| `QA_USE_SMOOTHED` | `voxResQA.C` option — `true` draws the smoothed dXS/dYS/dZS (needs `SmoothingExtrapolate.C`'s output, which is exactly what it runs on); `false` draws raw dX/dY/dZ instead. |
| `QA_Z2X_BIN_SEL` | `voxResQA.C` option — `-1` = all z2x bins. |

**QA plots**: stage 2 also runs `voxResQA.C` on each slot's smoothed map, producing
`voxResQA<suffix>_1D.root`/`_2D.root` (canvases) plus individual `.png` quick-look images. QA failure
is non-fatal — it won't fail an otherwise-good slot.

Then:

```bash
./submitPostProcess.sh
```

This downloads the *existing* manifest stage 1 already uploaded (does not rebuild it — see the comment in
the script for why that matters), re-stages the three macros if `MACRO_SOURCE=alien`, and submits one
production, same slot granularity as stage 1.

**Local single-slot test:**

```bash
SUBJOBID=1 ./postProcessJob.sh
```

Stage 2's final output (the smoothed map, `FT_*.root` FastTransform file, and the two `voxResQA*.root`
QA files) is staged the same way as stage 1's — directly to *this job's own* `${ALIEN_JDL_OUTPUTDIR}`,
not stage 1's. Since stage 2 is a completely separate GRID submission (its own `JOBNAME`, its own
submission timestamp), this is a **different directory tree** from stage 1's, even for the exact same
logical slot:

```
<your-job-workdir-root>/<stage-2 JOBNAME>-<a-different-submission-timestamp>/<N zero-padded>/
    voxRes.<run>_<firstTS>_<lastTS>.TD<w>of<W>.it0.GausSmooth.Extrapolation.root
    FT_voxRes.<run>_<firstTS>_<lastTS>.TD<w>of<W>.it0.GausSmooth.Extrapolation.root
    voxResQA.voxRes.<run>_<firstTS>_<lastTS>.TD<w>of<W>.it0.GausSmooth.Extrapolation_1D.root
    voxResQA.voxRes.<run>_<firstTS>_<lastTS>.TD<w>of<W>.it0.GausSmooth.Extrapolation_2D.root
```

Stage 1's and stage 2's output for the same slot are *not* grouped under one tidy parent directory —
that's the direct cost of letting the JDL own output placement instead of managing it ourselves (see
the note at the end of Step 3). Same disk-quota reasoning as stage 1: explicit, synchronous `alien.py cp`
straight there, not the passive `#JDL_OUTPUT@disk=N` auto-upload (which only happens during the job's
asynchronous SAVING phase, after this script has already exited).

## Partial failure — this is by design, not a workaround

- **Some stage-1 slots fail or haven't finished**: stage 2, for that slot, finds nothing at the
  reconstructed `${ALIEN_JDL_OUTPUTDIR}` location, logs a warning, and exits 0 (success/no-op) — it does
  not fail the whole production. Resubmit just the missing stage-1 slot(s) later, then resubmit the
  corresponding stage-2 subjob(s).
- **A stage-1 slot is marked `badCalib_`** (too few tracks — see Step 3): stage 2 recognizes the
  `badCalib_` prefix specifically and logs that the calibration was intentionally marked bad, rather
  than the generic "not found" message. Also a no-op, not a failure.
- **Some stage-2 subjobs fail** (e.g. a transient GRID/network issue): only those need resubmitting —
  stage 1's expensive output is untouched and doesn't need to be redone.

## Known gotchas

- **`STAGE1_JOBNAME_TAG` is the only thing stage 2 has to get right.** It selects both the manifest and the `stage1Workdir` pointer. There is no time-window arithmetic to keep in sync any more — both stages read each slot's window straight off the same manifest line. A wrong tag fails loudly at the pointer fetch; a *stale* pointer under a reused tag would still no-op silently, so keep `JOBNAME` unique per submission.
- **Don't hand-edit `STAGE1_OUTPUTDIR_BASE`/`COUNTERWIDTH`/`MACRO_ALIEN_DIR_BARE`/`BAD_RANGES_NAME` inside the payload scripts** — like `JOBNAME_TAG`, these are placeholder lines the wrapper substitutes automatically per submission, not real per-user settings.
- **A window split can, rarely, produce a half with zero real data** if the split point lands past the run's actual end-of-run (a residual file's nominal timestamp range can pad past the true last data). That slot correctly gets marked `badCalib_` — it's an expected edge case, not something to debug further; the macro now also fails fast on it instead of wasting the CPU-time quota downloading data it will discard.
- **AliEn `wc -l`-derived counts can come back whitespace-padded**, which `grid_submit.sh --prodsplit` rejects outright (`Production split must be a positive integer (got '      70')`) — already fixed in the checked-in scripts, just noting it in case you copy this pattern elsewhere.
- **Job success rate around 80-90% is normal** for a first production pass — check individual failed-job logs on alimonitor before assuming something is systemically broken.

#!/usr/bin/env bash
# submitMapCreation.sh
#
# Submits one grid_submit.sh production-split job, one subjob per time-window slot found in <listsDir>
# (built beforehand by discoverResiduals.sh -- run that first).
#
# Before each submission, this re-stages the slot manifest (mapSlots.tsv, built here via
# stageSlotsForGrid.py) -- and, when MACRO_SOURCE=alien, the macro (staticMapCreatorCPM.C) too -- to
# the same AliEn dir mapCreationJob.sh downloads from. Both must be fresh: a stale macro, or
# stageSlotsForGrid.py pointed at a different destination than the job script expects, would silently
# desync what a running job downloads from what this wrapper thinks it uploaded. The bad-time-ranges list
# is treated differently -- see BAD_RANGES_LOCAL below -- it's occasionally-updated reference data, not
# something edited every session like the macro, so forcing a fresh re-upload on every submission is
# unnecessary friction.
#
# Slot windowing: stageSlotsForGrid.py cuts each run into windows of ~SLOT_LENGTH_MIN and writes ONE
# manifest line per window, carrying the window bounds and exactly the files that can contribute to it.
# A subjob index therefore identifies a (run, window) pair on its own, so this is a SINGLE submission --
# no loop over TimeDivisionIndex, no TIME_DIVISION placeholders substituted into the payload, and one
# stage1Workdir pointer instead of one per index. (With a fixed window length, runs of different length
# produce different window counts, so the old "one production per index x prodsplit runs" rectangle
# does not exist any more.) Both stages read the window off the same manifest line, which removes the
# old failure mode where stage 2 recomputed it and any mismatch silently produced zero output.
#
# Output location (2026-07-26, per ALICE Grid support): the actual map data (voxRes.*.root) is staged by
# mapCreationJob.sh directly to ${ALIEN_JDL_OUTPUTDIR} (the JDL-assigned per-subjob output dir --
# see that script), NOT to a fixed personal-space path -- avoids a separate disk-quota request on top of
# the CPU one, and is the standard mechanism support asked us to use. That directory is only known once
# the job actually runs, and its parent (MY_JOBWORKDIR, timestamped at THIS submission) is otherwise
# unrecoverable later -- grid_submit.sh prints it once, right here, before any GRID execution starts:
#   pok "Your job's working directory will be $MY_JOBWORKDIR"
# So this wrapper captures that one line, once per submission, and uploads it as a small pointer file
# (stage1Workdir.<JOBNAME>.txt, negligible size, fine to keep in personal space) -- submitPostProcess.sh
# downloads it and reconstructs each slot's exact
# ${ALIEN_JDL_OUTPUTDIR} from MY_JOBWORKDIR + the same alien_counter formula grid_submit.sh itself uses
# (see that script), without needing any in-job breadcrumb or querying AliEn after the fact.
#
# ASUSER / quota: setting ASUSER="pwg_pp" charges this job's CPU usage to that working group instead of
# the personal account, per ALICE Grid support's instruction (the account must already be a member of
# that group). grid_submit.sh's --asuser sets MY_USER=${ASUSER}, which determines BOTH the role active
# when its own internal transaction issues `submit` (so JAliEn attributes the job to that role) AND
# MY_HOMEDIR="/alice/cern.ch/user/${MY_USER:0:1}/${MY_USER}" -- so OutputDir automatically lands under
# that group's own writable space, with zero extra redirection needed. MACRO_ALIEN_DIR_BARE (the small
# manifest/macro staging area this wrapper itself uploads to, read-only from the job's point of view)
# stays fixed under the submitting account regardless of ASUSER -- read access there is unaffected by
# role.
#
# Usage:
#   ./submitMapCreation.sh [listsDir]
#   (listsDir defaults to ./lists -- discoverResiduals.sh's WORK_DIR, run from wherever you ran that
#   script)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LISTS_DIR="${1:-./lists}"

# ---------------------------------------------------------------------------
# Config -- edit per submission
# ---------------------------------------------------------------------------
JOBNAME="mapcreation-v1"   # must be unique per submission -- bump the suffix for each new production
TOPWORKDIR="MapCreation"   # replaces grid_submit.sh's generic default "selfjobs" bucket (on top of $HOME)
                           # with something identifiable -- matches MACRO_ALIEN_DIR_BARE's own naming
                           # below. Still just a static string per submission, not a per-run/period path
                           # like the real input data's own convention (.../2026/LHC26ak/572244/...) --
                           # that needs a real post-processing/organize step, deliberately deferred to a
                           # later iteration of this pipeline.
PACKAGESPEC="O2::daily-20260730-0000-1"
ASUSER="pwg_pp"        # your own account = personal quota. "pwg_pp" = charged to that working group's quota AND
                       # moves MY_JOBWORKDIR/OutputDir to pwg_pp's own space automatically -- see the
                       # long comment above for why this one value now does everything. NOTE support
                       # hedged on whether pwg_pp behaves like the other major accounts -- confirm on
                       # alimonitor that usage is really charged to the group before a large batch.
MACRO_SOURCE="official" # "official" (default): GRID jobs run staticMapCreatorCPM.C straight from the
                       # O2 package loaded via PACKAGESPEC ($O2_ROOT/share/macro/), no macro upload
                       # needed here at all -- requires PACKAGESPEC to resolve to a tag built from an O2
                       # version that includes it (Detectors/TPC/calibration/SpacePoints/macro/). "alien":
                       # stage MACRO_LOCAL_PATH to AliEn and have jobs download it instead -- use this
                       # until such a tag is published.
MACRO_LOCAL_PATH=""    # only used when MACRO_SOURCE=alien: local path to staticMapCreatorCPM.C to
                       # upload, e.g. your O2 checkout's
                       # Detectors/TPC/calibration/SpacePoints/macro/staticMapCreatorCPM.C.
                       # Staging area for the manifest + stage1Workdir pointer (and the macro, when
                       # MACRO_SOURCE=alien). No alien:// prefix. Derived from your own AliEn account the
                       # same way grid_submit.sh derives MY_HOMEDIR (ALIEN_USER, else the local
                       # username), so this file needs no per-user edit. Stays under the SUBMITTING
                       # account regardless of ASUSER -- read access there is unaffected by role, see the
                       # comment above. If your laptop's local username differs from your AliEn account
                       # (common), export ALIEN_USER, or just set MAPCREATION_ALIEN_DIR outright.
ALIEN_USER_NAME="${ALIEN_USER:-$(whoami)}"
MACRO_ALIEN_DIR_BARE="${MAPCREATION_ALIEN_DIR:-/alice/cern.ch/user/${ALIEN_USER_NAME:0:1}/${ALIEN_USER_NAME}/MapCreation}"
BAD_RANGES_NAME="Merge_BadIntervals_LHC26_PbPb_DCA-0P300.txt"
                       # Filename of the bad-time-ranges list, under ${MACRO_ALIEN_DIR}/lists/. Period-
                       # and system-specific (this one is PbPb26), so it changes when the data does --
                       # hence a variable rather than a constant baked into three places. Substituted
                       # into mapCreationJob.sh the same way as JOBNAME_TAG, so
                       # set it only here. Used both as the upload destination (when BAD_RANGES_LOCAL is
                       # set) and as the name each job downloads -- the two cannot drift apart.
                       # Set to "" to disable bad-ranges filtering entirely for this submission
                       # (staticMapCreatorCPM.C treats an empty badRangeList argument that way) -- a
                       # deliberate opt-out, not the same as forgetting to set it.
BAD_RANGES_LOCAL=""   # optional: local path to the bad-time-ranges file to (re-)upload this run (real
                       # source for the PbPb26 list above:
                       # /lustre/alice/tpcdata/Run3/SCDprodTests/lists/badRange/PbPb26/). Leave empty to
                       # skip the upload and just use the copy already at
                       # ${MACRO_ALIEN_DIR}/lists/${BAD_RANGES_NAME}.
RUNS_FILTER=""         # optional comma-separated run whitelist, e.g. "572557,572558". Empty = every run
                       # found under listsDir. discoverResiduals.sh appends to the same ./lists tree
                       # across batches, so leaving this empty after a second discovery round silently
                       # folds the EARLIER batch's runs into this submission too -- recalibrating them
                       # from scratch at hours per slot. Set it when ./lists holds more than you want.
                       # A run named here with no lists under listsDir is a hard error.
OVERLAP_MARGIN_MS=1000 # a file is assigned to a window only if its aggregation label overlaps that
                       # window by MORE than this. Coarse labels routinely begin 1-2 ms before a window
                       # ends, and a bare overlap test drags all of their files into a window whose map
                       # they contribute nothing to. Bounded cost: at most this many ms of coverage per
                       # window edge, since the macro's per-TF cut discards the rest anyway.
SLOT_LENGTH_MIN=5      # target length of ONE map, in minutes. Each run is cut into whole steps of this
                       # length; a trailing remainder shorter than half a step is absorbed into the last
                       # window rather than left as a runt that would fail MIN_TRACKS_PER_SLICE. 0 means
                       # one map per run (no splitting). This replaces the old TIME_DIVISION count: with
                       # a fixed length, a 20 min run gives 4 maps and a 60 min run gives 12, instead of
                       # the same count regardless of run length. Stage 2 does not need this value -- it
                       # reuses stage 1's manifest, which already carries the windows.
# ---------------------------------------------------------------------------

MACRO_ALIEN_DIR="alien://${MACRO_ALIEN_DIR_BARE}"
echo "== Staging area (manifest + stage1Workdir pointer): ${MACRO_ALIEN_DIR_BARE} =="
echo "   (derived from AliEn user '${ALIEN_USER_NAME}' -- export ALIEN_USER or MAPCREATION_ALIEN_DIR if that is wrong)"

if [[ "${MACRO_SOURCE}" == "alien" ]]; then
  [[ -n "${MACRO_LOCAL_PATH}" && -f "${MACRO_LOCAL_PATH}" ]] || { echo "ERROR: MACRO_SOURCE=alien needs MACRO_LOCAL_PATH set to a real staticMapCreatorCPM.C (got '${MACRO_LOCAL_PATH}')" >&2; exit 1; }
  echo "== Re-staging macro from ${MACRO_LOCAL_PATH} to ${MACRO_ALIEN_DIR} =="
  alien.py cp -f "file:${MACRO_LOCAL_PATH}" "${MACRO_ALIEN_DIR}/staticMapCreatorCPM.C"
else
  echo "== MACRO_SOURCE=official -- skipping macro upload, jobs will use \${O2_ROOT}/share/macro/staticMapCreatorCPM.C from PACKAGESPEC =="
fi

if [[ -z "${BAD_RANGES_NAME}" ]]; then
  # Deliberate opt-out, not a mistake: an empty BAD_RANGES_NAME propagates through to
  # mapCreationJob.sh as BAD_RANGES_ARG="" -- staticMapCreatorCPM.C's own
  # `if (badRangeList.length() > 0)` guard treats that as "skip bad-ranges filtering entirely" for
  # this submission. Nothing to upload or verify.
  echo "== BAD_RANGES_NAME is empty -- bad-time-ranges filtering disabled for this submission =="
elif [[ -n "${BAD_RANGES_LOCAL}" ]]; then
  [[ -f "${BAD_RANGES_LOCAL}" ]] || { echo "ERROR: BAD_RANGES_LOCAL not found: ${BAD_RANGES_LOCAL}" >&2; exit 1; }
  echo "== Re-staging bad-ranges list from ${BAD_RANGES_LOCAL} to ${MACRO_ALIEN_DIR}/lists/${BAD_RANGES_NAME} =="
  alien.py cp -f "file:${BAD_RANGES_LOCAL}" "${MACRO_ALIEN_DIR}/lists/${BAD_RANGES_NAME}"
else
  # No local file to (re-)upload -- the job will download whatever is already staged under
  # BAD_RANGES_NAME, so check now, once, locally, that it actually exists. Left unchecked, a wrong
  # BAD_RANGES_NAME/ALIEN_USER or a never-uploaded file would only surface inside
  # mapCreationJob.sh's own alien.py cp, in every single subjob, with a raw/confusing AliEn error
  # instead of one clear message before anything is submitted.
  echo "== BAD_RANGES_LOCAL not set -- checking ${MACRO_ALIEN_DIR}/lists/${BAD_RANGES_NAME} already exists on AliEn =="
  if ! alien.py stat "${MACRO_ALIEN_DIR}/lists/${BAD_RANGES_NAME}" &>/dev/null; then
    echo "ERROR: ${MACRO_ALIEN_DIR}/lists/${BAD_RANGES_NAME} not found on AliEn, and BAD_RANGES_LOCAL is not set to (re-)upload one." >&2
    echo "       Either set BAD_RANGES_LOCAL to a local file to upload, set BAD_RANGES_NAME=\"\" to disable bad-ranges filtering, or upload the file to that path by hand." >&2
    exit 1
  fi
  echo "== Found existing ${MACRO_ALIEN_DIR}/lists/${BAD_RANGES_NAME} =="
fi

# Tagged by JOBNAME: a shared, untagged manifest name would let a second submission (different
# lists/config) silently overwrite the first's manifest, breaking any already-running job that re-reads
# it and desyncing stage 2's later subjob-index -> slot lookup.
MANIFEST_NAME="mapSlots.${JOBNAME}.tsv"
echo "== Building + uploading slot manifest from ${LISTS_DIR} (as ${MANIFEST_NAME}) =="
N=$("${SCRIPT_DIR}/stageSlotsForGrid.py" \
       --lists-dir          "${LISTS_DIR}" \
       --alien-dir          "${MACRO_ALIEN_DIR_BARE}" \
       --manifest-name      "${MANIFEST_NAME}" \
       --runs               "${RUNS_FILTER}" \
       --slot-length-min    "${SLOT_LENGTH_MIN}" \
       --overlap-margin-ms  "${OVERLAP_MARGIN_MS}")
echo "N=${N} slot(s) == map(s) to be produced"
[[ "${N}" -gt 0 ]] || { echo "ERROR: no slots found under ${LISTS_DIR}" >&2; exit 1; }

TMP_SCRIPT="$(mktemp)"
trap 'rm -f "${TMP_SCRIPT}"' EXIT

# ONE submission, one subjob per manifest line. There is no longer a loop over TimeDivisionIndex: the
# windows are baked into the manifest by stageSlotsForGrid.py, so a subjob index alone identifies a
# (run, window) pair. That also means one stage1Workdir pointer instead of one per index, and no
# TIME_DIVISION/TIME_DIVISION_INDEX placeholders to substitute -- with a fixed SLOT_LENGTH_MIN,
# different-length runs yield different window counts, so the old rectangular
# "one production per index x prodsplit runs" grid does not exist any more.
sed \
  -e "s/^JOBNAME_TAG=.*/JOBNAME_TAG=${JOBNAME}/" \
  -e "s/^MACRO_SOURCE=.*/MACRO_SOURCE=${MACRO_SOURCE}/" \
  -e "s|^MACRO_ALIEN_DIR_BARE=.*|MACRO_ALIEN_DIR_BARE=${MACRO_ALIEN_DIR_BARE}|" \
  -e "s|^BAD_RANGES_NAME=.*|BAD_RANGES_NAME=${BAD_RANGES_NAME}|" \
  "${SCRIPT_DIR}/mapCreationJob.sh" > "${TMP_SCRIPT}"

GRID_SUBMIT_ARGS=(
  --script "${TMP_SCRIPT}"
  --jobname "${JOBNAME}"
  --topworkdir "${TOPWORKDIR}"
  --prodsplit "${N}"
  --packagespec "${PACKAGESPEC}"
  --asuser "${ASUSER}"
)

echo "== Submitting ${JOBNAME} (prodsplit=${N}, asuser=${ASUSER}) =="
# Capture grid_submit.sh's own stderr (its "pok" status messages go there) while still showing it live,
# so we can pull out the one line that tells us where this submission's data will actually land.
SUBMIT_LOG=$("${O2DPG_ROOT}/GRID/utils/grid_submit.sh" "${GRID_SUBMIT_ARGS[@]}" 2>&1 | tee /dev/stderr)

# Strip ANSI color codes (pok() wraps its output in \033[32m...\033[m) before parsing.
MY_JOBWORKDIR=$(echo "${SUBMIT_LOG}" | sed -E 's/\x1b\[[0-9;]*m//g' | sed -n "s/^Your job's working directory will be //p" | tail -1)
if [[ -z "${MY_JOBWORKDIR}" ]]; then
  echo "ERROR: could not find \"Your job's working directory will be ...\" in grid_submit.sh's output -- stage 2 won't be able to find this submission's output. Aborting." >&2
  exit 1
fi
echo "== MY_JOBWORKDIR = ${MY_JOBWORKDIR} =="

WORKDIR_POINTER_NAME="stage1Workdir.${JOBNAME}.txt"
WORKDIR_POINTER_TMP="$(mktemp)"
echo "${MY_JOBWORKDIR}" > "${WORKDIR_POINTER_TMP}"
alien.py cp -f "file:${WORKDIR_POINTER_TMP}" "${MACRO_ALIEN_DIR}/${WORKDIR_POINTER_NAME}"
rm -f "${WORKDIR_POINTER_TMP}"
echo "== Uploaded ${WORKDIR_POINTER_NAME} =="

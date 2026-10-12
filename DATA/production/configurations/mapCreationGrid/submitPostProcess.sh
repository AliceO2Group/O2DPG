#!/usr/bin/env bash
# submitPostProcess.sh
#
# STAGE 2 submission wrapper: submits one grid_submit.sh production-split job, one subjob per slot --
# same granularity as stage 1 (submitMapCreation.sh), so a failed
# stage-2 subjob can be resubmitted on its own without touching stage 1's (hours-long) map creation.
#
# Unlike stage 1, this does NOT rebuild the slot manifest (mapSlots.tsv) -- it reuses the exact one
# stage 1 already uploaded (downloaded here only to count lines for --prodsplit N). Rebuilding it here
# would risk a mismatch if the local lists/ dir changed between the two submissions, which would
# silently desync stage 2's subjob-index -> slot mapping from stage 1's.
#
# IMPORTANT: STAGE1_JOBNAME_TAG must match whatever the stage-1 submission this is post-processing
# actually used -- it selects both the manifest and the stage1Workdir pointer. There is nothing else to
# keep in sync: the slot windows come from stage 1's own manifest, which this stage reuses verbatim, so
# the two stages cannot disagree about a slot's identity the way they could when each recomputed it.
#
# Output location (per ALICE Grid support -- see submitMapCreation.sh): stage 1 stages its map to its
# own ${ALIEN_JDL_OUTPUTDIR}, not a fixed personal-space path, so there's no static location
# to just look up. Stage 1's wrapper captured MY_JOBWORKDIR (that submission's timestamped parent
# directory) at submission time and uploaded it as a small pointer file --
# downloaded below and substituted into the payload script (STAGE1_OUTPUTDIR_BASE) alongside COUNTERWIDTH
# (grid_submit.sh's own alien_counter zero-padding width -- deterministic from N, which is shared between
# both stages since this wrapper reuses stage 1's manifest, so it's recomputed here rather than needing
# its own pointer file). The payload script reconstructs each slot's exact ${ALIEN_JDL_OUTPUTDIR} from
# those two values the same way grid_submit.sh itself derives OutputDir.
#
# ASUSER / quota: see submitMapCreation.sh's own comment for the full story -- ASUSER
# determines both the role JAliEn attributes the job to and where MY_HOMEDIR (and therefore OutputDir)
# lands. Must match whatever STAGE1_JOBNAME_TAG's submission actually used, since STAGE1_OUTPUTDIR_BASE
# below (from stage 1's pointer file) already reflects wherever stage 1's own ASUSER put it -- this
# script doesn't need its own OutputDir logic, it just needs to read/write consistently with whatever
# stage 1 did.
#
# This wrapper also captures and uploads ITS OWN workdir pointer (stage2Workdir.<JOBNAME>.txt), the same
# way stage 1 does for its own output -- nothing inside this pipeline needed that before (stage 2 is the
# end of the line here), but an external consumer that needs to locate a specific slot's final
# FT_*.root/smoothed map (e.g. a downstream pipeline using it as an input) has no other way to find it,
# since it also lands in an ephemeral ${ALIEN_JDL_OUTPUTDIR}, not a fixed path. Purely additive: this
# stage's own control flow and outputs are unchanged, it just also records where they went.
#
# Usage:
#   ./submitPostProcess.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
# Config -- edit per submission. STAGE1_JOBNAME_TAG must name the stage-1 submission this
# post-processes; everything else about the slot layout comes from that submission's manifest.
# ---------------------------------------------------------------------------
JOBNAME="mapcreation-postprocess-v1"      # this stage's OWN job name (GRID job monitoring identity) --
                                           # NOT the same thing as STAGE1_JOBNAME_TAG below.
STAGE1_JOBNAME_TAG="mapcreation-v1"        # must equal the JOBNAME stage 1 (submitMapCreation.sh) was
                                           # actually submitted with -- that's what determined where
                                           # stage 1 staged its map.
TOPWORKDIR="MapCreation"
PACKAGESPEC="O2::daily-20260730-0000-1"
ASUSER="pwg_pp"        # see the long comment above -- your own account for personal quota, "pwg_pp" for group
                       # quota (this stage's own submission; independent of what stage 1 used).
MACRO_SOURCE="official" # same meaning/default as stage 1 (submitMapCreation.sh) -- applies
                       # to all three macros used here.
MACRO_LOCAL_DIR=""     # only used when MACRO_SOURCE=alien: local directory containing
                       # SmoothingExtrapolate.C, TPCFastTransformInitCPM.C, voxResQA.C to upload, e.g.
                       # your O2 checkout's Detectors/TPC/calibration/SpacePoints/macro/ +
                       # GPU/TPCFastTransformation/macro/ (voxResQA.C and SmoothingExtrapolate.C live in
                       # the former, TPCFastTransformInitCPM.C in the latter -- symlink/copy them into one
                       # local dir first if they're not already colocated).
                       # Same staging root as stage 1, derived the same way (see that script's comment):
                       # ALIEN_USER, else the local username; override with MAPCREATION_ALIEN_DIR. Must
                       # resolve to whatever stage 1 actually used, since that's where its manifest and
                       # stage1Workdir pointer live.
ALIEN_USER_NAME="${ALIEN_USER:-$(whoami)}"
MACRO_ALIEN_DIR_BARE="${MAPCREATION_ALIEN_DIR:-/alice/cern.ch/user/${ALIEN_USER_NAME:0:1}/${ALIEN_USER_NAME}/MapCreation}"
# ---------------------------------------------------------------------------

MACRO_ALIEN_DIR="alien://${MACRO_ALIEN_DIR_BARE}"
echo "== Staging area (must match stage 1's): ${MACRO_ALIEN_DIR_BARE} =="
echo "   (derived from AliEn user '${ALIEN_USER_NAME}' -- export ALIEN_USER or MAPCREATION_ALIEN_DIR if that is wrong)"

if [[ "${MACRO_SOURCE}" == "alien" ]]; then
  [[ -n "${MACRO_LOCAL_DIR}" && -f "${MACRO_LOCAL_DIR}/SmoothingExtrapolate.C" && -f "${MACRO_LOCAL_DIR}/TPCFastTransformInitCPM.C" && -f "${MACRO_LOCAL_DIR}/voxResQA.C" ]] || { echo "ERROR: MACRO_SOURCE=alien needs MACRO_LOCAL_DIR set to a directory containing all three macros (got '${MACRO_LOCAL_DIR}')" >&2; exit 1; }
  echo "== Re-staging SmoothingExtrapolate.C / TPCFastTransformInitCPM.C / voxResQA.C from ${MACRO_LOCAL_DIR} to ${MACRO_ALIEN_DIR} =="
  alien.py cp -f "file:${MACRO_LOCAL_DIR}/SmoothingExtrapolate.C" "${MACRO_ALIEN_DIR}/SmoothingExtrapolate.C"
  alien.py cp -f "file:${MACRO_LOCAL_DIR}/TPCFastTransformInitCPM.C" "${MACRO_ALIEN_DIR}/TPCFastTransformInitCPM.C"
  alien.py cp -f "file:${MACRO_LOCAL_DIR}/voxResQA.C" "${MACRO_ALIEN_DIR}/voxResQA.C"
else
  echo "== MACRO_SOURCE=official -- skipping macro upload, jobs will use \${O2_ROOT}/share/macro/ from PACKAGESPEC =="
fi

# Tagged manifest name -- must match whatever stage 1 actually uploaded (mapSlots.<its JOBNAME>.tsv),
# hence STAGE1_JOBNAME_TAG rather than this stage's own JOBNAME.
MANIFEST_NAME="mapSlots.${STAGE1_JOBNAME_TAG}.tsv"
echo "== Fetching existing slot manifest from ${MACRO_ALIEN_DIR}/${MANIFEST_NAME} (NOT rebuilt) =="
TMP_MANIFEST="$(mktemp)"
alien.py cp -f "${MACRO_ALIEN_DIR}/${MANIFEST_NAME}" "file:${TMP_MANIFEST}"
N=$(wc -l < "${TMP_MANIFEST}" | tr -d '[:space:]')  # wc -l right-justifies its count with leading
                                                     # whitespace even without a filename arg; grid_submit.sh's
                                                     # --prodsplit does a strict positive-integer check that
                                                     # rejects that -- confirmed real, 2026-07-26 ("Production
                                                     # split must be a positive integer (got '      70')").
echo "N=${N} slot(s)"
[[ "${N}" -gt 0 ]] || { echo "ERROR: ${MANIFEST_NAME} has no lines -- was stage 1 ever submitted with this JOBNAME?" >&2; exit 1; }

# Same formula grid_submit.sh itself uses to derive its alien_counter zero-padding width -- deterministic
# from N, which is identical between stage 1 and stage 2 (same manifest, same line count), so this will
# match whatever stage 1's own submission actually used without needing to record it separately.
COUNTERWIDTH=${#N}
[[ "${COUNTERWIDTH}" -lt 3 ]] && COUNTERWIDTH=3

TMP_SCRIPT="$(mktemp)"
TMP_WORKDIR_POINTER="$(mktemp)"
TMP_STAGE2_WORKDIR_POINTER="$(mktemp)"
trap 'rm -f "${TMP_MANIFEST}" "${TMP_SCRIPT:-}" "${TMP_WORKDIR_POINTER}" "${TMP_STAGE2_WORKDIR_POINTER}"' EXIT

# ONE submission, mirroring stage 1: the windows live in the manifest, so a subjob index identifies a
# (run, window) pair by itself and there is nothing to loop over.
WORKDIR_POINTER_NAME="stage1Workdir.${STAGE1_JOBNAME_TAG}.txt"
echo "== Fetching ${WORKDIR_POINTER_NAME} =="
# Truncate first: an alien.py cp that returns 0 without writing would otherwise leave stale content
# here and point this whole submission at the wrong stage-1 workdir, silently no-opping every slot.
: > "${TMP_WORKDIR_POINTER}"
if ! alien.py cp -f "${MACRO_ALIEN_DIR}/${WORKDIR_POINTER_NAME}" "file:${TMP_WORKDIR_POINTER}" || [[ ! -s "${TMP_WORKDIR_POINTER}" ]]; then
  echo "ERROR: could not fetch ${WORKDIR_POINTER_NAME} -- was stage 1 actually submitted under STAGE1_JOBNAME_TAG=${STAGE1_JOBNAME_TAG}?" >&2
  exit 1
fi
STAGE1_OUTPUTDIR_BASE=$(head -1 "${TMP_WORKDIR_POINTER}")
if [[ "${STAGE1_OUTPUTDIR_BASE}" != /alice/* ]]; then
  echo "ERROR: ${WORKDIR_POINTER_NAME} does not contain an absolute /alice/... path: '${STAGE1_OUTPUTDIR_BASE}'" >&2
  exit 1
fi
echo "== STAGE1_OUTPUTDIR_BASE = ${STAGE1_OUTPUTDIR_BASE} =="

sed \
  -e "s/^STAGE1_JOBNAME_TAG=.*/STAGE1_JOBNAME_TAG=${STAGE1_JOBNAME_TAG}/" \
  -e "s/^MACRO_SOURCE=.*/MACRO_SOURCE=${MACRO_SOURCE}/" \
  -e "s|^MACRO_ALIEN_DIR_BARE=.*|MACRO_ALIEN_DIR_BARE=${MACRO_ALIEN_DIR_BARE}|" \
  -e "s|^STAGE1_OUTPUTDIR_BASE=.*|STAGE1_OUTPUTDIR_BASE=${STAGE1_OUTPUTDIR_BASE}|" \
  -e "s/^COUNTERWIDTH=.*/COUNTERWIDTH=${COUNTERWIDTH}/" \
  "${SCRIPT_DIR}/postProcessJob.sh" > "${TMP_SCRIPT}"

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
# so we can pull out the one line that tells us where this submission's data will actually land -- same
# mechanism submitMapCreation.sh uses for its own stage1Workdir pointer. Nothing downstream needed
# stage 2's own output location before now; this exists so a future consumer (e.g. a pipeline that reads
# stage 2's FT_*.root as an input) can find it without guessing.
SUBMIT_LOG=$("${O2DPG_ROOT}/GRID/utils/grid_submit.sh" "${GRID_SUBMIT_ARGS[@]}" 2>&1 | tee /dev/stderr)

# Strip ANSI color codes (pok() wraps its output in \033[32m...\033[m) before parsing.
MY_JOBWORKDIR=$(echo "${SUBMIT_LOG}" | sed -E 's/\x1b\[[0-9;]*m//g' | sed -n "s/^Your job's working directory will be //p" | tail -1)
if [[ -z "${MY_JOBWORKDIR}" ]]; then
  echo "ERROR: could not find \"Your job's working directory will be ...\" in grid_submit.sh's output -- a future consumer of this stage's output won't be able to find it. Aborting." >&2
  exit 1
fi
echo "== MY_JOBWORKDIR (stage 2's own) = ${MY_JOBWORKDIR} =="

STAGE2_WORKDIR_POINTER_NAME="stage2Workdir.${JOBNAME}.txt"
echo "${MY_JOBWORKDIR}" > "${TMP_STAGE2_WORKDIR_POINTER}"
alien.py cp -f "file:${TMP_STAGE2_WORKDIR_POINTER}" "${MACRO_ALIEN_DIR}/${STAGE2_WORKDIR_POINTER_NAME}"
echo "== Uploaded ${STAGE2_WORKDIR_POINTER_NAME} =="

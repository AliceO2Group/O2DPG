#!/usr/bin/env bash
# postProcessJob.sh — STAGE 2 of the two-stage pipeline.
#
# Runs the fast (minutes, not hours) part of the chain on an already-produced map:
#   SmoothingExtrapolate.C  ->  TPCFastTransformInitCPM.C
#
# Independent of stage 1 (mapCreationJob.sh): does NOT re-run map creation, does NOT even download the
# (multi-GB) residual files. It only needs the small manifest (mapSlots.tsv, reused as-is from stage 1,
# NOT rebuilt) to work out which map stage 1 should have produced for this same subjob index. Both
# stages read the run/window straight off the SAME manifest line, so they cannot disagree about a
# slot's identity.
#
# If stage 1 hasn't produced (or failed to produce) this slot's map yet, this script logs a warning
# and exits 0 (success/no-op) rather than failing -- so a partial stage-1 completion (some slots ok,
# some failed) doesn't turn every stage-2 subjob into a failure. Once stage 1 is resubmitted for the
# missing slots, just resubmit the corresponding stage-2 subjob(s).
#
# Slot windowing: none happens here. stageSlotsForGrid.py fixed the windows at submission time and
# wrote them into the manifest; this script just reads its line.
#
# STAGE1_JOBNAME_TAG: which stage-1 production's manifest/output to look for -- NOT this stage's own job
# name, but stage 1's JOBNAME_TAG (mapCreationJob.sh), since that's what determined the manifest
# name AND (via the STAGE1_OUTPUTDIR_BASE pointer file it uploaded) where stage 1's own jobs staged their
# maps. Must match exactly, or this will always hit the graceful-skip path even though stage 1 succeeded.
#
# STAGE1_OUTPUTDIR_BASE / COUNTERWIDTH (per ALICE Grid support): stage 1 stages its map to its own
# ${ALIEN_JDL_OUTPUTDIR} rather than a fixed personal-space path (avoids a separate disk-quota request),
# so there's no static location to just look up. STAGE1_OUTPUTDIR_BASE is stage 1's MY_JOBWORKDIR (that
# submission's timestamped parent directory, captured by submitMapCreation.sh right when it
# ran grid_submit.sh -- otherwise unrecoverable later) and COUNTERWIDTH is grid_submit.sh's own
# alien_counter zero-padding width -- together they let this script reconstruct stage 1's exact per-slot
# ${ALIEN_JDL_OUTPUTDIR} the same way grid_submit.sh itself derives OutputDir (see below), without any
# in-job breadcrumb from stage 1 or an extra AliEn round trip.
#
# MACRO_SOURCE: same meaning and default ("official") as stage 1 -- see mapCreationJob.sh. Applies
# to all three macros used here (SmoothingExtrapolate.C, TPCFastTransformInitCPM.C, voxResQA.C), all
# installed to the same $O2_ROOT/share/macro/ once the O2 PR is merged into this job's packagespec.
#
# MACRO_ALIEN_DIR_BARE: same placeholder mechanism, substituted from the wrapper's own
# MACRO_ALIEN_DIR_BARE -- must match stage 1's. Used for the manifest/stage1Workdir pointer regardless of
# MACRO_SOURCE; only used for the macros themselves when MACRO_SOURCE=alien.
STAGE1_JOBNAME_TAG=default
STAGE1_OUTPUTDIR_BASE=
COUNTERWIDTH=3
MACRO_SOURCE=official
MACRO_ALIEN_DIR_BARE=${MACRO_ALIEN_DIR_BARE:-}
#JDL_OUTPUT=*.log@disk=2,*.txt@disk=2,*.png@disk=2
#JDL_REQUIRE={member(other.GridPartitions,"multicore_8") && (other.CE != "ALICE::NIHAM::PBS64") && (other.CE != "ALICE::KISTI_GSDC::LCG") && (other.CE != "ALICE::SaoPaulo::LCG")};
# Site blacklist -- same three CEs excluded as stage 1, see that script's comment for why the
# GridPartitions clause has to be repeated here (grid_submit.sh replaces its whole default Requirements,
# doesn't merge with it).
# voxRes.*.root/FT_*.root/voxResQA*.root deliberately NOT in this pattern -- same reasoning as stage 1
# (mapCreationJob.sh): they're staged explicitly, once, to this job's own ${ALIEN_JDL_OUTPUTDIR}
# below, so having them ALSO match here would duplicate the upload to the same place for no benefit.
# The QA step's individual *.png canvases ARE left in this pattern -- they're small, convenience-only
# quick-look images, not worth a second explicit-staging code path for.

set -e

# xrootd client tuning -- see mapCreationJob.sh for the reasoning; same values, same rationale,
# applies equally here since this script does just as much alien://xrootd transfer (macros, manifest,
# the fixed-location map download) even though it doesn't touch the multi-GB residual files.
export XRD_TIMEOUTRESOLUTION=15
export XRD_CONNECTIONWINDOW=30
export XRD_CONNECTIONRETRY=4
export XRD_REQUESTTIMEOUT=120
export XRD_STREAMTIMEOUT=120
export XRD_STREAMERRORWINDOW=0

# --- AliEn path holding mapSlots.tsv / the stage1Workdir pointer file (and the three macros too, when
# MACRO_SOURCE=alien). Same root dir as stage 1's MACRO_ALIEN_DIR.
#
# Normally substituted above by submitPostProcess.sh; empty only on a standalone/local run -- see the
# same guard in mapCreationJob.sh.
: "${MACRO_ALIEN_DIR_BARE:?MACRO_ALIEN_DIR_BARE is empty -- the submission wrapper normally substitutes it. For a standalone/local run, export it first, e.g. MACRO_ALIEN_DIR_BARE=/alice/cern.ch/user/<initial>/<user>/MapCreation}"
MACRO_ALIEN_DIR="alien://${MACRO_ALIEN_DIR_BARE}"

if [[ "${MACRO_SOURCE}" == "official" ]]; then
  : "${O2_ROOT:?O2_ROOT is not set -- MACRO_SOURCE=official needs the O2 package loaded via --packagespec}"
  SMOOTHING_MACRO_PATH="${O2_ROOT}/share/macro/SmoothingExtrapolate.C"
  FASTTRANSFORM_MACRO_PATH="${O2_ROOT}/share/macro/TPCFastTransformInitCPM.C"
  QA_MACRO_PATH="${O2_ROOT}/share/macro/voxResQA.C"
  for f in "${SMOOTHING_MACRO_PATH}" "${FASTTRANSFORM_MACRO_PATH}" "${QA_MACRO_PATH}"; do
    if [[ ! -f "${f}" ]]; then
      echo "ERROR: MACRO_SOURCE=official but ${f} does not exist -- this job's --packagespec does not include it yet. Use MACRO_SOURCE=alien until a packagespec with it is published." >&2
      exit 1
    fi
  done
else
  alien.py cp -f "${MACRO_ALIEN_DIR}/SmoothingExtrapolate.C" file:./SmoothingExtrapolate.C
  alien.py cp -f "${MACRO_ALIEN_DIR}/TPCFastTransformInitCPM.C" file:./TPCFastTransformInitCPM.C
  alien.py cp -f "${MACRO_ALIEN_DIR}/voxResQA.C" file:./voxResQA.C
  SMOOTHING_MACRO_PATH="./SmoothingExtrapolate.C"
  FASTTRANSFORM_MACRO_PATH="./TPCFastTransformInitCPM.C"
  QA_MACRO_PATH="./voxResQA.C"
fi
# Tagged manifest name -- must match whatever stage 1 actually uploaded (mapSlots.<its JOBNAME>.tsv).
alien.py cp -f "${MACRO_ALIEN_DIR}/mapSlots.${STAGE1_JOBNAME_TAG}.tsv" file:./mapSlots.tsv

# --- Determine this subjob's index into mapSlots.tsv (same convention as stage 1) ---
SUBJOBID="${ALIEN_O2DPG_GRIDSUBMIT_SUBJOBID:-${SUBJOBID:-}}"
: "${SUBJOBID:?SUBJOBID must be set (via ALIEN_O2DPG_GRIDSUBMIT_SUBJOBID on GRID, or the SUBJOBID env var for --local testing)}"

LINE=$(sed -n "${SUBJOBID}p" mapSlots.tsv)
if [[ -z "${LINE}" ]]; then
  echo "ERROR: mapSlots.tsv has no line ${SUBJOBID}" >&2
  exit 1
fi

# Manifest line: <run> \t <winIdx> \t <winCount> \t <winFirstTS> \t <winLastTS> \t <paths>
# Stage 2 does NO time arithmetic: it reads the window straight off the same manifest line stage 1
# used, so OUTPUT_STEM below is identical to stage 1's by construction. Previously both stages
# recomputed the window from TIME_DIVISION/TIME_DIVISION_INDEX and any disagreement meant stage 2
# silently found nothing and no-opped for every slot.
# The 6th field (the file list) is deliberately discarded: stage 2 never touches the residual
# files, it only needs the run and the window. It still has to be READ, or lastTSIter would
# swallow the rest of the line.
IFS=$'\t' read -r RUN WIN_IDX WIN_COUNT firstTSIter lastTSIter _ <<< "${LINE}"
for v in RUN WIN_IDX WIN_COUNT firstTSIter lastTSIter; do
  if [[ ! "${!v}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: manifest line ${SUBJOBID} field ${v}='${!v}' is not numeric -- expected 6 tab-separated fields <run> <winIdx> <winCount> <winFirstTS> <winLastTS> <paths>" >&2
    exit 1
  fi
done
echo "Slot ${SUBJOBID}: run ${RUN}, window ${WIN_IDX}/${WIN_COUNT} [${firstTSIter},${lastTSIter}]"

# --- Config (production defaults) ---
USE_SMOOTHED=2                      # matches stage 1's USE_SMOOTHED -- selects doGausSmooth=true below
DO_GAUS_SMOOTH=true
DO_EXTRAPOLATION=2                  # smoothed AND raw values extrapolated
A11_MAX_Z2X=-1                      # disabled
MASK_IA11=0                         # disabled
USE_CTP_LUMI=2                      # matches stage 1's USE_CTP_LUMI

# voxResQA.C config -- needs SmoothingExtrapolate.C's DS[] (smoothed dX/dY/dZ) already filled in,
# hence run from here, on OUTPUT_MAP_SMOOTH, not the raw stage-1 map.
QA_DRAW_ERRORS=false
QA_USE_SMOOTHED=true                # true: draw dXS/dYS/dZS (needs SmoothingExtrapolate.C's output); false: raw dX/dY/dZ
QA_Z2X_BIN_SEL=-1                   # -1: all z2x bins

# --- Expected stage-1 output filename (must match mapCreationJob.sh's OUTPUT_STEM exactly) ---
OUTPUT_STEM="voxRes.${RUN}_${firstTSIter}_${lastTSIter}.TD${WIN_IDX}of${WIN_COUNT}.it0"
STAGE1_OUTPUT_FILE="${OUTPUT_STEM}.root"

# Reconstruct stage 1's exact per-slot ${ALIEN_JDL_OUTPUTDIR} -- same formula grid_submit.sh itself uses
# to derive OutputDir (MY_JOBWORKDIR/#alien_counter_0Wi#): STAGE1_OUTPUTDIR_BASE is stage 1's
# MY_JOBWORKDIR, and this slot's own subjob index (SUBJOBID, same manifest line/counter convention as
# stage 1) zero-padded to COUNTERWIDTH gives the exact subdirectory stage 1's own job for this slot wrote
# its output to.
SUBJOB_COUNTER_DIR=$(printf "%0${COUNTERWIDTH}d" "${SUBJOBID}")
STAGE1_OUTPUT_LOCATION="alien://${STAGE1_OUTPUTDIR_BASE}/${SUBJOB_COUNTER_DIR}"

# Local name deliberately does NOT look like our own output (voxRes.*.root/FT_*.root) -- both are now
# staged explicitly below rather than picked up via a JDL_OUTPUT glob, but naming this distinctly still
# avoids any confusion between "the map we downloaded as input" and "the map we produced" (the exact bug
# found+fixed earlier for badRanges.txt/badRanges.dat).
INPUT_MAP="input_map.root"

echo "Looking for stage-1 output at ${STAGE1_OUTPUT_LOCATION}/${STAGE1_OUTPUT_FILE}"
if ! alien.py cp -f "${STAGE1_OUTPUT_LOCATION}/${STAGE1_OUTPUT_FILE}" "file:${INPUT_MAP}" || [[ ! -s "${INPUT_MAP}" ]]; then
  rm -f "${INPUT_MAP}"
  # Not there under the normal name -- check whether stage 1 actually ran but renamed it away because
  # the calibration was marked bad (same convention as the real production, see mapCreationJob.sh),
  # rather than assuming it just hasn't run yet.
  if alien.py cp -f "${STAGE1_OUTPUT_LOCATION}/badCalib_${STAGE1_OUTPUT_FILE}" "file:${INPUT_MAP}" 2>/dev/null && [[ -s "${INPUT_MAP}" ]]; then
    echo "Stage 1 marked this slot's calibration as bad (found badCalib_${STAGE1_OUTPUT_FILE} instead of ${STAGE1_OUTPUT_FILE}) -- skipping post-processing on purpose, not an error." >&2
  else
    echo "WARNING: stage-1 output '${STAGE1_OUTPUT_FILE}' not found at ${STAGE1_OUTPUT_LOCATION} -- this slot's map creation likely hasn't run yet or failed. Skipping (not an error) -- resubmit this subjob once stage 1 has produced it." >&2
  fi
  rm -f "${INPUT_MAP}"
  exit 0
fi

# --- [1/2] Gaussian smoothing + extrapolation ---
GAUSSMOOTH_ADD=""
[[ "${DO_GAUS_SMOOTH}" == "true" ]] && GAUSSMOOTH_ADD+=".GausSmooth"
[[ "${DO_EXTRAPOLATION}" -gt 0 ]] && GAUSSMOOTH_ADD+=".Extrapolation"
OUTPUT_MAP_SMOOTH="${OUTPUT_STEM}${GAUSSMOOTH_ADD}.root"

cmd="(time root.exe -b -q -l -x '${SMOOTHING_MACRO_PATH}+Og(\"${INPUT_MAP}\", \"${OUTPUT_MAP_SMOOTH}\", ${DO_GAUS_SMOOTH}, ${DO_EXTRAPOLATION}, ${A11_MAX_Z2X}, ${MASK_IA11})')"
echo "$(date) ${cmd}"
eval "${cmd}"

if [[ ! -s "${OUTPUT_MAP_SMOOTH}" ]]; then
  echo "ERROR: ${OUTPUT_MAP_SMOOTH} was not produced -- SmoothingExtrapolate.C failed" >&2
  exit 1
fi

# --- Resolve this job's own JDL-assigned output directory (per ALICE Grid support -- see
# mapCreationJob.sh for the full reasoning: production data belongs in ${ALIEN_JDL_OUTPUTDIR},
# not a personal-space path). ALIEN_JDL_OUTPUTDIR is JAliEn's own per-JDL-field env var; fall back to
# ALIEN_JOB_OUTPUTDIR (grid_submit.sh's equivalent, computed from the same JDL field).
ALIEN_OUTPUT_DIR="alien://${ALIEN_JDL_OUTPUTDIR:-${ALIEN_JOB_OUTPUTDIR:-}}"
if [[ "${ALIEN_OUTPUT_DIR}" == "alien://" ]]; then
  echo "ERROR: neither ALIEN_JDL_OUTPUTDIR nor ALIEN_JOB_OUTPUTDIR is set -- don't know where to stage this slot's output" >&2
  exit 1
fi

# Stage the smoothed map NOW, before the QA and FastTransform steps rather than after them. Those steps
# can fail hard on input this script cannot control -- notably TPCFastTransformInitCPM.C's
# LOGP(fatal, "meanCTP ... not set!"), which fires for any slot whose stage-1 map carries meanCTP=0 in
# its UserInfo (useCTPLumi=2 exempts meanIDC from that check, but NOT meanCTP). Staging last meant such
# a slot lost its perfectly good smoothed map as well, forcing a resubmit to redo the smoothing.
if ! alien.py cp -f "file:${OUTPUT_MAP_SMOOTH}" "${ALIEN_OUTPUT_DIR}/${OUTPUT_MAP_SMOOTH}"; then
  echo "ERROR: failed to stage ${OUTPUT_MAP_SMOOTH} to ${ALIEN_OUTPUT_DIR}" >&2
  exit 1
fi
echo "Staged ${OUTPUT_MAP_SMOOTH} to ${ALIEN_OUTPUT_DIR}"

# --- Provenance pointer: unlike stage 1 -> stage 2 (which has the stage1Workdir.<tag>.txt pointer),
# stage 2's own output directory otherwise carries no trace of which exact stage-1 output it was built
# from. Record it as a one-line pointer, same idea, staged right alongside the smoothed map.
STAGE1_SOURCE_FILE="stage1Source.txt"
echo "${STAGE1_OUTPUT_LOCATION}/${STAGE1_OUTPUT_FILE}" > "${STAGE1_SOURCE_FILE}"
if ! alien.py cp -f "file:${STAGE1_SOURCE_FILE}" "${ALIEN_OUTPUT_DIR}/${STAGE1_SOURCE_FILE}"; then
  echo "WARNING: failed to stage ${STAGE1_SOURCE_FILE} -- provenance pointer only, not fatal" >&2
fi
# Remove the local copy now that it's staged: it matches the #JDL_OUTPUT *.txt glob above, and the
# JobAgent's own passive upload of that glob (run after this script exits) does a plain, non-forced
# cp -- it would otherwise collide with the LFN this explicit -f upload just created and put the
# whole subjob into ERROR_SV, even though the actual deliverable upload above succeeded.
rm -f "${STAGE1_SOURCE_FILE}"

# --- QA plots (voxResQA.C) -- runs on just this one slot's smoothed map, same per-slot granularity as
# everything else in this pipeline. Non-fatal on failure: QA is a diagnostic nice-to-have, not a blocking
# deliverable like the smoothed map/FastTransform output -- a QA hiccup shouldn't fail an otherwise-good
# slot.
QA_SUFFIX=".${OUTPUT_STEM}${GAUSSMOOTH_ADD}"
cmd="(time root.exe -b -q -l -x '${QA_MACRO_PATH}+Og(\"ls ${OUTPUT_MAP_SMOOTH}\", \"${QA_SUFFIX}\", ${QA_DRAW_ERRORS}, ${QA_USE_SMOOTHED}, ${QA_Z2X_BIN_SEL})')"
echo "$(date) ${cmd}"
eval "${cmd}" || echo "WARNING: voxResQA.C failed for this slot -- QA plots will be missing, but this doesn't affect ${OUTPUT_MAP_SMOOTH} itself" >&2

QA_FILE_1D="voxResQA${QA_SUFFIX}_1D.root"
QA_FILE_2D="voxResQA${QA_SUFFIX}_2D.root"

# --- [2/2] Final O2 FastTransform ---
OUTPUT_FT="FT_${OUTPUT_MAP_SMOOTH}"

cmd="(time root.exe -b -q -l -x '${FASTTRANSFORM_MACRO_PATH}+Og(\"${OUTPUT_MAP_SMOOTH}\", \"${OUTPUT_FT}\", ${USE_SMOOTHED}, ${USE_CTP_LUMI})')"
echo "$(date) ${cmd}"
eval "${cmd}"

if [[ ! -s "${OUTPUT_FT}" ]]; then
  echo "ERROR: ${OUTPUT_FT} was not produced -- TPCFastTransformInitCPM.C failed" >&2
  exit 1
fi

# --- Stage the FastTransform output to this job's own JDL-assigned output directory (the smoothed map
# was already staged above, right after it was produced). Explicit, synchronous cp rather than relying on
# the passive #JDL_OUTPUT@disk=N auto-upload, which only happens during the job's asynchronous SAVING
# phase after this script exits.
if ! alien.py cp -f "file:${OUTPUT_FT}" "${ALIEN_OUTPUT_DIR}/${OUTPUT_FT}"; then
  echo "ERROR: failed to stage ${OUTPUT_FT} to ${ALIEN_OUTPUT_DIR}" >&2
  exit 1
fi
echo "Staged ${OUTPUT_FT} to ${ALIEN_OUTPUT_DIR}"

# QA plots -- non-fatal staging, same reasoning as the non-fatal QA run itself above: if voxResQA.C
# failed or produced nothing, there's nothing to stage, and that shouldn't fail this otherwise-good slot.
for qaFile in "${QA_FILE_1D}" "${QA_FILE_2D}"; do
  if [[ -s "${qaFile}" ]]; then
    alien.py cp -f "file:${qaFile}" "${ALIEN_OUTPUT_DIR}/${qaFile}" || \
      echo "WARNING: failed to stage ${qaFile} -- non-fatal, just loses this slot's QA plots" >&2
  else
    echo "WARNING: ${qaFile} was not produced -- voxResQA.C likely failed above, skipping its staging" >&2
  fi
done

# TPCFastTransformInitCPM.C's own debug/summary trees (produced unconditionally alongside OUTPUT_FT,
# named after its stem -- see createFastTransform() in that macro) were never staged anywhere: the
# #JDL_OUTPUT pattern above only matches *.log/*.txt/*.png (no *.root), and the explicit staging block
# above only names OUTPUT_MAP_SMOOTH/OUTPUT_FT -- so these were produced on the worker and then silently
# discarded when the job finished. Non-fatal staging, same reasoning as the QA plots: diagnostic, not a
# blocking deliverable.
OUTPUT_FT_DEBUG="${OUTPUT_FT%.root}.debug.root"
OUTPUT_FT_SUMMARY="${OUTPUT_FT%.root}.summary.root"
for ftDebugFile in "${OUTPUT_FT_DEBUG}" "${OUTPUT_FT_SUMMARY}"; do
  if [[ -s "${ftDebugFile}" ]]; then
    alien.py cp -f "file:${ftDebugFile}" "${ALIEN_OUTPUT_DIR}/${ftDebugFile}" || \
      echo "WARNING: failed to stage ${ftDebugFile} -- non-fatal, just loses this slot's FT debug/summary tree" >&2
  else
    echo "WARNING: ${ftDebugFile} was not produced -- skipping its staging" >&2
  fi
done

echo "Stage 2 complete: ${OUTPUT_MAP_SMOOTH}, ${OUTPUT_FT}"

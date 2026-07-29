#!/usr/bin/env bash
# mapCreationJob.sh — TPC space-charge map creation, one time slot per GRID job.
#
# This is STAGE 1 of a two-stage pipeline: runs staticMapCreatorCPM.C directly to produce the raw
# per-slot voxRes.*.it0.root -- the heavy step, hours per slot. Stages its output to this job's own
# JDL-assigned ${ALIEN_JDL_OUTPUTDIR} (see below) so STAGE 2 (postProcessJob.sh:
# SmoothingExtrapolate.C + TPCFastTransformInitCPM.C, minutes per slot) can find it independently and
# be resubmitted on its own if it fails, without re-running this stage. Everything further downstream
# (iteration chains beyond it0, finalize/QA) stays local for now -- deliberately out of scope here.
#
# Submitted via:
#   ${O2DPG_ROOT}/GRID/utils/grid_submit.sh --script mapCreationJob.sh \
#       --prodsplit <nSlots> --packagespec O2PDPSuite::<tag> ...
#
# --prodsplit gives every subjob nothing but a plain integer index
# (ALIEN_O2DPG_GRIDSUBMIT_SUBJOBID, exported by grid_submit.sh -- real GRID only). This script
# downloads the mapSlots.<JOBNAME_TAG>.tsv manifest that stageSlotsForGrid.py uploaded (one line
# per slot: "<run>\t<comma-separated alien:// o2tpc_residuals_*.root paths>") -- tagged by JOBNAME_TAG
# so a different-named submission's manifest doesn't overwrite this one's (see JOBNAME_TAG below) --
# picks its own line by index, and reconstructs a local slot-list file. --prodsplit is used instead of
# --split-on-collection: the latter needs one already-registered AliEn catalog file per split unit
# (N slow alien.py round trips, N tiny objects cluttering one AliEn directory), while a single manifest
# upload avoids both.
#
# Slot windowing: this script does NO time arithmetic. stageSlotsForGrid.py decides the windows at
# submission time (from SLOT_LENGTH_MIN) and writes one manifest line per window, carrying the window's
# bounds and exactly the files that can contribute to it. Stage 2 reads the same line, so the two
# stages cannot disagree about a slot's identity -- they used to each recompute it from
# TIME_DIVISION/TIME_DIVISION_INDEX, and any mismatch silently produced zero output.
#
# JOBNAME_TAG: tags the slot manifest name (mapSlots.<JOBNAME_TAG>.tsv) so a different-named submission's
# manifest doesn't silently overwrite this one's. Substituted from the wrapper's own JOBNAME.
#
# MACRO_SOURCE: "official" (default) runs the macro straight from the O2 package already loaded by this
# job's --packagespec ($O2_ROOT/share/macro/staticMapCreatorCPM.C -- the same idiom
# DATA/production/configurations/asyncCalib/createCorrectionMap.sh already uses for staticMapCreator.C),
# no staging/download needed. Requires a packagespec built from an O2 tag that includes
# staticMapCreatorCPM.C (Detectors/TPC/calibration/SpacePoints/macro/) -- until such a tag is published,
# use MACRO_SOURCE=alien instead, which downloads a copy staged ahead of time under MACRO_ALIEN_DIR (see
# submitMapCreation.sh's MACRO_LOCAL_PATH).
#
# MACRO_ALIEN_DIR_BARE: same placeholder mechanism, substituted from the wrapper's own
# MACRO_ALIEN_DIR_BARE -- if you change that in submitMapCreation.sh (e.g. to point at a
# different AliEn user/directory), it now propagates here automatically instead of needing a second,
# easy-to-forget manual edit of this file. Used for the bad-time-ranges list and the slot manifest
# regardless of MACRO_SOURCE; only used for the macro itself when MACRO_SOURCE=alien.
JOBNAME_TAG=default
MACRO_SOURCE=official
MACRO_ALIEN_DIR_BARE=${MACRO_ALIEN_DIR_BARE:-}
#
# BAD_RANGES_NAME: filename of the bad-time-ranges list to pull from ${MACRO_ALIEN_DIR}/lists/. Same
# placeholder mechanism -- substituted from the wrapper's own BAD_RANGES_NAME, which is also what the
# wrapper uploads to when BAD_RANGES_LOCAL is set, so the uploaded name and the downloaded name are the
# same value by construction. The list is period/system-specific (the default below is PbPb26), so
# expect to change it in the wrapper when the data changes -- not here. Empty ("") is a supported value
# meaning "skip bad-ranges filtering entirely for this submission" -- see BAD_RANGES_ARG below.
BAD_RANGES_NAME=${BAD_RANGES_NAME:-Merge_BadIntervals_LHC26_PbPb_DCA-0P300.txt}
#JDL_OUTPUT=*.log@disk=1,*.txt@disk=1,*.info@disk=1
#JDL_REQUIRE={member(other.GridPartitions,"multicore_8") && (other.CE != "ALICE::NIHAM::PBS64") && (other.CE != "ALICE::KISTI_GSDC::LCG") && (other.CE != "ALICE::SaoPaulo::LCG")};
# Site blacklist: these three CEs excluded from this pipeline's jobs. Setting #JDL_REQUIRE overrides
# grid_submit.sh's own default Requirements entirely (it's read verbatim, not merged -- see
# grid_submit.sh's REQUIRESPEC handling), so the multicore_8 GridPartitions clause is repeated here
# rather than dropped.
# voxRes.*.root deliberately NOT in this pattern -- it's staged explicitly, once, via the synchronous
# alien.py cp below (to a fixed, predictable location stage 2 can find). Having it ALSO match here would
# make the automatic per-job upload duplicate the same (100+ MB) file a second time, to the ephemeral
# per-job dir, for no benefit now that the fixed-location copy is the reliable one. See "Two-stage
# pipeline" in README.md.

set -e

# xrootd client tuning -- retry/timeout behavior for alien://xrootd reads. Set before any AliEn
# transfer below (both our own alien.py cp calls and the macro's own residual-file reads go through
# this same client). Without it, a stalled read can hang until AliEn's own watchdog kills the payload
# for staying below its CPU-usage threshold too long (TJAlienFile "Operation expired").
#
# CONNECTIONRETRY=2, CONNECTIONWINDOW=30: patiently retrying a sick storage server for many minutes is
# fine on a machine you own, but fatal on the GRID -- AliEn's job agent kills any payload whose CPU
# stays below threshold for 15 minutes, and a stalled bulk read burns that budget at ~0% CPU. A higher
# CONNECTIONRETRY would allow correspondingly longer silent reconnection per request before an error is
# ever raised; at 2 x 30s the worst case is 60 s, so the macro's own "could not load entry -> skip file"
# path (which handles a FAILED read perfectly well -- the problem is only ever that xrootd does not
# fail, it waits) gets a chance to run before the watchdog does.
#
# Note this is a mitigation, not a guarantee: none of these knobs bound a transfer that is trickling
# rather than dead, since each sub-request completes before its own timeout while the overall read
# crawls. That case is caught earlier instead, by the unhealthy-replica open-time gate in
# staticMapCreatorCPM.C (SCDCALIB_MAX_FILE_OPEN_SEC).
export XRD_TIMEOUTRESOLUTION=15
export XRD_CONNECTIONWINDOW=30
export XRD_CONNECTIONRETRY=2
export XRD_REQUESTTIMEOUT=120
export XRD_STREAMTIMEOUT=120
export XRD_STREAMERRORWINDOW=0

# --- AliEn path holding the bad-time-ranges list / mapSlots.tsv (and staticMapCreatorCPM.C too, when
# MACRO_SOURCE=alien). grid_submit.sh only ships this one script; everything else is staged here once
# and pulled down per job.
#
# Normally substituted above by submitMapCreation.sh (which derives it from your AliEn
# account), so it is empty only when this script is run by hand -- in which case say so explicitly
# rather than building "alien:///mapSlots...tsv" and failing later with a confusing catalog error.
: "${MACRO_ALIEN_DIR_BARE:?MACRO_ALIEN_DIR_BARE is empty -- the submission wrapper normally substitutes it. For a standalone/local run, export it first, e.g. MACRO_ALIEN_DIR_BARE=/alice/cern.ch/user/<initial>/<user>/MapCreation}"
MACRO_ALIEN_DIR="alien://${MACRO_ALIEN_DIR_BARE}"

if [[ "${MACRO_SOURCE}" == "official" ]]; then
  : "${O2_ROOT:?O2_ROOT is not set -- MACRO_SOURCE=official needs the O2 package loaded via --packagespec}"
  MACRO_PATH="${O2_ROOT}/share/macro/staticMapCreatorCPM.C"
  if [[ ! -f "${MACRO_PATH}" ]]; then
    echo "ERROR: MACRO_SOURCE=official but ${MACRO_PATH} does not exist -- this job's --packagespec does not include staticMapCreatorCPM.C yet. Use MACRO_SOURCE=alien until a packagespec with it is published." >&2
    exit 1
  fi
else
  alien.py cp -f "${MACRO_ALIEN_DIR}/staticMapCreatorCPM.C" file:./staticMapCreatorCPM.C
  MACRO_PATH="./staticMapCreatorCPM.C"
fi
# BAD_RANGES_NAME="" is a deliberate, supported value -- see the wrapper's own comment on it -- meaning
# "skip bad-ranges filtering entirely" (staticMapCreatorCPM.C treats an empty badRangeList argument that
# way, see its `if (badRangeList.length() > 0)` guard). BAD_RANGES_ARG is what actually gets passed to
# the macro below; empty there, not "badRanges.dat", is what selects that mode.
BAD_RANGES_ARG=""
if [[ -n "${BAD_RANGES_NAME}" ]]; then
  alien.py cp -f "${MACRO_ALIEN_DIR}/lists/${BAD_RANGES_NAME}" file:./badRanges.dat
  BAD_RANGES_ARG="badRanges.dat"
fi
alien.py cp -f "${MACRO_ALIEN_DIR}/mapSlots.${JOBNAME_TAG}.tsv" file:./mapSlots.tsv

# --- Determine this subjob's index into mapSlots.tsv ---
# ALIEN_O2DPG_GRIDSUBMIT_SUBJOBID is set by grid_submit.sh on the real GRID (--prodsplit mode) before
# it runs this script. For --local testing without it, pass SUBJOBID explicitly, e.g.:
#   SUBJOBID=3 grid_submit.sh --local ...
SUBJOBID="${ALIEN_O2DPG_GRIDSUBMIT_SUBJOBID:-${SUBJOBID:-}}"
: "${SUBJOBID:?SUBJOBID must be set (via ALIEN_O2DPG_GRIDSUBMIT_SUBJOBID on GRID, or the SUBJOBID env var for --local testing)}"

LINE=$(sed -n "${SUBJOBID}p" mapSlots.tsv)
if [[ -z "${LINE}" ]]; then
  echo "ERROR: mapSlots.tsv has no line ${SUBJOBID}" >&2
  exit 1
fi

# Manifest line: <run> \t <winIdx> \t <winCount> \t <winFirstTS> \t <winLastTS> \t <comma-separated paths>
# The window bounds and the file selection are decided once, at submission time, by
# stageSlotsForGrid.py -- this script does no time arithmetic of its own. That is deliberate: stage 2
# reads the SAME manifest line, so the two stages cannot disagree about a slot's identity (they
# previously each recomputed it and a mismatch silently produced zero output).
IFS=$'\t' read -r RUN WIN_IDX WIN_COUNT firstTSIter lastTSIter PATHS <<< "${LINE}"
for v in RUN WIN_IDX WIN_COUNT firstTSIter lastTSIter; do
  if [[ ! "${!v}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: manifest line ${SUBJOBID} field ${v}='${!v}' is not numeric -- expected 6 tab-separated fields <run> <winIdx> <winCount> <winFirstTS> <winLastTS> <paths>" >&2
    exit 1
  fi
done
[[ -n "${PATHS}" ]] || { echo "ERROR: manifest line ${SUBJOBID} carries no file paths" >&2; exit 1; }

SLOT_LIST="slotlist_${SUBJOBID}.txt"
tr ',' '\n' <<< "${PATHS}" > "${SLOT_LIST}"
nSlotFiles=$(wc -l < "${SLOT_LIST}" | tr -d '[:space:]')   # tr: wc right-justifies its count
echo "Processing slot ${SUBJOBID}: run ${RUN}, window ${WIN_IDX}/${WIN_COUNT} [${firstTSIter},${lastTSIter}] ($(( (lastTSIter - firstTSIter) / 1000 ))s), ${nSlotFiles} file(s)"

# --- Process the files in the order that reaches this window's data soonest ---
# WHY: the macro's per-file skip still has to OPEN every out-of-window file to read its records tree --
# ~7 s each over alien://, at ~zero CPU -- and AliEn's job agent kills any payload whose CPU stays
# below threshold for 15 minutes (observed for real, run 572246: 47 files skipped in 6 min, killed
# before reaching in-window data).
#
# stageSlotsForGrid.py already dropped every file whose aggregation label cannot overlap this window,
# but that filter can only be as sharp as the labels are. A coarse label produced by the aggregator
# merging an underpopulated slot forward can span several windows, so overlapping this window by as
# little as 1 ms pulls in all of its files. Ordering fixes what filtering cannot: each file's CTF
# directory carries an _orbit<N> field, which IS that file's true position in time, so we sort by
# distance from this window's centre. The files that can actually contribute are opened first and
# maxTracksPerSlice usually stops the job before it ever reaches the far ones.
#
# Only the ORDER depends on this, never which files are considered, so the orbit->time estimate below
# is allowed to be approximate: it is interpolated from the list's own extremes.
if awk -F'_orbit' 'NF < 2 {exit 1}' "${SLOT_LIST}"; then
  awk -F'_orbit' -v lo="${firstTSIter}" -v hi="${lastTSIter}" '
    {
      line[NR] = $0
      # orbit from the CTF directory name
      split($2, o, "_"); orb[NR] = o[1] + 0
      # Time anchor: the EXTREMES of the aggregation labels present, not their midpoints. In nearly
      # every window all files carry a single label (one aggregator slot spans several windows), and
      # identical midpoints collapse the interpolation to frac=0 -- which sorts ascending no matter
      # where the window actually sits, the exact order that gets a late window killed by the CPU
      # watchdog. Extremes stay meaningful with one label: [labelFirst,labelLast] maps onto
      # [oMin,oMax].
      if (match($0, /o2tpc_residuals_[0-9]{13}_[0-9]{13}_/)) {
        split(substr($0, RSTART + 16, 27), t, "_")
        if (!seen || (t[1] + 0) < mMin) mMin = t[1] + 0
        if (!seen || (t[2] + 0) > mMax) mMax = t[2] + 0
        seen = 1
      }
      if (n == 0 || orb[NR] < oMin) oMin = orb[NR]
      if (n == 0 || orb[NR] > oMax) oMax = orb[NR]
      n = NR
    }
    END {
      centre = (lo + hi) / 2
      # map the window centre onto the orbit axis using this list own extremes
      frac = (seen && mMax > mMin) ? (centre - mMin) / (mMax - mMin) : 0
      if (frac < 0) frac = 0
      if (frac > 1) frac = 1
      target = oMin + frac * (oMax - oMin)
      for (i = 1; i <= n; i++) {
        d = orb[i] - target; if (d < 0) d = -d
        printf "%d\t%s\n", d, line[i]
      }
    }' "${SLOT_LIST}" \
    | sort -n -k1,1 | cut -f2- > "${SLOT_LIST}.ord"
  if [[ -s "${SLOT_LIST}.ord" ]]; then
    mv "${SLOT_LIST}.ord" "${SLOT_LIST}"
    echo "File order: sorted by orbit distance from the window centre (closest first)"
  else
    rm -f "${SLOT_LIST}.ord"
    echo "WARNING: could not order ${SLOT_LIST} by orbit -- leaving the file order untouched" >&2
  fi
else
  # No _orbit field in at least one path -- cannot establish a time order, so leave the list alone
  # rather than reorder it on a key that is not there. Costs the optimization, never correctness.
  echo "WARNING: not every path in ${SLOT_LIST} carries an _orbit<N> field -- leaving the file order untouched (no time-ordering possible)" >&2
fi

# --- Config (production values; createSpline is the one deliberate exception, see CREATE_SPLINE
# below: TPCFastTransformInitCPM.C runs separately in stage 2 here instead) ---
# NOTE: nScalerRanges/useScalerRange/useCTPLumi are gone from the macro's signature. It no longer reads
# IDC scalers from CCDB at all; the values are joined in offline by SmoothingExtrapolate.C in stage 2.
Z2XBINNING="28"
Y2XBINNING="20"
USE_SMOOTHED=2
CREATE_SPLINE=false                 # TPCFastTransformInitCPM.C runs in stage 2 instead; leave false here
MAX_TRACKS_PER_SLICE=10000
MIN_TRACKS_PER_SLICE=3000
MAX_DEDX=-1
MAX_DEDX_EXP=-1
MAX_DEV_DEDX_OVER_EXP=-1
SKIP_EDGE_PADS=1
BAD_RANGE_SELECTION="ALL"
MAX_Z2X_CUT=1.4                     # SpacePointsCalibConfParam scdcalib.maxZ2X override -- real
                                     # production value, vs. the struct's own compiled-in default of 1.0
MAX_TRACK_WORKERS=8                 # matches the JDL's CPUCores/multicore_8 allocation (grid_submit.sh's
                                     # default) -- hardware_concurrency() does NOT reliably reflect the
                                     # real GRID allocation (confirmed 2026-07-25: auto-detected 32 on an
                                     # 8-core job, 4x oversubscription), so pass the known real value.

OUTPUT_STEM="voxRes.${RUN}_${firstTSIter}_${lastTSIter}.TD${WIN_IDX}of${WIN_COUNT}.it0"
OUTPUT_FILE="${OUTPUT_STEM}.root"

export alien_CLOSE_SE="ALICE::CERN::EOS"
cmd="(time root.exe -b -q -l -x '${MACRO_PATH}+O(\"${SLOT_LIST}\", ${RUN}, \"${OUTPUT_FILE}\", \"\", \"ITS-TPC\", \"${Z2XBINNING}\", \"${Y2XBINNING}\", ${USE_SMOOTHED}, ${CREATE_SPLINE}, ${MAX_TRACKS_PER_SLICE}, ${MIN_TRACKS_PER_SLICE}, \"${BAD_RANGES_ARG}\", ${firstTSIter}, ${lastTSIter}, ${MAX_DEDX}, ${MAX_DEDX_EXP}, ${MAX_DEV_DEDX_OVER_EXP}, ${SKIP_EDGE_PADS}, \"${BAD_RANGE_SELECTION}\", ${MAX_Z2X_CUT}, ${MAX_TRACK_WORKERS})')"
echo "$(date) ${cmd}"
eval "${cmd}"

if [[ ! -s "${OUTPUT_FILE}" ]]; then
  echo "ERROR: ${OUTPUT_FILE} was not produced -- this slot's map creation failed" >&2
  exit 1
fi

# Bad-calib handling: the macro creates an extensionless badCalib.<stem> marker file when
# minTracksPerSlice wasn't reached. Stage under a badCalib_-prefixed
# name instead of the normal one -- stage 2, looking for the normal (unprefixed) name, simply won't
# find it and will hit the same graceful-skip path already used for "stage 1 hasn't produced this yet",
# with no extra logic needed there. The marker file itself has no extension and matches none of our
# JDL output patterns, so it doesn't survive on its own -- this rename is what actually carries the
# bad-calib status forward.
STAGE_NAME="${OUTPUT_FILE}"
if [[ -f "badCalib.${OUTPUT_STEM}" ]]; then
  STAGE_NAME="badCalib_${OUTPUT_FILE}"
  echo "Calibration marked bad for this slot (found badCalib.${OUTPUT_STEM}) -- staging as ${STAGE_NAME} instead of ${OUTPUT_FILE}"
fi

# --- Two-stage pipeline: stage the produced map to THIS job's own JDL-assigned output directory
# (per ALICE Grid support -- do not write production data to a personal-space path; that needs its own
# disk-quota request on top of the CPU one, unlike ${ALIEN_JDL_OUTPUTDIR}, which is already covered by
# however this job's quota/ownership is set up). ALIEN_JDL_OUTPUTDIR is JAliEn's own per-JDL-field env
# var (case-sensitive, same convention as ALIEN_JDL_CPUCORES etc.); fall back to ALIEN_JOB_OUTPUTDIR
# (grid_submit.sh's own equivalent, computed the same way from the same JDL field -- see that script) in
# case the former isn't exported in some execution context. Explicit, synchronous cp rather than relying
# on the passive #JDL_OUTPUT@disk=N auto-upload -- that only happens during the job's asynchronous
# SAVING phase after this script exits, which can take minutes and would race against a later reader
# (stage 2 doesn't try to read this immediately, but no reason to introduce that fragility when an
# explicit cp is just as easy and finishes before this script does).
#
# NOTE: this directory is only known once the job actually runs -- see
# submitMapCreation.sh for how the post-processing stage (postProcessJob.sh,
# SmoothingExtrapolate.C + TPCFastTransformInitCPM.C) finds it later without needing an in-job breadcrumb.
ALIEN_OUTPUT_DIR="alien://${ALIEN_JDL_OUTPUTDIR:-${ALIEN_JOB_OUTPUTDIR:-}}"
if [[ "${ALIEN_OUTPUT_DIR}" == "alien://" ]]; then
  echo "ERROR: neither ALIEN_JDL_OUTPUTDIR nor ALIEN_JOB_OUTPUTDIR is set -- don't know where to stage ${OUTPUT_FILE}" >&2
  exit 1
fi
if ! alien.py cp -f "file:${OUTPUT_FILE}" "${ALIEN_OUTPUT_DIR}/${STAGE_NAME}"; then
  echo "ERROR: failed to stage ${OUTPUT_FILE} to ${ALIEN_OUTPUT_DIR} -- the post-processing stage won't be able to find this slot's map" >&2
  exit 1
fi
echo "Staged ${OUTPUT_FILE} to ${ALIEN_OUTPUT_DIR}/${STAGE_NAME}"

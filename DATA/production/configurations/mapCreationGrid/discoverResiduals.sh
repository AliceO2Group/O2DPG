#!/usr/bin/env bash
# discoverResiduals.sh
#
# Runs locally. For each run in a batch file, calls makeResidualLists.sh
# with --alien to query AliEn for o2tpc_residuals*.root files and build
# per-period residual lists under lists/<RUN>/.
#
# Runs are processed in parallel using GNU parallel.
#
# Usage:
#   ./discoverResiduals.sh <batch_file> [--calib-pass <pass>]
#   ./discoverResiduals.sh <batch_file> --mc [--mc-cycle <cycle>]
#
# --mc: the batch file lists MC productions instead of data periods. Field 1 is then the MC production
# tag and field 2 the anchor run, e.g. "LHC26j19_residuals 568336", and the search path becomes
# /alice/sim/<YEAR>/<prodTag>/<cycle>/<RUN>/ (cycle = --mc-cycle, default 0) instead of
# /alice/data/<YEAR>/<PERIOD>/<RUN>/<calib-pass>/ -- or rather its ResidualTPCmerging/Stage_0/ subdir,
# the production's merged residuals, whenever that holds any (see per_run). MC residual files carry no time label in their
# names, so makeResidualLists.sh writes them as one timeless list per run; submit those with
# MC_MODE=true in submitMapCreation.sh (stageSlotsForGrid.py --mc).
#
# Batch file format (one run per line, whitespace-separated):
#   <period_token> <run> [<fill> <startTimestampMs>]
#   e.g.:  LHC26ak 572557
#          LHC26ac.b5p 569945 11500 1773347865674
#
# The last two columns are OPTIONAL and only needed for hybrid map creation (pp: fine-length maps for
# the first part of a fill, coarse-length for the rest -- see submitMapCreation.sh's MAKE_HYBRID_MAPS).
# When given, both must be present together: <fill> is the LHC fill number (shared by every run in it,
# used to anchor the fine/coarse cutoff to the FILL's start rather than each run's own start -- a pp
# fill routinely spans several runs), <startTimestampMs> is that run's start-of-run (SOR) timestamp,
# UTC milliseconds (13 digits), same convention as the old SLURM-era makeStaggerd.py's metadata file.
# When present, per_run() writes them to <RUN_DIR>/<RUN>.fillinfo.txt, which
# stageSlotsForGrid.py --hybrid reads later, at submission time. Omit both columns for a
# non-hybrid production -- nothing downstream needs them then.
#
# PERIOD is derived from the first field by stripping from the first '.' onward
#   (e.g. LHC26ab.b5p → LHC26ab — a trailing '.xyz' suffix is tolerated but not
#   required).
# YEAR is derived from the two-digit year in the period token
#   (e.g. LHC26ab → 2026).
#
# Dependencies: alien.py, parallel, makeResidualLists.sh

set -euo pipefail

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
BATCH_FILE=""
CALIB_PASS="cpass2_residuals"
CALIB_PASS_SET=0
MC_MODE=0
MC_CYCLE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --calib-pass)
            [[ $# -lt 2 ]] && { echo "ERROR: --calib-pass requires an argument"; exit 1; }
            CALIB_PASS="$2"; CALIB_PASS_SET=1; shift 2 ;;
        --mc)
            MC_MODE=1; shift ;;
        --mc-cycle)
            [[ $# -lt 2 ]] && { echo "ERROR: --mc-cycle requires an argument"; exit 1; }
            MC_CYCLE="$2"; shift 2 ;;
        -*)
            echo "ERROR: Unknown option: $1"; exit 1 ;;
        *)
            [[ -n "${BATCH_FILE}" ]] && { echo "ERROR: unexpected extra argument: $1"; exit 1; }
            BATCH_FILE="$1"; shift ;;
    esac
done

[[ -z "${BATCH_FILE}" ]] && { echo "Usage: $0 <batch_file> [--calib-pass <pass>] | [--mc [--mc-cycle <cycle>]]"; exit 1; }
[[ -f "${BATCH_FILE}" ]] || { echo "ERROR: batch file not found: ${BATCH_FILE}"; exit 1; }
# The data and MC paths share no component after the year, so a flag of the other mode is a mistake,
# not something to ignore.
if (( MC_MODE )); then
    (( CALIB_PASS_SET )) && { echo "ERROR: --calib-pass is a data-only option, the MC path has no calib-pass level"; exit 1; }
    MC_CYCLE="${MC_CYCLE:-0}"
    [[ "${MC_CYCLE}" =~ ^[0-9]+$ ]] || { echo "ERROR: --mc-cycle must be numeric, got '${MC_CYCLE}'"; exit 1; }
else
    [[ -n "${MC_CYCLE}" ]] && { echo "ERROR: --mc-cycle needs --mc"; exit 1; }
    # Never used in data mode, but per_run takes it positionally and GNU parallel would drop an empty word.
    MC_CYCLE="0"
fi

# ---------------------------------------------------------------------------
# Parse the batch file into one "<period_token> <run>" entry per line
# ---------------------------------------------------------------------------
# The period is resolved PER LINE, not once from the first line: the batch format carries a period
# token on every row, so a batch legitimately spanning two periods must not silently inherit the
# first row's period for all of its runs (that produced a valid-looking /alice/data/<year>/<wrong
# period>/<run>/ query, which just finds nothing and degrades into a per-run warning).
mapfile -t ENTRIES < <(awk 'NF > 0 && !/^[[:space:]]*#/ {print $1, $2, $3, $4}' "${BATCH_FILE}")
[[ ${#ENTRIES[@]} -gt 0 ]] || { echo "ERROR: no runs found in ${BATCH_FILE}"; exit 1; }

# Validate every entry up front -- a malformed row should stop the batch here, not surface as one
# failed run out of fifty after the parallel fan-out has already started.
RUNS=()
PERIODS_SEEN=()
for entry in "${ENTRIES[@]}"; do
    read -r _tok _run _fill _sor <<< "${entry}"
    [[ -n "${_tok}" && -n "${_run}" ]] \
        || { echo "ERROR: malformed line in ${BATCH_FILE} (need '<period_token> <run> [<fill> <startTimestampMs>]'): '${entry}'"; exit 1; }
    [[ "${_run}" =~ ^[0-9]+$ ]] \
        || { echo "ERROR: run number is not numeric in ${BATCH_FILE}: '${entry}'"; exit 1; }
    # Field 1 example: LHC26ab.b5p  →  PERIOD=LHC26ab, YEAR=2026
    [[ "${_tok%%.*}" =~ LHC([0-9]{2}) ]] \
        || { echo "ERROR: cannot extract year from period token '${_tok}' (line: '${entry}')"; exit 1; }
    # fill/startTimestampMs are optional, but only as a pair -- stageSlotsForGrid.py --hybrid needs
    # both or neither, so one without the other is a malformed row, not a partially-specified one.
    if [[ -n "${_fill}" || -n "${_sor}" ]]; then
        [[ -n "${_fill}" && -n "${_sor}" ]] \
            || { echo "ERROR: fill and startTimestampMs must both be given or both omitted in ${BATCH_FILE}: '${entry}'"; exit 1; }
        [[ "${_fill}" =~ ^[0-9]+$ ]] \
            || { echo "ERROR: fill number is not numeric in ${BATCH_FILE}: '${entry}'"; exit 1; }
        [[ "${_sor}" =~ ^[0-9]{13}$ ]] \
            || { echo "ERROR: startTimestampMs must be a 13-digit UTC-ms timestamp in ${BATCH_FILE}: '${entry}'"; exit 1; }
    fi
    RUNS+=("${_run}")
    PERIODS_SEEN+=("${_tok%%.*}")
done

mapfile -t PERIODS_UNIQ < <(printf '%s\n' "${PERIODS_SEEN[@]}" | sort -u)

# ---------------------------------------------------------------------------
# Fixed configuration
# ---------------------------------------------------------------------------
# Maximum number of runs to process in parallel (0 = one per CPU core)
N_PARALLEL=8

# Root of the output tree (relative or absolute)
WORK_DIR="./lists"

# Directory containing this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Path to makeResidualLists.sh (co-located here)
MAKE_LISTS_SCRIPT="${SCRIPT_DIR}/makeResidualLists.sh"

# ---------------------------------------------------------------------------

echo "Batch file  : ${BATCH_FILE}"
if (( MC_MODE )); then
    echo "MC prod(s)  : ${PERIODS_UNIQ[*]}"
    echo "MC cycle    : ${MC_CYCLE}"
else
    echo "Period(s)   : ${PERIODS_UNIQ[*]}"
    echo "Calib pass  : ${CALIB_PASS}"
fi
echo "Runs (${#RUNS[@]}): ${RUNS[*]}"
echo

mkdir -p "${WORK_DIR}"

# ---------------------------------------------------------------------------
# per_run — all work for a single run, called by parallel
#
# On success writes <RUN_DIR>/run_completed.txt containing the absolute
# path of RUN_DIR so the parent shell can collect completed runs after
# parallel finishes.
# ---------------------------------------------------------------------------
per_run() {
    local PERIOD_TOKEN="$1"           # field 1 of this batch-file row
    local RUN="$2"                    # field 2 of this batch-file row
    local CALIB_PASS="$3"
    local WORK_DIR="$4"
    local MAKE_LISTS_SCRIPT="$5"
    local MC_MODE="$6"                # 1: field 1 is an MC production tag, search /alice/sim
    local MC_CYCLE="$7"               # MC production cycle (path level after the tag), unused for data
    local FILL="$8"                   # field 3 of this batch-file row, empty if omitted
    local SOR="$9"                    # field 4 of this batch-file row, empty if omitted

    # Period/year come from THIS row, so a multi-period batch resolves each run against its own period.
    # Already validated in the caller's pre-flight loop, so a parse failure here would be a bug.
    local PERIOD YEAR
    PERIOD="${PERIOD_TOKEN%%.*}"      # strip suffix after first '.'
    [[ "${PERIOD}" =~ LHC([0-9]{2}) ]]
    YEAR="20${BASH_REMATCH[1]}"

    local RUN_DIR="${WORK_DIR}/${RUN}"
    mkdir -p "${RUN_DIR}"

    # Only for hybrid map creation (stageSlotsForGrid.py --hybrid reads this later); a non-hybrid batch
    # file omits fill/SOR and no sidecar is written -- nothing downstream needs one then.
    if [[ -n "${FILL}" && -n "${SOR}" ]]; then
        printf '%s\t%s\n' "${FILL}" "${SOR}" > "${RUN_DIR}/${RUN}.fillinfo.txt"
    fi

    local ALIEN_PATH="/alice/data/${YEAR}/${PERIOD}/${RUN}/${CALIB_PASS}/"
    if (( MC_MODE )); then
        ALIEN_PATH="/alice/sim/${YEAR}/${PERIOD}/${MC_CYCLE}/${RUN}/"
    fi

    echo "========================================"
    echo "Processing run ${RUN} (period ${PERIOD}, year ${YEAR})"
    echo "========================================"

    # MC productions merge their per-job residuals into ResidualTPCmerging/Stage_0/<NNN>/o2tpc_residuals.root
    # (~150 jobs per file, same trees). Read those when present: the recursive search over the run dir
    # would otherwise list every residual twice (per-job + merged), and each alien:// open costs ~7 s,
    # so ~40 merged files instead of thousands of per-job ones. A merge job that failed or is still
    # running leaves its Stage_0/<NNN>/ without the file, and its share of the statistics is then
    # missing -- warned about, not fatal. Without any merged file, fall back to the per-job files (the
    # recursive search then cannot pick up merged ones, there are none).
    if (( MC_MODE )); then
        local MERGED_PATH="${ALIEN_PATH}ResidualTPCmerging/Stage_0/"
        local nMerged nMergeJobs
        # grep on the file name, not just non-empty lines: alien.py prints its "Not a directory" error
        # for a missing path as a line too.
        nMerged=$(alien.py find "${MERGED_PATH}" "o2tpc_residuals*.root" 2>/dev/null | grep -c 'o2tpc_residuals[^/]*\.root$' || true)
        if (( nMerged > 0 )); then
            nMergeJobs=$(alien.py ls "${MERGED_PATH}" 2>/dev/null | grep -c '/$' || true)
            echo "  [${RUN}] Using merged residuals: ${nMerged} file(s) in ${nMergeJobs} merge job dir(s) under ${MERGED_PATH}"
            if (( nMerged < nMergeJobs )); then
                echo "  [${RUN}] WARNING: only ${nMerged}/${nMergeJobs} merge jobs produced o2tpc_residuals.root (failed or still running) -- this run's map misses that share of the statistics."
            fi
            ALIEN_PATH="${MERGED_PATH}"
        else
            echo "  [${RUN}] WARNING: no merged residuals under ${MERGED_PATH} -- falling back to the per-job files under ${ALIEN_PATH}"
        fi
    fi

    echo "  [${RUN}] Calling makeResidualLists.sh (alien path: ${ALIEN_PATH})..."
    (
        cd "${RUN_DIR}"
        run="${RUN}" "${MAKE_LISTS_SCRIPT}" --subdir "${CALIB_PASS}" --alien --alien-path "${ALIEN_PATH}"
    ) || {
        echo "  [${RUN}] WARNING: makeResidualLists.sh failed, skipping."
        return 0
    }

    echo "  [${RUN}] Done."

    # Signal success to the parent by writing the absolute run dir path
    realpath "${RUN_DIR}" > "${RUN_DIR}/run_completed.txt"
}

# Export everything parallel needs to call per_run in a subshell
export -f per_run

# ---------------------------------------------------------------------------
# Run all runs in parallel
# ---------------------------------------------------------------------------
echo "========================================"
echo "Launching ${#RUNS[@]} runs with N_PARALLEL=${N_PARALLEL}..."
echo "========================================"

# Fan out over the full "<period_token> <run> [<fill> <startTimestampMs>]" entries, not bare run
# numbers, so each job carries its own period (and fill/SOR, when given). --colsep splits each entry
# into {1}=period token, {2}=run, {3}=fill, {4}=SOR -- {3}/{4} come through as empty strings for a
# 2-column row (awk already padded ENTRIES to 4 fields, see above), which per_run treats as "no
# fillinfo sidecar for this run". --tagstring uses {2} to keep the log prefix to just the run number.
# shellcheck disable=SC1083  # {1}/{2}/{3}/{4} are GNU parallel replacement strings, not brace expansions
parallel \
    --jobs "${N_PARALLEL}" \
    --line-buffer \
    --colsep ' ' \
    --tagstring "[{2}]" \
    per_run {1} {2} "${CALIB_PASS}" "${WORK_DIR}" "${MAKE_LISTS_SCRIPT}" "${MC_MODE}" "${MC_CYCLE}" {3} {4} \
    ::: "${ENTRIES[@]}"

# ---------------------------------------------------------------------------
# Collect completed runs (sentinel files written by per_run on success)
# ---------------------------------------------------------------------------
COMPLETED_RUNS=()
for RUN in "${RUNS[@]}"; do
    SENTINEL="${WORK_DIR}/${RUN}/run_completed.txt"
    if [[ -f "${SENTINEL}" ]]; then
        COMPLETED_RUNS+=("$(cat "${SENTINEL}")")
        rm -f "${SENTINEL}"
    fi
done

echo "========================================"
echo "All runs processed. ${#COMPLETED_RUNS[@]}/${#RUNS[@]} succeeded."
echo "========================================"

if (( ${#COMPLETED_RUNS[@]} == 0 )); then
    echo "No runs completed successfully."
    exit 0
fi

# Sort for deterministic output order. Must come AFTER the empty check: expanding "${arr[@]}" on an
# empty array is an "unbound variable" error under `set -u` in bash <= 4.3.
IFS=$'\n' COMPLETED_RUNS=($(printf '%s\n' "${COMPLETED_RUNS[@]}" | sort))
unset IFS

echo "Per-run slot-file indexes (input for stageSlotsForGrid.py):"
for RUN_DIR in "${COMPLETED_RUNS[@]}"; do
    RUN="$(basename "${RUN_DIR}")"
    echo "  ${RUN_DIR}/${RUN}.residuals_lists.txt"
done

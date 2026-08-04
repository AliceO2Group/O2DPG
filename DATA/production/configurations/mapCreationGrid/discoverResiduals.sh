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
#
# Batch file format (one run per line, whitespace-separated):
#   <period_token> <run>
#   e.g.:  LHC26ak 572557
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

while [[ $# -gt 0 ]]; do
    case "$1" in
        --calib-pass)
            [[ $# -lt 2 ]] && { echo "ERROR: --calib-pass requires an argument"; exit 1; }
            CALIB_PASS="$2"; shift 2 ;;
        -*)
            echo "ERROR: Unknown option: $1"; exit 1 ;;
        *)
            [[ -n "${BATCH_FILE}" ]] && { echo "ERROR: unexpected extra argument: $1"; exit 1; }
            BATCH_FILE="$1"; shift ;;
    esac
done

[[ -z "${BATCH_FILE}" ]] && { echo "Usage: $0 <batch_file> [--calib-pass <pass>]"; exit 1; }
[[ -f "${BATCH_FILE}" ]] || { echo "ERROR: batch file not found: ${BATCH_FILE}"; exit 1; }

# ---------------------------------------------------------------------------
# Parse the batch file into one "<period_token> <run>" entry per line
# ---------------------------------------------------------------------------
# The period is resolved PER LINE, not once from the first line: the batch format carries a period
# token on every row, so a batch legitimately spanning two periods must not silently inherit the
# first row's period for all of its runs (that produced a valid-looking /alice/data/<year>/<wrong
# period>/<run>/ query, which just finds nothing and degrades into a per-run warning).
mapfile -t ENTRIES < <(awk 'NF > 0 && !/^[[:space:]]*#/ {print $1, $2}' "${BATCH_FILE}")
[[ ${#ENTRIES[@]} -gt 0 ]] || { echo "ERROR: no runs found in ${BATCH_FILE}"; exit 1; }

# Validate every entry up front -- a malformed row should stop the batch here, not surface as one
# failed run out of fifty after the parallel fan-out has already started.
RUNS=()
PERIODS_SEEN=()
for entry in "${ENTRIES[@]}"; do
    read -r _tok _run <<< "${entry}"
    [[ -n "${_tok}" && -n "${_run}" ]] \
        || { echo "ERROR: malformed line in ${BATCH_FILE} (need '<period_token> <run>'): '${entry}'"; exit 1; }
    [[ "${_run}" =~ ^[0-9]+$ ]] \
        || { echo "ERROR: run number is not numeric in ${BATCH_FILE}: '${entry}'"; exit 1; }
    # Field 1 example: LHC26ab.b5p  →  PERIOD=LHC26ab, YEAR=2026
    [[ "${_tok%%.*}" =~ LHC([0-9]{2}) ]] \
        || { echo "ERROR: cannot extract year from period token '${_tok}' (line: '${entry}')"; exit 1; }
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
echo "Period(s)   : ${PERIODS_UNIQ[*]}"
echo "Calib pass  : ${CALIB_PASS}"
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

    # Period/year come from THIS row, so a multi-period batch resolves each run against its own period.
    # Already validated in the caller's pre-flight loop, so a parse failure here would be a bug.
    local PERIOD YEAR
    PERIOD="${PERIOD_TOKEN%%.*}"      # strip suffix after first '.'
    [[ "${PERIOD}" =~ LHC([0-9]{2}) ]]
    YEAR="20${BASH_REMATCH[1]}"

    local RUN_DIR="${WORK_DIR}/${RUN}"
    mkdir -p "${RUN_DIR}"

    local ALIEN_PATH="/alice/data/${YEAR}/${PERIOD}/${RUN}/${CALIB_PASS}/"

    echo "========================================"
    echo "Processing run ${RUN} (period ${PERIOD}, year ${YEAR})"
    echo "========================================"

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

# Fan out over the full "<period_token> <run>" entries, not bare run numbers, so each job carries its
# own period. --colsep splits each entry into {1}=period token and {2}=run; note that under --colsep
# a bare {} means column 1 ONLY, so both columns must be passed explicitly. --tagstring uses {2} to
# keep the log prefix to just the run number.
# shellcheck disable=SC1083  # {1}/{2} are GNU parallel replacement strings, not brace expansions
parallel \
    --jobs "${N_PARALLEL}" \
    --line-buffer \
    --colsep ' ' \
    --tagstring "[{2}]" \
    per_run {1} {2} "${CALIB_PASS}" "${WORK_DIR}" "${MAKE_LISTS_SCRIPT}" \
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

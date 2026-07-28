#!/usr/bin/env bash
# makeResidualLists.sh
# Find o2tpc_residuals*.root files (local or alien) and split them into
# per-period lists plus a combined all-runs list.
#
# Single-run usage:
#   run=<run> ./makeResidualLists.sh [--subdir <name>] [--alien] [--dry-run]
#
# Multi-run usage (loops over all run directories automatically):
#   ./makeResidualLists.sh --all [--subdir <name>] [--alien] [--dry-run]
#
# Arguments:
#   --all             loop over all NNN*/ subdirs in the current directory
#   --subdir <name>   subdirectory within each run dir to search in (default: cpass1_residuals)
#   --alien           use alien.py instead of local find
#   --alien-path <p>  explicit AliEn directory to search (overrides --year/--period/--subdir)
#   --year <YYYY>     year component of the AliEn path (required with --alien unless --alien-path)
#   --period <LHCxxy> period component of the AliEn path (required with --alien unless --alien-path)
#   --dry-run         print what would be done without writing files
# In the normal chain you never pass --year/--period by hand: discoverResiduals.sh derives them per
# run from the batch file and passes a fully-formed --alien-path instead.
#
# Environment (single-run mode):
#   run : run number (optional; used in output filenames)

set -euo pipefail

# ── colours ───────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'


# Safe exit: use return when sourced, exit when run directly
_finish() { local code=${1:-0}; [[ "${BASH_SOURCE[0]}" != "${0}" ]] && return "$code" || exit "$code"; }
error() { echo -e "${RED}[ERROR]${RESET} $*" >&2; _finish 1; }
warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
info()  { echo -e "${CYAN}[INFO]${RESET}  $*"; }
ok()    { echo -e "${GREEN}[OK]${RESET}    $*"; }

# ── settings ──────────────────────────────────────────────────────────────────
: ${run:=""}
USE_ALIEN=0
DRY_RUN=0
ALL_MODE=0
SUBDIR="cpass1_residuals"
ALIEN_PATH_OVERRIDE=""
YEAR=""
PERIOD=""

# ── parse arguments ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --alien)    USE_ALIEN=1 ; shift ;;
        --dry-run)  DRY_RUN=1  ; shift ;;
        --all)      ALL_MODE=1 ; shift ;;
        --subdir)
            [[ $# -lt 2 ]] && error "--subdir requires an argument"
            SUBDIR="$2" ; shift 2 ;;
        --alien-path)
            [[ $# -lt 2 ]] && error "--alien-path requires an argument"
            ALIEN_PATH_OVERRIDE="$2" ; shift 2 ;;
        --year)
            [[ $# -lt 2 ]] && error "--year requires an argument"
            YEAR="$2" ; shift 2 ;;
        --period)
            [[ $# -lt 2 ]] && error "--period requires an argument"
            PERIOD="$2" ; shift 2 ;;
        *) error "Unknown argument: $1" ;;
    esac
done

# AliEn search path, e.g. /alice/data/2024/LHC24as/560334/cpass4_residuals/
#
# There is deliberately NO default year/period here any more. There used to be a hardcoded
# YEAR=2026 / PERIOD=LHC26ab pair, which was harmless in the normal chain (discoverResiduals.sh always
# passes --alien-path, which overrides it) but became live in --all mode, where it silently queried
# LHC26ab for every run regardless of what the caller actually asked for. Requiring the caller to be
# explicit turns that into an up-front error instead of an empty result set.
ALIEN_PATH=""
if [[ -n "${ALIEN_PATH_OVERRIDE}" ]]; then
    ALIEN_PATH="${ALIEN_PATH_OVERRIDE}"
elif [[ $USE_ALIEN -eq 1 ]]; then
    [[ -n "$YEAR" && -n "$PERIOD" ]] \
        || error "--alien needs either --alien-path <path>, or both --year <YYYY> and --period <LHCxxy>"
    ALIEN_PATH="/alice/data/${YEAR}/${PERIOD}/${run}/${SUBDIR}/"
fi

# ── multi-run mode ────────────────────────────────────────────────────────────
# Re-invokes this script once per run directory, then collects all_list files.
if [[ $ALL_MODE -eq 1 ]]; then
    SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
    TOP="$PWD"

    echo
    echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${BOLD}║          TPC Residual List Builder  [multi-run mode]         ║${RESET}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${RESET}"
    echo
    info "Base directory : $TOP"
    info "Subdir         : $SUBDIR"
    [[ $DRY_RUN -eq 1 ]] && warn "DRY-RUN mode — no files will be written"
    echo

    RUNS=( $(ls -d [0-9]*/ 2>/dev/null | sed 's|/$||') )
    [[ ${#RUNS[@]} -eq 0 ]] && error "No run directories (NNN*/) found in $TOP"
    info "Found ${#RUNS[@]} run director(ies): ${RUNS[*]}"
    echo

    FAILED=()
    for r in "${RUNS[@]}"; do
        WORK_DIR="$TOP/$r/$SUBDIR"
        if [[ ! -d "$WORK_DIR" ]]; then
            warn "Skipping run $r — subdir not found: $WORK_DIR"
            FAILED+=("$r")
            continue
        fi
        echo -e "${BOLD}════ Run $r ════${RESET}"
        (
            cd "$WORK_DIR"
            # Propagate every option that affects WHERE we look, not just the two mode flags. --subdir
            # was previously dropped here: the parent used it to build WORK_DIR while the child fell
            # back to the "cpass1_residuals" default, so the two disagreed about which calib pass was
            # being listed. Array, not a string, so a value containing spaces cannot re-split.
            EXTRA_FLAGS=("--subdir" "$SUBDIR")
            [[ $USE_ALIEN -eq 1 ]] && EXTRA_FLAGS+=("--alien")
            [[ $DRY_RUN   -eq 1 ]] && EXTRA_FLAGS+=("--dry-run")
            [[ -n "$YEAR"   ]] && EXTRA_FLAGS+=("--year" "$YEAR")
            [[ -n "$PERIOD" ]] && EXTRA_FLAGS+=("--period" "$PERIOD")
            run="$r" bash "$SCRIPT" "${EXTRA_FLAGS[@]}"
        ) || { warn "Run $r failed — continuing"; FAILED+=("$r"); }
        echo
    done

    # Collect the per-run index files back to the top directory
    if [[ $DRY_RUN -eq 0 ]]; then
        info "Collecting *.residuals_lists.txt → $TOP"
        find "$TOP" -mindepth 3 -maxdepth 3 -name "*.residuals_lists.txt" \
            -exec cp {} "$TOP/" \;
    else
        info "[DRY-RUN] Would copy *.residuals_lists.txt to $TOP"
    fi

    echo
    if [[ ${#FAILED[@]} -gt 0 ]]; then
        warn "Finished with ${#FAILED[@]} skipped/failed run(s): ${FAILED[*]}"
    else
        ok "All ${#RUNS[@]} run(s) processed successfully."
    fi
    _finish 0
fi

# ── single-run mode ───────────────────────────────────────────────────────────
# Safety check: refuse to run in single-run mode from a directory that contains
# numeric run subdirectories — that almost certainly means --all was forgotten.
if [[ -z "$run" ]] && ls -d [0-9][0-9][0-9][0-9][0-9][0-9]*/ &>/dev/null; then
    error "Current directory contains run subdirectories but no run number is set.\n" \
          "       Did you mean: $0 --all\n" \
          "       Or:           run=<number> $0"
fi

FILE_ALL="residuals.all.txt"
RUN_PREFIX="${run:+${run}_}"

echo
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}║              TPC Residual List Builder                       ║${RESET}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${RESET}"
echo
[[ -n "$run" ]] && info "Run number : ${run}" || warn "No run number set — output filenames will omit run"
info "Working dir: $PWD"
info "Source     : $([ $USE_ALIEN -eq 1 ] && echo "alien ($ALIEN_PATH)" || echo "local")"
[[ $DRY_RUN -eq 1 ]] && warn "DRY-RUN mode — no files will be written"
echo

# ── clean up stale output files from previous run ─────────────────────────────
mapfile -t STALE < <(ls "$FILE_ALL" "residuals.${RUN_PREFIX}"*.txt \
    "${run:-NOMATCH}.residuals_lists.txt" \
    "${run:-NOMATCH}.residuals_all_list.txt" 2>/dev/null || true)

if [[ ${#STALE[@]} -gt 0 ]]; then
    warn "Removing ${#STALE[@]} stale file(s) from previous run:"
    for f in "${STALE[@]}"; do
        echo "    rm $f"
        [[ $DRY_RUN -eq 0 ]] && rm -f "$f"
    done
    echo
fi

# ── collect residual file list ────────────────────────────────────────────────
info "Searching for o2tpc_residuals*.root files..."

if [[ $DRY_RUN -eq 1 ]]; then
    if [[ $USE_ALIEN -eq 1 ]]; then
        info "[DRY-RUN] Would run: alien.py find $ALIEN_PATH o2tpc_residuals*.root | sed 's|^|alien://|' > $FILE_ALL"
    else
        COUNT=$(find "$PWD" -name "o2tpc_residuals*.root" | wc -l)
        info "[DRY-RUN] Would write $COUNT file path(s) to: $FILE_ALL"
        find "$PWD" -name "o2tpc_residuals*.root" \
            | awk -F'/' '{print $NF";"$0}' | sort | awk -F';' '{print $NF}' \
            | head -5 | sed 's/^/    /' || true   # `|| true`: head -5 SIGPIPEs the upstream find,
                                                     # which under pipefail would abort this dry run
        [[ $COUNT -gt 5 ]] && echo "    ... ($COUNT total)"
    fi
    echo
    info "[DRY-RUN] Would rename to residuals.all.${RUN_PREFIX}<firstTS>_<lastTS>_<firstTF>_<lastTF>.txt"
    info "[DRY-RUN] Would split into per-period lists residuals.${RUN_PREFIX}<period>.txt"
    info "[DRY-RUN] Would write index file ${run:-norunnumber}.residuals_lists.txt"
    echo
    ok "Dry-run complete — no files written."
    _finish 0
fi

# ── real mode from here ───────────────────────────────────────────────────────
if [[ $USE_ALIEN -eq 1 ]]; then
    alien.py find "$ALIEN_PATH" o2tpc_residuals*.root \
        | sed 's|^|alien://|' > "$FILE_ALL"
else
    find "$PWD" -name "o2tpc_residuals*.root" \
        | awk -F'/' '{print $NF";"$0}' \
        | sort \
        | awk -F';' '{print $NF}' \
        > "$FILE_ALL"
fi

if [[ ! -s "$FILE_ALL" ]]; then
    warn "No o2tpc_residuals*.root files found — all output lists will be empty."
    _finish 0
fi
ok "Found $(wc -l < "$FILE_ALL" | tr -d '[:space:]') file(s)."

# ── extract timestamp range ───────────────────────────────────────────────────
read -r firstTS1 lastTS1 firstTF1 lastTF1 <<< \
    "$(head -1 "$FILE_ALL" | sed -rn 's|.*_([0-9]{13})_([0-9]{13})_([0-9]+)_([0-9]+).*|\1 \2 \3 \4|p')"
read -r firstTS2 lastTS2 firstTF2 lastTF2 <<< \
    "$(tail -1 "$FILE_ALL" | sed -rn 's|.*_([0-9]{13})_([0-9]{13})_([0-9]+)_([0-9]+).*|\1 \2 \3 \4|p')"

# ── MC fallback (no timestamps) ───────────────────────────────────────────────
if [[ -z "${firstTS1:-}" || -z "${lastTS2:-}" ]]; then
    warn "No timestamp info found — assuming MC input."
    FILE_ALL_RANGE="residuals.all.${run}.txt"
    mv "$FILE_ALL" "$FILE_ALL_RANGE"
    ls "$PWD/${FILE_ALL_RANGE}" > "${run}.residuals_lists.txt"
    ok "Done (MC mode)."
    _finish 0
fi

# ── rename with timestamp range ───────────────────────────────────────────────
FILE_ALL_RANGE="residuals.all.${RUN_PREFIX}${firstTS1}_${lastTS2}_${firstTF1}_${lastTF2}.txt"
info "Renaming: $FILE_ALL → $FILE_ALL_RANGE"
mv "$FILE_ALL" "$FILE_ALL_RANGE"

# ── write the run's slot list ─────────────────────────────────────────────────
# ONE list per run, holding every residual file found. Slot granularity is deliberately NOT taken from
# the aggregation labels in the filenames -- it is chosen at submission time via SLOT_LENGTH_MIN, and
# mapCreationJob.sh prefilters each subjob's copy of this list down to the files that can actually
# contribute to its own time window.
#
# Why not group by label: each residual filename carries a slot label
# <firstTS>_<lastTS>_<firstTF>_<lastTF>, and those labels are NOT a uniform grid -- same-length slots
# are not guaranteed, and a run's catalog can hold overlapping/nested labels at different granularities
# (why doesn't matter here, just that it happens), e.g. run 572266:
#     0_105425 (22 files)  105426_210851 (6)  0_210851 (35)
#     210852_316277 (2)    210852_421703 (45)
# Slicing per distinct label would give overlapping slots with wildly uneven statistics -- the 2- and
# 6-file ones trip minTracksPerSlice and come back badCalib_ while the data that would have fixed them
# sits in a sibling list. Keeping one list per run makes granularity a deliberate choice instead of an
# artefact of the upstream catalog's granularity, and keeps it uniform across runs.
# The run's slot list IS the all-files list -- there is exactly one per run, so it is not copied to a
# second name. Both index files below therefore point at this one file.
info "Slot list: $FILE_ALL_RANGE ($(wc -l < "$FILE_ALL_RANGE" | tr -d '[:space:]') file(s))"
info "Windowing happens at submission time (SLOT_LENGTH_MIN), not here -- this is the whole run."

# ── write index files ─────────────────────────────────────────────────────────
# One index per run, holding the single path to that run's slot list.
LISTS_INDEX="${run:-norunnumber}.residuals_lists.txt"
ls "$PWD/${FILE_ALL_RANGE}" > "$LISTS_INDEX"

echo
ok "Done. 1 slot list written."
ok "Slot list index    : $LISTS_INDEX"
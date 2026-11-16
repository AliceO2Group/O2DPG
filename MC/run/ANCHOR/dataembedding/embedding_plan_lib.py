# Pure helpers for planning MC-DATA embedding productions (no ROOT, no GRID).
#
# The work table (embedding_table.json) has the form
#   {"run": R, "orbits_per_tf": n,
#    "files": {"alien:///.../AO2D.root": [{"dfs": {"DF_123": [tf, ...]}}, ...]}}
# Each entry of a file's list is one job ("row"). A DF folder is never split across rows.

import hashlib
import math
import random
import re

_DF_NUMBER = re.compile(r"^DF_(\d+)")


def df_number(df_name):
    """Numeric part of a DF folder name such as DF_2500123."""
    m = _DF_NUMBER.match(df_name)
    if not m:
        raise ValueError(f"not a DF folder name: {df_name}")
    return int(m.group(1))


def sample_files(lfns, fraction, seed):
    """Deterministic sample of ceil(fraction * N) files (at least one), returned sorted."""
    pool = sorted(set(lfns))
    n = min(len(pool), max(1, math.ceil(fraction * len(pool))))
    return sorted(random.Random(seed).sample(pool, n))


def empty_dfs(dfs):
    """DF folders without any timeframe to embed (no triggered collision)."""
    return sorted((df for df, tfs in dfs.items() if not tfs), key=df_number)


def pack_rows(dfs, tfs_per_job):
    """
    Pack whole DF folders, in numeric DF order, greedily and contiguously into rows
    of at most tfs_per_job timeframes. A DF larger than the budget gets a row of its own;
    tfs_per_job <= 0 puts all DFs into one row. Empty DFs get no row.
    """
    rows, current, ntf = [], {}, 0
    for df in sorted(dfs, key=df_number):
        tfs = sorted(dfs[df])
        if not tfs:
            continue
        if current and tfs_per_job > 0 and ntf + len(tfs) > tfs_per_job:
            rows.append(current)
            current, ntf = {}, 0
        current[df] = tfs
        ntf += len(tfs)
    if current:
        rows.append(current)
    return rows


def embedding_seed(job_id, df, tf):
    """
    Seed for one data timeframe of a GRID job: a hash of (job id, DF folder, timeframe) in [1, 2^31).
    The job id is normally ALIEN_PROC_ID. Timeframes collide only by chance (about 2 pairs per 10^5).
    """
    digest = hashlib.sha1(f"{job_id}:{df}:{tf}".encode()).digest()
    return max(1, int.from_bytes(digest[:4], "big") & 0x7fffffff)


def flat_rows(table):
    """All (lfn, row) pairs: files sorted by LFN, then row index (rows submission mode)."""
    return [(lfn, row) for lfn in sorted(table["files"]) for row in table["files"][lfn]]


def num_cycles(table):
    """Number of masterjobs in cycles submission mode: the largest row count of any file."""
    return max((len(rows) for rows in table["files"].values()), default=0)


def files_for_cycle(table, cycle):
    """Files that have a row with index `cycle` (cycles submission mode)."""
    return sorted(lfn for lfn, rows in table["files"].items() if len(rows) > cycle)


def aod_lfns(found):
    """
    Per-job data AO2D files from an 'alien.py find' listing, with an alien:// prefix.
    Merged copies under an AOD/ directory are left out, so a DF is not planned twice.
    """
    out = set()
    for path in found:
        path = path.strip()
        if not path.endswith("/AO2D.root") or "/AOD/" in path:
            continue
        out.add(path if path.startswith("alien://") else "alien://" + path)
    return sorted(out)


if __name__ == "__main__":
    # embedding_plan_lib.py seed <job id> <DF folder> <tf>: prints the seed, for the job script
    import sys
    if len(sys.argv) == 5 and sys.argv[1] == "seed":
        print(embedding_seed(sys.argv[2], sys.argv[3], int(sys.argv[4])))
    else:
        print("usage: embedding_plan_lib.py seed <job id> <DF folder> <tf>", file=sys.stderr)
        sys.exit(1)

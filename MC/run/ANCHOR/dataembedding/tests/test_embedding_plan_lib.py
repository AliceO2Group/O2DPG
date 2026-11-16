#!/usr/bin/env python3
"""Offline tests for the MC-DATA embedding work planner (no ROOT, no GRID)."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import embedding_plan_lib as lib

LFNS = [f"alien:///alice/data/2023/LHC23zzm/544653/apass4/{i:04d}/AO2D.root" for i in range(100)]


def dfs_with(counts):
    """DF name -> list of TF ids; DF numbers increase, TF ids are consecutive."""
    dfs, tf = {}, 1000
    for i, n in enumerate(counts):
        dfs[f"DF_{100 + i}"] = list(range(tf, tf + n))
        tf += n
    return dfs


class TestSampling(unittest.TestCase):

    def test_sample_deterministic_and_size(self):
        a = lib.sample_files(LFNS, 0.05, 42)
        self.assertEqual(len(a), 5)
        self.assertEqual(a, lib.sample_files(list(reversed(LFNS)), 0.05, 42))
        self.assertEqual(a, sorted(a))
        self.assertNotEqual(a, lib.sample_files(LFNS, 0.05, 43))

    def test_sample_at_least_one(self):
        self.assertEqual(len(lib.sample_files(LFNS, 0.0001, 1)), 1)

    def test_sample_fraction_one_takes_all(self):
        self.assertEqual(lib.sample_files(LFNS, 1.0, 1), sorted(LFNS))


class TestPacking(unittest.TestCase):

    def test_pack_contiguous(self):
        rows = lib.pack_rows(dfs_with([2, 2, 2, 2]), 4)
        self.assertEqual([sorted(r) for r in rows], [["DF_100", "DF_101"], ["DF_102", "DF_103"]])

    def test_oversized_df_own_row(self):
        rows = lib.pack_rows(dfs_with([1, 5, 1]), 2)
        self.assertEqual([sorted(r) for r in rows], [["DF_100"], ["DF_101"], ["DF_102"]])

    def test_budget_zero_is_one_row(self):
        self.assertEqual(len(lib.pack_rows(dfs_with([3, 3, 3]), 0)), 1)

    def test_pack_numeric_df_order(self):
        dfs = {"DF_9": [1], "DF_10": [2], "DF_100": [3]}
        rows = lib.pack_rows(dfs, 1)
        self.assertEqual([list(r) for r in rows], [["DF_9"], ["DF_10"], ["DF_100"]])

    def test_pack_order_independent(self):
        dfs = dfs_with([1, 3, 2, 2, 1, 4])
        items = list(dfs.items())
        random.Random(7).shuffle(items)
        self.assertEqual(lib.pack_rows(dfs, 4), lib.pack_rows(dict(items), 4))

    def test_rows_cover_each_df_once(self):
        dfs = dfs_with([1, 3, 2, 2, 1, 4, 7, 1])
        rows = lib.pack_rows(dfs, 3)
        seen = [df for r in rows for df in r]
        self.assertEqual(sorted(seen), sorted(dfs))
        self.assertEqual(len(seen), len(set(seen)))
        for r in rows:
            self.assertEqual({df: dfs[df] for df in r}, r)

    def test_empty_df_gets_no_row(self):
        dfs = {"DF_1": [5], "DF_2": [], "DF_3": [6]}
        rows = lib.pack_rows(dfs, 0)
        self.assertEqual(rows, [{"DF_1": [5], "DF_3": [6]}])
        self.assertEqual(lib.empty_dfs(dfs), ["DF_2"])


class TestSeed(unittest.TestCase):
    JOB = 3752251383   # an ALIEN_PROC_ID

    def test_seed_deterministic(self):
        self.assertEqual(lib.embedding_seed(self.JOB, "DF_1", 1234), lib.embedding_seed(self.JOB, "DF_1", 1234))

    def test_seed_depends_on_job_df_and_tf(self):
        base = lib.embedding_seed(self.JOB, "DF_1", 1000)
        others = [lib.embedding_seed(self.JOB + 1, "DF_1", 1000),   # same timeframe in another job
                  lib.embedding_seed(self.JOB, "DF_2", 1000),       # same timeframe in another DF folder
                  lib.embedding_seed(self.JOB, "DF_1", 1001)]
        self.assertNotIn(base, others)
        self.assertEqual(len(set(others)), len(others))

    def test_consecutive_jobs_do_not_shift_onto_each_other(self):
        # the old SEED + timeframe gave job N timeframe X+1 the seed of job N+1 timeframe X
        self.assertNotEqual(lib.embedding_seed(self.JOB, "DF_1", 1001), lib.embedding_seed(self.JOB + 1, "DF_1", 1000))

    def test_seed_range(self):
        for tf in range(0, 2_000_000, 997):
            self.assertTrue(1 <= lib.embedding_seed(self.JOB, "DF_7", tf) < 2**31)

    def test_seed_collisions_rare(self):
        # 1e5 timeframes over 2000 consecutive jobs in a 2^31 space: about 2 colliding pairs expected
        seeds = [lib.embedding_seed(self.JOB + tf // 50, f"DF_{tf // 50}", tf) for tf in range(100_000)]
        self.assertLess(len(seeds) - len(set(seeds)), 20)

    def test_seed_cli(self):
        import subprocess
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        out = subprocess.run([sys.executable, os.path.join(here, "embedding_plan_lib.py"), "seed", str(self.JOB), "DF_3", "12"],
                             capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(int(out), lib.embedding_seed(self.JOB, "DF_3", 12))


class TestFind(unittest.TestCase):

    def test_aod_lfns_filters_and_prefixes(self):
        found = ["/alice/data/2023/LHC23zzm/544653/apass4/0710/o2_ctf_run00544653_orbit0064712416_tf0000150534_epn244/001/AO2D.root",
                 "/alice/data/2023/LHC23zzm/544653/apass4/AOD/012/AO2D.root",
                 "/alice/data/2023/LHC23zzm/544653/apass4/0710/o2_ctf_x/001/AO2D.root.bak",
                 "",
                 "alien:///alice/data/2023/LHC23zzm/544653/apass4/0711/o2_ctf_y/001/AO2D.root"]
        self.assertEqual(lib.aod_lfns(found),
                         ["alien:///alice/data/2023/LHC23zzm/544653/apass4/0710/o2_ctf_run00544653_orbit0064712416_tf0000150534_epn244/001/AO2D.root",
                          "alien:///alice/data/2023/LHC23zzm/544653/apass4/0711/o2_ctf_y/001/AO2D.root"])


class TestTable(unittest.TestCase):

    def test_flat_rows_order(self):
        table = {"run": 1, "orbits_per_tf": 32, "files": {
            "alien:///b/AO2D.root": [{"dfs": {"DF_1": [1]}}],
            "alien:///a/AO2D.root": [{"dfs": {"DF_5": [7]}}, {"dfs": {"DF_6": [8]}}]}}
        flat = lib.flat_rows(table)
        self.assertEqual([(lfn, r["dfs"]) for lfn, r in flat],
                         [("alien:///a/AO2D.root", {"DF_5": [7]}),
                          ("alien:///a/AO2D.root", {"DF_6": [8]}),
                          ("alien:///b/AO2D.root", {"DF_1": [1]})])

    def test_files_for_cycle(self):
        table = {"files": {"x": [{}, {}, {}], "y": [{}], "z": [{}, {}]}}
        self.assertEqual(lib.files_for_cycle(table, 0), ["x", "y", "z"])
        self.assertEqual(lib.files_for_cycle(table, 1), ["x", "z"])
        self.assertEqual(lib.files_for_cycle(table, 2), ["x"])
        self.assertEqual(lib.files_for_cycle(table, 3), [])
        self.assertEqual(lib.num_cycles(table), 3)


if __name__ == "__main__":
    unittest.main()

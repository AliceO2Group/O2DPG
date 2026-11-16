#!/usr/bin/env python3
"""Offline tests for the pure checks of the MC-DATA embedding merge/validation (no ROOT, no GRID)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import check_embedding_output as chk

A = "alien:///d/a/AO2D.root"
B = "alien:///d/b/AO2D.root"


class TestCoverage(unittest.TestCase):

    def test_coverage_clean(self):
        self.assertEqual(chk.coverage(["DF_1", "DF_2"], ["DF_1", "DF_2"]), ([], [], []))

    def test_coverage_missing_duplicated_unexpected(self):
        missing, duplicated, unexpected = chk.coverage(["DF_1", "DF_2", "DF_3"], ["DF_1", "DF_1", "DF_3", "DF_9"])
        self.assertEqual((missing, duplicated, unexpected), (["DF_2"], ["DF_1"], ["DF_9"]))

    def test_empty_df_counts_as_covered(self):
        # empty DFs are not in the plan's rows, so they are never expected in the output
        planned = chk.planned_dfs({"files": {A: [{"dfs": {"DF_1": [5]}}, {"dfs": {"DF_3": [6]}}]}}, A)
        self.assertEqual(planned, ["DF_1", "DF_3"])
        self.assertEqual(chk.coverage(planned, ["DF_1", "DF_3"]), ([], [], []))


class TestBCs(unittest.TestCase):

    def test_bc_subset(self):
        self.assertTrue(chk.bc_subset([10, 20], [5, 10, 20, 30]))
        self.assertFalse(chk.bc_subset([10, 21], [5, 10, 20, 30]))

    def test_collision_counts(self):
        self.assertEqual(chk.count_mismatches({"DF_1": 90, "DF_2": 80}, {"DF_1": 90, "DF_2": 81}),
                         ["DF_2: 80 MC collisions for 81 data collisions"])


class TestTables(unittest.TestCase):

    def test_mccollision_key_exact(self):
        self.assertEqual(chk.mccollision_key(["O2mccollisionlabel_001", "O2bc_001", "O2mccollision_001"]), "O2mccollision_001")
        self.assertIsNone(chk.mccollision_key(["O2mccollisionlabel_001"]))

    def test_data_counts_skip_excluded(self):
        data = {"DF_1": {10: [1, 2, 3], 11: [4]}, "DF_2": {12: [5]}}
        self.assertEqual(chk.data_counts(data, ["DF_1", "DF_2"], {("DF_1", 11)}), {"DF_1": 3, "DF_2": 1})

    def test_excluded_from_status(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "embedding_status.tsv"), "w") as f:
                f.write("DF_1\t10\tdone\nDF_1\t11\texcluded\n")
            self.assertEqual(chk.excluded_tfs([os.path.join(d, "embedding_row.json")]), {("DF_1", 11)})


class TestExcluded(unittest.TestCase):

    TABLE = {"files": {A: [{"dfs": {"DF_1": [10, 11], "DF_2": [12]}}]}}

    def test_fully_excluded_dfs(self):
        self.assertEqual(chk.fully_excluded_dfs(self.TABLE, A, {("DF_1", 10), ("DF_2", 12)}), ["DF_2"])
        self.assertEqual(chk.fully_excluded_dfs(self.TABLE, A, set()), [])

    def test_expected_dfs_skip_fully_excluded(self):
        self.assertEqual(chk.expected_dfs(self.TABLE, A, {("DF_2", 12)}), ["DF_1"])

    def test_excluded_from_status_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "embedding_status.tsv")
            with open(p, "w") as f:
                f.write("DF_2\t12\texcluded\nDF_1\t10\tdone\n")
            self.assertEqual(chk.excluded_from_status([p]), {("DF_2", 12)})


class TestMissingAOD(unittest.TestCase):

    def _status(self, d, text):
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "embedding_status.tsv"), "w") as f:
            f.write(text)
        return os.path.join(d, "embedding_row.json")

    def test_all_excluded_job_may_lack_aod(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            m = self._status(d, "DF_1\t10\texcluded\nDF_1\t11\texcluded\n")
            self.assertFalse(chk.missing_aod_is_error(m))

    def test_failed_or_unknown_job_without_aod_is_error(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(chk.missing_aod_is_error(self._status(os.path.join(d, "a"), "DF_1\t10\texcluded\nDF_1\t11\tfailed\n")))
            self.assertTrue(chk.missing_aod_is_error(os.path.join(d, "b", "embedding_row.json")))  # no status file


class TestGrouping(unittest.TestCase):

    def test_group_outputs_by_parent_in_row_order(self):
        manifests = [("o/3/embedding_row.json", {"lfn": A, "cycle": 1, "row": None, "dfs": {"DF_3": [6]}}),
                     ("o/1/embedding_row.json", {"lfn": B, "cycle": 0, "row": None, "dfs": {"DF_9": [1]}}),
                     ("o/2/embedding_row.json", {"lfn": A, "cycle": 0, "row": None, "dfs": {"DF_1": [5]}})]
        groups = chk.group_by_parent(manifests)
        cwd = os.getcwd()
        self.assertEqual(groups, {A: [os.path.join(cwd, "o/2/AO2D.root"), os.path.join(cwd, "o/3/AO2D.root")],
                                  B: [os.path.join(cwd, "o/1/AO2D.root")]})

    def test_rows_mode_orders_by_first_df(self):
        manifests = [("x/embedding_row.json", {"lfn": A, "cycle": None, "row": 7, "dfs": {"DF_30": [6]}}),
                     ("y/embedding_row.json", {"lfn": A, "cycle": None, "row": 2, "dfs": {"DF_4": [5]}})]
        self.assertEqual(chk.group_by_parent(manifests), {A: [os.path.abspath("y/AO2D.root"), os.path.abspath("x/AO2D.root")]})


if __name__ == "__main__":
    unittest.main()

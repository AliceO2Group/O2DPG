#!/usr/bin/env python3
"""Offline tests for how an embedding job finds its row of the work table."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import embedding_row as er

A = "alien:///alice/data/2023/LHC23zzm/544653/apass4/0710/o2_ctf_a/001/AO2D.root"
B = "alien:///alice/data/2023/LHC23zzm/544653/apass4/0711/o2_ctf_b/001/AO2D.root"
TABLE = {"run": 544653, "orbits_per_tf": 32, "files": {
    B: [{"dfs": {"DF_20": [7]}}],
    A: [{"dfs": {"DF_1": [1, 2], "DF_2": [3]}}, {"dfs": {"DF_3": [4, 5]}}]}}

WN_XML = """<?xml version="1.0"?>
<alien>
  <collection name="wn.xml">
    <event name="1">
      <file name="AO2D.root" aclId="" broken="0" ctime="2023-10-01 10:00:00" dir="1" entryId="1" expiretime="" gowner="alidaq"
            guid="0" lfn="/alice/data/2023/LHC23zzm/544653/apass4/0710/o2_ctf_a/001/AO2D.root" md5="0" owner="alidaq" perm="755"
            replicated="0" size="1" turl="alien:///alice/data/2023/LHC23zzm/544653/apass4/0710/o2_ctf_a/001/AO2D.root" type="f" />
    </event>
  </collection>
</alien>
"""


class TestJobLfn(unittest.TestCase):

    def test_lfn_from_input_list(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "input.list"), "w") as f:
                f.write("\n/alice/data/2023/LHC23zzm/544653/apass4/0710/o2_ctf_a/001/AO2D.root\n")
            self.assertEqual(er.job_lfn(d), A)

    def test_lfn_from_wn_xml(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "wn.xml"), "w") as f:
                f.write(WN_XML)
            self.assertEqual(er.job_lfn(d), A)

    def test_no_input_gives_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(er.job_lfn(d))


class TestResolveRow(unittest.TestCase):

    def test_row_by_cycle_and_lfn(self):
        self.assertEqual(er.resolve_row(TABLE, {"ALIEN_JDL_MC_DATA_EMBEDDING_CYCLE": "1"}, A),
                         (A, {"DF_3": [4, 5]}))

    def test_row_by_flat_index(self):
        # flat order: files sorted by LFN (A before B), then row index
        self.assertEqual(er.resolve_row(TABLE, {"ALIEN_JDL_MC_DATA_EMBEDDING_ROW": "3"}, None), (B, {"DF_20": [7]}))
        self.assertEqual(er.resolve_row(TABLE, {"ALIEN_JDL_MC_DATA_EMBEDDING_ROW": "1"}, None), (A, {"DF_1": [1, 2], "DF_2": [3]}))

    def test_row_out_of_range_raises(self):
        with self.assertRaises(ValueError):
            er.resolve_row(TABLE, {"ALIEN_JDL_MC_DATA_EMBEDDING_CYCLE": "1"}, B)
        with self.assertRaises(ValueError):
            er.resolve_row(TABLE, {"ALIEN_JDL_MC_DATA_EMBEDDING_ROW": "4"}, None)
        with self.assertRaises(ValueError):
            er.resolve_row(TABLE, {"ALIEN_JDL_MC_DATA_EMBEDDING_ROW": "0"}, None)

    def test_lfn_not_in_table_raises(self):
        with self.assertRaises(ValueError):
            er.resolve_row(TABLE, {"ALIEN_JDL_MC_DATA_EMBEDDING_CYCLE": "0"}, "alien:///other/AO2D.root")

    def test_cycle_without_lfn_raises(self):
        with self.assertRaises(ValueError):
            er.resolve_row(TABLE, {"ALIEN_JDL_MC_DATA_EMBEDDING_CYCLE": "0"}, None)

    def test_neither_variable_raises(self):
        with self.assertRaises(ValueError):
            er.resolve_row(TABLE, {}, A)


class TestCli(unittest.TestCase):

    def test_expect_tfs_and_manifest_written(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "table.json"), "w") as f:
                json.dump(TABLE, f)
            with open(os.path.join(d, "input.list"), "w") as f:
                f.write(A + "\n")
            line = er.run_cli(["--table", "table.json", "--expect-out", "expect.json", "--manifest", "m.json"],
                              {"ALIEN_JDL_MC_DATA_EMBEDDING_CYCLE": "0"}, d)
            self.assertEqual(line, f"{A} DF_1,DF_2")
            with open(os.path.join(d, "expect.json")) as f:
                self.assertEqual(json.load(f), {"DF_1": [1, 2], "DF_2": [3]})
            with open(os.path.join(d, "m.json")) as f:
                m = json.load(f)
            self.assertEqual((m["lfn"], m["cycle"], m["row"], m["run"]), (A, 0, None, 544653))


if __name__ == "__main__":
    unittest.main()

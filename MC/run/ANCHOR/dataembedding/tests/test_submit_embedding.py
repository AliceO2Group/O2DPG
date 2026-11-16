#!/usr/bin/env python3
"""Offline tests for the MC-DATA embedding submission wrapper (no GRID)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import submit_embedding as se

A = "alien:///alice/data/2023/LHC23zzm/544653/apass4/0710/a/001/AO2D.root"
B = "alien:///alice/data/2023/LHC23zzm/544653/apass4/0711/b/001/AO2D.root"
TABLE = {"run": 544653, "files": {A: [{"dfs": {"DF_1": [1]}}, {"dfs": {"DF_2": [2]}}], B: [{"dfs": {"DF_3": [3]}}]}}
ANCHOR_ENV = "export ALIEN_JDL_LPMRUNNUMBER=544653\nexport ALIEN_JDL_LPMANCHORPASSNAME=apass4\n"


class TestSubmissions(unittest.TestCase):

    def test_cycles_mode_one_masterjob_per_cycle(self):
        subs = se.submissions(TABLE, "cycles")
        self.assertEqual([s["name"] for s in subs], ["cycle0", "cycle1"])
        self.assertEqual(subs[0]["collection"], ["/alice/data/2023/LHC23zzm/544653/apass4/0710/a/001/AO2D.root",
                                                 "/alice/data/2023/LHC23zzm/544653/apass4/0711/b/001/AO2D.root"])
        self.assertEqual(subs[1]["collection"], ["/alice/data/2023/LHC23zzm/544653/apass4/0710/a/001/AO2D.root"])
        self.assertIsNone(subs[0]["prodsplit"])

    def test_rows_mode_one_masterjob(self):
        subs = se.submissions(TABLE, "rows")
        self.assertEqual(len(subs), 1)
        self.assertEqual((subs[0]["prodsplit"], subs[0]["collection"]), (3, None))


class TestJobScript(unittest.TestCase):

    def test_cycles_script_exports_cycle_and_table(self):
        text = se.job_script({"name": "cycle1", "cycle": 1, "prodsplit": None, "collection": ["x"]}, ANCHOR_ENV)
        self.assertIn("export ALIEN_JDL_MC_DATA_EMBEDDING_TABLE=embedding_table.json", text)
        self.assertIn("export ALIEN_JDL_MC_DATA_EMBEDDING_CYCLE=1", text)
        self.assertNotIn("MC_DATA_EMBEDDING_ROW", text)
        self.assertIn("export ALIEN_JDL_LPMRUNNUMBER=544653", text)
        self.assertTrue(text.startswith("#!/bin/bash\n"))
        self.assertIn("#JDL_OUTPUT=", text)
        outputs = text.split("#JDL_OUTPUT=")[1].split("\n")[0].split(",")
        for f in ("AO2D*.root@disk=2", "embedding_row.json@disk=2", "embedding_status*.tsv@disk=2"):
            self.assertIn(f, outputs)
        self.assertIn("anchorMC_DataEmbedding.sh", text)

    def test_outputs_that_may_be_absent_are_patterns(self):
        # JAliEn fails a successful job whose plain output file is missing; a pattern may match nothing
        outputs = [o.split("@")[0] for o in se.OUTPUTS]
        self.assertNotIn("AO2D.root", outputs)
        self.assertNotIn("embedding_status.tsv", outputs)

    def test_rows_script_takes_row_from_subjob_id(self):
        text = se.job_script({"name": "rows", "cycle": None, "prodsplit": 3, "collection": None}, ANCHOR_ENV)
        self.assertIn("export ALIEN_JDL_MC_DATA_EMBEDDING_ROW=${ALIEN_JDL_MC_DATA_EMBEDDING_ROW:-${ALIEN_O2DPG_GRIDSUBMIT_SUBJOBID}}", text)
        self.assertNotIn("MC_DATA_EMBEDDING_CYCLE", text)

    def test_anchor_env_may_set_tuning_knobs(self):
        env = ANCHOR_ENV + "export ALIEN_JDL_MC_DATA_EMBEDDING_PARALLEL=4\nexport ALIEN_JDL_MC_DATA_EMBEDDING_RETRIES=3\n"
        text = se.job_script({"name": "cycle0", "cycle": 0, "prodsplit": None, "collection": ["x"]}, env)
        self.assertIn("ALIEN_JDL_MC_DATA_EMBEDDING_PARALLEL=4", text)

    def test_anchor_env_must_not_set_embedding_variables(self):
        with self.assertRaises(ValueError):
            se.job_script({"name": "cycle0", "cycle": 0, "prodsplit": None, "collection": ["x"]},
                          ANCHOR_ENV + "export ALIEN_JDL_MC_DATA_EMBEDDING_CYCLE=5\n")


class TestGridSubmitArgs(unittest.TestCase):

    def test_args_for_cycle(self):
        args = se.grid_submit_args({"name": "cycle0", "cycle": 0, "prodsplit": None, "collection": ["x"]},
                                   "job.sh", "list.txt", "/alice/cern.ch/user/s/swenzel/emb/embedding_table.json", "emb_544653", True, ["--ttl", "36000"])
        self.assertEqual(args, ["--script", "job.sh", "--jobname", "emb_544653_cycle0",
                                "--inputfile", "/alice/cern.ch/user/s/swenzel/emb/embedding_table.json",
                                "--split-on-collection", "list.txt", "--dry", "--ttl", "36000"])

    def test_args_for_rows(self):
        args = se.grid_submit_args({"name": "rows", "cycle": None, "prodsplit": 3, "collection": None},
                                   "job.sh", None, "/t/embedding_table.json", "emb", False, [])
        self.assertEqual(args, ["--script", "job.sh", "--jobname", "emb_rows", "--inputfile", "/t/embedding_table.json",
                                "--prodsplit", "3"])


if __name__ == "__main__":
    unittest.main()

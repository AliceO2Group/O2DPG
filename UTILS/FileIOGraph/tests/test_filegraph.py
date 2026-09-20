#!/usr/bin/env python3
"""Offline tests for the report machinery, the comparison and the backends.

Plain unittest: this has to run on the bare interpreter of a GRID worker
or a CVMFS O2 environment, neither of which has pytest.

    python3 -m unittest discover -s UTILS/FileIOGraph/tests -t UTILS/FileIOGraph/tests
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from filegraph_test_support import FILEGRAPH_DIR, filegraph

import equivalence_test  # noqa: E402
from compare_reports import compare  # noqa: E402
from filegraph_report import (  # noqa: E402
    basedir_prefix, build_report, keep_file, relative_to_basedir,
)

ALL = [re.compile(r".*")]
LOG = logging.getLogger("test")


class TestPathHelpers(unittest.TestCase):
    def test_relative_to_basedir(self):
        for base in ("/w", "/w/"):
            prefix = basedir_prefix(base)
            self.assertEqual(relative_to_basedir("/w/tf1/a.root", prefix),
                             "./tf1/a.root")
            self.assertIsNone(relative_to_basedir("/usr/lib/libc.so", prefix))

    def test_logs_and_dpl_config_are_noise(self):
        self.assertFalse(keep_file("./tf1/sgnsim_1.log", ALL))
        self.assertFalse(keep_file("./tf1/sgnsim_1.log_done", ALL))
        self.assertFalse(keep_file("./dpl-config.json", ALL))
        self.assertTrue(keep_file("./tf1/AO2D.root", ALL))

    def test_filters_apply(self):
        self.assertTrue(keep_file("./tf1/a.root", [re.compile(r".*\.root")]))
        self.assertFalse(keep_file("./tf1/a.dat", [re.compile(r".*\.root")]))


class TestBuildReport(unittest.TestCase):
    def setUp(self):
        self.doc = build_report(
            {"./tf1/a.root": {"digi_1"}, "./tf2/a.root": {"digi_2"},
             "./AO2D.root": {"aodmerge"}},
            {"./tf1/a.root": {"reco_1", "aodmerge"},
             "./tf2/a.root": {"reco_2", "aodmerge"}},
            ["digi_1", "digi_2", "reco_1", "reco_2", "aodmerge"])
        self.tpl = {e["file"]: e for e in self.doc["file_template_report"]}

    def test_timeframe_tasks_become_templates(self):
        self.assertEqual(self.tpl["./tfX/a.root"]["written_by"], ["digi_X"])
        self.assertEqual(self.tpl["./tfX/a.root"]["source_timeframes"], [1, 2])

    def test_global_reader_is_not_templated(self):
        # a naive "strip the trailing _N" would corrupt aodmerge
        self.assertIn("aodmerge", self.tpl["./tfX/a.root"]["read_by"])
        self.assertIn("reco_X", self.tpl["./tfX/a.root"]["read_by"])

    def test_non_timeframe_file_absent_from_templates(self):
        self.assertNotIn("./AO2D.root", self.tpl)

    def test_task_report_covers_every_task(self):
        self.assertEqual([t["task"] for t in self.doc["task_report"]],
                         ["aodmerge", "digi_1", "digi_2", "reco_1", "reco_2"])


class TestCompare(unittest.TestCase):
    def _verdict(self, cand_written, cand_read):
        ref = build_report({"./tf1/a.root": {"digi_1"}},
                           {"./tf1/a.root": {"reco_1"}}, ["digi_1", "reco_1"])
        cand = build_report(cand_written, cand_read, ["digi_1", "reco_1"])
        return compare(ref, cand)[1]

    def test_identical_is_exact(self):
        s = self._verdict({"./tf1/a.root": {"digi_1"}}, {"./tf1/a.root": {"reco_1"}})
        self.assertEqual(s["verdict"], "EXACT")

    def test_extra_reader_is_safe(self):
        s = self._verdict({"./tf1/a.root": {"digi_1"}},
                          {"./tf1/a.root": {"reco_1", "qc_1"}})
        self.assertEqual(s["verdict"], "SAFE")
        self.assertEqual(s["sections"]["file_report"]["missing_edges"], 0)

    def test_missing_reader_is_unsafe(self):
        s = self._verdict({"./tf1/a.root": {"digi_1"}}, {})
        self.assertEqual(s["verdict"], "UNSAFE")
        self.assertEqual(s["sections"]["file_report"]["missing_edges"], 1)
        self.assertAlmostEqual(s["sections"]["file_report"]["recall"], 0.5)

    def test_missing_file_is_unsafe(self):
        self.assertEqual(self._verdict({}, {})["verdict"], "UNSAFE")


class TestAnalyseFanotifyLog(unittest.TestCase):
    """End-to-end on the fanotify analyser, so the shared module stays honest."""

    ACTION = (
        "2026-05-06 16:49:18,267 INFO Task pid=101 tid=0 bkg finished rc=0\n"
        "2026-05-06 16:49:19,267 INFO Task pid=102 tid=1 sgnsim_1 finished rc=0\n"
        "2026-05-06 16:49:20,267 INFO Task pid=103 tid=2 reco_1 finished rc=0\n"
    )

    def test_report(self):
        with tempfile.TemporaryDirectory() as d:
            action = os.path.join(d, "action.log")
            monitor = os.path.join(d, "monitor.log")
            out = os.path.join(d, "report.json")
            with open(action, "w") as f:
                f.write(self.ACTION)
            with open(monitor, "w") as f:
                f.write(f'"{d}/bkg.dat",write,101\n'
                        f'"{d}/tf1/sgn.dat",write,201;102\n'
                        f'"{d}/bkg.dat",read,201;102\n'
                        f'"{d}/tf1/sgn.dat",read,103\n'
                        f'"{d}/tf1/reco_1.log",write,103\n'
                        f'"/usr/lib/libc.so.6",read,103\n')
            subprocess.run(
                [sys.executable, os.path.join(FILEGRAPH_DIR, "analyse_FileIO_v2.py"),
                 "--actionFile", action, "--monitorFile", monitor,
                 "--basedir", d, "-o", out],
                check=True, stdout=subprocess.DEVNULL)
            with open(out) as f:
                doc = json.load(f)

        got = {e["file"]: (e["written_by"], e["read_by"]) for e in doc["file_report"]}
        self.assertEqual(got["./bkg.dat"], (["bkg"], ["sgnsim_1"]))
        # a grandchild's access is attributed through the parent chain
        self.assertEqual(got["./tf1/sgn.dat"], (["sgnsim_1"], ["reco_1"]))
        self.assertNotIn("./tf1/reco_1.log", got)
        self.assertNotIn("/usr/lib/libc.so.6", got)


class StubBackend(filegraph.FileGraphBackend):
    name = "stub"

    def wrap(self, argv, taskname, tid):
        return ["stub", taskname, str(tid), "--"] + argv


def manager(spec, action_log="action.log"):
    return filegraph.FileGraphManager.from_config(spec, "/w", 4242, action_log, LOG)


class TestBackendSelection(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.dict(os.environ, {}, clear=False)
        patch.start()
        self.addCleanup(patch.stop)
        for k in ("O2DPG_PRODUCE_FILEGRAPH", "O2DPG_FILEGRAPH_BACKENDS"):
            os.environ.pop(k, None)
        filegraph.BACKENDS["stub"] = StubBackend
        self.addCleanup(filegraph.BACKENDS.pop, "stub", None)

    def test_nothing_requested_means_no_backend(self):
        self.assertEqual(manager("").backends, [])

    def test_named_backends_are_built_in_order(self):
        self.assertEqual([b.name for b in manager("stub,fanotify").backends],
                         ["stub", "fanotify"])

    def test_legacy_variable_selects_fanotify_with_that_exe(self):
        os.environ["O2DPG_PRODUCE_FILEGRAPH"] = "/opt/mon.exe"
        m = manager("")
        self.assertEqual([b.name for b in m.backends], ["fanotify"])
        self.assertEqual(m.backends[0].exe, "/opt/mon.exe")

    def test_unknown_backend_is_skipped_not_fatal(self):
        self.assertEqual([b.name for b in manager("stub,nonsense").backends], ["stub"])

    def test_the_action_log_reaches_the_backend_that_needs_it(self):
        b = manager("fanotify", action_log="pipeline_action_7.log").backends[0]
        self.assertIn("pipeline_action_7.log", b.analyser_args())

    def test_only_fanotify_writes_the_legacy_report_name(self):
        self.assertTrue(filegraph.FanotifyBackend.legacy_report)
        self.assertFalse(StubBackend.legacy_report)


class TestBackendWrapping(unittest.TestCase):
    ARGV = ["/bin/bash", "-c", "echo hi"]

    def setUp(self):
        filegraph.BACKENDS["stub"] = StubBackend
        self.addCleanup(filegraph.BACKENDS.pop, "stub", None)

    def test_a_backend_that_does_not_wrap_leaves_the_command_alone(self):
        self.assertEqual(manager("fanotify").wrap(list(self.ARGV), "sgnsim_1", 3),
                         self.ARGV)

    def test_a_wrapping_backend_keeps_the_command_as_the_tail(self):
        argv = manager("stub").wrap(list(self.ARGV), "sgnsim_1", 3)
        self.assertEqual(argv[:4], ["stub", "sgnsim_1", "3", "--"])
        self.assertEqual(argv[4:], self.ARGV)

    def test_an_empty_manager_is_a_no_op(self):
        m = manager("")
        self.assertEqual(m.wrap(list(self.ARGV), "sgnsim_1", 3), self.ARGV)
        m.start()
        m.stop()
        self.assertEqual(m.analyse(), {})


class TestFilegraphDir(unittest.TestCase):
    def test_resolves_without_o2dpg_root(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("O2DPG_ROOT", None)
            d = filegraph.filegraph_dir()
        self.assertTrue(os.path.exists(os.path.join(d, "analyse_FileIO_v2.py")), d)


class TestSyntheticWorkflow(unittest.TestCase):
    def test_the_truth_matches_the_commands(self):
        wf, truth = equivalence_test.build_workflow(2, "0")
        files = {e["file"]: e for e in truth["file_report"]}
        self.assertEqual(files["./tf1/AO2D.dat"]["read_by"], ["aodmerge"])
        # a run-time subdirectory is part of the expected graph
        self.assertEqual(files["./tf1/sub/extra.dat"]["written_by"], ["digi_1"])
        for s in wf["stages"]:
            self.assertIn("cwd", s)
            self.assertIn("resources", s)
            self.assertIn("timeframe", s)


if __name__ == "__main__":
    unittest.main()

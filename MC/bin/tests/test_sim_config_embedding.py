#!/usr/bin/env python3
"""Offline tests: MC-DATA embedding switches the TPC looper generator and the QED background off."""
import argparse
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import o2dpg_sim_config as simconfig


def args(**kw):
    base = dict(gen="pythia8pp", col="PbPb", with_ZDC=False, skipModules=[], data_anchoring="")
    base.update(kw)
    return argparse.Namespace(**base)


class TestLoopersVeto(unittest.TestCase):

    def test_data_anchoring_vetoes_loopers(self):
        cfg = simconfig.create_geant_config(args(data_anchoring="ctx.root"), "")
        self.assertEqual(cfg["GenTPCLoopers"].get("loopersVeto"), "true")

    def test_ordinary_production_keeps_loopers(self):
        cfg = simconfig.create_geant_config(args(), "")
        self.assertNotIn("loopersVeto", cfg["GenTPCLoopers"])

    def test_explicit_key_wins(self):
        cfg = simconfig.create_geant_config(args(data_anchoring="ctx.root"), "GenTPCLoopers.loopersVeto=false")
        self.assertEqual(cfg["GenTPCLoopers"].get("loopersVeto"), "false")


class TestQED(unittest.TestCase):
    PB = 1000822080

    def test_default_on_for_heavy_ions_only(self):
        self.assertTrue(simconfig.qed_included(self.PB, self.PB, False, False, ""))
        self.assertFalse(simconfig.qed_included(2212, 2212, False, False, ""))

    def test_flags(self):
        self.assertTrue(simconfig.qed_included(2212, 2212, True, False, ""))
        self.assertFalse(simconfig.qed_included(self.PB, self.PB, False, True, ""))

    def test_data_anchoring_switches_qed_off(self):
        self.assertFalse(simconfig.qed_included(self.PB, self.PB, False, False, "ctx.root"))

    def test_with_qed_wins_over_data_anchoring(self):
        self.assertTrue(simconfig.qed_included(self.PB, self.PB, True, False, "ctx.root"))


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Offline tests: align-geom.mDetectors of the transport and what geomprefetch derives from it."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import o2dpg_sim_config as simconfig


class TestSimAlignDetectors(unittest.TestCase):

    def test_absent(self):
        self.assertEqual(simconfig.sim_align_detectors(""), "all")
        self.assertEqual(simconfig.sim_align_detectors("G4.navmode=kTGeo"), "all")

    def test_none(self):
        self.assertEqual(simconfig.sim_align_detectors("align-geom.mDetectors=none"), "none")

    def test_not_first_and_spaces(self):
        self.assertEqual(simconfig.sim_align_detectors("G4.navmode=kTGeo; align-geom.mDetectors = none ;"), "none")

    def test_partial_list(self):
        self.assertEqual(simconfig.sim_align_detectors("align-geom.mDetectors=MCH,MID;G4.navmode=kTGeo"), "MCH,MID")

    def test_last_wins(self):
        self.assertEqual(simconfig.sim_align_detectors("align-geom.mDetectors=none;align-geom.mDetectors=ITS"), "ITS")

    def test_other_align_geom_key(self):
        self.assertEqual(simconfig.sim_align_detectors("align-geom.mTimeStamp=1"), "all")


class TestForwardedKey(unittest.TestCase):

    def test_default_adds_nothing(self):
        self.assertEqual(simconfig.geom_align_configkey("all"), "")

    def test_values(self):
        self.assertEqual(simconfig.geom_align_configkey("none"), ";align-geom.mDetectors=none")
        self.assertEqual(simconfig.geom_align_configkey("MCH,MID"), ";align-geom.mDetectors=MCH,MID")


class TestAlignedInTransport(unittest.TestCase):

    def test_all_and_none(self):
        self.assertTrue(simconfig.aligned_in_transport("all", "ITS"))
        self.assertFalse(simconfig.aligned_in_transport("none", "ITS"))
        self.assertFalse(simconfig.aligned_in_transport("all,none", "ITS"))  # none wins, as in DetID::getMask

    def test_list(self):
        self.assertTrue(simconfig.aligned_in_transport("MCH,ITS", "ITS"))
        self.assertTrue(simconfig.aligned_in_transport("MCH ITS", "ITS"))
        self.assertFalse(simconfig.aligned_in_transport("MCH,MID", "ITS"))
        self.assertFalse(simconfig.aligned_in_transport("ITS3", "ITS"))


class TestITSIdeal(unittest.TestCase):

    def test_truth_table(self):
        self.assertTrue(simconfig.its_ideal_in_transport(0, "all"))
        self.assertTrue(simconfig.its_ideal_in_transport(0, "none"))
        self.assertFalse(simconfig.its_ideal_in_transport(1, "all"))
        self.assertTrue(simconfig.its_ideal_in_transport(1, "none"))
        self.assertTrue(simconfig.its_ideal_in_transport(1, "MCH,MID"))
        self.assertFalse(simconfig.its_ideal_in_transport(1, "MCH,ITS"))


if __name__ == "__main__":
    unittest.main()

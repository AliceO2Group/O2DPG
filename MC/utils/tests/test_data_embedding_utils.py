#!/usr/bin/env python3
"""Offline tests for the DF selection in o2dpg_data_embedding_utils (needs ROOT + pandas, no GRID)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import pandas as pd
    import o2dpg_data_embedding_utils as utils   # needs ROOT
except ImportError:                              # pragma: no cover
    utils = None


def structure(tfs_per_folder):
    """Mimics get_timeframe_structure: 'DF_x@file' -> DataFrame(timeframeID, position_vectors)."""
    merged = {}
    for df, tfs in tfs_per_folder.items():
        merged[f"{df}@local.root"] = pd.DataFrame({"timeframeID": tfs,
                                                   "position_vectors": [[(0, 0., 0., 0., 0, 0, 0.)]] * len(tfs)})
    return merged


@unittest.skipIf(utils is None, "needs ROOT and pandas")
class TestDFSelection(unittest.TestCase):

    def test_units_from_timeframe_structure(self):
        units = utils.units_from_timeframe_structure(structure({"DF_7": [31, 30], "DF_5": [12], "DF_9": []}))
        self.assertEqual(units, {"DF_5": [12], "DF_7": [30, 31], "DF_9": []})

    def test_select_rows_keeps_only_requested_dfs(self):
        merged = structure({"DF_5": [12], "DF_7": [30, 31], "DF_9": [40]})
        selected = utils.select_folders(merged, ["DF_7", "DF_9"])
        self.assertEqual(sorted(k.split("@")[0] for k in selected), ["DF_7", "DF_9"])

    def test_missing_requested_df_is_a_mismatch(self):
        units = {"DF_5": [12]}
        self.assertEqual(utils.expectation_mismatches(units, {"DF_5": [12], "DF_6": [13]}), ["DF_6: expected [13], found none"])

    def test_different_tfs_are_a_mismatch(self):
        units = {"DF_5": [12, 13]}
        self.assertEqual(utils.expectation_mismatches(units, {"DF_5": [12]}), ["DF_5: expected [12], found [12, 13]"])

    def test_matching_expectation_is_clean(self):
        self.assertEqual(utils.expectation_mismatches({"DF_5": [12], "DF_6": [1]}, {"DF_5": [12]}), [])


@unittest.skipIf(utils is None, "needs ROOT and pandas")
class TestTimeframeStructureFile(unittest.TestCase):
    """get_timeframe_structure on a small AO2D-like file written with uproot."""

    RUN_INFO = {"OrbitReset": 0, "FirstOrbit": 1000, "OrbitsPerTF": 32}

    def write_file(self, path):
        import numpy as np
        import uproot
        first_bc = 1000 * 3564
        with uproot.recreate(path) as f:
            # DF_1: two triggered collisions in TF 0 and one untriggered
            f["DF_1/O2bc_001"] = {"fGlobalBC": np.array([first_bc + 10, first_bc + 20, first_bc + 30], dtype=np.uint64),
                                  "fTriggerMask": np.array([1, 1, 0], dtype=np.uint64)}
            f["DF_1/O2collision_001"] = {"fIndexBCs": np.array([0, 1, 2], dtype=np.int32),
                                         "fPosX": np.zeros(3, dtype=np.float32), "fPosY": np.zeros(3, dtype=np.float32),
                                         "fPosZ": np.zeros(3, dtype=np.float32), "fCollisionTime": np.zeros(3, dtype=np.float32)}
            # DF_2: no triggered collision at all
            f["DF_2/O2bc_001"] = {"fGlobalBC": np.array([first_bc + 40], dtype=np.uint64),
                                  "fTriggerMask": np.array([0], dtype=np.uint64)}
            f["DF_2/O2collision_001"] = {"fIndexBCs": np.array([0], dtype=np.int32),
                                         "fPosX": np.zeros(1, dtype=np.float32), "fPosY": np.zeros(1, dtype=np.float32),
                                         "fPosZ": np.zeros(1, dtype=np.float32), "fCollisionTime": np.zeros(1, dtype=np.float32)}

    def test_empty_df_does_not_crash(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "aod.root")
            self.write_file(path)
            merged = utils.get_timeframe_structure(path, self.RUN_INFO, max_folders=None)
            self.assertEqual(utils.units_from_timeframe_structure(merged), {"DF_1": [0], "DF_2": []})


@unittest.skipIf(utils is None, "needs ROOT and pandas")
class TestTimeOrder(unittest.TestCase):
    # (globalBC, x, y, z, orbit, bc_within_orbit, collisionTime ns)
    A = (1000, 0., 0., 1., 0, 1000, 0.0)
    B = (1001, 0., 0., 2., 0, 1001, -40.0)   # 1 BC later, but 40 ns earlier in time
    C = (1002, 0., 0., 3., 0, 1002, 3.0)

    def test_time_ordered_collisions(self):
        self.assertEqual(utils.time_ordered_collisions([self.A, self.B, self.C]), [self.B, self.A, self.C])

    def test_order_kept_when_already_ordered(self):
        self.assertEqual(utils.time_ordered_collisions([self.A, self.C]), [self.A, self.C])

    def test_context_records_are_time_ordered(self):
        import tempfile
        from ROOT import o2
        with tempfile.TemporaryDirectory() as d:
            cwd = os.getcwd()
            os.chdir(d)
            try:
                utils.convert_to_digicontext([self.A, self.B, self.C], "DF_1", 7)
                ctx = o2.steer.DigitizationContext.loadFromFile("collission_context_DF_1:7.root")
            finally:
                os.chdir(cwd)
            times = [r.getTimeNS() for r in ctx.getEventRecords()]
            self.assertEqual(times, sorted(times))
            zs = [v.Z() for v in ctx.getInteractionVertices()]
            self.assertEqual(zs, [2., 1., 3.])


@unittest.skipIf(utils is None, "needs ROOT and pandas")
class TestContextInteractionRate(unittest.TestCase):

    def test_set_interaction_rate(self):
        import tempfile
        import ROOT
        from ROOT import o2
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "collisioncontext.root")
            ctx = o2.steer.DigitizationContext()
            ctx.saveToFile(path)
            self.assertLess(o2.steer.DigitizationContext.loadFromFile(path).getDigitizerInteractionRate(), 0)
            utils.set_context_interaction_rate(path, 31234.)
            self.assertAlmostEqual(o2.steer.DigitizationContext.loadFromFile(path).getDigitizerInteractionRate(), 31234., places=0)

    def test_rejects_non_positive_rate(self):
        with self.assertRaises(ValueError):
            utils.set_context_interaction_rate("unused.root", 0)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Offline test: an explicit timeframe ID is placed from the unshifted run start (MC-DATA embedding)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

os.environ.setdefault("O2DPG_ROOT", os.path.dirname(os.path.dirname(os.path.dirname(HERE))))

try:
    import o2dpg_sim_workflow_anchored as anchored     # needs ROOT
except ImportError as exc:                             # pragma: no cover
    anchored = None

SOR = 1778806732526
FIRST_ORBIT = 20505888
ORBITS_PER_TF = 32
ITS_RAMPUP_MS = 5000


@unittest.skipIf(anchored is None, "o2dpg_sim_workflow_anchored not importable (needs ROOT)")
class TestTimeframeIdAnchor(unittest.TestCase):

    def test_explicit_timeframe_ignores_rampup_shift(self):
        start, orbit = anchored.anchor_origin(SOR, FIRST_ORBIT, ORBITS_PER_TF, ITS_RAMPUP_MS, explicit_timeframe=True)
        self.assertEqual((start, orbit), (SOR, FIRST_ORBIT))
        # the MC timeframe tf then starts where the data timeframe tf starts
        tf = 10
        self.assertEqual(orbit + tf * ORBITS_PER_TF, FIRST_ORBIT + 320)

    def test_sampled_timeframe_keeps_rampup_shift(self):
        self.assertEqual(anchored.anchor_origin(SOR, FIRST_ORBIT, ORBITS_PER_TF, ITS_RAMPUP_MS, explicit_timeframe=False),
                         anchored.shift_anchor_past_ITS_rampup(SOR, FIRST_ORBIT, ORBITS_PER_TF, ITS_RAMPUP_MS))


@unittest.skipIf(anchored is None, "o2dpg_sim_workflow_anchored not importable (needs ROOT)")
class TestEndOfRun(unittest.TestCase):
    """Data timeframes can lie a little past the end of run recorded in CCDB."""
    EOR = SOR + 2232696   # run 544653: last data TF starts about 0.6 s after EOR

    def test_explicit_timeframe_past_eor_is_accepted(self):
        tf = 784641
        ts = anchored.determine_timestamp_from_timeframeID(SOR, self.EOR, tf, ORBITS_PER_TF)
        self.assertGreater(ts, self.EOR)

    def test_rate_lookup_time_clamped_for_explicit_timeframe(self):
        collisions_end = self.EOR - 500
        self.assertEqual(anchored.rate_lookup_time(self.EOR + 600, SOR, collisions_end, True), collisions_end - 1000)
        self.assertEqual(anchored.rate_lookup_time(SOR + 5000, SOR, collisions_end, True), SOR + 5000)

    def test_conditions_timestamp_clamped_to_run(self):
        self.assertEqual(anchored.conditions_timestamp(self.EOR + 68, self.EOR), self.EOR - 1)
        self.assertEqual(anchored.conditions_timestamp(self.EOR - 5000, self.EOR), self.EOR - 5000)

    def test_rate_lookup_time_unchanged_for_sampled(self):
        self.assertEqual(anchored.rate_lookup_time(self.EOR + 600, SOR, self.EOR, False), self.EOR + 600)


if __name__ == "__main__":
    unittest.main()

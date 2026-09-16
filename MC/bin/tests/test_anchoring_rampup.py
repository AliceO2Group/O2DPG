#!/usr/bin/env python3
"""Offline test: the ITS ramp-up shift must move the first orbit, not only the timestamp."""
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
    IMPORT_ERROR = exc

# Run 571781 of LHC26e9, whose SPLITID=1 job reconstructed no collisions at all:
# the ITS time-dead map masks all 24120 chips up to orbit 20539968 and the job was
# placed at the run's first orbit. See https://its.cern.ch/jira/browse/O2-6894
FIRST_ORBIT = 20505888
SOR = 1778806732526
ITS_RAMPUP_MS = 5000
FIRST_ALIVE_ORBIT = 20539968


@unittest.skipIf(anchored is None, "o2dpg_sim_workflow_anchored not importable (needs ROOT)")
class TestRampUpShift(unittest.TestCase):

    def test_orbits_from_milliseconds(self):
        orbit_ms = anchored.LHCOrbitMUS / 1000.
        self.assertEqual(anchored.milliseconds_to_orbits(0), 0)
        # a span of one orbit minus an epsilon still has to cover a full orbit
        self.assertEqual(anchored.milliseconds_to_orbits(0.5 * orbit_ms), 1)
        self.assertEqual(anchored.milliseconds_to_orbits(orbit_ms), 1)

    def test_both_coordinates_move(self):
        """A ramp-up of a few seconds must move the orbit as well as the timestamp."""
        start, orbit = anchored.shift_anchor_past_ITS_rampup(SOR, FIRST_ORBIT, ITS_RAMPUP_MS)
        self.assertEqual(start, SOR + ITS_RAMPUP_MS)
        self.assertGreater(orbit, FIRST_ORBIT)

    def test_nothing_moves_without_a_ramp(self):
        self.assertEqual(anchored.shift_anchor_past_ITS_rampup(SOR, FIRST_ORBIT, 0),
                         (SOR, FIRST_ORBIT))

    def test_shifted_orbit_is_never_inside_the_ramp(self):
        """The shifted orbit must sit at or after the shifted timestamp, never before."""
        for ramp_ms in (0, 1, 500, ITS_RAMPUP_MS, 30000):
            start, orbit = anchored.shift_anchor_past_ITS_rampup(SOR, FIRST_ORBIT, ramp_ms)
            time_of_orbit = SOR + (orbit - FIRST_ORBIT) * anchored.LHCOrbitMUS / 1000.
            self.assertGreaterEqual(time_of_orbit, start,
                                    f"orbit shift falls short of the ramp for {ramp_ms} ms")

    def test_shift_agrees_with_the_timestamp_to_orbit_conversion(self):
        """Closure: the shifted orbit is what main() derives from the shifted timestamp."""
        start, orbit = anchored.shift_anchor_past_ITS_rampup(SOR, FIRST_ORBIT, ITS_RAMPUP_MS)
        # this is the conversion main() uses for the exclude_timestamp() check
        derived = FIRST_ORBIT + int((start - SOR) / (anchored.LHCOrbitMUS / 1000.))
        self.assertLessEqual(abs(orbit - derived), 1)

    def test_split_id_one_clears_the_its_dead_window(self):
        """Regression: the first job of a production must not sample the dead window."""
        _, orbit = anchored.shift_anchor_past_ITS_rampup(SOR, FIRST_ORBIT, ITS_RAMPUP_MS)
        self.assertGreater(orbit, FIRST_ALIVE_ORBIT)


if __name__ == "__main__":
    unittest.main()

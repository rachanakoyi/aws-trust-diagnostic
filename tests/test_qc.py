"""Unit tests for Deterministic Quality Control (QC) Engine."""

import unittest
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from data_sources.schema import WeatherObservation
from qc.qc_engine import DeterministicQCEngine


class TestDeterministicQC(unittest.TestCase):
    """Test suite for DeterministicQCEngine."""

    def setUp(self):
        self.qc = DeterministicQCEngine(
            temp_min=-10.0, temp_max=50.0,
            pressure_min=900.0, pressure_max=1060.0,
            humidity_min=0.0, humidity_max=100.0,
            max_temp_step=4.0, max_pressure_step=5.0, max_humidity_step=20.0,
            persistence_window=4
        )
        self.base_obs = WeatherObservation(
            timestamp="2026-09-27T10:00:00+00:00",
            station_id="AWS_QC_TEST",
            temperature=30.0,
            pressure=1008.0,
            humidity=60.0,
            latitude=28.585,
            longitude=77.209,
            source="TEST"
        )

    def test_nominal_qc_passes(self):
        """Nominal observation produces no flags and zero QC score."""
        res = self.qc.evaluate(self.base_obs)
        self.assertFalse(res.has_any_flag)
        self.assertEqual(res.qc_score, 0.0)

    def test_rate_of_change_violation(self):
        """Sudden impossible temperature jump triggers rate check."""
        prev = WeatherObservation.from_dict(self.base_obs.to_dict())
        prev.timestamp = "2026-09-27T09:50:00+00:00"
        prev.temperature = 28.0

        curr = WeatherObservation.from_dict(self.base_obs.to_dict())
        curr.temperature = 42.0  # +14.0°C jump exceeds max_temp_step (4.0)

        res = self.qc.evaluate(curr, history=[prev])
        self.assertTrue(res.rate_flag)
        self.assertGreater(res.qc_score, 0.0)
        self.assertTrue(any("step change" in r for r in res.flagged_reasons))

    def test_persistence_frozen_sensor(self):
        """4 identical consecutive temperature values trigger persistence check."""
        history = []
        for i in range(3):
            obs = WeatherObservation.from_dict(self.base_obs.to_dict())
            obs.temperature = 31.42
            obs.timestamp = f"2026-09-27T09:{30+i*10}:00+00:00"
            history.append(obs)

        curr = WeatherObservation.from_dict(self.base_obs.to_dict())
        curr.temperature = 31.42  # 4th identical reading
        curr.timestamp = "2026-09-27T10:00:00+00:00"

        res = self.qc.evaluate(curr, history=history)
        self.assertTrue(res.persistence_flag)
        self.assertTrue(any("frozen" in r.lower() for r in res.flagged_reasons))

    def test_multivariate_consistency_violation(self):
        """Extreme temperature with 98% humidity violates thermodynamic consistency."""
        curr = WeatherObservation.from_dict(self.base_obs.to_dict())
        curr.temperature = 49.0
        curr.humidity = 95.0

        res = self.qc.evaluate(curr)
        self.assertTrue(res.consistency_flag)
        self.assertTrue(any("implausible" in r.lower() for r in res.flagged_reasons))


if __name__ == "__main__":
    unittest.main()

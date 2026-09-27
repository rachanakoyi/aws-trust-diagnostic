"""Unit tests for Data Validation Module."""

import unittest
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from data_sources.schema import WeatherObservation
from qc.validation import DataValidator


class TestDataValidation(unittest.TestCase):
    """Test suite for DataValidator."""

    def setUp(self):
        self.validator = DataValidator(
            temp_min=-10.0, temp_max=50.0,
            pressure_min=900.0, pressure_max=1060.0,
            humidity_min=0.0, humidity_max=100.0
        )
        self.base_obs = WeatherObservation(
            timestamp=datetime.now(timezone.utc).isoformat(),
            station_id="AWS_TEST_01",
            temperature=28.5,
            pressure=1008.2,
            humidity=65.0,
            latitude=28.585,
            longitude=77.209,
            source="TEST"
        )

    def test_nominal_observation_passes(self):
        """Standard observation should pass all checks."""
        res = self.validator.validate(self.base_obs)
        self.assertTrue(res.passed)
        self.assertEqual(res.summary, "VALID")
        self.assertFalse(res.has_missing_values)

    def test_missing_temperature_detected(self):
        """Missing temperature field must be flagged."""
        obs = WeatherObservation.from_dict(self.base_obs.to_dict())
        obs.temperature = None
        res = self.validator.validate(obs)
        self.assertFalse(res.passed)
        self.assertTrue(res.has_missing_values)
        self.assertIn("temperature", res.missing_fields)

    def test_physical_range_violation(self):
        """Extreme temperature out of plausible bounds must be flagged."""
        obs = WeatherObservation.from_dict(self.base_obs.to_dict())
        obs.temperature = 68.0  # Impossible high
        res = self.validator.validate(obs)
        self.assertFalse(res.passed)
        self.assertTrue(any("out of bounds" in v for v in res.physical_range_violations))

    def test_duplicate_flag(self):
        """Duplicate timestamp must be flagged."""
        res = self.validator.validate(self.base_obs, is_duplicate=True)
        self.assertFalse(res.passed)
        self.assertTrue(res.is_duplicate)

    def test_out_of_order_timestamp(self):
        """Earlier timestamp than prior observation must be flagged."""
        now = datetime.now(timezone.utc)
        prev = WeatherObservation.from_dict(self.base_obs.to_dict())
        prev.timestamp = now.isoformat()

        curr = WeatherObservation.from_dict(self.base_obs.to_dict())
        curr.timestamp = (now - timedelta(minutes=15)).isoformat()

        res = self.validator.validate(curr, previous_observation=prev)
        self.assertFalse(res.passed)
        self.assertTrue(res.is_out_of_order)


if __name__ == "__main__":
    unittest.main()

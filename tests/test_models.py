"""Unit tests for AI/ML Models, Evidence Fusion, and Explanation Engine."""

import unittest
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from data_sources.schema import WeatherObservation
from qc.qc_engine import DeterministicQCEngine, QCResult
from models.temporal_model import TemporalAnomalyDetector
from models.multivariate_model import MultivariateAnomalyDetector
from models.evidence_fusion import EvidenceFusionEngine
from models.explanation import ExplanationEngine
from data.synthetic_faults import SyntheticAnomalyGenerator


class TestDiagnosticModels(unittest.TestCase):
    """Test suite for ML detectors, Evidence Fusion, and Explanations."""

    def setUp(self):
        self.qc_engine = DeterministicQCEngine()
        self.temporal_detector = TemporalAnomalyDetector(min_history_required=5)
        self.mv_detector = MultivariateAnomalyDetector()
        self.fusion = EvidenceFusionEngine()
        self.base_obs = WeatherObservation(
            timestamp="2026-09-27T12:00:00+00:00",
            station_id="AWS_MODEL_TEST",
            temperature=31.0,
            pressure=1007.5,
            humidity=55.0,
            latitude=28.585,
            longitude=77.209,
            source="TEST"
        )

    def test_multivariate_detector_normal(self):
        """Standard weather readings should not be flagged by multivariate model."""
        res = self.mv_detector.analyze(self.base_obs)
        self.assertIn("multivariate_anomaly_score", res)
        self.assertFalse(res["multivariate_anomaly_flag"])

    def test_sensor_fault_diagnosis(self):
        """Hard jump or frozen sensor must produce PROBABLE_SENSOR_FAULT."""
        # Previous normal point
        prev = WeatherObservation.from_dict(self.base_obs.to_dict())
        # Severe spike
        fault_obs = SyntheticAnomalyGenerator.inject_temperature_spike(self.base_obs, delta=15.0)

        qc_res = self.qc_engine.evaluate(fault_obs, history=[prev])
        temp_res = {"temporal_anomaly_score": 0.8, "temporal_anomaly_flag": True}
        mv_res = {"multivariate_anomaly_score": 0.75, "multivariate_anomaly_flag": True}

        verdict = self.fusion.fuse(
            current=fault_obs,
            qc_result=qc_res,
            temporal_result=temp_res,
            multivariate_result=mv_res,
            previous_observation=prev
        )

        self.assertEqual(verdict.classification, "PROBABLE_SENSOR_FAULT")
        self.assertGreaterEqual(verdict.confidence, 70.0)
        self.assertIn("Inspect", verdict.recommended_action)

    def test_genuine_squall_event_diagnosis(self):
        """Coupled temp drop + humidity surge must produce PROBABLE_GENUINE_EVENT."""
        prev = WeatherObservation(
            timestamp="2026-09-27T11:50:00+00:00",
            station_id="AWS_MODEL_TEST",
            temperature=34.0,
            pressure=1006.0,
            humidity=45.0,
            latitude=28.585,
            longitude=77.209,
            source="TEST"
        )
        # Downdraft / squall event
        squall_obs = SyntheticAnomalyGenerator.inject_genuine_squall_event(
            prev, temp_drop=6.0, humidity_surge=32.0, pressure_jump=2.0
        )

        qc_res = self.qc_engine.evaluate(squall_obs, history=[prev])
        temp_res = {"temporal_anomaly_score": 0.7, "temporal_anomaly_flag": True}
        mv_res = {"multivariate_anomaly_score": 0.35, "multivariate_anomaly_flag": False}

        verdict = self.fusion.fuse(
            current=squall_obs,
            qc_result=qc_res,
            temporal_result=temp_res,
            multivariate_result=mv_res,
            previous_observation=prev
        )

        self.assertEqual(verdict.classification, "PROBABLE_GENUINE_EVENT")
        self.assertIn("Retain", verdict.recommended_action)

    def test_explanation_engine_structure(self):
        """Explanation must contain rationale, snapshot, and recommended action."""
        prev = WeatherObservation.from_dict(self.base_obs.to_dict())
        fault_obs = SyntheticAnomalyGenerator.inject_temperature_spike(self.base_obs, delta=12.0)
        qc_res = self.qc_engine.evaluate(fault_obs, history=[prev])

        verdict = self.fusion.fuse(
            current=fault_obs,
            qc_result=qc_res,
            temporal_result={"temporal_anomaly_score": 0.7, "temporal_anomaly_flag": True},
            multivariate_result={"multivariate_anomaly_score": 0.6, "multivariate_anomaly_flag": True},
            previous_observation=prev
        )

        explanation = ExplanationEngine.generate_explanation(verdict, fault_obs, previous_observation=prev)
        self.assertIn("WHY WAS THIS FLAGGED?", explanation)
        self.assertIn("DIAGNOSIS:", explanation)
        self.assertIn("RECOMMENDED ACTION:", explanation)
        self.assertIn(str(round(fault_obs.temperature, 1)), explanation)


if __name__ == "__main__":
    unittest.main()

"""Inference pipeline for AWS Observation Trust & Diagnostic Layer.

Coordinates data validation, deterministic QC, temporal ML, multivariate ML,
evidence fusion, explanation generation, and immutable SQLite persistence.
"""

from typing import Dict, Any, List, Optional, Tuple
import logging

from config.settings import settings
from data_sources.schema import WeatherObservation
from database.database import db, Database
from qc.validation import DataValidator, ValidationResult
from qc.qc_engine import DeterministicQCEngine, QCResult
from models.temporal_model import TemporalAnomalyDetector
from models.multivariate_model import MultivariateAnomalyDetector
from models.spatial_analysis import SpatialAnalyzer
from models.evidence_fusion import EvidenceFusionEngine, DiagnosticVerdict
from models.explanation import ExplanationEngine

logger = logging.getLogger(__name__)


class DiagnosticPipeline:
    """End-to-end processing pipeline for AWS observations."""

    def __init__(self, database: Optional[Database] = None):
        self.db = database or db
        self.validator = DataValidator()
        self.qc_engine = DeterministicQCEngine()
        self.temporal_detector = TemporalAnomalyDetector()
        self.multivariate_detector = MultivariateAnomalyDetector()
        self.spatial_analyzer = SpatialAnalyzer()
        self.fusion_engine = EvidenceFusionEngine()
        self.explanation_engine = ExplanationEngine()

    def process_observation(
        self,
        observation: WeatherObservation,
        neighbor_observations: Optional[List[WeatherObservation]] = None,
        persist: bool = True
    ) -> Dict[str, Any]:
        """Process a single observation through the full diagnostic pipeline."""
        station_id = observation.station_id

        # 1. Fetch recent history from DB for temporal context
        recent_records = self.db.get_recent_observations(station_id, limit=30)
        history: List[WeatherObservation] = [
            WeatherObservation.from_dict(r) for r in recent_records
        ]
        prev_obs = history[-1] if history else None

        # 2. Check for duplicate observation in database
        is_dup = self.db.check_duplicate(observation.station_id, observation.timestamp) if persist else False

        # 3. Data Validation
        val_result: ValidationResult = self.validator.validate(
            observation,
            previous_observation=prev_obs,
            is_duplicate=is_dup
        )

        # 4. Deterministic QC Engine
        qc_result: QCResult = self.qc_engine.evaluate(
            current=observation,
            history=history
        )

        # 5. AI/ML Temporal Anomaly Detection
        temporal_result = self.temporal_detector.analyze(
            current=observation,
            history=history
        )

        # 6. AI/ML Multivariate Anomaly Detection
        multivariate_result = self.multivariate_detector.analyze(observation)

        # 7. Optional Spatial Analysis
        spatial_result = self.spatial_analyzer.analyze(
            current=observation,
            neighbor_observations=neighbor_observations
        )

        # 8. Evidence Fusion
        verdict: DiagnosticVerdict = self.fusion_engine.fuse(
            current=observation,
            qc_result=qc_result,
            temporal_result=temporal_result,
            multivariate_result=multivariate_result,
            spatial_result=spatial_result,
            previous_observation=prev_obs
        )

        # 9. Explanation Generation
        explanation_text = self.explanation_engine.generate_explanation(
            verdict=verdict,
            observation=observation,
            previous_observation=prev_obs
        )

        # 10. Immutable Persistence to SQLite
        obs_id: Optional[int] = None
        qc_id: Optional[int] = None
        diag_id: Optional[int] = None

        if persist:
            # Preserve original observation unmodified
            obs_id = self.db.insert_observation(observation)

            qc_id = self.db.insert_qc_result(
                observation_id=obs_id,
                range_flag=qc_result.range_flag,
                rate_flag=qc_result.rate_flag,
                persistence_flag=qc_result.persistence_flag,
                missing_flag=qc_result.missing_flag,
                consistency_flag=qc_result.consistency_flag,
                qc_score=qc_result.qc_score,
                details=qc_result.details
            )

            diag_id = self.db.insert_diagnostic(
                observation_id=obs_id,
                classification=verdict.classification,
                confidence=verdict.confidence,
                temporal_score=verdict.temporal_score,
                multivariate_score=verdict.multivariate_score,
                evidence=verdict.evidence,
                recommended_action=verdict.recommended_action,
                explanation=explanation_text
            )

        return {
            "observation_id": obs_id,
            "qc_id": qc_id,
            "diagnostic_id": diag_id,
            "observation": observation.to_dict(),
            "validation": {
                "passed": val_result.passed,
                "summary": val_result.summary,
                "missing_fields": val_result.missing_fields,
                "range_violations": val_result.physical_range_violations
            },
            "qc_result": qc_result.to_dict(),
            "temporal_result": temporal_result,
            "multivariate_result": multivariate_result,
            "spatial_result": spatial_result,
            "verdict": verdict.to_dict(),
            "explanation": explanation_text
        }


# Singleton pipeline instance
pipeline = DiagnosticPipeline()

"""Multivariate Anomaly Detector for Joint Weather Parameters (T, P, RH).

Analyzes the simultaneous, coupled physical behavior of dry bulb temperature,
atmospheric pressure, and relative humidity. Identifies anomalous combinations
that may appear benign in single-variable checks but violate coupled atmospheric physics.
"""

import numpy as np
from typing import Dict, Any, List, Optional
from sklearn.ensemble import IsolationForest
from sklearn.covariance import EllipticEnvelope

from data_sources.schema import WeatherObservation


class MultivariateAnomalyDetector:
    """Evaluates the multidimensional joint distribution of (Temperature, Pressure, Humidity)."""

    def __init__(self, contamination: float = 0.04):
        self.contamination = contamination
        self.is_initialized = False
        self._init_reference_distribution()

    def _init_reference_distribution(self) -> None:
        """Seed a physically realistic climatological covariance reference for Indian AWS stations.
        
        Covers the joint envelope of standard Indian climate zones:
          - Pre-monsoon dry heat (High T, Low RH, Moderate P)
          - Monsoon humid warmth (Moderate T, High RH, Lower P)
          - Post-monsoon / Winter cool dry (Lower T, Moderate RH, Higher P)
        """
        np.random.seed(42)
        n_samples = 800

        # Cluster 1: Warm/Humid (Monsoon/Coastal)
        t1 = np.random.normal(30.0, 3.5, n_samples // 3)
        rh1 = np.random.normal(80.0, 8.0, n_samples // 3)
        p1 = np.random.normal(1004.0, 4.0, n_samples // 3)

        # Cluster 2: Hot/Dry (Continental/Summer)
        t2 = np.random.normal(38.0, 4.0, n_samples // 3)
        rh2 = np.random.normal(32.0, 10.0, n_samples // 3)
        p2 = np.random.normal(1007.0, 4.0, n_samples // 3)

        # Cluster 3: Cool/Moderate (Winter/Night)
        t3 = np.random.normal(18.0, 4.0, n_samples - 2 * (n_samples // 3))
        rh3 = np.random.normal(65.0, 12.0, n_samples - 2 * (n_samples // 3))
        p3 = np.random.normal(1015.0, 3.5, n_samples - 2 * (n_samples // 3))

        T = np.concatenate([t1, t2, t3])
        RH = np.clip(np.concatenate([rh1, rh2, rh3]), 10.0, 98.0)
        P = np.concatenate([p1, p2, p3])

        X_ref = np.column_stack([T, P, RH])

        self.model = IsolationForest(
            n_estimators=50,
            contamination=self.contamination,
            random_state=42
        )
        self.model.fit(X_ref)

        # Also fit EllipticEnvelope for Mahalanobis-like statistical distance
        self.envelope = EllipticEnvelope(
            contamination=self.contamination,
            random_state=42
        )
        try:
            self.envelope.fit(X_ref)
        except Exception:
            self.envelope = None

        self.is_initialized = True

    def fit_station_history(self, observations: List[WeatherObservation]) -> None:
        """Incrementally calibrate model with genuine observations from local station."""
        valid_points = [
            [o.temperature, o.pressure, o.humidity]
            for o in observations
            if o.temperature is not None and o.pressure is not None and o.humidity is not None
        ]
        if len(valid_points) >= 30:
            X = np.array(valid_points)
            self.model.fit(X)
            if self.envelope:
                try:
                    self.envelope.fit(X)
                except Exception:
                    pass

    def analyze(self, observation: WeatherObservation) -> Dict[str, Any]:
        """Compute multivariate anomaly score for an observation."""
        if (
            observation.temperature is None or
            observation.pressure is None or
            observation.humidity is None
        ):
            return {
                "multivariate_anomaly_score": 0.0,
                "multivariate_anomaly_flag": False,
                "details": {"status": "MISSING_DATA"}
            }

        X = np.array([[
            observation.temperature,
            observation.pressure,
            observation.humidity
        ]])

        # 1. Isolation Forest score
        # decision_function: higher is normal, negative is anomalous
        raw_df = float(self.model.decision_function(X)[0])
        # Map: >= 0.15 is 0.0 (clean), 0.0 is ~0.5, <= -0.15 is 1.0 (anomalous)
        if_score = max(0.0, min(1.0, (0.15 - raw_df) / 0.30))

        # 2. Mahalanobis distance / Envelope score if available
        envelope_dist = 0.0
        if self.envelope:
            try:
                # mahalanobis distance
                dist = float(self.envelope.mahalanobis(X)[0])
                envelope_dist = dist
                # Chi-square with 3 dof: 99th percentile is ~11.3
                env_score = max(0.0, min(1.0, (dist - 7.0) / 10.0))
            except Exception:
                env_score = if_score
        else:
            env_score = if_score

        # Blended score
        combined_score = round(0.6 * if_score + 0.4 * env_score, 3)
        is_flagged = bool(combined_score > 0.58 or raw_df < -0.04)

        return {
            "multivariate_anomaly_score": combined_score,
            "multivariate_anomaly_flag": is_flagged,
            "details": {
                "isolation_decision": round(raw_df, 3),
                "mahalanobis_distance": round(envelope_dist, 2),
                "joint_vector": [
                    round(observation.temperature, 2),
                    round(observation.pressure, 2),
                    round(observation.humidity, 1)
                ]
            }
        }

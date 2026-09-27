"""Temporal Anomaly Detector for AWS Station Observations.

Analyzes the station's recent temporal trajectory using a sliding window
of observations (Temperature, Atmospheric Pressure, Relative Humidity).
Employs rolling Z-score statistical deviation coupled with a lightweight
scikit-learn Isolation Forest on temporal delta features.
"""

import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from sklearn.ensemble import IsolationForest

from data_sources.schema import WeatherObservation


class TemporalAnomalyDetector:
    """Detects deviations from recent station temporal behavior."""

    def __init__(
        self,
        window_size: int = 15,
        z_threshold: float = 3.5,
        contamination: float = 0.03,
        min_history_required: int = 8
    ):
        self.window_size = window_size
        self.z_threshold = z_threshold
        self.contamination = contamination
        self.min_history_required = min_history_required

    def analyze(
        self,
        current: WeatherObservation,
        history: List[WeatherObservation]
    ) -> Dict[str, Any]:
        """Analyze current observation relative to recent temporal history.
        
        Returns:
            Dict containing:
                - temporal_anomaly_score: float [0.0, 1.0]
                - temporal_anomaly_flag: bool
                - deviation_details: Dict with z-scores and isolation score
                - status: 'OK' or 'INSUFFICIENT_HISTORY'
        """
        if current.temperature is None or current.pressure is None or current.humidity is None:
            return {
                "temporal_anomaly_score": 0.0,
                "temporal_anomaly_flag": False,
                "status": "MISSING_DATA",
                "message": "Missing telemetry prevents temporal evaluation"
            }

        # Filter complete observations from history
        valid_history = [
            o for o in history 
            if o.temperature is not None and o.pressure is not None and o.humidity is not None
        ]

        if len(valid_history) < self.min_history_required:
            return {
                "temporal_anomaly_score": 0.0,
                "temporal_anomaly_flag": False,
                "status": "INSUFFICIENT_HISTORY",
                "message": f"INSUFFICIENT HISTORY: {len(valid_history)}/{self.min_history_required} observations. Waiting for more observations before temporal analysis."
            }

        recent = valid_history[-self.window_size:]
        temps = [o.temperature for o in recent]
        press = [o.pressure for o in recent]
        rhs = [o.humidity for o in recent]

        # 1. Rolling Statistical Z-score deviation against recent window mean & std
        mean_t, std_t = float(np.mean(temps)), float(np.std(temps)) or 0.2
        mean_p, std_p = float(np.mean(press)), float(np.std(press)) or 0.3
        mean_rh, std_rh = float(np.mean(rhs)), float(np.std(rhs)) or 1.0

        z_t = abs(current.temperature - mean_t) / std_t
        z_p = abs(current.pressure - mean_p) / std_p
        z_rh = abs(current.humidity - mean_rh) / std_rh
        max_z = max(z_t, z_p, z_rh)

        # 2. Isolation Forest on Temporal Delta Sequences
        # Feature representation: [T, P, RH, delta_T, delta_P, delta_RH]
        features = []
        for i in range(1, len(recent)):
            dt = recent[i].temperature - recent[i-1].temperature
            dp = recent[i].pressure - recent[i-1].pressure
            drh = recent[i].humidity - recent[i-1].humidity
            features.append([
                recent[i].temperature, recent[i].pressure, recent[i].humidity,
                dt, dp, drh
            ])

        # Current feature vector compared to previous point
        curr_dt = current.temperature - recent[-1].temperature
        curr_dp = current.pressure - recent[-1].pressure
        curr_drh = current.humidity - recent[-1].humidity
        curr_vector = np.array([[
            current.temperature, current.pressure, current.humidity,
            curr_dt, curr_dp, curr_drh
        ]])

        if_anomaly_score = 0.0
        if len(features) >= 5:
            try:
                clf = IsolationForest(
                    n_estimators=30,
                    contamination=self.contamination,
                    random_state=42
                )
                clf.fit(np.array(features))
                # decision_function: lower score = more anomalous (negative for outliers)
                raw_score = clf.decision_function(curr_vector)[0]
                # Normalize decision function roughly to [0, 1] range
                # Normal scores are around 0.1 to 0.2, anomalies are < 0
                if_anomaly_score = float(max(0.0, min(1.0, (0.15 - raw_score) / 0.35)))
            except Exception:
                if_anomaly_score = 0.0

        # Combined temporal anomaly score
        # Scale Z-score: z=0 -> 0.0, z=3.5 -> 0.65, z>=5.0 -> 1.0
        z_score_norm = min(1.0, max_z / 4.8)
        combined_score = round(0.55 * z_score_norm + 0.45 * if_anomaly_score, 3)

        # Ensure physical magnitude is also non-trivial (prevent false alarms on micro-noise)
        has_physical_delta = (abs(curr_dt) >= 2.0 or abs(curr_dp) >= 1.5 or abs(curr_drh) >= 12.0)
        is_flagged = bool((max_z > self.z_threshold and has_physical_delta) or (if_anomaly_score > 0.75 and has_physical_delta) or combined_score > 0.68)

        return {
            "temporal_anomaly_score": combined_score,
            "temporal_anomaly_flag": is_flagged,
            "status": "OK",
            "deviation_details": {
                "max_z_score": round(max_z, 2),
                "z_temperature": round(z_t, 2),
                "z_pressure": round(z_p, 2),
                "z_humidity": round(z_rh, 2),
                "isolation_forest_score": round(if_anomaly_score, 3),
                "window_used": len(recent)
            }
        }

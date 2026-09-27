"""Synthetic Fault & Anomaly Generator for AWS Verification and Testing.

Provides controlled, reproducible anomaly injections across physical fault categories:
  1. Temperature Spike (Sensor ADC glitch / electrical pulse)
  2. Temperature Drop (Abrupt hardware discontinuity)
  3. Frozen Sensor (Stuck telemetry / dead sensor repeat)
  4. Gradual Sensor Drift (Calibration bias creeping over time)
  5. Missing Telemetry (Missing mandatory parameters)
  6. Communication Gap (Transmission timeout / telemetry gap)
  7. Humidity Inconsistency (Thermodynamically implausible combination)
  8. Pressure Anomaly (Severe barometric step anomaly)
  9. Genuine Meteorological Squall / Convective Downdraft (Physically coupled event)
"""

import copy
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta

from data_sources.schema import WeatherObservation


class SyntheticAnomalyGenerator:
    """Generates controlled anomalies onto baseline observation series."""

    @staticmethod
    def inject_temperature_spike(
        base_obs: WeatherObservation,
        delta: float = 12.5
    ) -> WeatherObservation:
        """Inject sudden single-step positive temperature jump."""
        obs = copy.deepcopy(base_obs)
        if obs.temperature is not None:
            obs.temperature = round(obs.temperature + delta, 2)
        else:
            obs.temperature = 48.0
        obs.ingestion_status = "SYNTHETIC_TEMP_SPIKE"
        return obs

    @staticmethod
    def inject_temperature_drop(
        base_obs: WeatherObservation,
        delta: float = 14.0
    ) -> WeatherObservation:
        """Inject sudden unphysical negative temperature jump."""
        obs = copy.deepcopy(base_obs)
        if obs.temperature is not None:
            obs.temperature = round(obs.temperature - delta, 2)
        else:
            obs.temperature = 10.0
        obs.ingestion_status = "SYNTHETIC_TEMP_DROP"
        return obs

    @staticmethod
    def inject_frozen_sensor(
        base_series: List[WeatherObservation],
        freeze_steps: int = 5,
        frozen_value: Optional[float] = None
    ) -> List[WeatherObservation]:
        """Generate a sequence where temperature reports the exact same value."""
        series = copy.deepcopy(base_series)
        val = frozen_value if frozen_value is not None else (series[-1].temperature or 31.2)
        for i in range(-freeze_steps, 0):
            if abs(i) <= len(series):
                series[i].temperature = round(val, 2)
                series[i].ingestion_status = "SYNTHETIC_FROZEN_SENSOR"
        return series

    @staticmethod
    def inject_gradual_drift(
        base_series: List[WeatherObservation],
        drift_rate_per_step: float = 0.6,
        drift_steps: int = 8
    ) -> List[WeatherObservation]:
        """Inject progressive uncalibrated drift into temperature sensor."""
        series = copy.deepcopy(base_series)
        n = min(drift_steps, len(series))
        for idx, i in enumerate(range(-n, 0)):
            if series[i].temperature is not None:
                series[i].temperature = round(series[i].temperature + (idx + 1) * drift_rate_per_step, 2)
                series[i].ingestion_status = "SYNTHETIC_SENSOR_DRIFT"
        return series

    @staticmethod
    def inject_missing_telemetry(
        base_obs: WeatherObservation,
        missing_variable: str = "temperature"
    ) -> WeatherObservation:
        """Inject null/missing reading for specified parameter."""
        obs = copy.deepcopy(base_obs)
        if missing_variable == "temperature":
            obs.temperature = None
        elif missing_variable == "pressure":
            obs.pressure = None
        elif missing_variable == "humidity":
            obs.humidity = None
        elif missing_variable == "all":
            obs.temperature = None
            obs.pressure = None
            obs.humidity = None
        obs.ingestion_status = f"SYNTHETIC_MISSING_{missing_variable.upper()}"
        return obs

    @staticmethod
    def inject_communication_gap(
        base_obs: WeatherObservation,
        gap_minutes: int = 65
    ) -> WeatherObservation:
        """Inject temporal jump simulating telemetry drop-out."""
        obs = copy.deepcopy(base_obs)
        try:
            dt = datetime.fromisoformat(obs.timestamp.replace("Z", "+00:00"))
            obs.timestamp = (dt + timedelta(minutes=gap_minutes)).isoformat()
        except Exception:
            pass
        obs.ingestion_status = "SYNTHETIC_COMM_GAP"
        return obs

    @staticmethod
    def inject_humidity_inconsistency(
        base_obs: WeatherObservation
    ) -> WeatherObservation:
        """Inject physically impossible temperature-humidity combination (e.g. 48°C with 96% RH)."""
        obs = copy.deepcopy(base_obs)
        obs.temperature = 48.5
        obs.humidity = 97.0
        obs.ingestion_status = "SYNTHETIC_PHYSICAL_INCONSISTENCY"
        return obs

    @staticmethod
    def inject_pressure_anomaly(
        base_obs: WeatherObservation,
        delta: float = -28.0
    ) -> WeatherObservation:
        """Inject sudden drastic barometric sensor glitch."""
        obs = copy.deepcopy(base_obs)
        if obs.pressure is not None:
            obs.pressure = round(obs.pressure + delta, 2)
        else:
            obs.pressure = 840.0
        obs.ingestion_status = "SYNTHETIC_PRESSURE_ANOMALY"
        return obs

    @staticmethod
    def inject_genuine_squall_event(
        base_obs: WeatherObservation,
        temp_drop: float = 6.2,
        humidity_surge: float = 32.0,
        pressure_jump: float = 2.4
    ) -> WeatherObservation:
        """Inject physically coupled thunderstorm / squall signature.
        
        Demonstrates the genuine meteorological event diagnostic:
          - Sharp drop in temperature (rain-cooled downdraft)
          - Sharp surge in humidity
          - Brief barometric pressure jump (meso-high gust front)
          - Thermodynamic consistency is preserved
        """
        obs = copy.deepcopy(base_obs)
        if obs.temperature is not None:
            obs.temperature = max(10.0, round(obs.temperature - temp_drop, 2))
        if obs.humidity is not None:
            obs.humidity = min(98.0, round(obs.humidity + humidity_surge, 1))
        if obs.pressure is not None:
            obs.pressure = round(obs.pressure + pressure_jump, 2)
        obs.ingestion_status = "SYNTHETIC_GENUINE_SQUALL_EVENT"
        return obs

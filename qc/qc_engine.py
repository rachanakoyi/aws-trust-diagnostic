"""Deterministic Quality Control (QC) Engine for AWS observations.

Implements standard World Meteorological Organization (WMO) and IMD
guidelines for automatic weather stations:
  1. Plausible Climatological Range Check
  2. Rate-of-Change (Step) Check
  3. Sensor Persistence / Frozen Sensor Check
  4. Communication Gap / Missing Data Check
  5. Meteorological Multivariate Consistency Check
"""

import math
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from config.settings import settings
from data_sources.schema import WeatherObservation


@dataclass
class QCResult:
    """Standardized deterministic quality control verdict."""
    range_flag: bool = False
    rate_flag: bool = False
    persistence_flag: bool = False
    missing_flag: bool = False
    consistency_flag: bool = False
    qc_score: float = 0.0  # 0.0 = completely normal, 1.0 = severely anomalous
    details: Dict[str, Any] = field(default_factory=dict)
    flagged_reasons: List[str] = field(default_factory=list)

    @property
    def has_any_flag(self) -> bool:
        """True if any deterministic check flagged an anomaly."""
        return (
            self.range_flag or
            self.rate_flag or
            self.persistence_flag or
            self.missing_flag or
            self.consistency_flag
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert QCResult to dictionary."""
        return asdict(self)


class DeterministicQCEngine:
    """Runs deterministic meteorological quality control checks."""

    def __init__(
        self,
        temp_min: Optional[float] = None,
        temp_max: Optional[float] = None,
        pressure_min: Optional[float] = None,
        pressure_max: Optional[float] = None,
        humidity_min: Optional[float] = None,
        humidity_max: Optional[float] = None,
        max_temp_step: Optional[float] = None,
        max_pressure_step: Optional[float] = None,
        max_humidity_step: Optional[float] = None,
        persistence_window: Optional[int] = None,
        persistence_tolerance: float = 0.05
    ):
        self.temp_min = temp_min if temp_min is not None else settings.temp_min
        self.temp_max = temp_max if temp_max is not None else settings.temp_max
        self.pressure_min = pressure_min if pressure_min is not None else settings.pressure_min
        self.pressure_max = pressure_max if pressure_max is not None else settings.pressure_max
        self.humidity_min = humidity_min if humidity_min is not None else settings.humidity_min
        self.humidity_max = humidity_max if humidity_max is not None else settings.humidity_max

        self.max_temp_step = max_temp_step if max_temp_step is not None else settings.max_temp_step_change
        self.max_pressure_step = max_pressure_step if max_pressure_step is not None else settings.max_pressure_step_change
        self.max_humidity_step = max_humidity_step if max_humidity_step is not None else settings.max_humidity_step_change

        self.persistence_window = persistence_window or settings.persistence_window
        self.persistence_tolerance = persistence_tolerance

    def evaluate(
        self,
        current: WeatherObservation,
        history: Optional[List[WeatherObservation]] = None
    ) -> QCResult:
        """Evaluate an observation against physical limits and recent station history."""
        details: Dict[str, Any] = {}
        flagged_reasons: List[str] = []

        range_flag = False
        rate_flag = False
        persistence_flag = False
        missing_flag = False
        consistency_flag = False

        # ---------------------------------------------------------
        # Check A: Missing / Communication Gap Check
        # ---------------------------------------------------------
        if current.temperature is None or current.pressure is None or current.humidity is None:
            missing_flag = True
            missing_vars = [k for k, v in [
                ("Temperature", current.temperature),
                ("Pressure", current.pressure),
                ("Humidity", current.humidity)
            ] if v is None]
            reason = f"Missing telemetry parameters: {', '.join(missing_vars)}"
            flagged_reasons.append(reason)
            details["missing_check"] = {"passed": False, "missing": missing_vars}
        else:
            details["missing_check"] = {"passed": True}

        # Check gap between current and previous observation timestamp
        prev_obs = history[-1] if history else None
        if prev_obs and current.timestamp and prev_obs.timestamp:
            try:
                curr_dt = datetime.fromisoformat(current.timestamp.replace("Z", "+00:00"))
                prev_dt = datetime.fromisoformat(prev_obs.timestamp.replace("Z", "+00:00"))
                gap_seconds = (curr_dt - prev_dt).total_seconds()
                details["time_gap_seconds"] = gap_seconds
                if gap_seconds > settings.communication_gap_threshold_sec:
                    missing_flag = True
                    gap_min = round(gap_seconds / 60.0, 1)
                    flagged_reasons.append(f"Communication telemetry gap of {gap_min} minutes detected")
                    details["missing_check"] = {"passed": False, "gap_minutes": gap_min}
            except Exception:
                pass

        # ---------------------------------------------------------
        # Check B: Plausible Meteorological Range Check
        # ---------------------------------------------------------
        range_violations = []
        if current.temperature is not None:
            if not (self.temp_min <= current.temperature <= self.temp_max):
                range_violations.append(f"Temp {current.temperature:.1f}°C outside [{self.temp_min}, {self.temp_max}]")
        if current.pressure is not None:
            if not (self.pressure_min <= current.pressure <= self.pressure_max):
                range_violations.append(f"Pressure {current.pressure:.1f} hPa outside [{self.pressure_min}, {self.pressure_max}]")
        if current.humidity is not None:
            if not (self.humidity_min <= current.humidity <= self.humidity_max):
                range_violations.append(f"Humidity {current.humidity:.1f}% outside [{self.humidity_min}, {self.humidity_max}]")

        if range_violations:
            range_flag = True
            flagged_reasons.extend(range_violations)
            details["range_check"] = {"passed": False, "violations": range_violations}
        else:
            details["range_check"] = {"passed": True}

        # ---------------------------------------------------------
        # Check C: Rate-of-Change Check (Step check)
        # ---------------------------------------------------------
        if prev_obs:
            rate_violations = []
            if current.temperature is not None and prev_obs.temperature is not None:
                delta_t = abs(current.temperature - prev_obs.temperature)
                details["delta_temp"] = round(delta_t, 2)
                if delta_t > self.max_temp_step:
                    rate_violations.append(f"Temperature step change {delta_t:.1f}°C exceeds threshold ({self.max_temp_step}°C)")

            if current.pressure is not None and prev_obs.pressure is not None:
                delta_p = abs(current.pressure - prev_obs.pressure)
                details["delta_pressure"] = round(delta_p, 2)
                if delta_p > self.max_pressure_step:
                    rate_violations.append(f"Pressure step change {delta_p:.1f} hPa exceeds threshold ({self.max_pressure_step} hPa)")

            if current.humidity is not None and prev_obs.humidity is not None:
                delta_rh = abs(current.humidity - prev_obs.humidity)
                details["delta_humidity"] = round(delta_rh, 1)
                if delta_rh > self.max_humidity_step:
                    rate_violations.append(f"Humidity step change {delta_rh:.1f}% exceeds threshold ({self.max_humidity_step}%)")

            if rate_violations:
                rate_flag = True
                flagged_reasons.extend(rate_violations)
                details["rate_check"] = {"passed": False, "violations": rate_violations}
            else:
                details["rate_check"] = {"passed": True}
        else:
            details["rate_check"] = {"passed": True, "note": "Insufficient prior observation for rate check"}

        # ---------------------------------------------------------
        # Check D: Sensor Persistence / Frozen Sensor Check
        # ---------------------------------------------------------
        if history and len(history) >= (self.persistence_window - 1):
            window = history[-(self.persistence_window - 1):] + [current]
            frozen_sensors = []

            # Check Temperature
            t_vals = [o.temperature for o in window if o.temperature is not None]
            if len(t_vals) == len(window) and len(t_vals) >= self.persistence_window:
                if (max(t_vals) - min(t_vals)) <= self.persistence_tolerance:
                    frozen_sensors.append(f"Temperature frozen at ~{t_vals[-1]:.2f}°C")

            # Check Pressure
            p_vals = [o.pressure for o in window if o.pressure is not None]
            if len(p_vals) == len(window) and len(p_vals) >= self.persistence_window:
                if (max(p_vals) - min(p_vals)) <= self.persistence_tolerance:
                    frozen_sensors.append(f"Pressure frozen at ~{p_vals[-1]:.2f} hPa")

            # Check Humidity
            rh_vals = [o.humidity for o in window if o.humidity is not None]
            if len(rh_vals) == len(window) and len(rh_vals) >= self.persistence_window:
                if (max(rh_vals) - min(rh_vals)) <= self.persistence_tolerance:
                    frozen_sensors.append(f"Relative humidity frozen at ~{rh_vals[-1]:.1f}%")

            if frozen_sensors:
                persistence_flag = True
                flagged_reasons.extend(frozen_sensors)
                details["persistence_check"] = {"passed": False, "frozen": frozen_sensors}
            else:
                details["persistence_check"] = {"passed": True}
        else:
            details["persistence_check"] = {"passed": True, "note": "Insufficient history for persistence window"}

        # ---------------------------------------------------------
        # Check E: Basic Multivariate Consistency Check
        # ---------------------------------------------------------
        consistency_violations = []
        if current.temperature is not None and current.humidity is not None:
            T = current.temperature
            RH = current.humidity

            # Physical test: Wet-bulb / Dew point impossibility
            # If RH > 0, compute dew point approximation (Magnus-Tetens formula)
            if RH > 0.0:
                try:
                    a, b = 17.27, 237.7
                    alpha = ((a * T) / (b + T)) + math.log(RH / 100.0)
                    dew_point = (b * alpha) / (a - alpha)
                    details["calculated_dew_point"] = round(dew_point, 2)
                    # Dew point cannot exceed dry bulb temperature by more than 0.1°C tolerance
                    if dew_point > (T + 0.1):
                        consistency_violations.append(
                            f"Dew point ({dew_point:.1f}°C) exceeds ambient temperature ({T:.1f}°C)"
                        )
                except (ValueError, ZeroDivisionError):
                    pass

            # Physical test: Extreme tropical heat with saturation
            # e.g., T > 46°C and RH > 85% violates natural atmospheric thermodynamics
            if T > 46.0 and RH > 85.0:
                consistency_violations.append(
                    f"Thermodynamically implausible combination: Temp {T:.1f}°C with RH {RH:.1f}%"
                )

            # Sub-zero temperature with impossible humidity condition
            if T < -10.0 and RH > 98.0:
                consistency_violations.append(
                    f"Supersaturation anomaly at subzero: Temp {T:.1f}°C with RH {RH:.1f}%"
                )

        if consistency_violations:
            consistency_flag = True
            flagged_reasons.extend(consistency_violations)
            details["consistency_check"] = {"passed": False, "violations": consistency_violations}
        else:
            details["consistency_check"] = {"passed": True}

        # ---------------------------------------------------------
        # Deterministic QC Score Computation (0.0 = clean, 1.0 = severe)
        # ---------------------------------------------------------
        score = 0.0
        if range_flag:
            score += 0.35
        if rate_flag:
            score += 0.25
        if persistence_flag:
            score += 0.30
        if missing_flag:
            score += 0.25
        if consistency_flag:
            score += 0.30
        qc_score = min(1.0, round(score, 2))

        return QCResult(
            range_flag=range_flag,
            rate_flag=rate_flag,
            persistence_flag=persistence_flag,
            missing_flag=missing_flag,
            consistency_flag=consistency_flag,
            qc_score=qc_score,
            details=details,
            flagged_reasons=flagged_reasons
        )

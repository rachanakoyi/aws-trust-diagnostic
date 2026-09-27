"""Data validation module for AWS observations.

Checks for missing variables, out-of-order timestamps, duplicate readings,
and extreme physically impossible values. Generates structured validation flags
without ever mutating or deleting the raw observation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from config.settings import settings
from data_sources.schema import WeatherObservation


@dataclass
class ValidationResult:
    """Structured report produced by initial ingest validation."""
    is_valid_format: bool
    missing_fields: List[str] = field(default_factory=list)
    has_missing_values: bool = False
    is_duplicate: bool = False
    is_future_timestamp: bool = False
    is_out_of_order: bool = False
    physical_range_violations: List[str] = field(default_factory=list)
    validation_flags: Dict[str, bool] = field(default_factory=dict)
    summary: str = "VALID"

    @property
    def passed(self) -> bool:
        """Indicates if the observation passed fundamental integrity checks."""
        return (
            not self.has_missing_values and
            not self.is_duplicate and
            not self.is_future_timestamp and
            not self.is_out_of_order and
            len(self.physical_range_violations) == 0
        )


class DataValidator:
    """Validates structural and physical bounds on incoming weather observations."""

    def __init__(
        self,
        temp_min: Optional[float] = None,
        temp_max: Optional[float] = None,
        pressure_min: Optional[float] = None,
        pressure_max: Optional[float] = None,
        humidity_min: Optional[float] = None,
        humidity_max: Optional[float] = None,
        future_tolerance_seconds: int = 300  # 5 min clock skew allowance
    ):
        self.temp_min = temp_min if temp_min is not None else settings.temp_min
        self.temp_max = temp_max if temp_max is not None else settings.temp_max
        self.pressure_min = pressure_min if pressure_min is not None else settings.pressure_min
        self.pressure_max = pressure_max if pressure_max is not None else settings.pressure_max
        self.humidity_min = humidity_min if humidity_min is not None else settings.humidity_min
        self.humidity_max = humidity_max if humidity_max is not None else settings.humidity_max
        self.future_tolerance = timedelta(seconds=future_tolerance_seconds)

    def validate(
        self,
        observation: WeatherObservation,
        previous_observation: Optional[WeatherObservation] = None,
        is_duplicate: bool = False
    ) -> ValidationResult:
        """Run complete deterministic validation suite on an observation."""
        missing: List[str] = []
        violations: List[str] = []
        flags: Dict[str, bool] = {}

        # 1. Missing Values Check
        if observation.temperature is None:
            missing.append("temperature")
        if observation.pressure is None:
            missing.append("pressure")
        if observation.humidity is None:
            missing.append("humidity")
        if not observation.timestamp:
            missing.append("timestamp")

        has_missing = len(missing) > 0
        flags["missing_temperature"] = observation.temperature is None
        flags["missing_pressure"] = observation.pressure is None
        flags["missing_humidity"] = observation.humidity is None

        # 2. Timestamp Integrity Checks
        is_future = False
        is_out_of_order = False
        obs_dt: Optional[datetime] = None

        try:
            # Parse ISO timestamp
            t_str = observation.timestamp.replace("Z", "+00:00")
            obs_dt = datetime.fromisoformat(t_str)
            if obs_dt.tzinfo is None:
                obs_dt = obs_dt.replace(tzinfo=timezone.utc)

            now_utc = datetime.now(timezone.utc)
            if obs_dt > (now_utc + self.future_tolerance):
                is_future = True

            if previous_observation and previous_observation.timestamp:
                prev_t_str = previous_observation.timestamp.replace("Z", "+00:00")
                prev_dt = datetime.fromisoformat(prev_t_str)
                if prev_dt.tzinfo is None:
                    prev_dt = prev_dt.replace(tzinfo=timezone.utc)
                if obs_dt < prev_dt:
                    is_out_of_order = True

        except (ValueError, TypeError):
            missing.append("malformed_timestamp")
            flags["malformed_timestamp"] = True

        flags["is_future_timestamp"] = is_future
        flags["is_out_of_order"] = is_out_of_order
        flags["is_duplicate"] = is_duplicate

        # 3. Physical Plausibility Ranges Check
        if observation.temperature is not None:
            if not (self.temp_min <= observation.temperature <= self.temp_max):
                violations.append(
                    f"Temperature ({observation.temperature:.1f}°C) out of bounds [{self.temp_min}, {self.temp_max}]"
                )
                flags["range_temp_violation"] = True

        if observation.pressure is not None:
            if not (self.pressure_min <= observation.pressure <= self.pressure_max):
                violations.append(
                    f"Pressure ({observation.pressure:.1f} hPa) out of bounds [{self.pressure_min}, {self.pressure_max}]"
                )
                flags["range_pressure_violation"] = True

        if observation.humidity is not None:
            if not (self.humidity_min <= observation.humidity <= self.humidity_max):
                violations.append(
                    f"Humidity ({observation.humidity:.1f}%) out of bounds [{self.humidity_min}, {self.humidity_max}]"
                )
                flags["range_humidity_violation"] = True

        # Summary determination
        summary_reasons = []
        if has_missing:
            summary_reasons.append(f"Missing: {', '.join(missing)}")
        if is_duplicate:
            summary_reasons.append("Duplicate station+time")
        if is_future:
            summary_reasons.append("Future timestamp")
        if is_out_of_order:
            summary_reasons.append("Out of chronological order")
        if violations:
            summary_reasons.append(f"Range violations: {len(violations)}")

        summary = "VALID" if not summary_reasons else "; ".join(summary_reasons)

        return ValidationResult(
            is_valid_format=True,
            missing_fields=missing,
            has_missing_values=has_missing,
            is_duplicate=is_duplicate,
            is_future_timestamp=is_future,
            is_out_of_order=is_out_of_order,
            physical_range_violations=violations,
            validation_flags=flags,
            summary=summary
        )

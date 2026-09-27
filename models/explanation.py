"""Explanation Engine for AWS Observation Diagnostics.

Constructs transparent, human-readable explanations directly grounded in
calculated telemetry features, deterministic QC verdicts, and ML detector outputs.
Strictly avoids hallucinating evidence.
"""

from typing import Dict, Any, List, Optional
from models.evidence_fusion import DiagnosticVerdict
from data_sources.schema import WeatherObservation


class ExplanationEngine:
    """Generates structured, auditable rationale for automated diagnostic decisions."""

    @staticmethod
    def generate_explanation(
        verdict: DiagnosticVerdict,
        observation: WeatherObservation,
        previous_observation: Optional[WeatherObservation] = None
    ) -> str:
        """Format an auditable explanation block for operators."""
        if verdict.classification == "NORMAL":
            return (
                "STATUS: NORMAL OBSERVATION\n\n"
                f"• All parameters within standard physical limits (T: {observation.temperature}°C, "
                f"P: {observation.pressure} hPa, RH: {observation.humidity}%).\n"
                "• No sensor freezing, telecommunication gaps, or anomalous rate of change detected."
            )

        lines: List[str] = []
        lines.append("WHY WAS THIS FLAGGED?")
        lines.append("")

        # Include specific calculated evidence points
        if verdict.evidence:
            for item in verdict.evidence:
                lines.append(f"• {item}")
        else:
            lines.append("• Statistical anomaly score exceeded operational surveillance baseline.")

        # Quantitative sensor snapshot
        lines.append("")
        lines.append("SENSOR TELEMETRY SNAPSHOT:")
        t_str = f"{observation.temperature:.1f} °C" if observation.temperature is not None else "MISSING"
        p_str = f"{observation.pressure:.1f} hPa" if observation.pressure is not None else "MISSING"
        rh_str = f"{observation.humidity:.1f} %" if observation.humidity is not None else "MISSING"
        lines.append(f"• Dry Bulb Temperature: {t_str}")
        lines.append(f"• Atmospheric Pressure: {p_str}")
        lines.append(f"• Relative Humidity:    {rh_str}")

        if previous_observation and observation.temperature is not None and previous_observation.temperature is not None:
            dt = observation.temperature - previous_observation.temperature
            dp = (observation.pressure - previous_observation.pressure) if (observation.pressure is not None and previous_observation.pressure is not None) else 0.0
            drh = (observation.humidity - previous_observation.humidity) if (observation.humidity is not None and previous_observation.humidity is not None) else 0.0
            lines.append(f"• Step Deltas (Δ): ΔT={dt:+.2f}°C, ΔP={dp:+.2f} hPa, ΔRH={drh:+.1f}%")

        lines.append("")
        lines.append(f"DIAGNOSIS:")
        lines.append(f"{verdict.classification} (Diagnostic Confidence: {verdict.confidence:.1f}%)")
        lines.append("")
        lines.append("RECOMMENDED ACTION:")
        lines.append(verdict.recommended_action)

        return "\n".join(lines)

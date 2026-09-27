"""Evidence Fusion Engine for AWS Observation Diagnostics.

Synthesizes deterministic QC results, temporal ML scores, multivariate ML scores,
persistence patterns, and optional spatial analysis into a transparent, three-way
diagnostic assessment:
  1. PROBABLE_SENSOR_FAULT
  2. PROBABLE_GENUINE_EVENT
  3. UNCERTAIN (Human Review Required)
  (or NORMAL when no anomalies are present)
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import math

from qc.qc_engine import QCResult
from data_sources.schema import WeatherObservation


@dataclass
class DiagnosticVerdict:
    """Final diagnostic result produced by the evidence fusion layer."""
    classification: str  # 'NORMAL', 'PROBABLE_SENSOR_FAULT', 'PROBABLE_GENUINE_EVENT', 'UNCERTAIN'
    confidence: float    # Calibrated diagnostic confidence percentage (0.0 to 100.0)
    evidence: List[str]  # Structured bullet points of verified evidence
    recommended_action: str
    temporal_score: float
    multivariate_score: float
    qc_score: float
    is_anomaly: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert diagnostic verdict to dictionary."""
        return {
            "classification": self.classification,
            "confidence": round(self.confidence, 1),
            "evidence": self.evidence,
            "recommended_action": self.recommended_action,
            "temporal_score": round(self.temporal_score, 3),
            "multivariate_score": round(self.multivariate_score, 3),
            "qc_score": round(self.qc_score, 3),
            "is_anomaly": self.is_anomaly
        }


class EvidenceFusionEngine:
    """Multi-source evidence fusion engine based on transparent meteorological criteria."""

    def fuse(
        self,
        current: WeatherObservation,
        qc_result: QCResult,
        temporal_result: Dict[str, Any],
        multivariate_result: Dict[str, Any],
        spatial_result: Optional[Dict[str, Any]] = None,
        previous_observation: Optional[WeatherObservation] = None
    ) -> DiagnosticVerdict:
        """Execute transparent multi-factor evidence fusion."""
        evidence: List[str] = []
        is_anomaly = False

        qc_score = qc_result.qc_score
        temp_score = float(temporal_result.get("temporal_anomaly_score", 0.0))
        mv_score = float(multivariate_result.get("multivariate_anomaly_score", 0.0))

        temp_flag = bool(temporal_result.get("temporal_anomaly_flag", False))
        mv_flag = bool(multivariate_result.get("multivariate_anomaly_flag", False))

        # Check if any detector alerted
        has_qc_alert = qc_result.has_any_flag
        is_anomaly = has_qc_alert or temp_flag or mv_flag

        # -----------------------------------------------------------------
        # Case 0: Normal Observation
        # -----------------------------------------------------------------
        if not is_anomaly:
            evidence.append("All deterministic range and step checks within physical limits")
            evidence.append("Temporal trajectory aligns with recent station trends")
            evidence.append("Multivariate T-P-RH joint covariance is meteorologically coherent")
            if spatial_result and spatial_result.get("is_available"):
                evidence.append(spatial_result.get("status_text"))

            confidence = max(88.0, min(99.0, 100.0 - (qc_score * 30.0 + temp_score * 20.0 + mv_score * 20.0)))

            return DiagnosticVerdict(
                classification="NORMAL",
                confidence=round(confidence, 1),
                evidence=evidence,
                recommended_action="Observation verified. No action required.",
                temporal_score=temp_score,
                multivariate_score=mv_score,
                qc_score=qc_score,
                is_anomaly=False
            )

        # -----------------------------------------------------------------
        # Analyze Specific Evidence Signals
        # -----------------------------------------------------------------
        fault_indicators: List[str] = []
        event_indicators: List[str] = []
        uncertain_indicators: List[str] = []

        # 1. Physical range violation (Unforgiving fault signature)
        if qc_result.range_flag:
            for r in qc_result.flagged_reasons:
                if "outside" in r:
                    fault_indicators.append(f"Hard range violation: {r}")

        # 2. Frozen sensor check (Unambiguous hardware fault signature)
        if qc_result.persistence_flag:
            for r in qc_result.flagged_reasons:
                if "frozen" in r.lower():
                    fault_indicators.append(f"Persistence check: {r} (unvarying sensor output)")

        # 3. Thermodynamic inconsistency check (Hardware calibration fault)
        if qc_result.consistency_flag:
            for r in qc_result.flagged_reasons:
                if "Dew point" in r or "implausible" in r or "Supersaturation" in r:
                    fault_indicators.append(f"Physical consistency violation: {r}")

        # 4. Telemetry missing values or communication gaps
        if qc_result.missing_flag:
            for r in qc_result.flagged_reasons:
                if "Missing" in r or "gap" in r:
                    fault_indicators.append(f"Telemetry integrity issue: {r}")

        # 5. Rate of Change & Temporal / Multivariate Coherence Check
        # Here lies the key distinction between Genuine Meteorological Events and Sensor Glitches:
        # A genuine squall / gust front:
        # - Sharp temperature drop
        # - Simultaneous sharp humidity surge
        # - Pressure perturbation
        # - Thermodynamic consistency IS PRESERVED (no dew point violation, no frozen sensor)
        # An isolated sensor spike:
        # - Only temperature jumps sharply with 0 change in humidity or pressure
        # - Or multivariate detector strongly flags an impossible joint state
        is_coherent_multivariate_event = False
        if previous_observation and current.temperature is not None and previous_observation.temperature is not None:
            delta_t = current.temperature - previous_observation.temperature
            delta_rh = (current.humidity - previous_observation.humidity) if (current.humidity is not None and previous_observation.humidity is not None) else 0.0
            delta_p = (current.pressure - previous_observation.pressure) if (current.pressure is not None and previous_observation.pressure is not None) else 0.0

            # Thunderstorm / Convective Downdraft Signature:
            # Significant temp drop (e.g. <= -2.5°C) accompanied by humidity increase (e.g. >= +8%)
            if delta_t <= -2.5 and delta_rh >= 8.0 and not qc_result.persistence_flag and not qc_result.consistency_flag:
                is_coherent_multivariate_event = True
                event_indicators.append(
                    f"Coupled multi-variable change observed: Temp dropped {abs(delta_t):.1f}°C while Humidity rose {delta_rh:.1f}% (characteristic downdraft/squall signature)"
                )
                if abs(delta_p) >= 1.0:
                    event_indicators.append(f"Accompanying barometric pressure perturbation: {delta_p:+.1f} hPa")

            # Frontal / Diurnal solar heating: gradual coherent shift
            elif abs(delta_t) > 2.0 and not qc_result.range_flag and not qc_result.persistence_flag:
                # If humidity moves in expected opposite direction
                if (delta_t > 0 and delta_rh < -3.0) or (delta_t < 0 and delta_rh > 3.0):
                    is_coherent_multivariate_event = True
                    event_indicators.append("Inverse temperature-humidity relationship consistently preserved across time step")

            # Isolated single variable jump without physical counterpart
            elif (abs(delta_t) > 4.0 and abs(delta_rh) < 2.0) or (abs(delta_rh) > 20.0 and abs(delta_t) < 0.5):
                fault_indicators.append(
                    f"Isolated single-parameter excursion: Delta T={delta_t:+.1f}°C without corresponding humidity or pressure response"
                )

        # Rate of change interpretation: supported by coupled weather vs uncoupled hardware glitch
        if qc_result.rate_flag:
            for r in qc_result.flagged_reasons:
                if "step change" in r:
                    if is_coherent_multivariate_event:
                        event_indicators.append(f"Meso-scale rate-of-change: {r} (supported by coupled atmospheric transition)")
                    else:
                        fault_indicators.append(f"Rate-of-change violation: {r} (unsupported by atmospheric coupling)")

        if temp_flag:
            evidence_str = f"Temporal detector flagged station deviation (score: {temp_score:.2f})"
            if is_coherent_multivariate_event:
                event_indicators.append(evidence_str + " — aligns with rapid meso-scale weather transition")
            else:
                uncertain_indicators.append(evidence_str)

        if mv_flag:
            if not is_coherent_multivariate_event:
                fault_indicators.append(f"Multivariate detector flagged anomalous joint parameter combination (score: {mv_score:.2f})")
            else:
                uncertain_indicators.append(f"Multivariate score elevated ({mv_score:.2f}) during rapid transition")

        # 6. Spatial validation factor
        if spatial_result and spatial_result.get("is_available"):
            if spatial_result.get("spatial_consistent") is True:
                event_indicators.append(spatial_result.get("status_text"))
            elif spatial_result.get("spatial_consistent") is False:
                fault_indicators.append(spatial_result.get("status_text"))
        else:
            evidence.append("Spatial evidence: NOT AVAILABLE")

        # -----------------------------------------------------------------
        # Classification Resolution Logic
        # -----------------------------------------------------------------
        fault_count = len(fault_indicators)
        event_count = len(event_indicators)

        # Rule 1: Definitive Sensor Fault
        # Triggered if hard range violated, frozen sensor, impossible thermodynamics, or multiple strong fault signals
        if (
            qc_result.persistence_flag or
            qc_result.range_flag or
            qc_result.consistency_flag or
            (qc_result.rate_flag and not is_coherent_multivariate_event) or
            (fault_count >= 2 and not is_coherent_multivariate_event)
        ):
            classification = "PROBABLE_SENSOR_FAULT"
            # Calculate calibrated diagnostic confidence
            base_conf = 75.0 + (fault_count * 7.0) + (qc_score * 12.0)
            confidence = min(98.5, round(base_conf, 1))
            evidence.extend(fault_indicators)
            if uncertain_indicators:
                evidence.extend(uncertain_indicators)
            recommended_action = "Inspect sensor hardware, calibration, and telemetry transmission."

        # Rule 2: Probable Genuine Event
        # Triggered if multi-variable changes are physically coupled and no hardware failure indicators
        elif is_coherent_multivariate_event and fault_count == 0 and event_count >= 1:
            classification = "PROBABLE_GENUINE_EVENT"
            base_conf = 72.0 + (event_count * 9.0) + (temp_score * 10.0)
            confidence = min(94.0, round(base_conf, 1))
            evidence.extend(event_indicators)
            if uncertain_indicators:
                evidence.extend(uncertain_indicators)
            recommended_action = "Retain observation in official records and monitor event progression."

        # Rule 3: Uncertain / Human Review Required
        # Conflicting evidence, borderline scores, or insufficient information to decide
        else:
            classification = "UNCERTAIN"
            confidence = round(max(52.0, min(70.0, 50.0 + (temp_score + mv_score + qc_score) * 10.0)), 1)
            evidence.extend(fault_indicators)
            evidence.extend(event_indicators)
            evidence.extend(uncertain_indicators)
            if not evidence:
                evidence.append("Borderline statistical threshold exceeded without conclusive failure signature.")
            recommended_action = "Human review required. Review station history and neighboring observations."

        return DiagnosticVerdict(
            classification=classification,
            confidence=confidence,
            evidence=evidence,
            recommended_action=recommended_action,
            temporal_score=temp_score,
            multivariate_score=mv_score,
            qc_score=qc_score,
            is_anomaly=True
        )

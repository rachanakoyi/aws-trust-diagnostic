"""Streamlit UI components for the AWS Observation Trust & Diagnostic Layer.

Renders executive status cards, telemetry panels, diagnostic evidence checklists,
measurable station health metrics, and operator action triggers.
"""

from typing import Dict, Any, List, Optional
import streamlit as st
from datetime import datetime


def render_top_header_cards(
    source_status: Dict[str, Any],
    station_meta: Any,
    latest_record: Optional[Dict[str, Any]]
) -> None:
    """Render top operational KPI cards and status banners."""
    st.markdown("""
    <div style="background: linear-gradient(90deg, #102a45 0%, #1a365d 100%); padding: 18px 24px; border-radius: 10px; margin-bottom: 20px; color: white;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h2 style="margin: 0; font-size: 24px; font-weight: 700; color: #ffffff;">
                    AWS OBSERVATION TRUST & DIAGNOSTIC SYSTEM
                </h2>
                <p style="margin: 4px 0 0 0; font-size: 13px; color: #cbd5e1;">
                    Ministry of Earth Sciences (MoES) • India Meteorological Department (IMD) • Disaster Management
                </p>
            </div>
            <div style="text-align: right;">
                <span style="background: rgba(255,255,255,0.15); padding: 6px 12px; border-radius: 20px; font-size: 12px; font-weight: 600;">
                    PROTOTYPE v1.0 • LOCAL VERIFIED
                </span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Determine risk level from latest record
    risk_level = "NORMAL"
    risk_color = "#2E7D32"  # Green
    risk_bg = "#E8F5E9"

    if latest_record:
        classification = latest_record.get("classification", "NORMAL")
        if classification == "PROBABLE_SENSOR_FAULT":
            risk_level = "CRITICAL (FAULT)"
            risk_color = "#C62828"
            risk_bg = "#FFEBEE"
        elif classification == "PROBABLE_GENUINE_EVENT":
            risk_level = "EVENT DETECTED"
            risk_color = "#6A1B9A"
            risk_bg = "#F3E5F5"
        elif classification == "UNCERTAIN":
            risk_level = "ELEVATED (REVIEW)"
            risk_color = "#E65100"
            risk_bg = "#FFF3E0"

    # Display 5 Key Metric Cards
    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        source_name = source_status.get("active_source", "FALLBACK PUBLIC WEATHER API")
        is_imd = "IMD" in source_name and "FALLBACK" not in source_name
        badge_color = "#1565C0" if is_imd else "#EF6C00"
        st.markdown(f"""
        <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; background: white; min-height: 95px;">
            <div style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600;">● Data Source</div>
            <div style="font-size: 13px; font-weight: 700; color: {badge_color}; margin-top: 4px;">
                {'SOURCE: IMD AWS' if is_imd else 'SOURCE: FALLBACK PUBLIC WEATHER API'}
            </div>
            <div style="font-size: 10px; color: #94a3b8; margin-top: 2px;">
                {'Authenticated API' if is_imd else 'Open-Meteo Verified'}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; background: white; min-height: 95px;">
            <div style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600;">● Station</div>
            <div style="font-size: 14px; font-weight: 700; color: #1e293b; margin-top: 4px;">
                {station_meta.name if hasattr(station_meta, 'name') else station_meta}
            </div>
            <div style="font-size: 11px; color: #64748b;">
                ID: {station_meta.station_id if hasattr(station_meta, 'station_id') else ''}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        update_time = source_status.get("last_update_time")
        if update_time:
            try:
                time_formatted = datetime.fromisoformat(update_time.replace("Z", "+00:00")).strftime("%H:%M:%S UTC")
            except Exception:
                time_formatted = str(update_time)[:19]
        else:
            time_formatted = "Pending Ingestion"

        st.markdown(f"""
        <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; background: white; min-height: 95px;">
            <div style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600;">● Last Update</div>
            <div style="font-size: 14px; font-weight: 700; color: #1e293b; margin-top: 4px;">
                {time_formatted}
            </div>
            <div style="font-size: 11px; color: #64748b;">
                Poll: {source_status.get('poll_interval_seconds', 10)}s
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c4:
        conn_stat = source_status.get("connection_status", "ONLINE")
        is_ok = "ONLINE" in conn_stat or "FALLBACK_ACTIVE" in conn_stat
        stat_color = "#2E7D32" if is_ok else "#C62828"
        st.markdown(f"""
        <div style="border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; background: white; min-height: 95px;">
            <div style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: 600;">● Connection Status</div>
            <div style="font-size: 13px; font-weight: 700; color: {stat_color}; margin-top: 4px;">
                {conn_stat}
            </div>
            <div style="font-size: 11px; color: #64748b;">
                {source_status.get('observations_received', 0)} packet(s)
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c5:
        st.markdown(f"""
        <div style="border: 1px solid {risk_color}30; border-radius: 8px; padding: 12px; background: {risk_bg}; min-height: 95px;">
            <div style="font-size: 11px; text-transform: uppercase; color: {risk_color}; font-weight: 600;">● Current Risk</div>
            <div style="font-size: 14px; font-weight: 800; color: {risk_color}; margin-top: 4px;">
                {risk_level}
            </div>
            <div style="font-size: 11px; color: {risk_color};">
                Diagnostics Active
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_live_telemetry_panel(latest_record: Optional[Dict[str, Any]]) -> None:
    """Render live telemetry readings with visual status badges."""
    st.subheader("📡 Live Automatic Weather Station Observation")

    if not latest_record:
        st.info("Awaiting live AWS observation packet...")
        return

    t = latest_record.get("temperature")
    p = latest_record.get("pressure")
    rh = latest_record.get("humidity")
    station_id = latest_record.get("station_id", "AWS_UNKNOWN")
    ts = str(latest_record.get("timestamp", ""))

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        val_str = f"{t:.2f} °C" if t is not None else "MISSING"
        st.metric(
            label="🌡️ Dry Bulb Temperature",
            value=val_str,
            delta="Nominal" if t is not None and -10 <= t <= 50 else "Warning"
        )

    with c2:
        val_str = f"{p:.2f} hPa" if p is not None else "MISSING"
        st.metric(
            label="⏱️ Atmospheric Pressure",
            value=val_str,
            delta="Nominal" if p is not None and 900 <= p <= 1050 else "Warning"
        )

    with c3:
        val_str = f"{rh:.1f} %" if rh is not None else "MISSING"
        st.metric(
            label="💧 Relative Humidity",
            value=val_str,
            delta="Nominal" if rh is not None and 5 <= rh <= 98 else "Warning"
        )

    with c4:
        st.markdown(f"""
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 10px; height: 100%;">
            <div style="font-size: 11px; color: #64748b; font-weight: 600;">TELEMETRY META</div>
            <div style="font-size: 13px; font-weight: 600; color: #1e293b; margin-top: 3px;">Station: <code>{station_id}</code></div>
            <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Time: {ts[:19]}</div>
        </div>
        """, unsafe_allow_html=True)


def render_diagnostic_panel(record: Dict[str, Any]) -> None:
    """Render the detailed 3-way diagnosis, confidence, and structured evidence list."""
    classification = record.get("classification", "NORMAL")
    conf = record.get("confidence", 0.0)
    evidence = record.get("evidence", [])
    rec_action = record.get("recommended_action", "No action needed.")
    explanation = record.get("explanation", "")

    st.subheader("🔍 AI/ML Diagnostic Verdict & Evidence Analysis")

    if classification == "PROBABLE_SENSOR_FAULT":
        badge_style = "background: #FFEBEE; border: 2px solid #D32F2F; color: #B71C1C;"
        title_icon = "🚨"
    elif classification == "PROBABLE_GENUINE_EVENT":
        badge_style = "background: #F3E5F5; border: 2px solid #7B1FA2; color: #4A148C;"
        title_icon = "🌪️"
    elif classification == "UNCERTAIN":
        badge_style = "background: #FFF8E1; border: 2px solid #FFA000; color: #E65100;"
        title_icon = "⚠️"
    else:
        badge_style = "background: #E8F5E9; border: 2px solid #388E3C; color: #1B5E20;"
        title_icon = "✅"

    st.markdown(f"""
    <div style="{badge_style} border-radius: 8px; padding: 16px; margin-bottom: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="font-size: 18px; font-weight: 800;">
                {title_icon} DIAGNOSIS: {classification.replace('_', ' ')}
            </div>
            <div style="font-size: 16px; font-weight: 700;">
                Diagnostic Confidence: {conf:.1f}%
            </div>
        </div>
        <div style="font-size: 11px; margin-top: 4px; opacity: 0.85;">
            *Diagnostic confidence is an internal multi-criteria evidence fusion score.
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([3, 2])

    with c1:
        st.markdown("#### Evidence Checklist")
        if isinstance(evidence, list) and evidence:
            for item in evidence:
                if "violation" in item.lower() or "frozen" in item.lower() or "fault" in item.lower() or "isolated" in item.lower():
                    icon = "❌"
                    color = "#c62828"
                elif "genuine" in item.lower() or "coupled" in item.lower() or "consistent" in item.lower() or "aligns" in item.lower():
                    icon = "✓"
                    color = "#2e7d32"
                elif "not available" in item.lower():
                    icon = "ℹ️"
                    color = "#64748b"
                else:
                    icon = "●"
                    color = "#1e293b"

                st.markdown(f"""
                <div style="display: flex; align-items: flex-start; margin-bottom: 6px; font-size: 13px;">
                    <span style="margin-right: 8px; font-weight: bold; color: {color};">{icon}</span>
                    <span style="color: #334155;">{item}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("✓ All deterministic and temporal ML criteria within nominal operating envelopes.")

        st.markdown(f"""
        <div style="background: #f1f5f9; border-left: 4px solid #0f172a; padding: 12px; margin-top: 14px; border-radius: 4px;">
            <div style="font-size: 11px; font-weight: 700; color: #475569; text-transform: uppercase;">Recommended Operator Action:</div>
            <div style="font-size: 13px; font-weight: 600; color: #0f172a; margin-top: 3px;">{rec_action}</div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("#### Auditable Rationale")
        st.text_area(
            label="Structured Explanation Log",
            value=explanation,
            height=200,
            disabled=True,
            help="Structured rationale generated strictly from computed observation telemetry."
        )


def render_station_health_card(health_stats: Dict[str, Any]) -> None:
    """Render measurable station health indicators."""
    st.subheader("🏥 Automatic Weather Station Measurable Health")

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    total = health_stats.get("total_observations", 0)
    avail = health_stats.get("data_availability_pct", 100.0)
    anomalies = health_stats.get("anomalous_count", 0)
    frozen = health_stats.get("frozen_sensor_incidents", 0)
    missing = health_stats.get("missing_data_incidents", 0)
    faults = health_stats.get("fault_alerts", 0)

    with c1:
        st.metric("Total Observations", total)
    with c2:
        st.metric("Data Availability", f"{avail}%", help="Calculated as: 100 × (1 - Missing Obs / Total Obs)")
    with c3:
        st.metric("Recent Anomalies", anomalies)
    with c4:
        st.metric("Frozen Incidents", frozen)
    with c5:
        st.metric("Missing Packets", missing)
    with c6:
        st.metric("Probable Faults", faults)

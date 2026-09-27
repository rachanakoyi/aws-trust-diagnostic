"""Main Streamlit Application for AWS Observation Trust & Diagnostic Layer.

Smart India Hackathon Prototype:
Ministry of Earth Sciences (MoES) / India Meteorological Department (IMD)
Problem: AI/ML-Based Intelligent Anomaly Detection for Automatic Weather Stations (AWS)
"""

import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import time
import copy
from datetime import datetime, timezone
import streamlit as st
import pandas as pd

from config.settings import settings, PRECONFIGURED_STATIONS
from data_sources.schema import WeatherObservation
from pipeline.ingestion import IngestionManager
from pipeline.inference import DiagnosticPipeline
from database.database import db
from data.synthetic_faults import SyntheticAnomalyGenerator
from dashboard.components import (
    render_top_header_cards,
    render_live_telemetry_panel,
    render_diagnostic_panel,
    render_station_health_card
)
from dashboard.charts import create_live_weather_charts
from dashboard.pages.evaluation import render_evaluation_page

# Set Page Config
st.set_page_config(
    page_title="IMD AWS Observation Trust & Diagnostic Layer",
    page_icon="🌦️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -----------------------------------------------------------------
# Session State Initialization
# -----------------------------------------------------------------
if "ingestion_mgr" not in st.session_state:
    st.session_state.ingestion_mgr = IngestionManager()

if "pipeline" not in st.session_state:
    st.session_state.pipeline = DiagnosticPipeline(database=db)

if "selected_station_id" not in st.session_state:
    st.session_state.selected_station_id = settings.default_station_id

if "auto_polling" not in st.session_state:
    st.session_state.auto_polling = False

if "last_poll_time" not in st.session_state:
    st.session_state.last_poll_time = 0

if "station_bootstrapped" not in st.session_state:
    st.session_state.station_bootstrapped = set()

if "selected_alert_idx" not in st.session_state:
    st.session_state.selected_alert_idx = None


def bootstrap_station_if_needed(station_id: str):
    """Seed station history with real observations upon first selection."""
    if station_id not in st.session_state.station_bootstrapped:
        existing = db.get_recent_observations(station_id, limit=5)
        if len(existing) < 5:
            with st.spinner(f"Bootstrapping historical observations for {station_id}..."):
                history = st.session_state.ingestion_mgr.bootstrap_station_history(station_id, past_hours=18)
                for obs in history:
                    st.session_state.pipeline.process_observation(obs, persist=True)
        st.session_state.station_bootstrapped.add(station_id)


# Initial bootstrap
bootstrap_station_if_needed(st.session_state.selected_station_id)


# -----------------------------------------------------------------
# Sidebar Controls & Demo Mode
# -----------------------------------------------------------------
st.sidebar.markdown("""
<div style="background: #1e293b; color: white; padding: 12px; border-radius: 8px; margin-bottom: 15px;">
    <h3 style="margin:0; font-size: 16px; color: #38bdf8;">🎛️ SYSTEM CONTROLS</h3>
    <p style="margin:2px 0 0 0; font-size: 11px; color: #94a3b8;">IMD AWS Operational Console</p>
</div>
""", unsafe_allow_html=True)

# Station Switcher
station_options = list(PRECONFIGURED_STATIONS.keys())
selected_station = st.sidebar.selectbox(
    "Select Automatic Weather Station:",
    options=station_options,
    format_func=lambda sid: f"{sid} - {PRECONFIGURED_STATIONS[sid].name}",
    index=station_options.index(st.session_state.selected_station_id)
)

if selected_station != st.session_state.selected_station_id:
    st.session_state.selected_station_id = selected_station
    bootstrap_station_if_needed(selected_station)
    st.session_state.selected_alert_idx = None
    st.rerun()

station_meta = PRECONFIGURED_STATIONS[selected_station]

# Navigation Tab Selection
app_mode = st.sidebar.radio(
    "Console View:",
    options=["Live Surveillance & Diagnostics", "Model Evaluation & Benchmarks"],
    index=0
)

st.sidebar.markdown("---")

# -----------------------------------------------------------------
# Ingestion Loop Trigger
# -----------------------------------------------------------------
st.sidebar.subheader("📡 Telemetry Stream Ingestion")
col_poll1, col_poll2 = st.sidebar.columns(2)

with col_poll1:
    if st.button("📥 Poll Now", use_container_width=True, help="Fetch latest live observation immediately"):
        with st.spinner("Polling station telemetry..."):
            obs = st.session_state.ingestion_mgr.poll_station(
                station_id=station_meta.station_id,
                latitude=station_meta.latitude,
                longitude=station_meta.longitude
            )
            st.session_state.pipeline.process_observation(obs, persist=True)
            st.session_state.selected_alert_idx = None
            st.success("New packet ingested!")
            st.rerun()

with col_poll2:
    if st.button(
        "⏸️ Pause Stream" if st.session_state.auto_polling else "▶️ Live Auto-Poll",
        use_container_width=True
    ):
        st.session_state.auto_polling = not st.session_state.auto_polling
        st.rerun()

if st.session_state.auto_polling:
    st.sidebar.info(f"🟢 Auto-polling active (Interval: {settings.poll_interval_seconds}s)")

st.sidebar.markdown("---")

# -----------------------------------------------------------------
# Section 32: DEMO MODE & SYNTHETIC FAULT INJECTION CONTROLS
# -----------------------------------------------------------------
st.sidebar.subheader("🧪 Presentation Demo Injection")
st.sidebar.caption(
    "Inject controlled anomalies into a DEMO copy of the telemetry stream to "
    "demonstrate AI diagnostics during hackathon presentation."
)

c_inj1, c_inj2 = st.sidebar.columns(2)

def inject_and_process(modified_obs: WeatherObservation, msg: str):
    """Helper to process synthetic injection and notify."""
    st.session_state.pipeline.process_observation(modified_obs, persist=True)
    st.session_state.selected_alert_idx = None
    st.sidebar.success(msg)
    st.rerun()

with c_inj1:
    if st.button("🌡️ Temp Spike", use_container_width=True, help="Inject +12.5°C unphysical sensor jump"):
        base = st.session_state.ingestion_mgr.poll_station(station_meta.station_id, station_meta.latitude, station_meta.longitude)
        injected = SyntheticAnomalyGenerator.inject_temperature_spike(base, delta=12.5)
        inject_and_process(injected, "Injected Temperature Spike (+12.5°C)")

    if st.button("🧊 Frozen Sensor", use_container_width=True, help="Inject repeating frozen temperature readings"):
        base = st.session_state.ingestion_mgr.poll_station(station_meta.station_id, station_meta.latitude, station_meta.longitude)
        # Inject 5 consecutive identical readings
        val = base.temperature or 31.2
        for i in range(5):
            t_obs = copy.deepcopy(base)
            t_obs.temperature = val
            t_obs.timestamp = datetime.now(timezone.utc).isoformat()
            t_obs.ingestion_status = "SYNTHETIC_FROZEN_SENSOR"
            st.session_state.pipeline.process_observation(t_obs, persist=True)
            time.sleep(0.05)
        st.session_state.selected_alert_idx = None
        st.sidebar.success(f"Injected Frozen Sensor Sequence (~{val}°C)")
        st.rerun()

    if st.button("📉 Temp Drop", use_container_width=True, help="Inject -14°C sudden plunge"):
        base = st.session_state.ingestion_mgr.poll_station(station_meta.station_id, station_meta.latitude, station_meta.longitude)
        injected = SyntheticAnomalyGenerator.inject_temperature_drop(base, delta=14.0)
        inject_and_process(injected, "Injected Temperature Drop (-14°C)")

with c_inj2:
    if st.button("🌪️ Squall Event", use_container_width=True, help="Inject genuine thunderstorm squall signature (ΔT<0, ΔRH>0, ΔP>0)"):
        base = st.session_state.ingestion_mgr.poll_station(station_meta.station_id, station_meta.latitude, station_meta.longitude)
        injected = SyntheticAnomalyGenerator.inject_genuine_squall_event(base, temp_drop=6.0, humidity_surge=30.0, pressure_jump=2.2)
        inject_and_process(injected, "Injected Genuine Squall Signature")

    if st.button("⚠️ Phys Inconsistency", use_container_width=True, help="Inject 48.5°C with 97% RH"):
        base = st.session_state.ingestion_mgr.poll_station(station_meta.station_id, station_meta.latitude, station_meta.longitude)
        injected = SyntheticAnomalyGenerator.inject_humidity_inconsistency(base)
        inject_and_process(injected, "Injected Physical Inconsistency")

    if st.button("🚫 Missing Data", use_container_width=True, help="Inject missing temperature reading"):
        base = st.session_state.ingestion_mgr.poll_station(station_meta.station_id, station_meta.latitude, station_meta.longitude)
        injected = SyntheticAnomalyGenerator.inject_missing_telemetry(base, "temperature")
        inject_and_process(injected, "Injected Missing Telemetry")

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Reset Station DB", use_container_width=True, help="Clear records and re-bootstrap"):
    db.clear_database()
    st.session_state.station_bootstrapped.clear()
    bootstrap_station_if_needed(station_meta.station_id)
    st.session_state.selected_alert_idx = None
    st.sidebar.info("Database reset and re-initialized.")
    st.rerun()

st.sidebar.caption("🔒 Immutable Data Guarantee: Original observations are never altered.")


# -----------------------------------------------------------------
# Main Screen Routing
# -----------------------------------------------------------------
if app_mode == "Model Evaluation & Benchmarks":
    render_evaluation_page()

else:
    # -------------------------------------------------------------
    # Live Operations & Diagnostics Screen
    # -------------------------------------------------------------
    # 1. Fetch current telemetry records from SQLite
    records = db.get_recent_pipeline_records(station_meta.station_id, limit=40)
    latest_record = records[-1] if records else None

    # Handle alert inspector selection
    inspected_record = latest_record
    if st.session_state.selected_alert_idx is not None and 0 <= st.session_state.selected_alert_idx < len(records):
        inspected_record = records[st.session_state.selected_alert_idx]

    # 2. Render Top Header KPI Cards
    source_status = st.session_state.ingestion_mgr.get_status_summary()
    render_top_header_cards(source_status, station_meta, inspected_record)

    # 3. Live Observation Panel
    render_live_telemetry_panel(latest_record)

    st.markdown("<br>", unsafe_allow_html=True)

    # 4. Live Charts (Time vs T, Time vs P, Time vs RH with Anomaly Markers)
    st.subheader("📈 Live Observation Time-Series Surveillance")
    fig = create_live_weather_charts(records)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 5. Diagnostic Panel for Selected / Latest Observation
    if inspected_record:
        render_diagnostic_panel(inspected_record)

    st.markdown("<br>", unsafe_allow_html=True)

    # 6. Operator Action Panel (Section 25)
    st.subheader("👨‍💼 Operator Audit & Decision Panel")
    st.markdown(
        "Meteorological duty officer review. Feedback is stored immutably in SQLite audit trail "
        "and does **not** silently overwrite observation data or trigger unverified model retraining."
    )

    if inspected_record:
        c_act1, c_act2 = st.columns([3, 2])
        obs_id = inspected_record.get("observation_id")
        diag_id = inspected_record.get("diagnostic_id")
        curr_op_action = inspected_record.get("operator_action")

        with c_act1:
            st.markdown(f"**Selected Observation ID:** `{obs_id}` | **Time:** `{inspected_record.get('timestamp')}`")
            if curr_op_action:
                st.info(f"Current Status: **{curr_op_action}** (Recorded at {inspected_record.get('operator_action_time')})")

            operator_choice = st.selectbox(
                "Select Action:",
                options=[
                    "INVESTIGATE",
                    "CONFIRM SENSOR FAULT",
                    "CONFIRM GENUINE EVENT",
                    "MARK FOR HUMAN REVIEW",
                    "DISMISS ALERT"
                ],
                index=0
            )
            op_notes = st.text_input("Operational Notes / Ticket ID:", placeholder="e.g. Field inspection ticket dispatched to Safdarjung technician")

            if st.button("💾 Submit Operator Action", type="primary"):
                action_code = operator_choice.replace(" ", "_")
                db.insert_operator_action(
                    observation_id=obs_id,
                    action=action_code,
                    diagnostic_id=diag_id,
                    notes=op_notes
                )
                st.success(f"Action '{operator_choice}' successfully recorded for Observation #{obs_id}.")
                time.sleep(0.5)
                st.rerun()

        with c_act2:
            st.markdown(f"""
            <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 14px; font-size: 13px;">
                <b style="color: #0f172a;">Observation Audit Trail:</b><br>
                • <b>Raw Temp:</b> {inspected_record.get('temperature')} °C<br>
                • <b>Raw Pressure:</b> {inspected_record.get('pressure')} hPa<br>
                • <b>Raw Humidity:</b> {inspected_record.get('humidity')} %<br>
                • <b>Telemetry Source:</b> {inspected_record.get('source')}<br>
                • <b>Ingestion Status:</b> <code>{inspected_record.get('ingestion_status')}</code><br>
                <div style="margin-top: 8px; font-size: 11px; color: #64748b;">
                    🛡️ Database Guarantee: Raw values stored in <code>observations</code> table are permanently immutable.
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 7. Anomaly Timeline & Station Health
    c_time, c_health = st.columns([3, 2])

    with c_time:
        st.subheader("⏱️ Observation & Anomaly Timeline")
        if records:
            timeline_rows = []
            for idx, r in enumerate(reversed(records)):
                orig_idx = len(records) - 1 - idx
                t_str = pd.to_datetime(r["timestamp"]).strftime("%H:%M:%S")
                cls = r.get("classification", "NORMAL")
                conf = r.get("confidence", 0.0)
                ingest_stat = r.get("ingestion_status", "OK")
                timeline_rows.append({
                    "Index": orig_idx,
                    "Time": t_str,
                    "Classification": cls,
                    "Confidence": f"{conf:.1f}%",
                    "Temp (°C)": r.get("temperature"),
                    "Pressure (hPa)": r.get("pressure"),
                    "Status": ingest_stat
                })

            t_df = pd.DataFrame(timeline_rows)
            st.dataframe(
                t_df[["Time", "Classification", "Confidence", "Temp (°C)", "Pressure (hPa)", "Status"]],
                use_container_width=True,
                height=240,
                hide_index=True
            )

            # Interactive Inspector selector
            idx_select = st.selectbox(
                "Select observation from timeline to inspect evidence:",
                options=list(range(len(records))),
                index=len(records) - 1,
                format_func=lambda i: f"#{records[i]['observation_id']} ({records[i]['timestamp'][:19]}) — {records[i].get('classification', 'NORMAL')}"
            )
            if idx_select != st.session_state.selected_alert_idx:
                st.session_state.selected_alert_idx = idx_select
                st.rerun()

    with c_health:
        health_stats = db.get_station_health_stats(station_meta.station_id, limit=100)
        render_station_health_card(health_stats)

    # -------------------------------------------------------------
    # Auto-polling loop execution
    # -------------------------------------------------------------
    if st.session_state.auto_polling:
        time.sleep(settings.poll_interval_seconds)
        obs = st.session_state.ingestion_mgr.poll_station(
            station_id=station_meta.station_id,
            latitude=station_meta.latitude,
            longitude=station_meta.longitude
        )
        st.session_state.pipeline.process_observation(obs, persist=True)
        st.rerun()

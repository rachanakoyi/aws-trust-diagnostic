"""Plotly interactive charts for AWS Observation Trust & Diagnostic Layer.

Renders synchronized time-series plots for Temperature, Atmospheric Pressure,
and Relative Humidity with distinct visual markers for anomalies and genuine events.
"""

from typing import List, Dict, Any, Optional
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_live_weather_charts(records: List[Dict[str, Any]]) -> go.Figure:
    """Create a 3-row stacked synchronized Plotly chart for T, P, and RH."""
    if not records:
        fig = go.Figure()
        fig.add_annotation(
            text="Waiting for AWS telemetry stream...",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=18, color="#888")
        )
        fig.update_layout(height=400, template="plotly_white")
        return fig

    df = pd.DataFrame(records)
    # Ensure timestamp is parsed nicely
    df["display_time"] = pd.to_datetime(df["timestamp"]).dt.strftime("%H:%M:%S")

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=(
            "Dry Bulb Temperature (°C)",
            "Atmospheric Pressure (hPa)",
            "Relative Humidity (%)"
        )
    )

    # -------------------------------------------------------------
    # 1. Base Continuous Telemetry Lines
    # -------------------------------------------------------------
    fig.add_trace(
        go.Scatter(
            x=df["display_time"],
            y=df["temperature"],
            mode="lines+markers",
            name="Temperature",
            line=dict(color="#FF5722", width=2.5),
            marker=dict(size=5),
            hovertemplate="Time: %{x}<br>Temp: %{y:.2f} °C<extra></extra>"
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=df["display_time"],
            y=df["pressure"],
            mode="lines+markers",
            name="Pressure",
            line=dict(color="#2196F3", width=2.5),
            marker=dict(size=5),
            hovertemplate="Time: %{x}<br>Pressure: %{y:.2f} hPa<extra></extra>"
        ),
        row=2, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=df["display_time"],
            y=df["humidity"],
            mode="lines+markers",
            name="Relative Humidity",
            line=dict(color="#009688", width=2.5),
            marker=dict(size=5),
            hovertemplate="Time: %{x}<br>Humidity: %{y:.1f} %<extra></extra>"
        ),
        row=3, col=1
    )

    # -------------------------------------------------------------
    # 2. Overlay Diagnostic Anomaly Markers
    # -------------------------------------------------------------
    # A. Probable Sensor Faults (Red Diamond)
    fault_mask = df["classification"] == "PROBABLE_SENSOR_FAULT"
    if fault_mask.any():
        faults_df = df[fault_mask]
        for row_idx, var_col in enumerate(["temperature", "pressure", "humidity"], start=1):
            fig.add_trace(
                go.Scatter(
                    x=faults_df["display_time"],
                    y=faults_df[var_col],
                    mode="markers",
                    name="Probable Sensor Fault" if row_idx == 1 else None,
                    showlegend=(row_idx == 1),
                    marker=dict(
                        symbol="diamond",
                        size=11,
                        color="#D32F2F",
                        line=dict(color="#ffffff", width=1.5)
                    ),
                    hovertemplate="FAULT ALERT<br>Time: %{x}<br>Val: %{y}<br>Diagnostic: Sensor Fault<extra></extra>"
                ),
                row=row_idx, col=1
            )

    # B. Probable Genuine Weather Events (Purple / Indigo Star)
    event_mask = df["classification"] == "PROBABLE_GENUINE_EVENT"
    if event_mask.any():
        events_df = df[event_mask]
        for row_idx, var_col in enumerate(["temperature", "pressure", "humidity"], start=1):
            fig.add_trace(
                go.Scatter(
                    x=events_df["display_time"],
                    y=events_df[var_col],
                    mode="markers",
                    name="Probable Genuine Event" if row_idx == 1 else None,
                    showlegend=(row_idx == 1),
                    marker=dict(
                        symbol="star",
                        size=13,
                        color="#7B1FA2",
                        line=dict(color="#ffffff", width=1.5)
                    ),
                    hovertemplate="GENUINE EVENT<br>Time: %{x}<br>Val: %{y}<br>Diagnostic: Genuine Event<extra></extra>"
                ),
                row=row_idx, col=1
            )

    # C. Uncertain / Review (Amber Hexagon)
    uncertain_mask = df["classification"] == "UNCERTAIN"
    if uncertain_mask.any():
        unc_df = df[uncertain_mask]
        for row_idx, var_col in enumerate(["temperature", "pressure", "humidity"], start=1):
            fig.add_trace(
                go.Scatter(
                    x=unc_df["display_time"],
                    y=unc_df[var_col],
                    mode="markers",
                    name="Uncertain / Review" if row_idx == 1 else None,
                    showlegend=(row_idx == 1),
                    marker=dict(
                        symbol="hexagon",
                        size=10,
                        color="#FF8F00",
                        line=dict(color="#ffffff", width=1.5)
                    ),
                    hovertemplate="REVIEW REQUIRED<br>Time: %{x}<br>Val: %{y}<br>Diagnostic: Uncertain<extra></extra>"
                ),
                row=row_idx, col=1
            )

    fig.update_layout(
        height=620,
        margin=dict(l=50, r=30, t=40, b=30),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="center",
            x=0.5,
            font=dict(size=11)
        ),
        hovermode="x unified",
        template="plotly_white"
    )

    fig.update_yaxes(title_text="°C", row=1, col=1)
    fig.update_yaxes(title_text="hPa", row=2, col=1)
    fig.update_yaxes(title_text="%", row=3, col=1)

    return fig

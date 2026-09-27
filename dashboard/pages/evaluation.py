"""Streamlit Evaluation Page for AWS Observation Trust & Diagnostic Layer.

Displays empirical performance metrics, confusion matrices, and the head-to-head
comparison between Baseline QC and the Proposed Evidence Fusion System.
"""

import sys
from pathlib import Path

# Ensure project root in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from evaluation.evaluate import run_benchmark_evaluation


def render_evaluation_page() -> None:
    """Render the comprehensive evaluation dashboard."""
    st.title("📊 Model Evaluation & Benchmark Comparison")
    st.markdown("""
    This evaluation suite executes an empirical, reproducible benchmark comparing:
    * **Baseline System**: Deterministic QC Only (Standard range, rate-of-change, and persistence rules)
    * **Proposed Prototype**: Deterministic QC + Temporal Isolation Forest + Multivariate Model + Evidence Fusion Layer
    """)

    st.info(
        "ℹ️ **Evaluation Integrity Principle**: Metrics below are calculated strictly from controlled "
        "synthetic verification ground-truth labels. The system does NOT falsely claim that unlabeled "
        "real-world observations prove model accuracy without expert meteorological audit."
    )

    if st.button("🚀 Run Empirical Benchmark Suite Now", type="primary"):
        with st.spinner("Running sequential time-series benchmark and computing confusion matrices..."):
            st.session_state["benchmark_results"] = run_benchmark_evaluation()
            st.success("Benchmark completed successfully!")

    results = st.session_state.get("benchmark_results")
    if not results:
        # Run automatically on first view if not present
        with st.spinner("Initializing baseline benchmark metrics..."):
            results = run_benchmark_evaluation()
            st.session_state["benchmark_results"] = results

    # -------------------------------------------------------------
    # 1. Dataset Breakdown
    # -------------------------------------------------------------
    st.subheader("1. Ground Truth Benchmark Dataset Composition")
    ds = results["dataset_summary"]
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Test Observations", ds["total_samples"])
    with c2:
        st.metric("Normal Observations", ds["normal_samples"])
    with c3:
        st.metric("Injected Sensor Faults", ds["fault_samples"], help="Spikes, drops, frozen, missing, drift, pressure glitch")
    with c4:
        st.metric("Genuine Meteorological Events", ds["genuine_event_samples"], help="Coupled thunderstorm squalls / downdrafts")

    st.markdown("---")

    # -------------------------------------------------------------
    # 2. Side-by-Side Model Comparison Table
    # -------------------------------------------------------------
    st.subheader("2. Baseline vs. Proposed Pipeline Performance")

    base_b = results["baseline"]["binary_metrics"]
    prop_b = results["proposed"]["binary_metrics"]

    comparison_df = pd.DataFrame([
        {
            "Metric": "Precision (Anomaly)",
            "Baseline (QC Only)": f"{base_b['precision']:.4f}",
            "Proposed (Fusion Layer)": f"{prop_b['precision']:.4f}",
            "Difference": f"{prop_b['precision'] - base_b['precision']:+.4f}"
        },
        {
            "Metric": "Recall (Detection Coverage)",
            "Baseline (QC Only)": f"{base_b['recall']:.4f}",
            "Proposed (Fusion Layer)": f"{prop_b['recall']:.4f}",
            "Difference": f"{prop_b['recall'] - base_b['recall']:+.4f}"
        },
        {
            "Metric": "F1-Score",
            "Baseline (QC Only)": f"{base_b['f1_score']:.4f}",
            "Proposed (Fusion Layer)": f"{prop_b['f1_score']:.4f}",
            "Difference": f"{prop_b['f1_score'] - base_b['f1_score']:+.4f}"
        },
        {
            "Metric": "False Alarm Rate (FAR)",
            "Baseline (QC Only)": f"{base_b['false_alarm_rate']:.4f}",
            "Proposed (Fusion Layer)": f"{prop_b['false_alarm_rate']:.4f}",
            "Difference": f"{prop_b['false_alarm_rate'] - base_b['false_alarm_rate']:+.4f}"
        },
        {
            "Metric": "Missed Anomaly Rate (MAR)",
            "Baseline (QC Only)": f"{base_b['missed_anomaly_rate']:.4f}",
            "Proposed (Fusion Layer)": f"{prop_b['missed_anomaly_rate']:.4f}",
            "Difference": f"{prop_b['missed_anomaly_rate'] - base_b['missed_anomaly_rate']:+.4f}"
        },
        {
            "Metric": "Average Latency (ms / obs)",
            "Baseline (QC Only)": f"{base_b['avg_latency_ms']:.2f} ms",
            "Proposed (Fusion Layer)": f"{prop_b['avg_latency_ms']:.2f} ms",
            "Difference": f"{prop_b['avg_latency_ms'] - base_b['avg_latency_ms']:+.2f} ms"
        }
    ])

    st.dataframe(comparison_df, use_container_width=True, hide_index=True)

    # -------------------------------------------------------------
    # 3. Core Qualitative Value Proposition
    # -------------------------------------------------------------
    st.subheader("3. Fault vs. Genuine Event Discrimination Advantage")
    st.markdown(f"""
    <div style="background: #eff6ff; border-left: 4px solid #2563eb; padding: 14px; border-radius: 4px; font-size: 14px; line-height: 1.6;">
        <b>Empirical Finding:</b> {results['comparison_delta']['event_discrimination_advantage']}
    </div>
    """, unsafe_allow_html=True)

    # -------------------------------------------------------------
    # 4. Confusion Matrices
    # -------------------------------------------------------------
    st.subheader("4. Confusion Matrices")

    def build_cm_chart(cm_data, colorscale_name):
        x_lbls = ["Predicted Normal", "Predicted Anomaly"]
        y_lbls = ["Actual Normal", "Actual Anomaly"]
        max_val = max(max(r) for r in cm_data) if cm_data else 1
        ann = []
        for i, row in enumerate(cm_data):
            for j, val in enumerate(row):
                ann.append(
                    dict(
                        x=x_lbls[j],
                        y=y_lbls[i],
                        text=f"<b>{val}</b>",
                        showarrow=False,
                        font=dict(color="white" if val > (max_val / 2) else "#1e293b", size=18)
                    )
                )
        chart = go.Figure(
            data=go.Heatmap(
                z=cm_data,
                x=x_lbls,
                y=y_lbls,
                colorscale=colorscale_name,
                showscale=False
            )
        )
        chart.update_layout(
            height=280,
            margin=dict(t=20, b=30, l=110, r=20),
            annotations=ann,
            yaxis=dict(autorange="reversed")
        )
        return chart

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("#### Baseline QC Confusion Matrix")
        fig_cm1 = build_cm_chart(base_b["confusion_matrix"], "Blues")
        st.plotly_chart(fig_cm1, use_container_width=True)

    with c2:
        st.markdown("#### Proposed Pipeline Confusion Matrix")
        fig_cm2 = build_cm_chart(prop_b["confusion_matrix"], "Greens")
        st.plotly_chart(fig_cm2, use_container_width=True)

    # -------------------------------------------------------------
    # 5. Multiclass 3-Way Diagnostic Breakdown
    # -------------------------------------------------------------
    st.subheader("5. 3-Way Diagnostic Classification Breakdown")
    m_classes = results["proposed"]["multiclass_metrics"]["per_class"]
    mc_rows = []
    for cls_name, vals in m_classes.items():
        mc_rows.append({
            "Diagnostic Class": cls_name,
            "Precision": f"{vals['precision']:.3f}",
            "Recall": f"{vals['recall']:.3f}",
            "F1-Score": f"{vals['f1_score']:.3f}",
            "Test Support": vals["support"]
        })
    st.dataframe(pd.DataFrame(mc_rows), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    st.set_page_config(page_title="Evaluation - AWS Diagnostic Layer", layout="wide")
    render_evaluation_page()

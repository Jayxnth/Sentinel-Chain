from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from frontend.data import load_dashboard_data, sidebar_config
from frontend.style import (
    SEVERITY_ORDER,
    apply_theme,
    badge,
    card,
    configure_page,
    global_alert,
    metric_card,
    page_header,
    safe_ts,
)


configure_page("Overview")
apply_theme()
config = sidebar_config()

reports, batches, integrity = load_dashboard_data(config)
global_alert(reports, integrity)

page_header(
    "Security Overview",
    "Live integrity posture, AI findings, and source activity across the monitored estate.",
)

total_batches = len(batches)
tampered_count = sum(1 for item in batches if item.get("integrity_status") == "TAMPERED")
critical_count = sum(1 for item in reports if item.get("severity") == "CRITICAL")
verified_sources = sum(1 for item in integrity.values() if item.get("status") == "VERIFIED")

metric_cols = st.columns(4)
with metric_cols[0]:
    metric_card("Log batches", total_batches, "Stored ingestion events", "accent")
with metric_cols[1]:
    metric_card("AI reports", len(reports), "Generated threat analyses", "purple")
with metric_cols[2]:
    metric_card("Critical findings", critical_count, "Immediate attention", "red" if critical_count else "green")
with metric_cols[3]:
    metric_card("Verified sources", f"{verified_sources}/{max(len(integrity), 1)}", "Passing hash-chain checks", "green")

left, right = st.columns([1.1, 0.9], gap="large")

with left:
    st.subheader("Latest Report")
    latest = reports[0] if reports else None
    if latest:
        body = f"""
        <div class="sc-muted">Batch {latest.get('batch_id', 'n/a')} · {latest.get('source_vm', 'unknown')} · {safe_ts(latest.get('ts'))}</div>
        <p>{latest.get('summary', 'No summary available.')}</p>
        <strong>Recommended action</strong>
        <p>{latest.get('recommendations', 'No recommendation available.')}</p>
        """
        card(f"Report #{latest.get('id', 'n/a')}", body, badge(latest.get("severity"), latest.get("severity")))
    else:
        st.info("No reports available yet.")

with right:
    st.subheader("Source VM Status")
    for vm, data in integrity.items():
        card(
            vm,
            f"""
            <div class="sc-muted">Batch count: {data.get('batch_count', 'unknown')}</div>
            <div class="sc-muted">Tampered batch: {data.get('tampered_batch_id') or 'none'}</div>
            <div class="sc-muted">Last verified: {safe_ts(data.get('last_verified_ts'))}</div>
            """,
            badge(data.get("status"), data.get("status")),
        )

st.subheader("Activity Feed")
if batches:
    activity = pd.DataFrame(batches)
    activity["ts"] = activity["ts"].apply(safe_ts)
    st.dataframe(
        activity[["id", "source_vm", "log_type", "filename", "integrity_status", "ts"]],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No batch activity available.")

chart_left, chart_right = st.columns(2, gap="large")
with chart_left:
    st.subheader("Severity Mix")
    severity_counts = Counter(report.get("severity", "UNKNOWN") for report in reports)
    if severity_counts:
        severity_df = pd.DataFrame(
            [{"severity": key, "count": value} for key, value in severity_counts.items()]
        ).sort_values("severity", key=lambda values: values.map(lambda x: -SEVERITY_ORDER.get(x, -1)))
        st.bar_chart(severity_df, x="severity", y="count", color="#30d5ff")
    else:
        st.info("No severity data yet.")

with chart_right:
    st.subheader("Log Type Volume")
    type_counts = Counter(batch.get("log_type", "unknown") for batch in batches)
    if type_counts:
        type_df = pd.DataFrame([{"log_type": key, "count": value} for key, value in type_counts.items()])
        st.bar_chart(type_df, x="log_type", y="count", color="#31d07f")
    else:
        st.info("No log type data yet.")

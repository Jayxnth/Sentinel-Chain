from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from frontend.data import cached_reports, load_dashboard_data, sidebar_config, vm_options
from frontend.exports import reports_csv, reports_pdf
from frontend.style import (
    LOG_TYPES,
    SEVERITIES,
    apply_theme,
    badge,
    card,
    configure_page,
    global_alert,
    page_header,
    safe_ts,
    split_lines,
)


configure_page("Reports")
apply_theme()
config = sidebar_config()
base_reports, batches, integrity = load_dashboard_data(config)
global_alert(base_reports, integrity)

page_header(
    "Reports",
    "Filter AI-generated investigations, inspect evidence, and export operator-ready artifacts.",
)

filter_cols = st.columns([1, 1, 1, 1])
source_vm = filter_cols[0].selectbox("Source VM", vm_options(base_reports, batches))
log_type = filter_cols[1].selectbox("Log type", LOG_TYPES)
severity = filter_cols[2].selectbox("Severity", SEVERITIES)
page_size = filter_cols[3].number_input("Page size", min_value=5, max_value=50, value=10, step=5)

report_payload = cached_reports(
    config.mode,
    config.base_url,
    config.api_key,
    source_vm=source_vm,
    log_type=log_type,
    severity=severity,
)
reports = report_payload["results"]
total_pages = max(1, math.ceil(len(reports) / page_size))
page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
start = (page - 1) * page_size
visible_reports = reports[start : start + page_size]

export_cols = st.columns([1, 1, 4])
export_cols[0].download_button("CSV", data=reports_csv(reports), file_name="sentinel_reports.csv", mime="text/csv")
export_cols[1].download_button("PDF", data=reports_pdf(reports), file_name="sentinel_reports.pdf", mime="application/pdf")
export_cols[2].caption(f"{len(reports)} report(s) match the current filters")

for report in visible_reports:
    body = f"""
    <div class="sc-muted">Batch {report.get('batch_id', 'n/a')} · {report.get('source_vm', 'unknown')} · {report.get('log_type', 'unknown')} · {safe_ts(report.get('ts'))}</div>
    <p>{report.get('summary', 'No summary available.')}</p>
    """
    card(f"Report #{report.get('id', 'n/a')}", body, badge(report.get("severity"), report.get("severity")))
    with st.expander("Evidence and recommendations"):
        st.markdown("**Findings**")
        for line in split_lines(report.get("findings")):
            st.write(f"- {line}")
        st.markdown("**Recommendations**")
        for line in split_lines(report.get("recommendations")):
            st.write(f"- {line}")

if not visible_reports:
    st.info("No reports match the current filters.")

st.subheader("Report Table")
if reports:
    df = pd.DataFrame(reports)
    if "ts" in df:
        df["ts"] = df["ts"].apply(safe_ts)
    st.dataframe(df, use_container_width=True, hide_index=True)

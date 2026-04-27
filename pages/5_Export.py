from __future__ import annotations

import streamlit as st

from frontend.data import load_dashboard_data, sidebar_config
from frontend.exports import integrity_csv, integrity_pdf, reports_csv, reports_pdf
from frontend.style import apply_theme, configure_page, global_alert, metric_card, page_header


configure_page("Export")
apply_theme()
config = sidebar_config()
reports, batches, integrity = load_dashboard_data(config)
global_alert(reports, integrity)

page_header(
    "Export",
    "Download report and integrity evidence for the demo, handoff, or incident review.",
)

st.subheader("Reports")
report_cols = st.columns([1, 1, 2])
report_cols[0].download_button("Reports CSV", data=reports_csv(reports), file_name="sentinel_reports.csv", mime="text/csv")
report_cols[1].download_button("Reports PDF", data=reports_pdf(reports), file_name="sentinel_reports.pdf", mime="application/pdf")
with report_cols[2]:
    metric_card("Reports included", len(reports), "Current dashboard dataset", "purple")

st.subheader("Integrity")
integrity_cols = st.columns([1, 1, 2])
integrity_cols[0].download_button("Integrity CSV", data=integrity_csv(integrity), file_name="sentinel_integrity.csv", mime="text/csv")
integrity_cols[1].download_button("Integrity PDF", data=integrity_pdf(integrity), file_name="sentinel_integrity.pdf", mime="application/pdf")
with integrity_cols[2]:
    metric_card("Chains included", len(integrity), "Visible source integrity records", "green")

from __future__ import annotations

import streamlit as st

from frontend.data import load_dashboard_data, sidebar_config, vm_options
from frontend.exports import integrity_csv, integrity_pdf
from frontend.style import apply_theme, badge, card, configure_page, global_alert, page_header, safe_ts


configure_page("Integrity")
apply_theme()
config = sidebar_config()
reports, batches, integrity = load_dashboard_data(config)
global_alert(reports, integrity)

page_header(
    "Integrity",
    "Verify hash-chain state and inspect tamper evidence for each source VM.",
)

source_vm = st.selectbox("Source VM", vm_options(reports, batches))
if source_vm != "All":
    integrity = {source_vm: integrity.get(source_vm, {})} if source_vm in integrity else {}

any_tampered = any(data.get("status") == "TAMPERED" for data in integrity.values())
if any_tampered:
    st.markdown('<div class="sc-alert">TAMPERED chain state detected. Treat affected batches as untrusted.</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="sc-okbar">All displayed chains verify successfully.</div>', unsafe_allow_html=True)

export_cols = st.columns([1, 1, 4])
export_cols[0].download_button("CSV", data=integrity_csv(integrity), file_name="sentinel_integrity.csv", mime="text/csv")
export_cols[1].download_button("PDF", data=integrity_pdf(integrity), file_name="sentinel_integrity.pdf", mime="application/pdf")

cols = st.columns(max(1, min(3, len(integrity))))
for index, (vm, data) in enumerate(integrity.items()):
    body = f"""
    <div class="sc-muted">Batch count: {data.get('batch_count', 'unknown')}</div>
    <div class="sc-muted">Tampered batch: {data.get('tampered_batch_id') or 'none'}</div>
    <div class="sc-muted">Last verified: {safe_ts(data.get('last_verified_ts'))}</div>
    """
    with cols[index % len(cols)]:
        card(vm, body, badge(data.get("status", "UNKNOWN"), data.get("status", "UNKNOWN")))
        if data.get("status") == "TAMPERED":
            st.code(
                "\n".join(
                    [
                        f"status: {data.get('status', 'UNKNOWN')}",
                        f"batch_count: {data.get('batch_count', 'unknown')}",
                        f"tampered_batch_id: {data.get('tampered_batch_id')}",
                        f"last_verified_ts: {data.get('last_verified_ts') or 'unknown'}",
                    ]
                )
            )
        else:
            st.code(
                "\n".join(
                    [
                        f"status: {data.get('status', 'UNKNOWN')}",
                        f"batch_count: {data.get('batch_count', 'unknown')}",
                        f"last_verified_ts: {data.get('last_verified_ts') or 'unknown'}",
                    ]
                )
            )

if not integrity:
    st.info("No integrity data available.")

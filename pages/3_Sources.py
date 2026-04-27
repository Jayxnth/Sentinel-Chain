from __future__ import annotations

from collections import Counter, defaultdict

import pandas as pd
import streamlit as st

from frontend.data import load_dashboard_data, sidebar_config
from frontend.style import apply_theme, badge, card, configure_page, global_alert, page_header, safe_ts


configure_page("Sources")
apply_theme()
config = sidebar_config()
reports, batches, integrity = load_dashboard_data(config)
global_alert(reports, integrity)

page_header(
    "Sources",
    "Monitor VM agent status, last-seen activity, and log volume by source.",
)

batch_counts = Counter(batch.get("source_vm", "unknown") for batch in batches)
last_seen = {}
log_volume = defaultdict(Counter)
for batch in batches:
    vm = batch.get("source_vm", "unknown")
    last_seen.setdefault(vm, batch.get("ts"))
    log_volume[vm][batch.get("log_type", "unknown")] += 1

source_cols = st.columns(max(1, min(3, len(set(batch_counts) | set(integrity)))))
for index, vm in enumerate(sorted(set(batch_counts) | set(integrity))):
    data = integrity.get(vm, {})
    body = f"""
    <div class="sc-muted">Last seen: {safe_ts(last_seen.get(vm))}</div>
    <div class="sc-muted">Batch count: {batch_counts.get(vm, data.get('checked_batches', 0))}</div>
    <div class="sc-muted">Tampered batch: {data.get('tampered_batch_id') or 'none'}</div>
    """
    with source_cols[index % len(source_cols)]:
        card(vm, body, badge(data.get("status", "UNKNOWN"), data.get("status", "UNKNOWN")))

st.subheader("Log Volume By VM")
rows = []
for vm, counts in log_volume.items():
    for log_type, count in counts.items():
        rows.append({"source_vm": vm, "log_type": log_type, "count": count})

if rows:
    df = pd.DataFrame(rows)
    st.bar_chart(df, x="source_vm", y="count", color="log_type")
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No source activity available.")

st.subheader("Recent Batches")
if batches:
    table = pd.DataFrame(batches)
    table["ts"] = table["ts"].apply(safe_ts)
    st.dataframe(table, use_container_width=True, hide_index=True)
else:
    st.info("No batches available.")

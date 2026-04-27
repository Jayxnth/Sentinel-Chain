from __future__ import annotations

import streamlit as st

from frontend.api_client import ApiError, SentinelApi
from frontend.data import load_dashboard_data, sidebar_config
from frontend.style import LOG_TYPES, SOURCE_VMS, apply_theme, configure_page, global_alert, page_header, safe_ts


configure_page("NLP Chat")
apply_theme()
config = sidebar_config()
reports, batches, integrity = load_dashboard_data(config)
global_alert(reports, integrity)

page_header(
    "NLP Chat",
    "Ask natural-language questions against retrieved log context, reports, and source filters.",
)

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "assistant", "content": "Ask about the logs, reports, integrity state, or a specific VM."}
    ]

if "chat_source_vm" not in st.session_state:
    st.session_state["chat_source_vm"] = "All"
if "chat_log_type" not in st.session_state:
    st.session_state["chat_log_type"] = "All"


def ask(prompt: str) -> None:
    user_message = {"role": "user", "content": prompt}
    st.session_state["messages"].append(user_message)

    try:
        result = SentinelApi(config).query(
            prompt,
            source_vm=st.session_state["chat_source_vm"],
            log_type=st.session_state["chat_log_type"],
            history=st.session_state["messages"][-8:],
        )
        assistant_message = {
            "role": "assistant",
            "content": result.get("answer", "No answer returned."),
            "citations": result.get("citations", []),
        }
    except ApiError as exc:
        assistant_message = {"role": "assistant", "content": str(exc), "citations": []}
    st.session_state["messages"].append(assistant_message)


def render_message(message: dict) -> None:
    with st.chat_message(message.get("role", "assistant")):
        st.markdown(message.get("content", ""))
        for citation in message.get("citations", []):
            st.caption(
                f"Batch {citation.get('batch_id', 'n/a')} · {citation.get('source_vm', 'unknown')} · "
                f"{safe_ts(citation.get('ts'))}: {citation.get('log_line', '')}"
            )


left_gutter, chat_col, right_gutter = st.columns([0.08, 0.84, 0.08])
with chat_col:
    with st.expander("Context and upload", expanded=False):
        filters = st.columns([1, 1, 1.2])
        source_vm = filters[0].selectbox("Source VM", SOURCE_VMS, key="chat_source_vm")
        log_type = filters[1].selectbox("Log type", LOG_TYPES, key="chat_log_type")
        uploaded = filters[2].file_uploader("Upload log file", type=["log", "txt", "json", "csv"])

        if uploaded is not None:
            upload_cols = st.columns([1, 1, 1])
            upload_vm = upload_cols[0].text_input("Upload source VM", value="vm1-linux")
            upload_type = upload_cols[1].selectbox("Upload log type", LOG_TYPES[1:])
            if upload_cols[2].button("Send upload", use_container_width=True, type="primary"):
                try:
                    result = SentinelApi(config).upload(uploaded, upload_vm, upload_type)
                    st.success(
                        f"{result.get('filename', uploaded.name)} uploaded: "
                        f"{result.get('status', 'ingested')} ({result.get('integrity_status', 'UNKNOWN')})"
                    )
                    st.cache_data.clear()
                except ApiError as exc:
                    st.error(str(exc))

    examples = [
        "What is the most urgent threat right now?",
        "Show suspicious SSH activity on vm1-linux.",
        "Were there malware indicators or outbound callbacks?",
        "Which reports need immediate remediation?",
    ]
    chip_cols = st.columns(2)
    for idx, example in enumerate(examples):
        if chip_cols[idx % 2].button(example, use_container_width=True):
            ask(example)
            st.rerun()

    if st.button("Clear chat", use_container_width=True):
        st.session_state["messages"] = [
            {"role": "assistant", "content": "Ask about the logs, reports, integrity state, or a specific VM."}
        ]
        st.rerun()

    for message in st.session_state["messages"]:
        render_message(message)

prompt = st.chat_input("Ask about threats, reports, remediation, integrity, or a specific VM")
if prompt:
    ask(prompt)
    st.rerun()

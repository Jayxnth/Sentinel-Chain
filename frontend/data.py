from __future__ import annotations

import os

import streamlit as st

from frontend.api_client import ApiConfig, ApiError, SentinelApi
from frontend.style import SOURCE_VMS


def _secret(name: str, default: str = "") -> str:
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def _query_value(name: str) -> str | None:
    try:
        value = st.query_params.get(name)
    except Exception:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _set_query_value(name: str, value: str) -> None:
    try:
        st.query_params[name] = value
    except Exception:
        pass


def _sync_theme_pref() -> None:
    light = bool(st.session_state.get("_theme_light_widget", False))
    st.session_state["theme_light_pref"] = light
    st.session_state["ui_theme"] = "Light" if light else "Dark"
    _set_query_value("theme", "light" if light else "dark")


def _sync_source_pref() -> None:
    mode = st.session_state.get("_data_source_widget", "Live")
    st.session_state["data_source_pref"] = mode
    _set_query_value("source", mode.lower())


def sidebar_config() -> ApiConfig:
    with st.sidebar:
        st.title("Sentinel-Chain")
        st.caption("Autonomous log integrity and AI analysis")
        default_theme = os.getenv("SENTINEL_UI_THEME", _secret("SENTINEL_UI_THEME", "Dark"))
        theme_param = (_query_value("theme") or "").lower()
        if "theme_light_pref" not in st.session_state:
            if theme_param in {"light", "dark"}:
                st.session_state["theme_light_pref"] = theme_param == "light"
            else:
                st.session_state["theme_light_pref"] = default_theme == "Light"
        st.session_state["_theme_light_widget"] = st.session_state["theme_light_pref"]
        light_mode = st.toggle("Light mode", key="_theme_light_widget", on_change=_sync_theme_pref)
        st.session_state["theme_light_pref"] = light_mode
        st.session_state["ui_theme"] = "Light" if light_mode else "Dark"
        st.divider()
        default_url = os.getenv("SENTINEL_API_URL") or _secret("SENTINEL_API_URL", "http://localhost:8000")
        default_key = os.getenv("SENTINEL_API_KEY") or os.getenv("API_KEY") or _secret("SENTINEL_API_KEY", "")
        default_mode = os.getenv("SENTINEL_DATA_SOURCE", _secret("SENTINEL_DATA_SOURCE", "Live"))
        source_param = (_query_value("source") or "").lower()
        if "data_source_pref" not in st.session_state:
            if source_param in {"mock", "live"}:
                st.session_state["data_source_pref"] = source_param.title()
            else:
                st.session_state["data_source_pref"] = default_mode if default_mode in {"Mock", "Live"} else "Live"
        st.session_state["_data_source_widget"] = st.session_state["data_source_pref"]
        mode = st.radio(
            "Data source",
            ["Mock", "Live"],
            horizontal=True,
            key="_data_source_widget",
            on_change=_sync_source_pref,
        )
        st.session_state["data_source_pref"] = mode
        base_url = st.text_input("FastAPI URL", value=st.session_state.get("api_url", default_url))
        api_key = st.text_input(
            "API key",
            value=st.session_state.get("api_key", default_key),
            type="password",
            help="Required for live FastAPI endpoints.",
        )
        st.session_state["api_url"] = base_url
        st.session_state["api_key"] = api_key
        if st.button("Check backend", use_container_width=True):
            try:
                status = SentinelApi(ApiConfig(mode=mode, base_url=base_url, api_key=api_key)).health()
                st.success(f"Backend status: {status.get('status', 'ok')}")
            except ApiError as exc:
                st.error(str(exc))
        st.caption("Mock mode uses the M4 demo dataset. Live mode calls VM3 FastAPI.")
    return ApiConfig(mode=mode, base_url=base_url, api_key=api_key)


@st.cache_data(ttl=30, show_spinner=False)
def cached_reports(mode: str, base_url: str, api_key: str, source_vm: str = "All", log_type: str = "All", severity: str = "All") -> dict:
    return SentinelApi(ApiConfig(mode=mode, base_url=base_url, api_key=api_key)).reports(
        source_vm=source_vm,
        log_type=log_type,
        severity=severity,
        page=1,
        page_size=100,
    )


@st.cache_data(ttl=30, show_spinner=False)
def cached_batches(mode: str, base_url: str, api_key: str, source_vm: str = "All") -> dict:
    return SentinelApi(ApiConfig(mode=mode, base_url=base_url, api_key=api_key)).batches(
        source_vm=source_vm,
        page=1,
        page_size=100,
    )


@st.cache_data(ttl=30, show_spinner=False)
def cached_integrity(mode: str, base_url: str, api_key: str, source_vm: str = "All") -> dict:
    source = None if source_vm == "All" else source_vm
    return SentinelApi(ApiConfig(mode=mode, base_url=base_url, api_key=api_key)).integrity(source)


def load_dashboard_data(config: ApiConfig, source_vm: str = "All") -> tuple[list[dict], list[dict], dict]:
    try:
        reports = cached_reports(config.mode, config.base_url, config.api_key, source_vm=source_vm)["results"]
        batches = cached_batches(config.mode, config.base_url, config.api_key, source_vm=source_vm)["results"]
        integrity = cached_integrity(config.mode, config.base_url, config.api_key, source_vm=source_vm)
        return reports, batches, integrity
    except ApiError as exc:
        st.error(str(exc))
        return [], [], {}


def vm_options(reports: list[dict] | None = None, batches: list[dict] | None = None) -> list[str]:
    values = set(SOURCE_VMS[1:])
    for collection in (reports or [], batches or []):
        for item in collection:
            if isinstance(item, dict):
                vm = item.get("source_vm")
                if vm:
                    values.add(vm)
    return ["All"] + sorted(values)

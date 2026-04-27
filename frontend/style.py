from __future__ import annotations

import html
from datetime import datetime
from typing import Any

import streamlit as st


SEVERITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1, "CLEAN": 0}
LOG_TYPES = ["All", "intrusion", "web", "malware", "http"]
SEVERITIES = ["All", "CRITICAL", "HIGH", "MEDIUM", "LOW", "CLEAN"]
SOURCE_VMS = ["All", "vm1-linux", "vm2-windows"]


def configure_page(title: str) -> None:
    st.set_page_config(page_title=f"Sentinel-Chain | {title}", layout="wide")


def current_theme() -> str:
    if "theme_light_pref" in st.session_state:
        return "Light" if st.session_state["theme_light_pref"] else "Dark"
    if "theme_light" in st.session_state:
        return "Light" if st.session_state["theme_light"] else "Dark"
    try:
        theme_param = str(st.query_params.get("theme", "")).lower()
        if theme_param in {"light", "dark"}:
            return "Light" if theme_param == "light" else "Dark"
    except Exception:
        pass
    value = st.session_state.get("ui_theme", "Dark")
    return "Light" if value == "Light" else "Dark"


def apply_theme() -> None:
    theme = current_theme()
    if theme == "Light":
        tokens = {
            "bg": "#f6f7fb",
            "surface": "#ffffff",
            "surface2": "#f0f3f8",
            "surface3": "#e7ecf3",
            "text": "#182230",
            "muted": "#667085",
            "line": "#d8e0ea",
            "line2": "#c7d1df",
            "accent": "#167f92",
            "accent2": "#6c5ce7",
            "green": "#14804a",
            "red": "#cf2438",
            "amber": "#b65c00",
            "blue": "#2563eb",
            "shadow": "0 14px 34px rgba(24, 34, 48, 0.08)",
            "sidebar": "#ffffff",
            "input": "#ffffff",
            "button": "#182230",
            "button_text": "#ffffff",
        }
    else:
        tokens = {
            "bg": "#0b0f14",
            "surface": "#121820",
            "surface2": "#171f2a",
            "surface3": "#202a37",
            "text": "#eef3f8",
            "muted": "#98a6b8",
            "line": "#263241",
            "line2": "#344154",
            "accent": "#18b7bd",
            "accent2": "#9b8cff",
            "green": "#2fd17c",
            "red": "#ff5268",
            "amber": "#ffb454",
            "blue": "#6aa6ff",
            "shadow": "0 16px 38px rgba(0, 0, 0, 0.26)",
            "sidebar": "#0f151d",
            "input": "#0f151d",
            "button": "#e9f7fb",
            "button_text": "#0b0f14",
        }

    st.markdown(
        f"""
        <style>
        :root {{
            --bg: {tokens["bg"]};
            --surface: {tokens["surface"]};
            --surface-2: {tokens["surface2"]};
            --surface-3: {tokens["surface3"]};
            --text: {tokens["text"]};
            --muted: {tokens["muted"]};
            --line: {tokens["line"]};
            --line-2: {tokens["line2"]};
            --accent: {tokens["accent"]};
            --accent-2: {tokens["accent2"]};
            --green: {tokens["green"]};
            --red: {tokens["red"]};
            --amber: {tokens["amber"]};
            --blue: {tokens["blue"]};
            --shadow: {tokens["shadow"]};
            --sidebar: {tokens["sidebar"]};
            --input: {tokens["input"]};
            --button: {tokens["button"]};
            --button-text: {tokens["button_text"]};
        }}
        html,
        body,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        .main {{
            background: var(--bg) !important;
            color: var(--text) !important;
        }}
        .stApp {{
            background: var(--bg) !important;
            color: var(--text) !important;
        }}
        [data-testid="stHeader"] {{
            background: var(--bg) !important;
            color: var(--text) !important;
            border-bottom: 1px solid var(--line);
        }}
        [data-testid="stToolbar"],
        [data-testid="stStatusWidget"],
        [data-testid="stDecoration"] {{
            background: transparent !important;
            color: var(--muted) !important;
        }}
        .block-container {{
            padding-top: 2rem;
            padding-bottom: 7.5rem;
            max-width: 1320px;
        }}
        [data-testid="stSidebar"] {{
            background: var(--sidebar);
            border-right: 1px solid var(--line);
        }}
        [data-testid="stSidebar"] > div:first-child {{
            padding-top: 1.8rem;
        }}
        h1, h2, h3 {{
            color: var(--text);
            letter-spacing: 0;
        }}
        h1 {{
            font-size: 2rem;
            line-height: 1.15;
            margin-bottom: 0.35rem;
        }}
        h2, h3 {{
            margin-top: 1.1rem;
        }}
        p, li, label, span, div {{
            letter-spacing: 0;
        }}
        .stMarkdown, p, span, div, label {{
            color: inherit;
        }}
        [data-testid="stSidebar"] h1 {{
            font-size: 1.25rem;
            margin-bottom: 0.1rem;
        }}
        [data-testid="stSidebar"] .stCaptionContainer,
        [data-testid="stSidebar"] p {{
            color: var(--muted);
        }}
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        textarea,
        input {{
            background: var(--input) !important;
            border-color: var(--line) !important;
            color: var(--text) !important;
            border-radius: 8px !important;
        }}
        [data-testid="stFileUploader"] section {{
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 8px;
        }}
        [data-testid="stDataFrame"] {{
            border: 1px solid var(--line);
            border-radius: 8px;
            overflow: hidden;
            box-shadow: var(--shadow);
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 4px;
            border-bottom: 1px solid var(--line);
        }}
        .stTabs [data-baseweb="tab"] {{
            border-radius: 8px 8px 0 0;
            color: var(--muted);
        }}
        .stTabs [aria-selected="true"] {{
            background: var(--surface-2);
            color: var(--text);
        }}
        .sc-page-kicker {{
            color: var(--muted);
            font-size: 0.92rem;
            margin-bottom: 0.2rem;
        }}
        .sc-page-title {{
            margin-bottom: 1rem;
        }}
        .sc-grid-spacer {{
            height: 0.45rem;
        }}
        .sc-card {{
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 18px;
            min-height: 100%;
            box-shadow: var(--shadow);
        }}
        .sc-card + .sc-card {{
            margin-top: 12px;
        }}
        .sc-soft {{
            background: var(--surface-2);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 14px 16px;
        }}
        .sc-muted {{
            color: var(--muted);
        }}
        .sc-title-row {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            margin-bottom: 10px;
        }}
        .sc-title-row strong {{
            font-size: 1rem;
            line-height: 1.3;
        }}
        .sc-meta {{
            color: var(--muted);
            font-size: 0.88rem;
            margin-bottom: 8px;
        }}
        .sc-metric {{
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: 8px;
            padding: 17px 18px;
            min-height: 118px;
            box-shadow: var(--shadow);
            position: relative;
            overflow: hidden;
        }}
        .sc-metric:before {{
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: var(--metric-color, var(--accent));
        }}
        .sc-metric-label {{
            color: var(--muted);
            font-size: 0.82rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}
        .sc-metric-value {{
            color: var(--text);
            font-size: 1.85rem;
            font-weight: 750;
            margin-top: 8px;
            line-height: 1.05;
        }}
        .sc-metric-note {{
            color: var(--muted);
            font-size: 0.86rem;
            margin-top: 8px;
        }}
        .sc-badge {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-height: 24px;
            padding: 3px 9px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0;
            border: 1px solid transparent;
            white-space: nowrap;
        }}
        .sc-badge-ok {{
            color: var(--green);
            background: color-mix(in srgb, var(--green) 14%, transparent);
            border-color: color-mix(in srgb, var(--green) 36%, transparent);
        }}
        .sc-badge-bad,
        .sc-badge-critical {{
            color: var(--red);
            background: color-mix(in srgb, var(--red) 14%, transparent);
            border-color: color-mix(in srgb, var(--red) 36%, transparent);
        }}
        .sc-badge-high {{
            color: #e46f2f;
            background: rgba(228, 111, 47, 0.14);
            border-color: rgba(228, 111, 47, 0.34);
        }}
        .sc-badge-medium {{
            color: var(--amber);
            background: color-mix(in srgb, var(--amber) 14%, transparent);
            border-color: color-mix(in srgb, var(--amber) 36%, transparent);
        }}
        .sc-badge-low {{
            color: var(--blue);
            background: color-mix(in srgb, var(--blue) 13%, transparent);
            border-color: color-mix(in srgb, var(--blue) 32%, transparent);
        }}
        .sc-badge-clean {{
            color: var(--green);
            background: color-mix(in srgb, var(--green) 12%, transparent);
            border-color: color-mix(in srgb, var(--green) 32%, transparent);
        }}
        .sc-alert,
        .sc-okbar {{
            border-radius: 8px;
            padding: 13px 15px;
            margin: 0 0 18px 0;
            font-weight: 700;
            box-shadow: var(--shadow);
        }}
        .sc-alert {{
            border: 1px solid color-mix(in srgb, var(--red) 40%, transparent);
            background: color-mix(in srgb, var(--red) 13%, var(--surface));
            color: var(--text);
        }}
        .sc-okbar {{
            border: 1px solid color-mix(in srgb, var(--green) 34%, transparent);
            background: color-mix(in srgb, var(--green) 10%, var(--surface));
            color: var(--text);
        }}
        .stButton > button, .stDownloadButton > button {{
            border-radius: 8px;
            border: 1px solid var(--line);
            background: var(--surface);
            color: var(--text);
            min-height: 40px;
            font-weight: 650;
        }}
        .stButton > button[kind="primary"] {{
            background: var(--button);
            color: var(--button-text);
            border-color: var(--button);
        }}
        .stButton > button:hover, .stDownloadButton > button:hover {{
            border-color: var(--accent);
            color: var(--text);
        }}
        .stExpander {{
            border-color: var(--line) !important;
            border-radius: 8px !important;
            background: var(--surface) !important;
        }}
        pre {{
            background: var(--surface-2) !important;
            border: 1px solid var(--line);
            border-radius: 8px;
        }}
        [data-testid="stChatMessage"] {{
            background: var(--surface) !important;
            border: 1px solid var(--line);
            border-radius: 8px;
            box-shadow: var(--shadow);
            padding: 14px 16px;
            margin: 12px 0;
            max-width: 920px;
        }}
        [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {{
            background: color-mix(in srgb, var(--accent) 10%, var(--surface)) !important;
            border-color: color-mix(in srgb, var(--accent) 30%, var(--line));
        }}
        [data-testid="stChatMessage"] [data-testid="chatAvatarIcon-user"],
        [data-testid="stChatMessage"] [data-testid="chatAvatarIcon-assistant"] {{
            color: var(--text);
        }}
        [data-testid="stChatMessageContent"] {{
            color: var(--text);
            line-height: 1.55;
        }}
        [data-testid="stChatInput"] {{
            max-width: 920px;
            margin: 0 auto;
        }}
        [data-testid="stBottom"],
        [data-testid="stBottomBlockContainer"],
        [data-testid="stChatFloatingInputContainer"],
        div[class*="stChatFloatingInputContainer"] {{
            background: var(--bg) !important;
            border-top: 1px solid var(--line);
            box-shadow: 0 -18px 34px color-mix(in srgb, var(--bg) 92%, transparent);
        }}
        [data-testid="stChatInput"] > div,
        [data-testid="stChatInput"] [data-baseweb="textarea"] {{
            background: var(--surface) !important;
            border-color: var(--line) !important;
            border-radius: 8px !important;
        }}
        [data-testid="stChatInput"] textarea {{
            background: var(--surface) !important;
            border: 1px solid var(--line) !important;
            border-radius: 8px;
            box-shadow: var(--shadow);
            color: var(--text) !important;
            caret-color: var(--text) !important;
        }}
        [data-testid="stChatInput"] textarea::placeholder {{
            color: var(--muted) !important;
            opacity: 0.9;
        }}
        [data-testid="stChatInputSubmitButton"] {{
            background: var(--surface-2) !important;
            border: 1px solid var(--line) !important;
            color: var(--text) !important;
            border-radius: 8px !important;
        }}
        [data-testid="stChatInputSubmitButton"]:hover {{
            border-color: var(--accent) !important;
            color: var(--accent) !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def badge(label: Any, kind: str | None = None) -> str:
    text = html.escape(str(label or "UNKNOWN"))
    normalized = str(kind or label or "").lower()
    if normalized == "verified":
        cls = "sc-badge-ok"
    elif normalized == "tampered":
        cls = "sc-badge-bad"
    elif normalized in {"critical", "high", "medium", "low", "clean"}:
        cls = f"sc-badge-{normalized}"
    else:
        cls = "sc-badge-low"
    return f'<span class="sc-badge {cls}">{text}</span>'


def card(title: str, body: str, badge_html: str = "") -> None:
    st.markdown(
        f"""
        <div class="sc-card">
            <div class="sc-title-row">
                <strong>{html.escape(title)}</strong>
                {badge_html}
            </div>
            <div>{body}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="sc-page-title">
            <div class="sc-page-kicker">Sentinel-Chain</div>
            <h1>{html.escape(title)}</h1>
            <div class="sc-muted">{html.escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: Any, note: str = "", color: str = "accent") -> None:
    color_map = {
        "accent": "var(--accent)",
        "green": "var(--green)",
        "red": "var(--red)",
        "amber": "var(--amber)",
        "blue": "var(--blue)",
        "purple": "var(--accent-2)",
    }
    css_color = color_map.get(color, color)
    st.markdown(
        f"""
        <div class="sc-metric" style="--metric-color: {css_color};">
            <div class="sc-metric-label">{html.escape(label)}</div>
            <div class="sc-metric-value">{html.escape(str(value))}</div>
            <div class="sc-metric-note">{html.escape(note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def global_alert(reports: list[dict[str, Any]], integrity: dict[str, Any]) -> None:
    critical = [r for r in reports if str(r.get("severity", "")).upper() == "CRITICAL"]
    tampered = [vm for vm, data in integrity.items() if str(data.get("status", "")).upper() == "TAMPERED"]
    if critical or tampered:
        parts = []
        if critical:
            parts.append(f"{len(critical)} critical finding(s)")
        if tampered:
            parts.append(f"tamper detected on {', '.join(tampered)}")
        st.markdown(f'<div class="sc-alert">Active security alert: {"; ".join(parts)}.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="sc-okbar">All monitored sources are currently verified.</div>', unsafe_allow_html=True)


def safe_ts(value: Any) -> str:
    if not value:
        return "unknown"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(value)


def split_lines(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return [line.strip(" -") for line in str(value).splitlines() if line.strip()]

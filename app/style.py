"""style.py — shared CSS for the RMB 3T Export Intelligence tool.

Structure and selectors are taken from the reference `style_template.py` in
RMB_UI_Design_System.md §6. Only the THEME colours differ, plus the Cambria
typography rule (FinIntel R4.1-4.3).

Do not edit _css() selectors without checking getComputedStyle() on the live
app — Streamlit has shipped two different tab-markup implementations and every
selector below is deliberately duplicated to cover both.
"""
from __future__ import annotations

import streamlit as st

# --- Confirmed palette: RMB green + gold (spec §9.1) ------------------------
THEME = {
    "brand_dark":              "#1A5C38",   # RMB green — gradient start, active sidebar pill
    "brand_accent":            "#C8960A",   # RMB gold  — gradient end
    "secondary_amber":         "#C8960A",

    "tab_inactive_bg":         "#D9D9D9",
    "tab_inactive_text":       "#888888",
    "tab_inactive_hover_bg":   "#CBCBCB",
    "tab_inactive_hover_text": "#444444",

    "tab_active_bg":           "#E8F5EE",
    "tab_active_text":         "#1A5C38",
    "tab_active_border":       "#1A5C38",
    "tab_list_border":         "#D8E8DC",

    "expander_bg":             "#F2FAF5",

    "sidebar_text":            "#2D3E35",
    "sidebar_hover_bg":        "#E8F5EE",

    "alert_bg":                "#FDECEA",
    "alert_text":              "#C00000",
    "alert_border":            "#F1A9A5",

    "warn_bg":                 "#FFF8E1",
    "warn_text":               "#8A6100",
    "warn_border":             "#E8C97A",

    "info_bg":                 "#F2FAF5",
    "info_text":               "#1A5C38",
    "info_border":             "#B7DCC6",

    # A fourth, deliberately distinct family for a strategic observation that
    # is neither a data-quality warning (amber) nor a routine note (green) —
    # e.g. the competitive-dynamics remark on the Worst Traders tab. Indigo/
    # blue reads as "insight" rather than "caution", so it doesn't get
    # visually lumped in with the other two.
    "insight_bg":              "#EEF1FD",
    "insight_text":            "#2C3E9E",
    "insight_border":          "#B9C2F0",
}

HEADING_FONT = "Cambria, 'Times New Roman', Georgia, serif"
MONO_FONT = "'Cascadia Mono', Consolas, 'Courier New', monospace"


def _css(t: dict) -> str:
    return f"""
<style>
/* --- Typography: Cambria for headings and prominent labels (R4.1);
   Streamlit default for body text and tables (R4.2); mono for codes (R4.3). --- */
h1, h2, h3, h4,
div[data-testid="stMetricLabel"],
.stTabs [data-baseweb="tab"], .stTabs [data-testid="stTab"] {{
    font-family: {HEADING_FONT} !important;
}}
code, kbd, pre {{ font-family: {MONO_FONT} !important; }}

/* --- Tabs: bold oversized labels; flat gray pills (rounded at the top only)
   for inactive tabs; light tint + solid underline for the active tab. Both
   BaseWeb and react-aria markup covered. --- */
.stTabs [data-baseweb="tab-list"],
.stTabs [role="tablist"] {{
    gap: 6px;
    background: transparent;
    border-bottom: 2px solid {t["tab_list_border"]};
    flex-wrap: wrap;
}}
.stTabs [data-baseweb="tab"],
.stTabs [data-testid="stTab"] {{
    font-weight: 700;
    font-size: 17px;
    padding: 10px 22px;
    border-radius: 8px 8px 0 0;
    color: {t["tab_inactive_text"]} !important;
    background: {t["tab_inactive_bg"]} !important;
    border-bottom: 3px solid transparent !important;
}}
.stTabs [data-baseweb="tab"] p,
.stTabs [data-testid="stTab"] p {{
    font-size: inherit !important;
    font-weight: inherit !important;
    color: inherit !important;
}}
.stTabs [data-baseweb="tab"]:hover,
.stTabs [data-testid="stTab"]:hover {{
    background: {t["tab_inactive_hover_bg"]} !important;
    color: {t["tab_inactive_hover_text"]} !important;
}}
.stTabs [aria-selected="true"] {{
    color: {t["tab_active_text"]} !important;
    background: {t["tab_active_bg"]} !important;
    border-bottom: 3px solid {t["tab_active_border"]} !important;
    font-weight: 700;
}}
.stTabs [aria-selected="true"]:hover {{
    background: {t["tab_active_bg"]} !important;
    color: {t["tab_active_text"]} !important;
}}
.stTabs [data-baseweb="tab-highlight"] {{ background-color: transparent !important; }}

/* --- Expanders --- */
.streamlit-expanderHeader, div[data-testid="stExpander"] summary {{
    font-weight: 600;
    background-color: {t["expander_bg"]};
    border-radius: 6px;
}}

/* --- Page header: st.title() must be the ONLY bare <h1> in the app. --- */
div[data-testid="stHeading"]:has(h1) {{
    background: linear-gradient(135deg, {t["brand_dark"]} 0%, {t["brand_accent"]} 100%);
    padding: 24px 32px;
    border-radius: 14px;
    margin-bottom: 18px;
}}
div[data-testid="stHeading"]:has(h1) h1 {{
    color: #FFFFFF !important;
    margin: 0;
}}

/* --- Sidebar nav as a vertical pill strip --- */
[data-testid="stSidebarNav"] [data-testid="stSidebarNavLink"] {{
    border-radius: 8px;
    margin: 2px 10px;
    padding: 10px 14px !important;
    font-weight: 600;
    color: {t["sidebar_text"]} !important;
    transition: background-color 0.15s ease;
}}
[data-testid="stSidebarNav"] [data-testid="stSidebarNavLink"] span,
[data-testid="stSidebarNav"] [data-testid="stSidebarNavLink"] p {{
    color: inherit !important;
    font-weight: inherit !important;
}}
[data-testid="stSidebarNav"] [data-testid="stSidebarNavLink"]:hover {{
    background-color: {t["sidebar_hover_bg"]} !important;
}}
[data-testid="stSidebarNav"] [data-testid="stSidebarNavLink"][aria-current="page"] {{
    background-color: {t["brand_dark"]} !important;
    color: #FFFFFF !important;
    font-weight: 700;
}}
[data-testid="stSidebarNav"] [data-testid="stSidebarNavLink"][aria-current="page"]:hover {{
    background-color: {t["brand_dark"]} !important;
}}

/* --- Section banner (ALL-CAPS, brand green) --- */
.t3i-section {{
    font-family: {HEADING_FONT};
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 700;
    font-size: 15px;
    color: #FFFFFF;
    background: {t["brand_dark"]};
    padding: 8px 16px;
    border-radius: 6px;
    margin: 18px 0 10px 0;
}}
</style>
"""


_CSS = _css(THEME)


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def section(title: str) -> None:
    """ALL-CAPS brand section banner."""
    st.markdown(f"<div class='t3i-section'>{title}</div>", unsafe_allow_html=True)


def _card(msg: str, icon: str, bg: str, fg: str, border: str) -> None:
    st.markdown(
        f"<div style='color:{fg}; font-weight:600; padding:12px 16px; "
        f"background:{bg}; border:1px solid {border}; border-radius:8px; "
        f"margin-bottom:10px;'>{icon} {msg}</div>",
        unsafe_allow_html=True,
    )


def red_alert(message: str, icon: str = "\U0001F6A8") -> None:
    _card(message, icon, THEME["alert_bg"], THEME["alert_text"], THEME["alert_border"])


def warn_banner(message: str, icon: str = "\u26A0\uFE0F") -> None:
    _card(message, icon, THEME["warn_bg"], THEME["warn_text"], THEME["warn_border"])


def info_banner(message: str, icon: str = "\u2139\uFE0F") -> None:
    _card(message, icon, THEME["info_bg"], THEME["info_text"], THEME["info_border"])


def insight_banner(message: str, icon: str = "\U0001F4A1") -> None:
    """A strategic-observation callout — visually distinct (indigo) from the
    amber data-quality warning and the green routine note, so a reader's eye
    doesn't lump this in with either."""
    _card(message, icon, THEME["insight_bg"], THEME["insight_text"],
          THEME["insight_border"])

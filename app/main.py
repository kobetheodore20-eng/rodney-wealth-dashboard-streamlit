from __future__ import annotations

import hmac
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import AUTHORITY_BOUNDARY, SOURCE_WORKBOOK, SOURCE_WORKBOOK_LABEL
from app.data_store import local_writes_enabled, money, read_price_cache, read_table, write_table
from app.insights import (
    banker_signals,
    monthly_attribution,
    portfolio_watchlist,
    property_debt_snapshot,
    update_checklist,
    wealth_scorecard,
    workbook_coverage,
)
from app.market_prices import is_trackable_ticker, refresh_prices
from app.monthly_update import build_monthly_update_frame
from app.portfolio import (
    allocation_view,
    executive_brief,
    holdings_with_live_prices,
    latest_month_bridge,
    monthly_change_view,
    numeric,
    price_source_view,
    risk_summary,
    stress_view,
    summary_metrics,
)


st.set_page_config(page_title="Rodney Wealth Cockpit", page_icon="RW", layout="wide")

st.markdown(
    """
    <style>
    :root {
      --ink: #121212;
      --soft-ink: #343638;
      --muted: #777b80;
      --hairline: rgba(18, 18, 18, 0.11);
      --paper: #f6f6f3;
      --panel: rgba(255, 255, 255, 0.78);
      --panel-solid: #ffffff;
      --mist: #e9e9e4;
      --blue: #435d67;
      --green: #2f6554;
      --amber: #8b744b;
      --line: #d8d8d1;
    }
    .stApp {
      background:
        linear-gradient(180deg, rgba(255,255,255,0.96), rgba(246,246,243,0.98) 46%, #eeeeea 100%);
      color: var(--ink);
    }
    header[data-testid="stHeader"] { background: transparent; }
    .block-container { max-width: 1360px; padding-top: 1.2rem; }
    h1, h2, h3, p { letter-spacing: 0; }
    .hero {
      padding: 26px 0 18px;
      border-bottom: 1px solid var(--hairline);
      margin-bottom: 20px;
    }
    .hero-title {
      color: var(--ink);
      font-size: clamp(2.25rem, 5.4vw, 4.7rem);
      line-height: 0.96;
      font-weight: 650;
      letter-spacing: 0;
      margin: 0;
    }
    .hero-sub {
      color: var(--muted);
      max-width: 760px;
      margin-top: 14px;
      font-size: 1.05rem;
      line-height: 1.55;
    }
    .hero-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
    }
    .pill {
      border: 1px solid var(--hairline);
      background: rgba(255,255,255,0.64);
      color: var(--soft-ink);
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 0.86rem;
      backdrop-filter: blur(18px);
    }
    .command-band {
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 12px;
      align-items: stretch;
      margin: 4px 0 16px;
    }
    .command-main {
      background: rgba(255,255,255,0.76);
      border: 1px solid var(--hairline);
      border-radius: 8px;
      padding: 18px;
      box-shadow: 0 22px 70px rgba(20,20,20,0.05);
      backdrop-filter: blur(22px);
    }
    .command-kicker {
      color: var(--muted);
      font-size: 0.78rem;
      margin-bottom: 8px;
    }
    .command-value {
      font-size: clamp(2.4rem, 5vw, 4.4rem);
      line-height: 0.98;
      font-weight: 640;
      letter-spacing: 0;
      color: var(--ink);
    }
    .command-subline {
      color: var(--soft-ink);
      margin-top: 10px;
      font-size: 1rem;
      line-height: 1.45;
      max-width: 820px;
    }
    .mandate-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      height: 100%;
    }
    .mandate-tile {
      border: 1px solid var(--hairline);
      background: rgba(255,255,255,0.62);
      border-radius: 8px;
      padding: 14px;
      min-height: 108px;
    }
    .mandate-tile span {
      display: block;
      color: var(--muted);
      font-size: 0.76rem;
      margin-bottom: 8px;
    }
    .mandate-tile strong {
      color: var(--ink);
      font-size: 1.28rem;
      font-weight: 620;
      letter-spacing: 0;
    }
    .mandate-tile p {
      color: var(--soft-ink);
      font-size: 0.84rem;
      line-height: 1.35;
      margin: 8px 0 0;
    }
    .boundary {
      border: 1px solid rgba(0,0,0,0.08);
      background: rgba(255,255,255,0.62);
      color: #4a4a4d;
      padding: 12px 14px;
      border-radius: 8px;
      font-size: 0.88rem;
      margin: 14px 0;
    }
    div[data-testid="stMetric"] {
      background: var(--panel);
      border: 1px solid var(--hairline);
      border-radius: 8px;
      padding: 12px 14px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.045);
      backdrop-filter: blur(20px);
    }
    div[data-testid="stMetricLabel"] {
      color: var(--muted);
      font-size: 0.78rem;
      font-weight: 520;
    }
    div[data-testid="stMetricValue"] {
      color: var(--ink);
      font-weight: 620;
      letter-spacing: -0.015em;
      font-size: 1.72rem;
    }
    div[data-testid="stMetricDelta"] { color: var(--green); }
    .section {
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: end;
      margin: 22px 0 10px;
    }
    .section h2 {
      color: var(--ink);
      font-size: 1.35rem;
      font-weight: 610;
      margin: 0;
    }
    .section p {
      color: var(--muted);
      margin: 5px 0 0;
      max-width: 760px;
      line-height: 1.45;
    }
    .quiet-panel {
      background: var(--panel);
      border: 1px solid var(--hairline);
      border-radius: 8px;
      padding: 16px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.04);
      backdrop-filter: blur(20px);
    }
    .read-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .read-card {
      border: 1px solid var(--hairline);
      background: rgba(255,255,255,0.68);
      border-radius: 8px;
      padding: 14px;
    }
    .read-title {
      color: var(--ink);
      font-weight: 620;
      margin-bottom: 5px;
    }
    .read-status {
      color: var(--blue);
      font-size: 0.84rem;
      margin-bottom: 8px;
    }
    .read-body {
      color: var(--soft-ink);
      font-size: 0.92rem;
      line-height: 1.45;
    }
    .model-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 8px;
    }
    .model-card {
      border: 1px solid var(--hairline);
      background: rgba(255,255,255,0.72);
      border-radius: 8px;
      padding: 12px;
    }
    .model-card span {
      color: var(--muted);
      font-size: 0.78rem;
    }
    .model-card strong {
      display: block;
      margin-top: 4px;
      color: var(--ink);
      font-size: 1rem;
    }
    .change-list {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin: 8px 0 12px;
    }
    .change-card {
      background: rgba(255,255,255,0.74);
      border: 1px solid var(--hairline);
      border-radius: 8px;
      padding: 12px 13px;
    }
    .change-label {
      color: var(--muted);
      font-size: 0.78rem;
      margin-bottom: 6px;
    }
    .change-value {
      color: var(--ink);
      font-weight: 620;
      font-size: 1.1rem;
    }
    .change-note {
      color: var(--muted);
      font-size: 0.78rem;
      margin-top: 5px;
    }
    .signal-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin: 8px 0 12px;
    }
    .signal-card {
      border: 1px solid var(--hairline);
      background: rgba(255,255,255,0.70);
      border-radius: 8px;
      padding: 14px;
      min-height: 142px;
    }
    .signal-priority {
      color: var(--amber);
      font-size: 0.75rem;
      margin-bottom: 8px;
    }
    .signal-title {
      color: var(--ink);
      font-weight: 620;
      margin-bottom: 5px;
    }
    .signal-status {
      color: var(--blue);
      font-size: 0.84rem;
      margin-bottom: 8px;
    }
    .signal-detail {
      color: var(--soft-ink);
      font-size: 0.9rem;
      line-height: 1.42;
    }
    .metric-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(135px, 1fr));
      gap: 10px;
      margin: 8px 0 12px;
    }
    .mini-metric {
      background: var(--panel);
      border: 1px solid var(--hairline);
      border-radius: 8px;
      padding: 12px 13px;
      box-shadow: 0 18px 50px rgba(0,0,0,0.04);
    }
    .mini-label {
      color: var(--muted);
      font-size: 0.78rem;
      margin-bottom: 6px;
    }
    .mini-value {
      color: var(--ink);
      font-size: 1.45rem;
      font-weight: 620;
      letter-spacing: -0.012em;
      line-height: 1.05;
    }
    .mini-delta {
      color: var(--green);
      font-size: 0.82rem;
      margin-top: 7px;
    }
    .stTabs [data-baseweb="tab-list"] {
      gap: 4px;
      border-bottom: 1px solid var(--hairline);
    }
    .stTabs [data-baseweb="tab"] {
      color: var(--muted);
      padding: 10px 12px;
      font-weight: 520;
      border-radius: 0;
    }
    .stTabs [aria-selected="true"] {
      color: var(--ink);
      border-bottom: 1px solid var(--ink) !important;
    }
    .stTabs [data-baseweb="tab-highlight"] {
      background-color: var(--ink) !important;
    }
    .stTabs [data-baseweb="tab-border"] {
      background-color: var(--hairline) !important;
    }
    div[data-testid="stDataFrame"] {
      border: 1px solid var(--hairline);
      border-radius: 8px;
      overflow: hidden;
      background: white;
    }
    button[kind="primary"], .stButton button {
      border-radius: 999px !important;
      border: 1px solid var(--hairline) !important;
      background: #151515 !important;
      color: white !important;
    }
    @media (max-width: 900px) {
      .read-grid, .model-grid, .change-list, .signal-grid, .command-band, .mandate-grid { grid-template-columns: 1fr; }
      .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .section { display: block; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


CURRENCY_HINTS = [
    "value",
    "debt",
    "loan",
    "offset",
    "rent",
    "cash",
    "assets",
    "worth",
    "super",
    "crypto",
    "shares",
    "equity",
    "amount",
    "payment",
    "balance",
    "proceeds",
    "cost",
    "profit",
    "loss",
    "impact",
]
PERCENT_HINTS = ["allocation", "target", "lvr", "yield", "return", "ratio", "threshold", "%", "drift"]
PRICE_COLUMNS = {"Live price", "Price used", "Current price native"}


def configured_password() -> str | None:
    secret_value = None
    try:
        secret_value = st.secrets.get("APP_PASSWORD")
    except Exception:  # noqa: BLE001 - secrets may be absent in local development.
        secret_value = None
    return os.environ.get("WEALTH_COCKPIT_APP_PASSWORD") or secret_value


def require_access() -> bool:
    if os.environ.get("WEALTH_COCKPIT_ALLOW_UNAUTHENTICATED") == "1":
        return True

    password = configured_password()
    if not password:
        st.markdown("<div class='hero'><div class='hero-title'>Rodney<br>Wealth Cockpit</div></div>", unsafe_allow_html=True)
        st.warning("Access is locked. Configure APP_PASSWORD in Streamlit secrets to open the cockpit.")
        return False

    if st.session_state.get("authenticated"):
        return True

    st.markdown("<div class='hero'><div class='hero-title'>Rodney<br>Wealth Cockpit</div></div>", unsafe_allow_html=True)
    with st.form("access_gate"):
        entered = st.text_input("Access code", type="password")
        submitted = st.form_submit_button("Unlock")
    if submitted and hmac.compare_digest(entered, str(password)):
        st.session_state["authenticated"] = True
        st.rerun()
    elif submitted:
        st.error("Access code incorrect.")
    return False


def section(title: str, subtitle: str | None = None) -> None:
    html = f"<div class='section'><div><h2>{title}</h2>"
    if subtitle:
        html += f"<p>{subtitle}</p>"
    html += "</div></div>"
    st.markdown(html, unsafe_allow_html=True)


def format_display(frame: pd.DataFrame, percent_cols: list[str] | None = None) -> pd.DataFrame:
    if frame.empty:
        return frame
    result = frame.copy()
    percent_cols = percent_cols or []
    for col in result.columns:
        lower = str(col).lower()
        if col in PRICE_COLUMNS:
            values = pd.to_numeric(result[col], errors="coerce")
            if values.notna().any():
                result[col] = values.map(lambda value: "" if pd.isna(value) else f"{value:,.2f}")
        elif col in percent_cols or any(hint in lower for hint in PERCENT_HINTS):
            values = pd.to_numeric(result[col], errors="coerce")
            if values.notna().any():
                result[col] = values.map(lambda value: "" if pd.isna(value) else f"{value * 100:.1f}%")
        elif any(hint in lower for hint in CURRENCY_HINTS):
            values = pd.to_numeric(result[col], errors="coerce")
            if values.notna().any():
                result[col] = values.map(lambda value: "" if pd.isna(value) else f"A${value:,.0f}")
    return result


def show_table(frame: pd.DataFrame, height: int | None = None, percent_cols: list[str] | None = None) -> None:
    if frame.empty:
        st.info("No data imported for this section yet.")
        return
    kwargs = {"width": "stretch", "hide_index": True}
    if height is not None:
        kwargs["height"] = height
    st.dataframe(format_display(frame, percent_cols), **kwargs)


def movement_chart_data() -> pd.DataFrame:
    changes = monthly_change_view()
    if changes.empty:
        return changes
    cols = [
        "Date",
        "Cash / offsets MoM",
        "Property equity MoM",
        "Crypto MoM",
        "Shares MoM",
        "Super MoM",
        "Debt reduction",
    ]
    cols = [col for col in cols if col in changes.columns]
    return changes[cols].iloc[1:].reset_index(drop=True)


def render_header() -> None:
    metrics = summary_metrics()
    monthly_delta = float(metrics.get("monthly_delta") or 0)
    delta_prefix = "+" if monthly_delta > 0 else ""
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-title">Rodney<br>Wealth Cockpit</div>
          <div class="hero-sub">A private wealth operating system: track the balance sheet, explain the monthly movement, separate live market marks from workbook fallbacks, and keep every decision approval-gated.</div>
          <div class="hero-meta">
            <div class="pill">A${metrics['net_worth'] / 1_000_000:,.2f}m net worth</div>
            <div class="pill">{delta_prefix}{money(monthly_delta)} month-on-month</div>
            <div class="pill">{metrics.get('as_of') or 'Latest import'}</div>
            <div class="pill">Rodney approval required</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_command_deck() -> None:
    metrics = summary_metrics()
    score = wealth_scorecard()
    monthly_delta = float(metrics.get("monthly_delta") or 0)
    delta_prefix = "+" if monthly_delta > 0 else ""
    mandates = score.head(4).to_dict("records") if not score.empty else []
    while len(mandates) < 4:
        mandates.append({"Mandate": "Control", "Read": "-", "Action": "Awaiting imported model"})
    st.markdown(
        f"""
        <div class="command-band">
          <div class="command-main">
            <div class="command-kicker">Family balance sheet command read</div>
            <div class="command-value">A${metrics.get('net_worth', 0) / 1_000_000:,.2f}m</div>
            <div class="command-subline">{delta_prefix}{money(monthly_delta)} month-on-month. The cockpit now treats the monthly ledger as the centre of gravity, with workbook depth and price provenance one click behind the read.</div>
          </div>
          <div class="mandate-grid">
            <div class="mandate-tile"><span>{mandates[0]['Mandate']}</span><strong>{mandates[0]['Read']}</strong><p>{mandates[0]['Action']}</p></div>
            <div class="mandate-tile"><span>{mandates[1]['Mandate']}</span><strong>{mandates[1]['Read']}</strong><p>{mandates[1]['Action']}</p></div>
            <div class="mandate-tile"><span>{mandates[2]['Mandate']}</span><strong>{mandates[2]['Read']}</strong><p>{mandates[2]['Action']}</p></div>
            <div class="mandate-tile"><span>{mandates[3]['Mandate']}</span><strong>{mandates[3]['Read']}</strong><p>{mandates[3]['Action']}</p></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_topline() -> None:
    metrics = summary_metrics()
    st.markdown(
        f"""
        <div class="metric-grid">
          <div class="mini-metric"><div class="mini-label">Net worth</div><div class="mini-value">{money(metrics.get("net_worth"))}</div><div class="mini-delta">+ {money(metrics.get("monthly_delta"))}</div></div>
          <div class="mini-metric"><div class="mini-label">Total assets</div><div class="mini-value">{money(metrics.get("assets"))}</div></div>
          <div class="mini-metric"><div class="mini-label">Total debt</div><div class="mini-value">{money(metrics.get("debt"))}</div></div>
          <div class="mini-metric"><div class="mini-label">Net debt</div><div class="mini-value">{money(metrics.get("net_debt"))}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kobe_read() -> None:
    with st.expander("Private banker review", expanded=False):
        signals = banker_signals()
        html = "<div class='signal-grid'>"
        for signal in signals:
            html += (
                "<div class='signal-card'>"
                f"<div class='signal-priority'>{signal.priority}</div>"
                f"<div class='signal-title'>{signal.name}</div>"
                f"<div class='signal-status'>{signal.status}</div>"
                f"<div class='signal-detail'>{signal.detail}</div>"
                "</div>"
            )
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)
        st.divider()
        cards = executive_brief()
        html = "<div class='read-grid'>"
        for card in cards:
            html += (
                "<div class='read-card'>"
                f"<div class='read-title'>{card['title']}</div>"
                f"<div class='read-status'>{card['status']}</div>"
                f"<div class='read-body'>{card['body']}</div>"
                "</div>"
            )
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)


def render_overview() -> None:
    render_command_deck()
    render_topline()

    render_kobe_read()

    section("Month-on-month attribution", "This is the control ledger: what changed, how big it was, and whether the swing improved or deteriorated against last month.")
    attribution = monthly_attribution()
    if not attribution.empty:
        html = "<div class='change-list'>"
        for _, row in attribution.head(6).iterrows():
            value = float(row["This month"])
            sign = "+" if value > 0 else ""
            html += (
                "<div class='change-card'>"
                f"<div class='change-label'>{row['Driver']}</div>"
                f"<div class='change-value'>{sign}{money(value)}</div>"
                f"<div class='change-note'>{row['Direction']} | swing {money(row['Swing'])}</div>"
                "</div>"
            )
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)
        show_table(attribution, height=300)

    monthly_changes = monthly_change_view()
    if not monthly_changes.empty:
        history_cols = [
            "Date",
            "Net worth",
            "Net worth MoM",
            "Net worth MoM %",
            "Cash / offsets MoM",
            "Property equity MoM",
            "Crypto MoM",
            "Shares MoM",
            "Debt reduction",
        ]
        history_cols = [col for col in history_cols if col in monthly_changes.columns]
        with st.expander("Monthly change history", expanded=False):
            show_table(monthly_changes[history_cols], height=300, percent_cols=["Net worth MoM %"])

    section("Mandate scorecard", "Percentages, policy ranges and controls without burying you in the full workbook.")
    score = wealth_scorecard()
    show_table(score, height=250)

    section("Allocation", "Current position against the workbook's policy base. Percentages are shown deliberately; raw values remain in the model sections.")
    alloc = allocation_view()
    if not alloc.empty:
        compact = alloc[["Asset class", "Current value", "Current allocation", "Target min", "Target base", "Target max", "Drift vs target", "Owner/lens"]]
        show_table(compact, percent_cols=["Current allocation", "Target min", "Target base", "Target max", "Drift vs target"])
        chart = alloc.set_index("Asset class")[["Current allocation", "Target base"]]
        st.bar_chart(chart)

    left, right = st.columns([1, 1])
    with left:
        section("Risk", "Quiet controls. Click into the workbook model for source detail.")
        show_table(risk_summary(), percent_cols=["Current"])
    with right:
        section("Stress", "Review-only scenario estimates.")
        stress = stress_view()
        show_table(stress)

    section("Wealth movement", "The useful view is not just the line; it is what changed the line each month.")
    components = movement_chart_data()
    if not components.empty:
        component_chart = components.copy()
        component_chart["Date"] = pd.to_datetime(component_chart["Date"], errors="coerce")
        component_cols = [
            col
            for col in ["Cash / offsets MoM", "Property equity MoM", "Crypto MoM", "Shares MoM", "Super MoM", "Debt reduction"]
            if col in component_chart
        ]
        st.bar_chart(component_chart.set_index("Date")[component_cols])

    monthly = read_table("monthly_tracking")
    if not monthly.empty:
        chart = monthly.copy()
        chart["Date"] = pd.to_datetime(chart["Date"], errors="coerce")
        chart["Net worth"] = numeric(chart["Net worth"])
        with st.expander("Net worth path and source monthly tracker", expanded=False):
            st.line_chart(chart.set_index("Date")[["Net worth"]])
            show_table(monthly, height=320)


def render_model_library() -> None:
    section("Workbook model", "The depth of the spreadsheet, organised into reviewable model rooms.")
    metrics = summary_metrics()
    index = read_table("workbook_sheet_index")
    sheet_count = len(index) if not index.empty else 0
    html = f"""
    <div class="model-grid">
      <div class="model-card"><span>Balance sheet date</span><strong>{metrics.get('as_of')}</strong></div>
      <div class="model-card"><span>Imported workbook sheets</span><strong>{sheet_count or 'Not imported'}</strong></div>
      <div class="model-card"><span>Primary source</span><strong>Excel workbook</strong></div>
      <div class="model-card"><span>Operating mode</span><strong>Evidence-backed</strong></div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
    coverage = workbook_coverage()
    if not coverage.empty:
        with st.expander("Workbook coverage map", expanded=False):
            show_table(coverage, height=360)

    model_rooms = ["Balance", "Liquidity", "Investments", "Shares", "Retirement", "Monthly", "Governance", "Full workbook"]
    room = st.radio("Model room", model_rooms, horizontal=True, label_visibility="collapsed")

    if room == "Balance":
        show_table(read_table("balance_sheet"), percent_cols=["% net worth", "Target min", "Target base", "Target max"])
        show_table(read_table("entity_ownership"))
    elif room == "Liquidity":
        show_table(read_table("liquidity_buckets"))
    elif room == "Investments":
        show_table(read_table("investment_register"), percent_cols=["% net worth", "Target min", "Target max"])
    elif room == "Shares":
        show_table(read_table("listed_share_snapshot"), height=420)
        with st.expander("Transaction lots"):
            show_table(read_table("share_transactions"), height=420)
        with st.expander("FY returns and consolidated growth"):
            show_table(read_table("fy_share_returns"), percent_cols=["Return %"])
            show_table(read_table("share_growth"), percent_cols=["Native return %", "AUD return %"])
    elif room == "Retirement":
        show_table(read_table("super_retirement"))
    elif room == "Monthly":
        show_table(monthly_change_view(), height=420, percent_cols=["Net worth MoM %"])
        attribution = monthly_attribution()
        if not attribution.empty:
            st.markdown("**Latest attribution**")
            show_table(attribution, height=280)
    elif room == "Governance":
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Decision queue**")
            show_table(read_table("decision_log"), height=420)
        with c2:
            st.markdown("**Evidence confidence**")
            show_table(read_table("evidence_register"), height=420)
    elif room == "Full workbook":
        if index.empty:
            st.info("Full workbook sheet index has not been imported yet.")
        else:
            st.caption("CSV imports use workbook cached/displayed values. Formula definitions are not recalculated here; formula audit counts flag where Excel formula fidelity may depend on opening the source workbook in Excel.")
            index_display = index.copy()
            show_table(index_display, height=220)
            selected = st.selectbox("Workbook sheet", index["Sheet"].astype(str).tolist())
            selected_meta = index.loc[index["Sheet"].astype(str).eq(selected)].iloc[0]
            table_name = selected_meta["Table"]
            st.caption(
                f"{selected_meta.get('Rows', 0)} rows x {selected_meta.get('Columns', 0)} columns"
                f" | formula cells: {selected_meta.get('Formula cells', 'unknown')}"
                f" | formula fidelity: {selected_meta.get('Formula fidelity', 'not audited')}"
            )
            sheet = read_table(table_name)
            query = st.text_input("Search selected sheet", value="")
            if query and not sheet.empty:
                mask = sheet.astype(str).apply(lambda col: col.str.contains(query, case=False, na=False, regex=False)).any(axis=1)
                sheet = sheet[mask]
            show_table(sheet, height=520)


def render_market_tape() -> None:
    section("Market tape", "Live prices where the asset has a public ticker. Workbook values remain the fallback when a feed is unavailable or suspect.")
    holdings = holdings_with_live_prices()
    cache = read_price_cache()
    price_sources = price_source_view()
    tickers = (
        [ticker for ticker in holdings["Ticker"].dropna().astype(str).tolist() if is_trackable_ticker(ticker)]
        if not holdings.empty and "Ticker" in holdings
        else []
    )

    left, right = st.columns([0.7, 1.3])
    if left.button("Refresh market tape", width="stretch"):
        with st.spinner("Refreshing public market prices and USD/AUD..."):
            cache = refresh_prices(tickers)
        refresh = cache.get("refresh", {})
        st.success(
            "Market tape refreshed: "
            f"{refresh.get('public_refreshed', 0)} public prices updated from "
            f"{refresh.get('requested_unique_tickers', len(set(tickers)))} unique tickers across {len(tickers)} holding rows; "
            f"{refresh.get('stale_cache', 0)} stale cached prices retained; "
            f"{refresh.get('public_unavailable_no_cache', 0)} workbook-only fallbacks."
        )
    right.caption(f"Refresh run: {cache.get('updated_at') or 'Not refreshed yet'}")
    if cache.get("errors"):
        with st.expander("Public feed gaps", expanded=False):
            st.write(cache["errors"])

    if not price_sources.empty:
        statuses = price_sources.get("Provenance status", pd.Series(dtype=str)).astype(str)
        public_sources = price_sources[statuses.eq("public_price_used")]
        tolerance_fallbacks = int(statuses.eq("workbook_fallback_public_outside_tolerance").sum())
        no_public_fallbacks = int(statuses.str.startswith("workbook_fallback").sum() - tolerance_fallbacks)
        stale_count = int(statuses.str.contains("stale_cache", na=False).sum())
        latest_stamp = public_sources["Price as of"].iloc[-1] if len(public_sources) else "No public timestamps"
        st.caption(
            f"Price provenance: {len(public_sources)} public holding rows, {stale_count} stale/cache rows, "
            f"{tolerance_fallbacks} outside-tolerance workbook fallbacks, {no_public_fallbacks} no-public-price workbook fallbacks. "
            f"Latest displayed public source time: {latest_stamp}."
        )

    if holdings.empty:
        st.info("No listed holdings table found yet.")
        return

    watchlist = portfolio_watchlist()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Unique tickers", len(set(tickers)))
    c2.metric("Holding rows", len(tickers))
    c3.metric("Live listed value", money(holdings["Live value AUD"].sum()))
    c4.metric("Live P/L", money(holdings["Live P/L AUD"].sum()))

    if not watchlist.empty:
        section("Investment watchlist", "Ranked by current AUD exposure with live/workbook confidence kept visible.")
        show_table(watchlist, height=420, percent_cols=["Weight", "P/L %"])

    market_col = "Market / account" if "Market / account" in holdings else "Market"
    display = holdings[
        [
            market_col,
            "Entity / owner",
            "Ticker",
            "Instrument",
            "Currency",
            "Shares",
            "Live price",
            "Price basis",
            "Tolerance check",
            "Live value AUD",
            "Live P/L AUD",
            "Source",
        ]
    ].rename(columns={market_col: "Market / account"})
    with st.expander("Holding detail", expanded=False):
        show_table(display, height=460)

    with st.expander("Price source and timestamp", expanded=True):
        st.caption("Public prices come from Yahoo Finance chart metadata where available. FX comes from open.er-api.com. If a public price is outside the 50% workbook tolerance, the app flags that status and uses the workbook value as an explicit fallback.")
        show_table(price_sources, height=360)


def render_property_and_debt() -> None:
    section("Property and debt", "Dan view: values, loans, offsets, P&L, Keith evidence and land-tax controls.")
    props = property_debt_snapshot()
    if not props.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Property value", money(props["Value"].sum()))
        c2.metric("Loans", money(props["Loan"].sum()))
        c3.metric("Offsets", money(props["Offset"].sum()))
        c4.metric("Net property debt", money(props["Net debt after offset"].sum()))
        show_table(props, height=260, percent_cols=["Gross LVR", "Net LVR", "Gross yield"])

    tabs = st.tabs(["Register", "Loans", "P&L", "Keith", "Keith coverage", "Controls"])
    with tabs[0]:
        show_table(read_table("property_register"), height=360, percent_cols=["Gross LVR", "Net LVR", "Gross yield"])
    with tabs[1]:
        show_table(read_table("loan_offset_register"), percent_cols=["Offset protection ratio", "Rate"])
    with tabs[2]:
        show_table(read_table("property_pnl"), height=360)
    with tabs[3]:
        show_table(read_table("keith_statements"), height=360)
        with st.expander("Maintenance and inspection register"):
            show_table(read_table("keith_maintenance"), height=360)
    with tabs[4]:
        show_table(read_table("keith_coverage"), height=360)
    with tabs[5]:
        show_table(read_table("land_tax_control"), height=360)
        show_table(read_table("last_month_cashflow"), height=240)


def render_governance() -> None:
    section("Governance", "Decision log, evidence register, benchmark policy and risk controls.")
    tabs = st.tabs(["Decisions", "Evidence", "Risk dashboard", "Stress tests", "Benchmark policy"])
    with tabs[0]:
        decisions = read_table("decision_log")
        if not decisions.empty and "Approval status" in decisions:
            status = decisions["Approval status"].astype(str).value_counts().reset_index()
            status.columns = ["Status", "Count"]
            show_table(status)
        show_table(decisions, height=460)
    with tabs[1]:
        evidence = read_table("evidence_register")
        if not evidence.empty and "Status" in evidence:
            status = evidence["Status"].astype(str).value_counts().reset_index()
            status.columns = ["Status", "Count"]
            show_table(status)
        show_table(evidence, height=460)
    with tabs[2]:
        show_table(read_table("risk_dashboard"), percent_cols=["Current", "Green threshold", "Amber threshold"])
    with tabs[3]:
        show_table(read_table("stress_tests"))
    with tabs[4]:
        show_table(read_table("benchmark_policy"), percent_cols=["FY26 approx return"])


def render_update_flow() -> None:
    section("Update flow", "Simple enough for Rodney; structured enough for Kobe to automate.")
    writes_enabled = local_writes_enabled()
    checklist = update_checklist()
    if not checklist.empty:
        show_table(checklist, height=260)
    st.markdown("**Re-import from the Drive-synced workbook**")
    workbook_status = "available locally" if SOURCE_WORKBOOK.exists() else "not attached in this environment"
    st.caption(f"Source: {SOURCE_WORKBOOK_LABEL} ({workbook_status}).")
    st.code(
        "export WEALTH_COCKPIT_WORKBOOK=\"/path/to/Rodney Wealth Cockpit.xlsx\"\n"
        "python scripts/import_workbook.py",
        language="bash",
    )
    if writes_enabled:
        st.success("Local write mode is enabled with WEALTH_COCKPIT_ENABLE_LOCAL_WRITES=1. Form submissions update local CSV files in this workspace.")
    else:
        st.warning("Read-only deployed mode: form submissions preview a non-durable monthly row only. Set WEALTH_COCKPIT_ENABLE_LOCAL_WRITES=1 in a trusted local environment to write CSV updates.")
    st.markdown("**Add or replace a monthly tracking row**")
    monthly = read_table("monthly_tracking")
    if monthly.empty:
        st.info("Monthly tracking table has not been imported yet.")
        return

    with st.form("monthly_update"):
        last = monthly.iloc[-1].to_dict()
        c1, c2, c3 = st.columns(3)
        date = c1.text_input("Date", value=str(last.get("Date", "")))
        cash = c2.number_input("Cash / offsets", value=float(last.get("Cash / offsets", 0) or 0), step=1000.0)
        property_value = c3.number_input("Property value", value=float(last.get("Property value", 0) or 0), step=1000.0)
        c4, c5, c6 = st.columns(3)
        crypto = c4.number_input("Crypto", value=float(last.get("Crypto", 0) or 0), step=1000.0)
        shares = c5.number_input("Shares", value=float(last.get("Shares", 0) or 0), step=1000.0)
        super_value = c6.number_input("Super", value=float(last.get("Super", 0) or 0), step=1000.0)
        debt = st.number_input("Total debt", value=float(last.get("Total debt", 0) or 0), step=1000.0)
        submitted = st.form_submit_button("Save monthly row" if writes_enabled else "Preview monthly row")

    if submitted:
        property_equity = property_value - debt
        total_assets = cash + property_value + crypto + shares + super_value
        net_debt = debt - cash
        net_worth = total_assets - debt
        new_row = {
            "Date": date,
            "Cash / offsets": cash,
            "Property value": property_value,
            "Property equity": property_equity,
            "Crypto": crypto,
            "Shares": shares,
            "Super": super_value,
            "Total assets": total_assets,
            "Total debt": debt,
            "Net debt": net_debt,
            "Net worth": net_worth,
        }
        monthly = build_monthly_update_frame(monthly, new_row)
        if writes_enabled:
            write_table("monthly_tracking", monthly)
            st.success("Monthly row saved locally with derived delta columns recalculated.")
        else:
            st.info("Preview only. No CSV was written in read-only mode.")
        show_table(monthly.tail(3), height=220, percent_cols=["Net worth MoM %"])

    with st.expander("Authority boundary"):
        st.write(AUTHORITY_BOUNDARY)
        st.caption(f"Workbook source: {SOURCE_WORKBOOK_LABEL}")


def main() -> None:
    if require_access():
        render_header()

        tabs = st.tabs(["Overview", "Model", "Market", "Property", "Governance", "Update"])
        with tabs[0]:
            render_overview()
        with tabs[1]:
            render_model_library()
        with tabs[2]:
            render_market_tape()
        with tabs[3]:
            render_property_and_debt()
        with tabs[4]:
            render_governance()
        with tabs[5]:
            render_update_flow()


if __name__ == "__main__":
    main()

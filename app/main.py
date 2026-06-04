from __future__ import annotations

import hmac
import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import AUTHORITY_BOUNDARY, SOURCE_WORKBOOK, SOURCE_WORKBOOK_LABEL
from app.data_store import money, read_price_cache, read_table, write_table
from app.market_prices import is_trackable_ticker, refresh_prices
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
      --ink: #151515;
      --soft-ink: #3b3b3d;
      --muted: #7a7c80;
      --hairline: rgba(20, 20, 20, 0.10);
      --paper: #f7f7f4;
      --panel: rgba(255, 255, 255, 0.82);
      --panel-solid: #ffffff;
      --mist: #ececea;
      --blue: #496676;
      --green: #2f6758;
      --amber: #9a6c2f;
      --red: #6f6f72;
    }
    .stApp {
      background:
        radial-gradient(circle at 50% -10%, rgba(255,255,255,0.98), rgba(247,247,244,0.92) 38%, #f1f1ee 100%);
      color: var(--ink);
    }
    header[data-testid="stHeader"] { background: transparent; }
    .block-container { max-width: 1360px; padding-top: 1.2rem; }
    h1, h2, h3, p { letter-spacing: 0; }
    .hero {
      padding: 22px 0 16px;
      border-bottom: 1px solid var(--hairline);
      margin-bottom: 20px;
    }
    .hero-title {
      color: var(--ink);
      font-size: clamp(2.25rem, 5.4vw, 4.7rem);
      line-height: 0.96;
      font-weight: 650;
      letter-spacing: -0.02em;
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
      .read-grid, .model-grid, .change-list { grid-template-columns: 1fr; }
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
    entered = st.text_input("Access code", type="password")
    if entered and hmac.compare_digest(entered, str(password)):
        st.session_state["authenticated"] = True
        st.rerun()
    elif entered:
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


def render_header() -> None:
    metrics = summary_metrics()
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-title">Rodney<br>Wealth Cockpit</div>
          <div class="hero-sub">A quiet operating system for wealth: balance sheet, market tape, property, debt, evidence and approval-gated decisions. The model stays deep; the interface stays calm.</div>
          <div class="hero-meta">
            <div class="pill">A${metrics['net_worth'] / 1_000_000:,.2f}m net worth</div>
            <div class="pill">+{money(metrics.get('monthly_delta'))} month-on-month</div>
            <div class="pill">{metrics.get('as_of') or 'Latest import'}</div>
            <div class="pill">Rodney approval required</div>
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
    with st.expander("Kobe's read", expanded=False):
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
    render_topline()

    section("Month-on-month", "What changed since the prior monthly snapshot. This is the main tracking layer, not an afterthought.")
    bridge = latest_month_bridge()
    if not bridge.empty:
        html = "<div class='change-list'>"
        for _, row in bridge.head(6).iterrows():
            value = float(row["Monthly change"])
            sign = "+" if value > 0 else ""
            html += (
                "<div class='change-card'>"
                f"<div class='change-label'>{row['Driver']}</div>"
                f"<div class='change-value'>{sign}{money(value)}</div>"
                f"<div class='change-note'>{row['Comment']}</div>"
                "</div>"
            )
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)
        show_table(bridge, height=300)

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

    render_kobe_read()

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

    section("Monthly path", "Net worth history imported from the workbook monthly tracker.")
    monthly = read_table("monthly_tracking")
    if not monthly.empty:
        chart = monthly.copy()
        chart["Date"] = pd.to_datetime(chart["Date"], errors="coerce")
        chart["Net worth"] = numeric(chart["Net worth"])
        st.line_chart(chart.set_index("Date")[["Net worth"]])


def render_model_library() -> None:
    section("Workbook model", "The depth of the spreadsheet, organised into reviewable model rooms.")
    metrics = summary_metrics()
    alloc = allocation_view()
    html = f"""
    <div class="model-grid">
      <div class="model-card"><span>Balance sheet date</span><strong>{metrics.get('as_of')}</strong></div>
      <div class="model-card"><span>Imported tables</span><strong>22</strong></div>
      <div class="model-card"><span>Primary source</span><strong>Excel workbook</strong></div>
      <div class="model-card"><span>Operating mode</span><strong>Evidence-backed</strong></div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

    model_tabs = st.tabs(["Balance", "Liquidity", "Investments", "Shares", "Retirement", "Monthly"])
    with model_tabs[0]:
        show_table(read_table("balance_sheet"), percent_cols=["% net worth", "Target min", "Target base", "Target max"])
        show_table(read_table("entity_ownership"))
    with model_tabs[1]:
        show_table(read_table("liquidity_buckets"))
    with model_tabs[2]:
        show_table(read_table("investment_register"), percent_cols=["% net worth", "Target min", "Target max"])
    with model_tabs[3]:
        show_table(read_table("listed_share_snapshot"), height=420)
        with st.expander("Transaction lots"):
            show_table(read_table("share_transactions"), height=420)
        with st.expander("FY returns and consolidated growth"):
            show_table(read_table("fy_share_returns"), percent_cols=["Return %"])
            show_table(read_table("share_growth"), percent_cols=["Native return %", "AUD return %"])
    with model_tabs[4]:
        show_table(read_table("super_retirement"))
    with model_tabs[5]:
        show_table(monthly_change_view(), height=420, percent_cols=["Net worth MoM %"])


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
        st.success("Market tape refreshed.")
    right.caption(f"Refresh run: {cache.get('updated_at') or 'Not refreshed yet'}")
    if cache.get("errors"):
        st.warning(f"Some prices could not be refreshed: {cache['errors']}")

    if not price_sources.empty:
        public_sources = price_sources[~price_sources["Price as of"].astype(str).eq("Workbook fallback")]
        fallback_count = int(price_sources["Price as of"].astype(str).eq("Workbook fallback").sum())
        latest_stamp = public_sources["Price as of"].iloc[-1] if len(public_sources) else "No public timestamps"
        st.caption(f"Price provenance: {len(public_sources)} public timestamped rows, {fallback_count} workbook fallback rows. Latest displayed source time: {latest_stamp}.")

    if holdings.empty:
        st.info("No listed holdings table found yet.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Tracked tickers", len(set(tickers)))
    c2.metric("Live listed value", money(holdings["Live value AUD"].sum()))
    c3.metric("Live P/L", money(holdings["Live P/L AUD"].sum()))

    market_col = "Market / account" if "Market / account" in holdings else "Market"
    display = holdings[
        [market_col, "Entity / owner", "Ticker", "Instrument", "Currency", "Shares", "Live price", "Price basis", "Live value AUD", "Live P/L AUD", "Source"]
    ].rename(columns={market_col: "Market / account"})
    show_table(display, height=460)

    with st.expander("Price source and timestamp", expanded=True):
        st.caption("Public prices come from Yahoo Finance chart metadata where available. FX comes from open.er-api.com. If a feed is unavailable or looks suspect versus the workbook value, the app uses the workbook value as a fallback.")
        show_table(price_sources, height=360)


def render_property_and_debt() -> None:
    section("Property and debt", "Dan view: values, loans, offsets, P&L, Keith evidence and land-tax controls.")
    props = read_table("property_register")
    if not props.empty:
        props["Value"] = numeric(props["Value"])
        props["Loan"] = numeric(props["Loan"])
        props["Offset"] = numeric(props["Offset"])
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Property value", money(props["Value"].sum()))
        c2.metric("Loans", money(props["Loan"].sum()))
        c3.metric("Offsets", money(props["Offset"].sum()))
        c4.metric("Net property debt", money((props["Loan"] - props["Offset"]).sum()))

    tabs = st.tabs(["Register", "Loans", "P&L", "Keith", "Controls"])
    with tabs[0]:
        show_table(props, height=360)
    with tabs[1]:
        show_table(read_table("loan_offset_register"), percent_cols=["Offset protection ratio", "Rate"])
    with tabs[2]:
        show_table(read_table("property_pnl"), height=360)
    with tabs[3]:
        show_table(read_table("keith_statements"), height=360)
        with st.expander("Maintenance and inspection register"):
            show_table(read_table("keith_maintenance"), height=360)
    with tabs[4]:
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
    st.markdown("**Re-import from the Drive-synced workbook**")
    workbook_status = "available locally" if SOURCE_WORKBOOK.exists() else "not attached in this environment"
    st.caption(f"Source: {SOURCE_WORKBOOK_LABEL} ({workbook_status}).")
    st.code(
        "export WEALTH_COCKPIT_WORKBOOK=\"/path/to/Rodney Wealth Cockpit.xlsx\"\n"
        "python scripts/import_workbook.py",
        language="bash",
    )
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
        submitted = st.form_submit_button("Save monthly row")

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
        monthly = monthly[monthly["Date"].astype(str) != str(date)]
        monthly = pd.concat([monthly, pd.DataFrame([new_row])], ignore_index=True)
        write_table("monthly_tracking", monthly)
        st.success("Monthly row saved.")

    with st.expander("Authority boundary"):
        st.write(AUTHORITY_BOUNDARY)
        st.caption(f"Workbook source: {SOURCE_WORKBOOK_LABEL}")


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

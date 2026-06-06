from __future__ import annotations

import hmac
import importlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import AUTHORITY_BOUNDARY, SOURCE_WORKBOOK, SOURCE_WORKBOOK_LABEL
from app import data_store

data_store = importlib.reload(data_store)
local_writes_enabled = getattr(data_store, "local_writes_enabled", lambda: os.environ.get("WEALTH_COCKPIT_ENABLE_LOCAL_WRITES") == "1")
money = data_store.money
read_price_cache = data_store.read_price_cache
read_table = data_store.read_table
write_table = data_store.write_table

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
    cockpit_data_status,
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
from app.property_refresh import property_refresh_view, refresh_property_estimates


st.set_page_config(page_title="Rodney Wealth Cockpit", page_icon="RW", layout="wide")


def refresh_bitcoin_prices() -> dict[str, object]:
    market_prices = importlib.import_module("app.market_prices")
    if hasattr(market_prices, "refresh_bitcoin_prices"):
        return market_prices.refresh_bitcoin_prices()

    cache = read_price_cache()
    crypto = cache.get("crypto", {})
    errors = cache.get("errors", {}).copy()
    refreshed = 0
    for key, symbol in {"BTC_AUD": "BTC-AUD", "BTC_USD": "BTC-USD"}.items():
        try:
            crypto[key] = market_prices.fetch_yahoo_price(symbol)
            refreshed += 1
            errors.pop(key, None)
        except Exception as exc:  # noqa: BLE001 - displayed in UI.
            errors[key] = str(exc)
            if key not in crypto:
                crypto[key] = {"symbol": symbol, "price": None, "source": "Unavailable"}
    cache["crypto"] = crypto
    cache["errors"] = errors
    cache["crypto_refresh"] = {
        "requested": 2,
        "public_refreshed": refreshed,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "Yahoo Finance chart endpoint",
    }
    data_store.save_price_cache(cache)
    return cache

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500;600&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    :root {
      --ink: #f7f2ea;
      --soft-ink: #ddd4c8;
      --muted: #a99f94;
      --hairline: rgba(232, 202, 171, 0.16);
      --paper: #030504;
      --panel: rgba(8, 37, 31, 0.76);
      --panel-solid: #071b17;
      --mist: #0c2b25;
      --blue: #9fd9cc;
      --navy: #f7f2ea;
      --orange: #d0aa84;
      --silver: #bfb0a1;
      --green: #2f6554;
      --gain: #35d07f;
      --loss: #ff6b6b;
      --amber: #d0aa84;
      --line: rgba(232, 202, 171, 0.16);
    }
    .stApp {
      background:
        linear-gradient(122deg, rgba(188, 173, 148, 0.20) 0%, rgba(4, 43, 35, 0.08) 22%, rgba(3, 5, 4, 0) 48%),
        linear-gradient(180deg, #030504 0%, #061611 36%, #08281f 100%);
      color: var(--ink);
      font-family: "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header[data-testid="stHeader"] { background: transparent; }
    .block-container { max-width: 1360px; padding-top: 1.2rem; }
    h1, h2, h3, p, label, span, div { letter-spacing: 0; }
    .hero {
      padding: 26px 0 18px;
      border-bottom: 1px solid rgba(208,170,132,0.54);
      margin-bottom: 20px;
      position: relative;
    }
    .hero:after {
      content: "";
      position: absolute;
      left: 0;
      bottom: -1px;
      width: 58px;
      height: 1px;
      background: var(--orange);
    }
    .hero-title {
      color: var(--navy);
      font-size: clamp(2.05rem, 5vw, 4.2rem);
      line-height: 0.96;
      font-family: "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-weight: 800;
      letter-spacing: 0;
      margin: 0;
    }
    .hero-sub {
      color: var(--muted);
      max-width: 760px;
      margin-top: 14px;
      font-size: 1.05rem;
      line-height: 1.52;
    }
    .hero-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
    }
    .pill {
      border: 1px solid rgba(208,170,132,0.20);
      background: rgba(0,0,0,0.20);
      color: var(--soft-ink);
      border-radius: 999px;
      padding: 8px 12px;
      font-size: 0.78rem;
      font-weight: 600;
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
      background: linear-gradient(135deg, rgba(8,37,31,0.90), rgba(5,18,15,0.92));
      border: 1px solid rgba(208,170,132,0.18);
      border-top: 1px solid rgba(208,170,132,0.52);
      border-radius: 8px;
      padding: 18px;
      box-shadow: 0 28px 80px rgba(0,0,0,0.30);
      backdrop-filter: blur(18px);
    }
    .command-kicker {
      color: var(--orange);
      font-size: 0.78rem;
      font-family: "IBM Plex Mono", monospace;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
    }
    .command-value {
      font-size: clamp(2.4rem, 5vw, 4.4rem);
      line-height: 0.98;
      font-weight: 800;
      letter-spacing: 0;
      color: var(--navy);
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
      border: 1px solid rgba(208,170,132,0.13);
      background: rgba(5,23,19,0.66);
      border-radius: 8px;
      padding: 14px;
      min-height: 108px;
    }
    .mandate-tile span {
      display: block;
      color: var(--muted);
      font-size: 0.76rem;
      font-family: "IBM Plex Mono", monospace;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 8px;
    }
    .mandate-tile strong {
      color: var(--navy);
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
      border: 1px solid rgba(208,170,132,0.15);
      border-top: 1px solid rgba(208,170,132,0.45);
      border-radius: 8px;
      padding: 12px 14px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.22);
      backdrop-filter: blur(20px);
    }
    div[data-testid="stMetricLabel"] {
      color: var(--muted);
      font-size: 0.78rem;
      font-family: "IBM Plex Mono", monospace;
      font-weight: 520;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    div[data-testid="stMetricValue"] {
      color: var(--navy);
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
      color: var(--navy);
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
      border: 1px solid rgba(208,170,132,0.13);
      border-radius: 8px;
      padding: 16px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.22);
      backdrop-filter: blur(20px);
    }
    .read-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .read-card {
      border: 1px solid rgba(208,170,132,0.13);
      background: rgba(5,23,19,0.62);
      border-radius: 8px;
      padding: 14px;
    }
    .read-title {
      color: var(--navy);
      font-weight: 620;
      margin-bottom: 5px;
    }
    .read-status {
      color: var(--orange);
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
      border: 1px solid rgba(208,170,132,0.13);
      background: rgba(5,23,19,0.62);
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
      color: var(--navy);
      font-size: 1rem;
    }
    .change-list {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin: 8px 0 12px;
    }
    .change-card {
      background: rgba(5,23,19,0.62);
      border: 1px solid rgba(208,170,132,0.13);
      border-radius: 8px;
      padding: 12px 13px;
    }
    .change-label {
      color: var(--muted);
      font-size: 0.78rem;
      margin-bottom: 6px;
    }
    .change-value {
      color: var(--navy);
      font-weight: 620;
      font-size: 1.1rem;
    }
    .positive { color: var(--gain) !important; }
    .negative { color: var(--loss) !important; }
    .neutral { color: var(--muted) !important; }
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
      border: 1px solid rgba(208,170,132,0.13);
      background: rgba(5,23,19,0.62);
      border-radius: 8px;
      padding: 14px;
      min-height: 142px;
    }
    .signal-priority {
      color: var(--orange);
      font-size: 0.75rem;
      margin-bottom: 8px;
    }
    .signal-title {
      color: var(--navy);
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
      border: 1px solid rgba(208,170,132,0.13);
      border-left: 3px solid var(--orange);
      border-radius: 8px;
      padding: 12px 13px;
      box-shadow: 0 18px 50px rgba(0,0,0,0.20);
    }
    .mini-label {
      color: var(--muted);
      font-size: 0.78rem;
      margin-bottom: 6px;
    }
    .mini-value {
      color: var(--navy);
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
      color: var(--navy);
      border-bottom: 2px solid var(--orange) !important;
    }
    .stTabs [data-baseweb="tab-highlight"] {
      background-color: var(--orange) !important;
    }
    .stTabs [data-baseweb="tab-border"] {
      background-color: var(--hairline) !important;
    }
    div[role="radiogroup"] {
      gap: 8px;
      align-items: stretch;
    }
    div[role="radiogroup"] label {
      border: 1px solid rgba(208,170,132,0.13);
      background: rgba(5,23,19,0.62);
      border-radius: 999px;
      padding: 7px 12px;
      min-height: 38px;
      justify-content: center;
    }
    div[role="radiogroup"] label:has(input:checked) {
      background: var(--ink);
      color: #080b0f;
      border-color: var(--blue);
    }
    div[role="radiogroup"] label:has(input:checked) * {
      color: white !important;
    }
    .refresh-panel {
      border: 1px solid rgba(208,170,132,0.13);
      border-left: 4px solid var(--orange);
      background: linear-gradient(135deg, rgba(20,26,33,0.92), rgba(12,16,21,0.92));
      border-radius: 8px;
      padding: 14px;
      margin: 10px 0 14px;
      box-shadow: 0 18px 45px rgba(0,0,0,0.22);
    }
    .refresh-title {
      color: var(--navy);
      font-weight: 620;
      font-size: 1rem;
      margin-bottom: 5px;
    }
    .refresh-note {
      color: var(--muted);
      font-size: 0.84rem;
      line-height: 1.4;
      margin-bottom: 10px;
    }
    .mobile-card-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin: 10px 0;
    }
    .mobile-card {
      border: 1px solid rgba(208,170,132,0.13);
      background: rgba(5,23,19,0.62);
      border-radius: 8px;
      padding: 12px;
      min-width: 0;
    }
    .mobile-card span {
      display: block;
      color: var(--muted);
      font-size: 0.74rem;
      margin-bottom: 5px;
    }
    .mobile-card strong {
      display: block;
      color: var(--navy);
      font-size: 1.1rem;
      font-weight: 620;
      line-height: 1.12;
      overflow-wrap: anywhere;
    }
    .mobile-card em {
      display: block;
      color: var(--muted);
      font-style: normal;
      font-size: 0.76rem;
      margin-top: 6px;
      line-height: 1.3;
      overflow-wrap: anywhere;
    }
    div[data-testid="stDataFrame"] {
      border: 1px solid rgba(208,170,132,0.13);
      border-radius: 8px;
      overflow: hidden;
      background: var(--panel-solid);
    }
    div[data-testid="stDataFrame"] * {
      font-family: "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
    }
    div[data-baseweb="select"] > div {
      border: 1px solid rgba(208,170,132,0.20) !important;
      background: rgba(255,255,255,0.065) !important;
      border-radius: 8px !important;
      color: var(--ink) !important;
    }
    div[data-baseweb="select"] span,
    div[data-baseweb="select"] div,
    div[data-baseweb="select"] input {
      color: var(--ink) !important;
      font-family: "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
    }
    div[data-testid="stSelectbox"] label,
    div[data-testid="stSelectbox"] label *,
    div[data-testid="stWidgetLabel"],
    div[data-testid="stWidgetLabel"] * {
      color: var(--soft-ink) !important;
    }
    div[data-baseweb="select"] svg {
      color: var(--orange);
    }
    div[data-baseweb="popover"],
    ul[role="listbox"] {
      background: #11171d !important;
      color: var(--ink) !important;
      border: 1px solid rgba(208,170,132,0.18) !important;
    }
    input, textarea {
      color: var(--ink) !important;
      background: rgba(255,255,255,0.065) !important;
      border-color: rgba(208,170,132,0.18) !important;
    }
    button[kind="primary"], .stButton button {
      border-radius: 999px !important;
      border: 1px solid rgba(208,170,132,0.44) !important;
      background: var(--orange) !important;
      color: #080b0f !important;
      font-weight: 650 !important;
      box-shadow: 0 10px 28px rgba(0,0,0,0.18) !important;
    }
    @media (max-width: 900px) {
      .read-grid, .model-grid, .change-list, .signal-grid, .command-band, .mandate-grid { grid-template-columns: 1fr; }
      .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .section { display: block; }
    }
    @media (max-width: 640px) {
      .block-container { padding: 0.45rem 0.72rem 4.5rem; }
      .hero { padding: 12px 0 10px; margin-bottom: 10px; }
      .hero-title { font-size: 2rem; line-height: 1; }
      .hero-sub { font-size: 0.88rem; line-height: 1.42; margin-top: 9px; }
      .hero-meta { gap: 6px; margin-top: 10px; }
      .pill { font-size: 0.74rem; padding: 6px 9px; }
      .command-main, .quiet-panel, .refresh-panel { padding: 12px; }
      .command-value { font-size: 2.25rem; }
      .command-subline { font-size: 0.88rem; }
      .mandate-tile, .change-card, .signal-card, .mini-metric { padding: 11px; min-height: 0; }
      .section { margin: 16px 0 8px; }
      .section h2 { font-size: 1.08rem; }
      .section p { font-size: 0.84rem; line-height: 1.35; }
      div[role="radiogroup"] {
        display: grid !important;
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
      div[role="radiogroup"] label {
        border-radius: 8px;
        padding: 9px 8px;
      }
      .mobile-card-grid, .metric-grid { grid-template-columns: 1fr; }
      div[data-testid="stMetric"] { padding: 10px 11px; }
      div[data-testid="stMetricValue"] { font-size: 1.42rem; }
      div[data-testid="stDataFrame"] { font-size: 0.78rem; }
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
GROWTH_HINTS = [
    "mom",
    "change",
    "delta",
    "growth",
    "swing",
    "return",
    "p/l",
    "profit",
    "loss",
    "drift",
    "impact",
    "reduction",
    "Δ",
]


def configured_password() -> str | None:
    secret_value = None
    try:
        secret_value = st.secrets.get("APP_PASSWORD")
    except Exception:  # noqa: BLE001 - secrets may be absent in local development.
        secret_value = None
    return os.environ.get("WEALTH_COCKPIT_APP_PASSWORD") or secret_value


def require_access() -> bool:
    return True


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
    display = format_display(frame, percent_cols)
    styles = growth_styles(frame)
    if styles.replace("", pd.NA).notna().any().any():
        st.dataframe(display.style.apply(lambda _: styles, axis=None), **kwargs)
    else:
        st.dataframe(display, **kwargs)


def tone_class(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "neutral"
    if number > 0:
        return "positive"
    if number < 0:
        return "negative"
    return "neutral"


def signed_money(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return money(value)
    prefix = "+" if number > 0 else ""
    return f"{prefix}{money(number)}"


def compact_amount(value: object, currency: str = "A$") -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if pd.isna(number):
        return "-"
    if abs(number) >= 1_000_000:
        return f"{currency}{number / 1_000_000:,.2f}m"
    if abs(number) >= 1_000:
        return f"{currency}{number / 1_000:,.1f}k"
    return f"{currency}{number:,.0f}"


def card_grid(cards: list[dict[str, str]]) -> None:
    html = "<div class='mobile-card-grid'>"
    for card in cards:
        html += (
            "<div class='mobile-card'>"
            f"<span>{card.get('label', '')}</span>"
            f"<strong>{card.get('value', '')}</strong>"
            f"<em>{card.get('note', '')}</em>"
            "</div>"
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def growth_styles(frame: pd.DataFrame) -> pd.DataFrame:
    styles = pd.DataFrame("", index=frame.index, columns=frame.columns)
    for col in frame.columns:
        lower = str(col).lower()
        if not any(hint.lower() in lower for hint in GROWTH_HINTS):
            continue
        values = pd.to_numeric(frame[col], errors="coerce")
        if not values.notna().any():
            continue
        styles[col] = values.map(
            lambda value: (
                "color: #24745c; font-weight: 650;"
                if pd.notna(value) and value > 0
                else "color: #a34038; font-weight: 650;"
                if pd.notna(value) and value < 0
                else "color: #777b80;"
            )
        )
    return styles


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
    delta_tone = tone_class(monthly_delta)
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-title">Rodney<br>Wealth Cockpit</div>
          <div class="hero-sub">A private wealth operating system: track the balance sheet, explain the monthly movement, separate live market marks from workbook fallbacks, and keep every decision approval-gated.</div>
          <div class="hero-meta">
            <div class="pill">A${metrics['net_worth'] / 1_000_000:,.2f}m net worth</div>
            <div class="pill {delta_tone}">{signed_money(monthly_delta)} month-on-month</div>
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
    delta_tone = tone_class(monthly_delta)
    mandates = score.head(4).to_dict("records") if not score.empty else []
    while len(mandates) < 4:
        mandates.append({"Mandate": "Control", "Read": "-", "Action": "Awaiting imported model"})
    st.markdown(
        f"""
        <div class="command-band">
          <div class="command-main">
            <div class="command-kicker">Family balance sheet command read</div>
            <div class="command-value">A${metrics.get('net_worth', 0) / 1_000_000:,.2f}m</div>
            <div class="command-subline"><span class="{delta_tone}">{signed_money(monthly_delta)} month-on-month</span>. The cockpit now treats the monthly ledger as the centre of gravity, with workbook depth and price provenance one click behind the read.</div>
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
    monthly_delta = float(metrics.get("monthly_delta") or 0)
    st.markdown(
        f"""
        <div class="metric-grid">
          <div class="mini-metric"><div class="mini-label">Net worth</div><div class="mini-value">{money(metrics.get("net_worth"))}</div><div class="mini-delta {tone_class(monthly_delta)}">{signed_money(monthly_delta)}</div></div>
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
            swing = float(row["Swing"])
            html += (
                "<div class='change-card'>"
                f"<div class='change-label'>{row['Driver']}</div>"
                f"<div class='change-value {tone_class(value)}'>{signed_money(value)}</div>"
                f"<div class='change-note'>{row['Direction']} | swing <span class='{tone_class(swing)}'>{signed_money(swing)}</span></div>"
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

    crypto_cache = cache.get("crypto", {}) if isinstance(cache, dict) else {}
    investments = read_table("investment_register")
    btc_row = pd.DataFrame()
    if not investments.empty:
        category = investments.get("Category", pd.Series("", index=investments.index)).astype(str).str.lower()
        sleeve = investments.get("Asset / sleeve", pd.Series("", index=investments.index)).astype(str).str.lower()
        btc_row = investments[category.eq("crypto") | sleeve.str.contains("btc", na=False)]

    st.markdown(
        "<div class='refresh-panel'><div class='refresh-title'>Bitcoin live feed</div>"
        "<div class='refresh-note'>Refreshes BTC-AUD and BTC-USD separately from the listed-share market tape.</div></div>",
        unsafe_allow_html=True,
    )
    b1, b2 = st.columns([0.72, 1.28])
    if b1.button("Refresh Bitcoin", width="stretch"):
        with st.spinner("Refreshing BTC-AUD and BTC-USD..."):
            cache = refresh_bitcoin_prices()
            crypto_cache = cache.get("crypto", {})
        crypto_refresh = cache.get("crypto_refresh", {})
        st.success(
            f"Bitcoin refreshed: {crypto_refresh.get('public_refreshed', 0)} of "
            f"{crypto_refresh.get('requested', 2)} public feeds updated."
        )
    b2.caption(f"Bitcoin refresh run: {cache.get('crypto_refresh', {}).get('updated_at') or 'Not refreshed yet'}")

    btc_units = pd.NA
    workbook_value = pd.NA
    if not btc_row.empty:
        btc_units = pd.to_numeric(btc_row.iloc[0].get("Units"), errors="coerce")
        workbook_value = pd.to_numeric(btc_row.iloc[0].get("Value AUD"), errors="coerce")
    btc_aud = crypto_cache.get("BTC_AUD", {})
    btc_usd = crypto_cache.get("BTC_USD", {})
    btc_aud_price = pd.to_numeric(pd.Series([btc_aud.get("price")]), errors="coerce").iloc[0]
    btc_usd_price = pd.to_numeric(pd.Series([btc_usd.get("price")]), errors="coerce").iloc[0]
    btc_units_number = pd.to_numeric(pd.Series([btc_units]), errors="coerce").iloc[0]
    live_value_aud = btc_aud_price * btc_units_number if pd.notna(btc_aud_price) and pd.notna(btc_units_number) else pd.NA
    live_value_usd = btc_usd_price * btc_units_number if pd.notna(btc_usd_price) and pd.notna(btc_units_number) else pd.NA
    card_grid(
        [
            {
                "label": "BTC-AUD",
                "value": compact_amount(btc_aud_price),
                "note": f"{compact_amount(live_value_aud)} live value | {btc_aud.get('source', 'Yahoo Finance') or 'Yahoo Finance'}",
            },
            {
                "label": "BTC-USD",
                "value": compact_amount(btc_usd_price, 'US$'),
                "note": f"{compact_amount(live_value_usd, 'US$')} live value | {btc_usd.get('source', 'Yahoo Finance') or 'Yahoo Finance'}",
            },
            {
                "label": "BTC units",
                "value": f"{btc_units_number:,.6f}" if pd.notna(btc_units_number) else "-",
                "note": "From investment register",
            },
            {
                "label": "Workbook BTC mark",
                "value": compact_amount(workbook_value),
                "note": "Fallback management value",
            },
        ]
    )
    bitcoin_display = pd.DataFrame(
        [
            {
                "Feed": "BTC-AUD",
                "Price": btc_aud_price,
                "Currency": btc_aud.get("currency", "AUD"),
                "BTC units": btc_units_number,
                "Live value AUD": live_value_aud,
                "Live value USD": pd.NA,
                "Workbook value AUD": workbook_value,
                "Source": btc_aud.get("source", ""),
                "Fetched at": btc_aud.get("fetched_at", ""),
            },
            {
                "Feed": "BTC-USD",
                "Price": btc_usd_price,
                "Currency": btc_usd.get("currency", "USD"),
                "BTC units": btc_units_number,
                "Live value AUD": pd.NA,
                "Live value USD": live_value_usd,
                "Workbook value AUD": workbook_value,
                "Source": btc_usd.get("source", ""),
                "Fetched at": btc_usd.get("fetched_at", ""),
            },
        ]
    )
    with st.expander("Bitcoin feed audit", expanded=False):
        show_table(bitcoin_display, height=180)

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

    st.markdown(
        "<div class='refresh-panel'><div class='refresh-title'>Property estimate refresh</div>"
        "<div class='refresh-note'>Separate from the market tape. Portal attempts never rewrite monthly tracking or workbook values automatically.</div></div>",
        unsafe_allow_html=True,
    )
    p1, p2 = st.columns([0.72, 1.28])
    if p1.button("Refresh property estimates", width="stretch"):
        with st.spinner("Refreshing configured public property sources..."):
            refresh_property_estimates()
        st.success("Property refresh completed. Review the status before applying any valuation changes.")
    p2.caption("If a property source blocks server-side requests or returns no structured estimate, cockpit values are retained.")
    property_refresh = property_refresh_view()
    if not property_refresh.empty:
        card_grid(
            [
                {
                    "label": str(row.get("Property", "")),
                    "value": compact_amount(row.get("Refreshed value")) if pd.notna(row.get("Refreshed value")) else compact_amount(row.get("Cockpit value")),
                    "note": str(row.get("Action", "Retained cockpit value")),
                }
                for _, row in property_refresh.head(4).iterrows()
            ]
        )
        with st.expander("Property refresh audit", expanded=False):
            show_table(property_refresh, height=260)

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


def render_no_data_state(status: dict[str, object]) -> None:
    missing = status.get("missing_tables", [])
    missing_text = ", ".join(str(item) for item in missing) if isinstance(missing, list) else "unknown"
    st.markdown(
        """
        <div class="hero">
          <div class="hero-title">Rodney<br>Wealth Cockpit</div>
          <div class="hero-sub">Private-banker dashboard is in safe no-data mode. No zero-value balance sheet, risk, evidence or allocation reads are decision-grade until the private workbook/data bundle is loaded.</div>
          <div class="hero-meta">
            <div class="pill">Data not loaded</div>
            <div class="pill">Fail closed</div>
            <div class="pill">No decisions from this state</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.error("Private operating data is not attached. The cockpit is deliberately failing closed instead of showing A$0 or clean status as if it were real.")
    show_table(
        pd.DataFrame(
            [
                {"Control": "Required operating tables", "Status": "Missing", "Detail": missing_text},
                {"Control": "Decision use", "Status": "Blocked", "Detail": "Import workbook or attach encrypted/secret data bundle first"},
                {"Control": "Update mode", "Status": "Read-only", "Detail": "Durable writes require trusted local WEALTH_COCKPIT_ENABLE_LOCAL_WRITES=1"},
                {"Control": "Authority", "Status": "Approval-gated", "Detail": AUTHORITY_BOUNDARY},
            ]
        ),
        height=210,
    )
    st.code(
        "export WEALTH_COCKPIT_WORKBOOK=\"/path/to/Rodney Wealth Cockpit.xlsx\"\n"
        "python scripts/import_workbook.py",
        language="bash",
    )


def main() -> None:
    if require_access():
        status = cockpit_data_status()
        if not status.get("loaded"):
            render_no_data_state(status)
            return
        render_header()

        view = st.selectbox(
            "View",
            ["Overview", "Market", "Property", "Model", "Governance", "Update"],
            key="main_view",
        )
        if view == "Overview":
            render_overview()
        elif view == "Market":
            render_market_tape()
        elif view == "Property":
            render_property_and_debt()
        elif view == "Model":
            render_model_library()
        elif view == "Governance":
            render_governance()
        elif view == "Update":
            render_update_flow()


if __name__ == "__main__":
    main()

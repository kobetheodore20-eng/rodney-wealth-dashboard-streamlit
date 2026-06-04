from __future__ import annotations

import pytest
import pandas as pd

from app.monthly_update import build_monthly_update_frame
from app import portfolio
from app import insights
from app.market_prices import refresh_prices


def test_outside_tolerance_public_price_uses_explicit_workbook_fallback(monkeypatch):
    holdings = pd.DataFrame(
        [
            {
                "Ticker": "ABC",
                "Currency": "AUD",
                "Shares": 10,
                "Equity / value native": 1_000,
                "Profit / loss native": 100,
                "Source": "workbook",
            }
        ]
    )

    monkeypatch.setattr(portfolio, "read_table", lambda name: holdings if name == "listed_share_snapshot" else pd.DataFrame())
    monkeypatch.setattr(
        portfolio,
        "read_price_cache",
        lambda: {"prices": {"ABC": {"price": 300, "source": "test feed"}}, "fx": {"USD_AUD": {"rate": 1}}},
    )

    result = portfolio.holdings_with_live_prices()

    assert result.loc[0, "Live price"] == 100
    assert result.loc[0, "Price basis"] == "Workbook fallback - public outside tolerance"
    assert result.loc[0, "Provenance status"] == "workbook_fallback_public_outside_tolerance"
    assert result.loc[0, "Tolerance check"] == "Outside 50% tolerance"

    source = portfolio.price_source_view()
    assert source.loc[source["Ticker"].eq("ABC"), "Price as of"].iloc[0] == "Workbook fallback; public price outside tolerance"


def test_allocation_and_brief_tolerate_missing_data_bundle(monkeypatch):
    monkeypatch.setattr(portfolio, "read_table", lambda name: pd.DataFrame())

    allocation = portfolio.allocation_view()
    brief = portfolio.executive_brief()

    assert "Asset class" in allocation.columns
    assert allocation.empty
    assert brief[0]["title"] == "Chief Read"


def test_stale_cached_price_is_not_reported_as_fresh_public(monkeypatch):
    holdings = pd.DataFrame(
        [
            {
                "Ticker": "ABC",
                "Currency": "AUD",
                "Shares": 10,
                "Equity / value native": 1_000,
                "Profit / loss native": 100,
                "Source": "workbook",
            }
        ]
    )

    monkeypatch.setattr(portfolio, "read_table", lambda name: holdings if name == "listed_share_snapshot" else pd.DataFrame())
    monkeypatch.setattr(
        portfolio,
        "read_price_cache",
        lambda: {
            "prices": {"ABC": {"price": 105, "source": "cached feed"}},
            "fx": {"USD_AUD": {"rate": 1}},
            "provenance": {"ABC": {"status": "stale_cache_after_refresh_error"}},
        },
    )

    result = portfolio.holdings_with_live_prices()

    assert result.loc[0, "Price basis"] == "Stale cached public feed"
    assert result.loc[0, "Provenance status"] == "stale_cache_price_used"


def test_monthly_update_recomputes_existing_delta_columns():
    monthly = pd.DataFrame(
        [
            {
                "Date": "2026-01-31",
                "Cash / offsets": 100,
                "Property value": 500,
                "Property equity": 400,
                "Crypto": 10,
                "Shares": 20,
                "Super": 30,
                "Total assets": 660,
                "Total debt": 100,
                "Net debt": 0,
                "Net worth": 560,
                "Net worth MoM": 0,
                "Net worth MoM %": 0,
                "Total debt MoM": 0,
                "Debt reduction": 0,
                "Cash Δ": 0,
                "Equity Δ": 0,
                "Crypto Δ": 0,
                "Shares Δ": 0,
                "Super Δ": 0,
                "Debt Δ": 0,
            }
        ]
    )
    new_row = {
        "Date": "2026-02-28",
        "Cash / offsets": 120,
        "Property value": 500,
        "Property equity": 380,
        "Crypto": 10,
        "Shares": 30,
        "Super": 40,
        "Total assets": 700,
        "Total debt": 120,
        "Net debt": 0,
        "Net worth": 580,
    }

    result = build_monthly_update_frame(monthly, new_row)

    latest = result.iloc[-1]
    assert latest["Net worth MoM"] == 20
    assert latest["Net worth MoM %"] == pytest.approx(20 / 560)
    assert latest["Total debt MoM"] == 20
    assert latest["Debt reduction"] == -20
    assert latest["Cash Δ"] == 20
    assert latest["Equity Δ"] == -20
    assert latest["Shares Δ"] == 10
    assert latest["Super Δ"] == 10
    assert latest["Debt Δ"] == -20


def test_refresh_prices_reports_unique_counts_and_stale_cache(monkeypatch):
    monkeypatch.setattr(
        "app.market_prices.read_price_cache",
        lambda: {
            "prices": {"ABC": {"price": 10, "symbol": "ABC", "source": "cached feed"}},
            "fx": {"USD_AUD": {"rate": 1.5}},
        },
    )
    monkeypatch.setattr("app.market_prices.fetch_yahoo_price", lambda symbol: (_ for _ in ()).throw(RuntimeError("feed down")))
    monkeypatch.setattr("app.market_prices.fetch_usd_aud", lambda: {"rate": 1.6, "source": "fx"})
    monkeypatch.setattr("app.market_prices.save_price_cache", lambda cache: None)

    result = refresh_prices(["ABC", "ABC", "BAD!"])

    assert result["refresh"]["requested_unique_tickers"] == 1
    assert result["refresh"]["public_refreshed"] == 0
    assert result["refresh"]["stale_cache"] == 1
    assert result["provenance"]["ABC"]["status"] == "stale_cache_after_refresh_error"


def test_monthly_attribution_sorts_by_absolute_current_impact(monkeypatch):
    monthly = pd.DataFrame(
        [
            {"Date": "2026-01-01", "Cash / offsets": 100, "Property value": 500, "Property equity": 400, "Crypto": 100, "Shares": 100, "Super": 100, "Total assets": 900, "Total debt": 100, "Net debt": 0, "Net worth": 800},
            {"Date": "2026-02-01", "Cash / offsets": 120, "Property value": 500, "Property equity": 405, "Crypto": 70, "Shares": 160, "Super": 100, "Total assets": 950, "Total debt": 95, "Net debt": -25, "Net worth": 855},
        ]
    )
    monkeypatch.setattr(portfolio, "read_table", lambda name: monthly if name == "monthly_tracking" else pd.DataFrame())

    result = insights.monthly_attribution()

    assert result.loc[0, "Driver"] == "Shares"
    assert result.loc[0, "This month"] == 60
    assert result.loc[1, "Driver"] == "Crypto"

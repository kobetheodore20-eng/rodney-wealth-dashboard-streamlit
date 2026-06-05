from __future__ import annotations

import base64
import io
import zipfile

import pytest
import pandas as pd

from app.monthly_update import build_monthly_update_frame
from app import portfolio
from app import insights
from app import data_store
from app.market_prices import refresh_prices
from scripts.import_workbook import enforce_formula_fidelity


def zipped_csv_b64(name: str, csv_text: str) -> str:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as bundle:
        bundle.writestr(f"{name}.csv", csv_text)
    return base64.b64encode(payload.getvalue()).decode("ascii")


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


def test_allocation_and_brief_fail_closed_without_data_bundle(monkeypatch):
    monkeypatch.setattr(portfolio, "read_table", lambda name: pd.DataFrame())
    monkeypatch.setattr(insights, "read_table", lambda name: pd.DataFrame())

    allocation = portfolio.allocation_view()
    brief = portfolio.executive_brief()
    scorecard = insights.wealth_scorecard()
    signals = insights.banker_signals()
    risks = portfolio.risk_summary()
    checklist = insights.update_checklist()

    assert "Asset class" in allocation.columns
    assert allocation.empty
    assert brief[0]["status"] == "Fail closed"
    assert scorecard.loc[0, "Read"] == "Data not loaded"
    assert scorecard.loc[0, "Quality"] == "Fail closed"
    assert signals[0].status == "Fail closed"
    assert "Data not loaded" in risks.loc[0, "Status"]
    assert checklist.loc[0, "Status"] == "Blocked - not loaded"


def test_read_table_prefers_encrypted_bundle_over_stale_secret(monkeypatch, tmp_path):
    monkeypatch.setattr(data_store, "DATA_DIR", tmp_path)

    def bundle_with(value: str) -> zipfile.ZipFile:
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as bundle:
            bundle.writestr("asset.csv", f"source,value\n{value},1\n")
        return zipfile.ZipFile(io.BytesIO(payload.getvalue()))

    monkeypatch.setattr(data_store, "encrypted_data_bundle", lambda: bundle_with("encrypted"))
    monkeypatch.setattr(data_store, "secret_data_bundle", lambda: bundle_with("stale-secret"))

    result = data_store.read_table("asset")

    assert result.loc[0, "source"] == "encrypted"


def test_read_table_falls_back_to_secret_when_encrypted_bundle_is_invalid(monkeypatch, tmp_path):
    from cryptography.fernet import Fernet

    invalid_bundle_path = tmp_path / "data_bundle.enc"
    invalid_bundle_path.write_bytes(b"not a valid encrypted bundle")
    monkeypatch.setattr(data_store, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(data_store, "ENCRYPTED_DATA_BUNDLE_PATH", invalid_bundle_path)
    monkeypatch.setenv("WEALTH_COCKPIT_DATA_BUNDLE_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setenv("WEALTH_COCKPIT_DATA_BUNDLE_B64", zipped_csv_b64("asset", "source,value\nsecret,1\n"))

    result = data_store.read_table("asset")

    assert result.loc[0, "source"] == "secret"


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


def test_malformed_required_tables_fail_closed(monkeypatch):
    junk = pd.DataFrame([{"Wrong": "not a model"}])
    monkeypatch.setattr(portfolio, "read_table", lambda name: junk)
    monkeypatch.setattr(insights, "read_table", lambda name: junk)

    status = portfolio.cockpit_data_status()
    brief = portfolio.executive_brief()
    risks = portfolio.risk_summary()
    scorecard = insights.wealth_scorecard()

    assert status["loaded"] is False
    assert "monthly_tracking" in status["invalid_tables"]
    assert "balance_sheet" in status["invalid_tables"]
    assert brief[0]["status"] == "Fail closed"
    assert "Data not loaded" in risks.loc[0, "Status"]
    assert scorecard.loc[0, "Quality"] == "Fail closed"


def test_usd_holding_blocks_aud_valuation_when_fx_missing(monkeypatch):
    holdings = pd.DataFrame(
        [
            {
                "Ticker": "GOOG",
                "Currency": "USD",
                "Shares": 2,
                "Equity / value native": 200,
                "Profit / loss native": 20,
                "Source": "workbook",
            }
        ]
    )
    monkeypatch.setattr(portfolio, "read_table", lambda name: holdings if name == "listed_share_snapshot" else pd.DataFrame())
    monkeypatch.setattr(portfolio, "read_price_cache", lambda: {"prices": {"GOOG": {"price": 110, "source": "test feed"}}, "fx": {}})

    result = portfolio.holdings_with_live_prices()
    sources = portfolio.price_source_view()

    assert result.loc[0, "Live price"] == 110
    assert pd.isna(result.loc[0, "Live value AUD"])
    assert pd.isna(result.loc[0, "Cost base AUD"])
    assert result.loc[0, "Provenance status"] == "fx_unavailable_usd_aud"
    assert result.loc[0, "Price basis"] == "FX unavailable - AUD value blocked"
    assert sources.loc[sources["Ticker"].eq("USD/AUD"), "Provenance status"].iloc[0] == "fx_unavailable"


def test_monthly_update_updates_balance_sheet_core_rows_atomically():
    from app.monthly_update import apply_monthly_row_to_balance_sheet

    balance = pd.DataFrame(
        [
            {"Asset class": "Cash / offsets", "Current value": 100, "Target base": 0.2},
            {"Asset class": "Property equity", "Current value": 400, "Target base": 0.5},
            {"Asset class": "Crypto", "Current value": 10, "Target base": 0.05},
            {"Asset class": "Shares", "Current value": 20, "Target base": 0.15},
            {"Asset class": "Super", "Current value": 30, "Target base": 0.15},
            {"Asset class": "TOTAL DEBT", "Current value": 100, "Target base": ""},
            {"Asset class": "TOTAL ASSETS", "Current value": 660, "Target base": ""},
            {"Asset class": "NET DEBT", "Current value": 0, "Target base": ""},
            {"Asset class": "NET WORTH", "Current value": 560, "Target base": ""},
        ]
    )
    new_row = {
        "Cash / offsets": 120,
        "Property equity": 380,
        "Crypto": 15,
        "Shares": 40,
        "Super": 45,
        "Total debt": 120,
        "Total assets": 720,
        "Net debt": 0,
        "Net worth": 600,
    }

    result = apply_monthly_row_to_balance_sheet(balance, new_row)
    lookup = result.set_index("Asset class")["Current value"]

    assert lookup["Cash / offsets"] == 120
    assert lookup["Property equity"] == 380
    assert lookup["Shares"] == 40
    assert lookup["TOTAL DEBT"] == 120
    assert lookup["TOTAL ASSETS"] == 720
    assert lookup["NET WORTH"] == 600
    assert result.loc[result["Asset class"].eq("NET WORTH"), "Notes"].iloc[0] == "Updated atomically from monthly update row"


def test_formula_fidelity_blocks_operating_sheet_with_blank_formula_cache():
    audit = {
        "01 Executive Dashboard": {"Formula cached blanks": 0},
        "13 Monthly Tracking": {"Formula cached blanks": 2},
    }

    with pytest.raises(ValueError, match="13 Monthly Tracking"):
        enforce_formula_fidelity(audit)

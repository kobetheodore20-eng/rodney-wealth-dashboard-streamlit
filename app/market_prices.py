from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
import re

import requests

from app.data_store import read_price_cache, save_price_cache


YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

TICKER_MAP = {
    "WIRE": "WIRE.AX",
    "VBTC": "VBTC.AX",
    "PGA1": "PGA1.AX",
    "PMGOLD": "PMGOLD.AX",
    "TSLA": "TSLA",
    "GOOG": "GOOG",
    "SOFI": "SOFI",
    "RIOT": "RIOT",
    "NVDA": "NVDA",
    "PLTR": "PLTR",
    "BTC": "BTC-AUD",
    "BTC_AUD": "BTC-AUD",
    "BTC_USD": "BTC-USD",
}

INVALID_TICKERS = {"", "AUD", "USD", "AUD EQUIVALENT", "NATIVE CURRENCY", "TOTAL", "NAN"}


def yahoo_symbol(ticker: str) -> str:
    ticker = str(ticker).strip().upper()
    return TICKER_MAP.get(ticker, ticker)


def is_trackable_ticker(ticker: str) -> bool:
    ticker = str(ticker).strip().upper()
    if ticker in INVALID_TICKERS:
        return False
    return bool(re.fullmatch(r"[A-Z0-9]{1,8}", ticker))


def fetch_yahoo_price(symbol: str) -> dict[str, object]:
    url = YAHOO_CHART.format(symbol=symbol)
    response = requests.get(
        url,
        params={"range": "1d", "interval": "1d"},
        headers={"User-Agent": "Mozilla/5.0 Rodney Wealth Cockpit"},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    result = payload["chart"]["result"][0]
    meta = result["meta"]
    price = meta.get("regularMarketPrice") or meta.get("previousClose")
    if price is None:
        raise ValueError(f"No public price returned for {symbol}")
    currency = meta.get("currency", "")
    return {
        "symbol": symbol,
        "price": price,
        "currency": currency,
        "market_time": meta.get("regularMarketTime"),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "Yahoo Finance chart endpoint",
    }


def fetch_usd_aud() -> dict[str, object]:
    response = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
    response.raise_for_status()
    payload = response.json()
    rate = payload.get("rates", {}).get("AUD")
    try:
        rate = float(rate)
    except (TypeError, ValueError) as exc:
        raise ValueError("No usable USD/AUD public FX rate returned") from exc
    if rate <= 0:
        raise ValueError("No usable USD/AUD public FX rate returned")
    return {
        "pair": "USD/AUD",
        "rate": rate,
        "source": "open.er-api.com",
        "source_time": payload.get("time_last_update_utc"),
    }


def refresh_prices(tickers: Iterable[str]) -> dict[str, object]:
    cache = read_price_cache()
    requested = sorted({str(t).strip().upper() for t in tickers if is_trackable_ticker(str(t))})
    previous_prices = cache.get("prices", {})
    prices = {ticker: previous_prices.get(ticker, {}) for ticker in requested if previous_prices.get(ticker)}
    errors: dict[str, str] = {}
    provenance: dict[str, dict[str, object]] = {}
    refreshed_count = 0
    stale_cache_count = 0
    unavailable_count = 0

    for ticker in requested:
        symbol = yahoo_symbol(ticker)
        try:
            prices[ticker] = fetch_yahoo_price(symbol)
            provenance[ticker] = {
                "status": "public_refreshed",
                "symbol": symbol,
                "source": prices[ticker].get("source"),
                "fetched_at": prices[ticker].get("fetched_at"),
            }
            refreshed_count += 1
        except Exception as exc:  # noqa: BLE001 - surface data-source failure in UI.
            errors[ticker] = str(exc)
            if previous_prices.get(ticker):
                prices[ticker] = previous_prices[ticker]
                provenance[ticker] = {
                    "status": "stale_cache_after_refresh_error",
                    "symbol": previous_prices[ticker].get("symbol") or symbol,
                    "source": previous_prices[ticker].get("source"),
                    "error": str(exc),
                }
                stale_cache_count += 1
            else:
                provenance[ticker] = {
                    "status": "public_unavailable_no_cache",
                    "symbol": symbol,
                    "error": str(exc),
                }
                unavailable_count += 1

    try:
        fx = {"USD_AUD": fetch_usd_aud()}
        fx_status = "public_refreshed"
    except Exception as exc:  # noqa: BLE001
        fx = cache.get("fx", {})
        errors["USD/AUD"] = str(exc)
        fx_status = "stale_cache_after_refresh_error" if fx else "public_unavailable_no_cache"

    refresh = {
        "requested_unique_tickers": len(requested),
        "public_refreshed": refreshed_count,
        "stale_cache": stale_cache_count,
        "public_unavailable_no_cache": unavailable_count,
        "fx_status": fx_status,
    }

    cache = {
        "prices": prices,
        "fx": fx,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "errors": errors,
        "provenance": provenance,
        "refresh": refresh,
    }
    save_price_cache(cache)
    return cache


def refresh_bitcoin_prices() -> dict[str, object]:
    cache = read_price_cache()
    crypto = cache.get("crypto", {})
    errors = cache.get("errors", {}).copy()
    refreshed = 0
    for key, symbol in {"BTC_AUD": "BTC-AUD", "BTC_USD": "BTC-USD"}.items():
        try:
            crypto[key] = fetch_yahoo_price(symbol)
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
    save_price_cache(cache)
    return cache

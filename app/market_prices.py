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
        "source": "Yahoo Finance chart endpoint",
    }


def fetch_usd_aud() -> dict[str, object]:
    response = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10)
    response.raise_for_status()
    payload = response.json()
    rate = payload.get("rates", {}).get("AUD")
    return {
        "pair": "USD/AUD",
        "rate": rate,
        "source": "open.er-api.com",
        "source_time": payload.get("time_last_update_utc"),
    }


def refresh_prices(tickers: Iterable[str]) -> dict[str, object]:
    cache = read_price_cache()
    requested = sorted({str(t).strip().upper() for t in tickers if is_trackable_ticker(str(t))})
    prices = {ticker: cache.get("prices", {}).get(ticker, {}) for ticker in requested if cache.get("prices", {}).get(ticker)}
    errors: dict[str, str] = {}

    for ticker in requested:
        symbol = yahoo_symbol(ticker)
        try:
            prices[ticker] = fetch_yahoo_price(symbol)
        except Exception as exc:  # noqa: BLE001 - surface data-source failure in UI.
            errors[ticker] = str(exc)

    try:
        fx = {"USD_AUD": fetch_usd_aud()}
    except Exception as exc:  # noqa: BLE001
        fx = cache.get("fx", {})
        errors["USD/AUD"] = str(exc)

    cache = {
        "prices": prices,
        "fx": fx,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "errors": errors,
    }
    save_price_cache(cache)
    return cache

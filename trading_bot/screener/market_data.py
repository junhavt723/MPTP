"""
Korean market data utilities.

- KRX listing  → kind.krx.co.kr  (one HTTP call, all names/codes)
- Bulk prices  → yfinance batched (30 symbols/batch, 1.5 s delay, retry on 429)
- Price cache  → local JSON file (5-minute TTL) so repeated runs are instant
"""

from __future__ import annotations

import io
import json
import os
import time
import warnings
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import List

warnings.filterwarnings("ignore")

_KRX_URL = (
    "https://kind.krx.co.kr/corpgeneral/corpList.do"
    "?method=download&searchType=13"
)
_HEADERS = {"User-Agent": "Mozilla/5.0"}
_CACHE_FILE = os.path.join(os.path.dirname(__file__), ".price_cache.json")
_CACHE_TTL_SEC = 300       # 5 minutes
_BATCH_SIZE    = 30
_BATCH_DELAY   = 1.5       # seconds between batches
_RATE_LIMIT_WAIT = 10      # seconds to wait after 429


# ─────────────────────────────────────────────────────────────────────────────
# KRX listing
# ─────────────────────────────────────────────────────────────────────────────

def fetch_krx_listing() -> pd.DataFrame:
    """
    Download the full KOSPI + KOSDAQ listing from KRX KIND.
    Returns DataFrame: ticker (str "012345"), name, market.
    """
    resp = requests.get(_KRX_URL, headers=_HEADERS, timeout=20)
    resp.raise_for_status()
    df = pd.read_html(io.StringIO(resp.text))[0]
    df = df.rename(columns={
        "회사명": "name",
        "시장구분": "market_raw",
        "종목코드": "ticker_raw",
    })
    df["ticker"] = df["ticker_raw"].astype(str).str.zfill(6)
    df = df[df["ticker"].str.match(r"^\d{6}$")].copy()
    df["market"] = df["market_raw"].map(
        {"유가증권": "KOSPI", "코스닥": "KOSDAQ"}
    ).fillna(df["market_raw"])
    return df[["ticker", "name", "market"]].reset_index(drop=True)


def ticker_to_yf(ticker: str, market: str) -> str:
    suffix = ".KS" if market == "KOSPI" else ".KQ"
    return ticker + suffix


# ─────────────────────────────────────────────────────────────────────────────
# Price cache helpers
# ─────────────────────────────────────────────────────────────────────────────

def _load_cache() -> tuple[dict[str, float], datetime | None]:
    """Return (prices_dict, timestamp) or ({}, None) if missing/expired."""
    if not os.path.exists(_CACHE_FILE):
        return {}, None
    try:
        with open(_CACHE_FILE) as f:
            data = json.load(f)
        ts = datetime.fromisoformat(data["ts"])
        if datetime.now() - ts > timedelta(seconds=_CACHE_TTL_SEC):
            return {}, None
        return data["prices"], ts
    except Exception:
        return {}, None


def _save_cache(prices: dict[str, float]) -> None:
    try:
        with open(_CACHE_FILE, "w") as f:
            json.dump({"ts": datetime.now().isoformat(), "prices": prices}, f)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Batched yfinance fetching with retry on rate-limit
# ─────────────────────────────────────────────────────────────────────────────

def _download_batch(symbols: list[str], period: str = "5d") -> dict[str, float]:
    """Download latest close for a single batch. Returns {symbol: price}."""
    for attempt in range(3):
        try:
            if len(symbols) == 1:
                df = yf.download(
                    symbols[0], period=period, interval="1d",
                    auto_adjust=True, progress=False
                )
                if df.empty:
                    return {}
                return {symbols[0]: float(df["Close"].dropna().iloc[-1])}

            df = yf.download(
                symbols, period=period, interval="1d",
                auto_adjust=True, progress=False, threads=False
            )
            if df.empty:
                return {}

            prices: dict[str, float] = {}
            for sym in symbols:
                try:
                    col = df["Close"][sym].dropna()
                    if not col.empty:
                        prices[sym] = float(col.iloc[-1])
                except Exception:
                    pass
            return prices

        except Exception as e:
            err = str(e).lower()
            if "rate" in err or "too many" in err or "429" in err:
                wait = _RATE_LIMIT_WAIT * (attempt + 1)
                time.sleep(wait)
            else:
                break
    return {}


def fetch_latest_prices(
    symbols: list[str],
    use_cache: bool = True,
    show_progress: bool = False,
) -> dict[str, float]:
    """
    Fetch the latest closing price for a list of yfinance symbols.

    - Checks local cache first (5-min TTL).
    - Downloads missing symbols in batches of 30.
    - Saves updated cache.
    """
    if use_cache:
        cached, ts = _load_cache()
        missing = [s for s in symbols if s not in cached]
    else:
        cached, missing = {}, list(symbols)

    if not missing:
        return {s: cached[s] for s in symbols if s in cached}

    fresh: dict[str, float] = {}
    total_batches = (len(missing) + _BATCH_SIZE - 1) // _BATCH_SIZE

    for i in range(0, len(missing), _BATCH_SIZE):
        batch = missing[i : i + _BATCH_SIZE]
        batch_num = i // _BATCH_SIZE + 1

        if show_progress:
            pct = batch_num / total_batches * 100
            bar_len = 30
            filled = int(bar_len * batch_num / total_batches)
            bar = "█" * filled + "░" * (bar_len - filled)
            print(
                f"\r  [{bar}] {pct:4.0f}%  ({batch_num}/{total_batches} 배치)",
                end="",
                flush=True,
            )

        batch_prices = _download_batch(batch)
        fresh.update(batch_prices)

        if i + _BATCH_SIZE < len(missing):
            time.sleep(_BATCH_DELAY)

    if show_progress:
        print()  # newline after progress bar

    # Merge and save cache
    combined = {**cached, **fresh}
    _save_cache(combined)

    return {s: combined[s] for s in symbols if s in combined}


# ─────────────────────────────────────────────────────────────────────────────
# Historical OHLCV
# ─────────────────────────────────────────────────────────────────────────────

def fetch_ohlcv_bulk(
    symbols: list[str],
    period: str = "3mo",
    interval: str = "1d",
) -> dict[str, pd.DataFrame]:
    """Download OHLCV history for multiple symbols."""
    results: dict[str, pd.DataFrame] = {}

    for i in range(0, len(symbols), _BATCH_SIZE):
        batch = symbols[i : i + _BATCH_SIZE]

        for attempt in range(3):
            try:
                if len(batch) == 1:
                    raw = yf.download(
                        batch[0], period=period, interval=interval,
                        auto_adjust=True, progress=False
                    )
                    if not raw.empty:
                        results[batch[0]] = raw[["Open","High","Low","Close","Volume"]].dropna()
                else:
                    raw = yf.download(
                        batch, period=period, interval=interval,
                        group_by="ticker", auto_adjust=True,
                        progress=False, threads=False
                    )
                    for sym in batch:
                        try:
                            df = raw[sym][["Open","High","Low","Close","Volume"]].dropna()
                            if not df.empty:
                                results[sym] = df
                        except Exception:
                            pass
                break
            except Exception as e:
                if "rate" in str(e).lower():
                    time.sleep(_RATE_LIMIT_WAIT * (attempt + 1))
                else:
                    break

        if i + _BATCH_SIZE < len(symbols):
            time.sleep(_BATCH_DELAY)

    return results

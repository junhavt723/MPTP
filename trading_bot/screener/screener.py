"""
Korean low-price stock screener.

Workflow:
  1. Fetch full KRX listing (KOSPI + KOSDAQ)
  2. Download latest prices (batched, cached for 5 min)
  3. Filter by price range and minimum volume
  4. For qualifying stocks, compute technical indicators (RSI, MA)
  5. Score and rank by opportunity strength
"""

from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List

from screener.market_data import (
    fetch_krx_listing,
    ticker_to_yf,
    fetch_ohlcv_bulk,
    fetch_latest_prices,
)
from strategies.rsi import _compute_rsi
import config


@dataclass
class StockOpportunity:
    ticker: str
    yf_symbol: str
    name: str
    market: str
    price: float
    change_pct: float
    volume: int
    rsi: float
    ma_signal: str      # "BUY" / "SELL" / "ABOVE" / "BELOW" / "HOLD"
    score: float        # 0–100
    reason: str


def _ma_signal(df: pd.DataFrame) -> str:
    if len(df) < config.MA_LONG + 1:
        return "HOLD"
    ma_s = df["Close"].rolling(config.MA_SHORT).mean()
    ma_l = df["Close"].rolling(config.MA_LONG).mean()
    if ma_s.iloc[-2] <= ma_l.iloc[-2] and ma_s.iloc[-1] > ma_l.iloc[-1]:
        return "BUY"
    if ma_s.iloc[-2] >= ma_l.iloc[-2] and ma_s.iloc[-1] < ma_l.iloc[-1]:
        return "SELL"
    return "ABOVE" if ma_s.iloc[-1] > ma_l.iloc[-1] else "BELOW"


def _score(rsi: float, ma_signal: str, change_pct: float, volume: int) -> tuple[float, str]:
    score = 0.0
    reasons: list[str] = []

    # RSI (0–40)
    if rsi <= 20:
        score += 40; reasons.append(f"RSI 극도 과매도({rsi:.0f})")
    elif rsi <= 30:
        score += 30; reasons.append(f"RSI 과매도({rsi:.0f})")
    elif rsi <= 40:
        score += 15; reasons.append(f"RSI 낮음({rsi:.0f})")

    # MA (0–30)
    if ma_signal == "BUY":
        score += 30; reasons.append("골든크로스")
    elif ma_signal == "ABOVE":
        score += 10; reasons.append("단기MA 위")

    # Price momentum (0–20)
    if -3 <= change_pct <= 0:
        score += 10; reasons.append("소폭 하락(매수 기회)")
    elif 0 < change_pct <= 3:
        score += 20; reasons.append("소폭 상승 반전")
    elif change_pct > 3:
        score += 5; reasons.append(f"급등 +{change_pct:.1f}%")

    # Volume (0–10)
    if volume >= 1_000_000:
        score += 10; reasons.append("거래량 풍부")
    elif volume >= 500_000:
        score += 5; reasons.append("거래량 양호")

    return score, " | ".join(reasons) if reasons else "신호 없음"


def run_screen(
    max_price: int = config.SCREEN_MAX_PRICE,
    min_price: int = config.SCREEN_MIN_PRICE,
    min_volume: int = config.SCREEN_MIN_VOLUME,
    top_n: int = config.SCREEN_TOP_N,
    market: str = config.SCREEN_MARKET,
    verbose: bool = True,
) -> List[StockOpportunity]:
    """Full pipeline: returns top_n StockOpportunity sorted by score desc."""

    # ── 1. KRX listing ──────────────────────────────────────────────────
    if verbose:
        print("  [1/4] KRX 종목 목록 불러오는 중…", flush=True)
    listing = fetch_krx_listing()
    if market != "ALL":
        listing = listing[listing["market"] == market]
    listing["yf_symbol"] = listing.apply(
        lambda r: ticker_to_yf(r["ticker"], r["market"]), axis=1
    )
    all_symbols = listing["yf_symbol"].tolist()

    # ── 2. Bulk price fetch (cached) ─────────────────────────────────────
    if verbose:
        print(
            f"  [2/4] {len(all_symbols)}개 종목 현재가 조회 중…"
            " (캐시 없으면 수분 소요)",
            flush=True,
        )
    prices = fetch_latest_prices(all_symbols, use_cache=True, show_progress=verbose)

    # ── 3. Price filter ──────────────────────────────────────────────────
    candidates = listing[
        listing["yf_symbol"].map(lambda s: min_price <= prices.get(s, 0) <= max_price)
    ].copy()
    candidates["price"] = candidates["yf_symbol"].map(prices)

    if verbose:
        print(
            f"  [3/4] 가격 필터 통과: {len(candidates)}개 "
            f"({min_price:,}~{max_price:,}원) — 기술지표 계산 중…",
            flush=True,
        )

    if candidates.empty:
        if verbose:
            print("  → 조건에 맞는 종목 없음.")
        return []

    # ── 4. Historical data + technical indicators ────────────────────────
    cand_syms = candidates["yf_symbol"].tolist()
    hist_map = fetch_ohlcv_bulk(cand_syms, period="3mo", interval="1d")

    opportunities: List[StockOpportunity] = []
    for _, row in candidates.iterrows():
        sym = row["yf_symbol"]
        df = hist_map.get(sym)
        if df is None or len(df) < 10:
            continue

        latest_vol = int(df["Volume"].iloc[-1])
        if latest_vol < min_volume:
            continue

        if len(df) >= 2:
            prev_close = float(df["Close"].iloc[-2])
            curr_close = float(df["Close"].iloc[-1])
            change_pct = (curr_close - prev_close) / prev_close * 100 if prev_close else 0.0
        else:
            change_pct = 0.0

        rsi_series = _compute_rsi(df["Close"], config.RSI_PERIOD)
        rsi_val = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0
        if np.isnan(rsi_val):
            rsi_val = 50.0

        ma_sig = _ma_signal(df)
        score, reason = _score(rsi_val, ma_sig, change_pct, latest_vol)

        opportunities.append(StockOpportunity(
            ticker=row["ticker"],
            yf_symbol=sym,
            name=row["name"],
            market=row["market"],
            price=float(row["price"]),
            change_pct=change_pct,
            volume=latest_vol,
            rsi=rsi_val,
            ma_signal=ma_sig,
            score=score,
            reason=reason,
        ))

    opportunities.sort(key=lambda x: x.score, reverse=True)

    if verbose:
        print(
            f"  [4/4] 완료 — 유효 {len(opportunities)}개 중 상위 {min(top_n, len(opportunities))}개\n",
            flush=True,
        )

    return opportunities[:top_n]

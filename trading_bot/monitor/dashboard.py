"""
Real-time terminal dashboard.

Clears the screen and redraws a ranked opportunity table every N seconds.
Press Ctrl+C to stop.
"""

from __future__ import annotations

import os
import sys
import time
import datetime
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tabulate import tabulate
from screener.screener import run_screen, StockOpportunity
from screener.market_data import fetch_latest_prices
import config

# ANSI colour helpers
_RED    = "\033[91m"
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_BOLD   = "\033[1m"
_RESET  = "\033[0m"
_CLEAR  = "\033[2J\033[H"   # clear screen + move cursor to top


def _clr(text: str, code: str) -> str:
    """Wrap text in an ANSI colour if stdout is a TTY."""
    if not sys.stdout.isatty():
        return text
    return f"{code}{text}{_RESET}"


def _fmt_price(price: float) -> str:
    return f"{price:,.0f}원"


def _fmt_change(pct: float) -> str:
    sign = "+" if pct >= 0 else ""
    s = f"{sign}{pct:.2f}%"
    if pct > 0:
        return _clr(s, _RED)      # Korean convention: red = up
    elif pct < 0:
        return _clr(s, _GREEN)    # green = down
    return s


def _fmt_signal(sig: str) -> str:
    if sig == "BUY":
        return _clr("★BUY", _RED + _BOLD)
    elif sig == "SELL":
        return _clr("▼SELL", _GREEN)
    elif sig == "ABOVE":
        return _clr("↑위", _YELLOW)
    elif sig == "BELOW":
        return _clr("↓아래", _CYAN)
    return sig


def _fmt_rsi(rsi: float) -> str:
    s = f"{rsi:.1f}"
    if rsi <= 30:
        return _clr(s, _RED + _BOLD)
    elif rsi <= 40:
        return _clr(s, _YELLOW)
    elif rsi >= 70:
        return _clr(s, _GREEN)
    return s


def _fmt_score(score: float) -> str:
    s = f"{score:.0f}"
    if score >= 60:
        return _clr(s, _RED + _BOLD)
    elif score >= 40:
        return _clr(s, _YELLOW)
    return s


def _fmt_volume(vol: int) -> str:
    if vol >= 1_000_000:
        return f"{vol / 1_000_000:.1f}M"
    if vol >= 1_000:
        return f"{vol / 1_000:.0f}K"
    return str(vol)


def _render_table(opportunities: list[StockOpportunity]) -> str:
    rows = []
    for rank, opp in enumerate(opportunities, 1):
        rows.append([
            rank,
            opp.ticker,
            opp.name[:12],
            opp.market,
            _fmt_price(opp.price),
            _fmt_change(opp.change_pct),
            _fmt_volume(opp.volume),
            _fmt_rsi(opp.rsi),
            _fmt_signal(opp.ma_signal),
            _fmt_score(opp.score),
            opp.reason[:35],
        ])
    return tabulate(
        rows,
        headers=["#", "코드", "종목명", "시장", "현재가", "등락", "거래량",
                 "RSI", "MA신호", "점수", "사유"],
        tablefmt="rounded_outline",
        colalign=("right", "left", "left", "left",
                  "right", "right", "right",
                  "right", "center", "right", "left"),
    )


def _header(refresh: int, cycle: int, price_range: tuple[int, int]) -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    w = shutil.get_terminal_size((80, 24)).columns
    title = _clr("  ★ TOSS 저가주 실시간 분석봇 ★  ", _BOLD + _YELLOW)
    info = (
        f"  {now}  |  새로고침 주기: {refresh}s  |  "
        f"가격범위: {price_range[0]:,}~{price_range[1]:,}원  |  "
        f"사이클: {cycle}"
    )
    sep = "─" * min(w, 100)
    return f"\n{title}\n{info}\n{sep}\n"


def _footer() -> str:
    return _clr("\n  [Ctrl+C 종료]  |  점수: RSI과매도(40) + 골든크로스(30) + 모멘텀(20) + 거래량(10)\n", _CYAN)


def _refresh_prices(opportunities: list[StockOpportunity]) -> list[StockOpportunity]:
    """Re-fetch latest prices for displayed stocks (fast update)."""
    syms = [o.yf_symbol for o in opportunities]
    prices = fetch_latest_prices(syms)
    updated = []
    for opp in opportunities:
        new_price = prices.get(opp.yf_symbol)
        if new_price is not None:
            # Recalculate change_pct relative to previous price
            if opp.price > 0:
                change = (new_price - opp.price) / opp.price * 100
            else:
                change = 0.0
            updated.append(StockOpportunity(
                ticker=opp.ticker,
                yf_symbol=opp.yf_symbol,
                name=opp.name,
                market=opp.market,
                price=new_price,
                change_pct=change,
                volume=opp.volume,
                rsi=opp.rsi,
                ma_signal=opp.ma_signal,
                score=opp.score,
                reason=opp.reason,
            ))
        else:
            updated.append(opp)
    return updated


def run_monitor(
    max_price: int = config.SCREEN_MAX_PRICE,
    min_price: int = config.SCREEN_MIN_PRICE,
    min_volume: int = config.SCREEN_MIN_VOLUME,
    top_n: int = config.SCREEN_TOP_N,
    market: str = config.SCREEN_MARKET,
    refresh: int = config.MONITOR_REFRESH_SEC,
    full_rescan_every: int = 10,   # full re-screen every N refresh cycles
) -> None:
    """
    Run the live dashboard loop.

    - Full re-screen (downloads all KRX data) every full_rescan_every × refresh seconds
    - Price-only refresh on every other cycle (much faster)
    """
    cycle = 0
    opportunities: list[StockOpportunity] = []

    print(f"\n토스 저가주 분석봇 시작\n"
          f"  가격 범위: {min_price:,}~{max_price:,}원\n"
          f"  최소 거래량: {min_volume:,}\n"
          f"  상위 {top_n}개 표시  |  새로고침: {refresh}초\n")

    try:
        while True:
            cycle += 1
            do_full = (cycle == 1) or (cycle % full_rescan_every == 0)

            if do_full:
                print(f"전체 스크리닝 중… (사이클 {cycle})")
                opportunities = run_screen(
                    max_price=max_price,
                    min_price=min_price,
                    min_volume=min_volume,
                    top_n=top_n,
                    market=market,
                    verbose=True,
                )
            else:
                # Fast price update only
                opportunities = _refresh_prices(opportunities)

            # Render
            if sys.stdout.isatty():
                print(_CLEAR, end="")

            print(_header(refresh, cycle, (min_price, max_price)))

            if opportunities:
                print(_render_table(opportunities))
            else:
                print(_clr("  해당 조건의 종목이 없습니다.", _YELLOW))

            print(_footer())

            time.sleep(refresh)

    except KeyboardInterrupt:
        print("\n\n모니터링 종료.")

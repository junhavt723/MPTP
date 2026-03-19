#!/usr/bin/env python3
"""
Toss 저가주 실시간 분석봇 (Trading Bot)

Commands
────────
  screen   — 저가주 스크리닝 (1회 실행)
  monitor  — 실시간 대시보드 (자동 새로고침)
  backtest — 단일 종목 전략 백테스트
  scan     — 지정 종목 현재 신호 조회

Usage examples
────────────────
  python bot.py screen
  python bot.py screen --max-price 3000 --market KOSDAQ --top 20
  python bot.py monitor
  python bot.py monitor --max-price 5000 --refresh 60
  python bot.py backtest --symbol 005930.KS --strategy ma --trades
  python bot.py scan --symbols 005930.KS 035720.KS --strategy rsi
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from tabulate import tabulate
from data.fetcher import fetch_ohlcv
from strategies.ma_crossover import MACrossoverStrategy
from strategies.rsi import RSIStrategy
from execution.paper_trader import PaperTrader
from backtest.engine import BacktestEngine
import config

STRATEGIES = {
    "ma": MACrossoverStrategy,
    "rsi": RSIStrategy,
}


# ─────────────────────────────────────────────────────────────────────────────
# screen
# ─────────────────────────────────────────────────────────────────────────────

def cmd_screen(args):
    """One-shot low-price stock screener for Korean markets."""
    from screener.screener import run_screen

    print(f"\n{'─'*60}")
    print(f"  저가주 스크리닝  ({args.market})")
    print(f"  가격: {args.min_price:,}~{args.max_price:,}원  |  "
          f"최소 거래량: {args.min_volume:,}  |  상위 {args.top}개")
    print(f"{'─'*60}\n")

    opps = run_screen(
        max_price=args.max_price,
        min_price=args.min_price,
        min_volume=args.min_volume,
        top_n=args.top,
        market=args.market,
        verbose=True,
    )

    if not opps:
        print("조건에 맞는 종목이 없습니다.")
        return

    rows = []
    for rank, o in enumerate(opps, 1):
        sign = "+" if o.change_pct >= 0 else ""
        rows.append([
            rank,
            o.ticker,
            o.name[:14],
            o.market,
            f"{o.price:,.0f}",
            f"{sign}{o.change_pct:.2f}%",
            f"{o.volume:,}",
            f"{o.rsi:.1f}",
            o.ma_signal,
            f"{o.score:.0f}",
            o.reason[:40],
        ])

    print(tabulate(
        rows,
        headers=["#", "코드", "종목명", "시장", "현재가(원)", "등락률",
                 "거래량", "RSI", "MA신호", "점수", "사유"],
        tablefmt="rounded_outline",
    ))

    print(f"\n  ★ 상위 종목 토스에서 즉시 매수 가능: {', '.join(o.ticker for o in opps[:5])}")


# ─────────────────────────────────────────────────────────────────────────────
# monitor
# ─────────────────────────────────────────────────────────────────────────────

def cmd_monitor(args):
    """Real-time live dashboard with auto-refresh."""
    from monitor.dashboard import run_monitor

    run_monitor(
        max_price=args.max_price,
        min_price=args.min_price,
        min_volume=args.min_volume,
        top_n=args.top,
        market=args.market,
        refresh=args.refresh,
    )


# ─────────────────────────────────────────────────────────────────────────────
# backtest
# ─────────────────────────────────────────────────────────────────────────────

def cmd_backtest(args):
    strategy = STRATEGIES[args.strategy]()
    engine = BacktestEngine(strategy, initial_capital=args.capital)

    print(f"\n{args.symbol} 백테스트 ({args.period}, {args.interval}) 데이터 다운로드 중…")
    df = fetch_ohlcv(args.symbol, period=args.period, interval=args.interval)
    print(f"  {len(df)}개 봉  ({df.index[0].date()} → {df.index[-1].date()})\n")

    result = engine.run(args.symbol, df)

    rows = [
        ["전략",         result["strategy"]],
        ["종목",         result["symbol"]],
        ["기간",         f"{result['start']} → {result['end']}"],
        ["초기 자본",     f"{result['initial_capital']:,.0f}원"],
        ["최종 평가액",   f"{result['portfolio_value']:,.0f}원"],
        ["총 손익",       f"{result['total_pnl']:+,.0f}원  ({result['total_pnl_pct']:+.2f}%)"],
        ["실현 손익",     f"{result['realized_pnl']:+,.0f}원"],
        ["거래 횟수",     result["total_trades"]],
        ["승률",          f"{result['win_rate']:.1f}%"],
        ["샤프 지수",     f"{result['sharpe']:.2f}"],
        ["최대 낙폭",     f"{result['max_drawdown_pct']:.2f}%"],
    ]
    print(tabulate(rows, tablefmt="rounded_outline"))

    if args.trades:
        sell_trades = [t for t in result["trades"] if t.side == "SELL"]
        if sell_trades:
            print("\n거래 내역:")
            trade_rows = [
                [t.time.date(), t.symbol, t.side,
                 f"{t.shares:.2f}", f"{t.price:,.0f}원",
                 f"{t.pnl:+,.0f}원", t.reason]
                for t in sell_trades
            ]
            print(tabulate(trade_rows,
                           headers=["날짜", "종목", "구분", "수량", "가격", "손익", "사유"],
                           tablefmt="simple"))


# ─────────────────────────────────────────────────────────────────────────────
# scan
# ─────────────────────────────────────────────────────────────────────────────

def cmd_scan(args):
    strategy = STRATEGIES[args.strategy]()

    print(f"\n{len(args.symbols)}개 종목 {strategy.name} 신호 조회 중…\n")
    rows = []
    for symbol in args.symbols:
        try:
            df = fetch_ohlcv(symbol, period=args.period, interval=args.interval)
            signal = strategy.generate_signal(df, symbol)
            sign = "+" if signal.price >= 0 else ""
            rows.append([symbol, signal.signal.value,
                         f"{signal.price:,.0f}원", signal.reason])
        except Exception as e:
            rows.append([symbol, "ERROR", "-", str(e)])

    print(tabulate(rows,
                   headers=["종목", "신호", "현재가", "사유"],
                   tablefmt="rounded_outline"))


# ─────────────────────────────────────────────────────────────────────────────
# Argument parser
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bot",
        description="토스 저가주 실시간 분석봇",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subs = parser.add_subparsers(dest="command", required=True)

    # ── screen ────────────────────────────────────────────────────────────
    sc = subs.add_parser("screen", help="저가주 1회 스크리닝")
    sc.add_argument("--max-price",  type=int, default=config.SCREEN_MAX_PRICE,
                    dest="max_price", help="최대 주가 (원, 기본 5000)")
    sc.add_argument("--min-price",  type=int, default=config.SCREEN_MIN_PRICE,
                    dest="min_price", help="최소 주가 (원, 기본 100)")
    sc.add_argument("--min-volume", type=int, default=config.SCREEN_MIN_VOLUME,
                    dest="min_volume", help="최소 거래량 (기본 100000)")
    sc.add_argument("--market",     default=config.SCREEN_MARKET,
                    choices=["KOSPI", "KOSDAQ", "ALL"])
    sc.add_argument("--top",        type=int, default=config.SCREEN_TOP_N,
                    help="표시할 상위 종목 수")

    # ── monitor ───────────────────────────────────────────────────────────
    mn = subs.add_parser("monitor", help="실시간 자동 새로고침 대시보드")
    mn.add_argument("--max-price",  type=int, default=config.SCREEN_MAX_PRICE,
                    dest="max_price")
    mn.add_argument("--min-price",  type=int, default=config.SCREEN_MIN_PRICE,
                    dest="min_price")
    mn.add_argument("--min-volume", type=int, default=config.SCREEN_MIN_VOLUME,
                    dest="min_volume")
    mn.add_argument("--market",     default=config.SCREEN_MARKET,
                    choices=["KOSPI", "KOSDAQ", "ALL"])
    mn.add_argument("--top",        type=int, default=config.SCREEN_TOP_N)
    mn.add_argument("--refresh",    type=int, default=config.MONITOR_REFRESH_SEC,
                    help="새로고침 주기 (초, 기본 30)")

    # ── backtest ──────────────────────────────────────────────────────────
    bt = subs.add_parser("backtest", help="종목 백테스트")
    bt.add_argument("--symbol",   default="005930.KS")
    bt.add_argument("--strategy", default="ma", choices=STRATEGIES.keys())
    bt.add_argument("--period",   default="2y")
    bt.add_argument("--interval", default="1d")
    bt.add_argument("--capital",  type=float, default=config.INITIAL_CAPITAL)
    bt.add_argument("--trades",   action="store_true")

    # ── scan ──────────────────────────────────────────────────────────────
    sv = subs.add_parser("scan", help="지정 종목 신호 조회")
    sv.add_argument("--symbols",  nargs="+", default=config.DEFAULT_SYMBOLS)
    sv.add_argument("--strategy", default="ma", choices=STRATEGIES.keys())
    sv.add_argument("--period",   default=config.DEFAULT_PERIOD)
    sv.add_argument("--interval", default=config.DEFAULT_INTERVAL)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    {"screen": cmd_screen, "monitor": cmd_monitor,
     "backtest": cmd_backtest, "scan": cmd_scan}[args.command](args)


if __name__ == "__main__":
    main()

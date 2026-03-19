#!/usr/bin/env python3
"""
Trading Bot – main CLI entry point.

Usage:
  python bot.py backtest --symbol AAPL --strategy ma
  python bot.py backtest --symbol AAPL --strategy rsi
  python bot.py scan    --symbols AAPL MSFT GOOGL --strategy ma
  python bot.py paper   --symbols AAPL MSFT GOOGL --strategy rsi
"""

import argparse
import sys
import os

# Make project root importable regardless of working directory
sys.path.insert(0, os.path.dirname(__file__))

from tabulate import tabulate
from data.fetcher import fetch_ohlcv, fetch_current_price
from strategies.ma_crossover import MACrossoverStrategy
from strategies.rsi import RSIStrategy
from execution.paper_trader import PaperTrader
from backtest.engine import BacktestEngine
import config


STRATEGIES = {
    "ma": MACrossoverStrategy,
    "rsi": RSIStrategy,
}


# ──────────────────────────────────────────────────────────────────────────────
# Sub-commands
# ──────────────────────────────────────────────────────────────────────────────

def cmd_backtest(args):
    """Run a historical backtest for a single symbol."""
    strategy = STRATEGIES[args.strategy]()
    engine = BacktestEngine(strategy, initial_capital=args.capital)

    print(f"\nFetching {args.period} of {args.interval} data for {args.symbol}…")
    df = fetch_ohlcv(args.symbol, period=args.period, interval=args.interval)
    print(f"  {len(df)} bars loaded  ({df.index[0].date()} → {df.index[-1].date()})\n")

    result = engine.run(args.symbol, df)

    # ── Summary table ──────────────────────────────────────────────────────
    rows = [
        ["Strategy",        result["strategy"]],
        ["Symbol",          result["symbol"]],
        ["Period",          f"{result['start']} → {result['end']}"],
        ["Initial capital", f"${result['initial_capital']:,.2f}"],
        ["Final value",     f"${result['portfolio_value']:,.2f}"],
        ["Total P&L",       f"${result['total_pnl']:+,.2f}  ({result['total_pnl_pct']:+.2f}%)"],
        ["Realized P&L",    f"${result['realized_pnl']:+,.2f}"],
        ["Trades",          result["total_trades"]],
        ["Win rate",        f"{result['win_rate']:.1f}%"],
        ["Sharpe ratio",    f"{result['sharpe']:.2f}"],
        ["Max drawdown",    f"{result['max_drawdown_pct']:.2f}%"],
    ]
    print(tabulate(rows, tablefmt="rounded_outline"))

    # ── Trade log ──────────────────────────────────────────────────────────
    if args.trades:
        sell_trades = [t for t in result["trades"] if t.side == "SELL"]
        if sell_trades:
            print("\nTrade log:")
            trade_rows = [
                [t.time.date(), t.symbol, t.side,
                 f"{t.shares:.4f}", f"${t.price:.2f}", f"${t.pnl:+.2f}",
                 t.reason]
                for t in sell_trades
            ]
            print(tabulate(trade_rows,
                           headers=["Date", "Symbol", "Side", "Shares",
                                    "Price", "P&L", "Reason"],
                           tablefmt="simple"))


def cmd_scan(args):
    """Scan a list of symbols and print current signals."""
    strategy = STRATEGIES[args.strategy]()

    print(f"\nScanning {len(args.symbols)} symbol(s) with {strategy.name} strategy…\n")
    rows = []
    for symbol in args.symbols:
        try:
            df = fetch_ohlcv(symbol, period=args.period, interval=args.interval)
            signal = strategy.generate_signal(df, symbol)
            rows.append([
                symbol,
                signal.signal.value,
                f"${signal.price:.2f}",
                signal.reason,
            ])
        except Exception as e:
            rows.append([symbol, "ERROR", "-", str(e)])

    print(tabulate(rows, headers=["Symbol", "Signal", "Price", "Reason"],
                   tablefmt="rounded_outline"))


def cmd_paper(args):
    """
    Run a live paper-trading session (one evaluation per cycle).
    Evaluates signals once and reports the resulting portfolio state.
    """
    strategy = STRATEGIES[args.strategy]()
    trader = PaperTrader(initial_capital=args.capital)

    print(f"\nPaper trading — {strategy.name} strategy")
    print(f"Capital: ${args.capital:,.2f} | Symbols: {', '.join(args.symbols)}\n")

    prices: dict = {}
    for symbol in args.symbols:
        try:
            df = fetch_ohlcv(symbol, period=args.period, interval=args.interval)
            price = float(df["Close"].iloc[-1])
            prices[symbol] = price

            signal = strategy.generate_signal(df, symbol)
            trade = trader.execute(signal)
            action = "→ no action"
            if trade:
                action = (f"→ {trade.side} {trade.shares:.4f} shares "
                          f"@ ${trade.price:.2f}")
            print(f"  {symbol:8s}  {signal.signal.value:4s}  {action}  ({signal.reason})")
        except Exception as e:
            print(f"  {symbol:8s}  ERROR  → {e}")

    # Risk-exit pass
    exits = trader.check_risk_exits(prices)
    for t in exits:
        print(f"  {t.symbol:8s}  RISK EXIT  → {t.reason}  P&L ${t.pnl:+.2f}")

    # Portfolio summary
    summary = trader.summary(prices)
    print()
    rows = [
        ["Cash",            f"${summary['cash']:,.2f}"],
        ["Portfolio value", f"${summary['portfolio_value']:,.2f}"],
        ["Total P&L",       f"${summary['total_pnl']:+,.2f}  ({summary['total_pnl_pct']:+.2f}%)"],
        ["Open positions",  summary["open_positions"]],
    ]
    print(tabulate(rows, tablefmt="rounded_outline"))


# ──────────────────────────────────────────────────────────────────────────────
# Argument parsing
# ──────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bot",
        description="Simple algorithmic trading bot (paper trading & backtesting)",
    )
    subs = parser.add_subparsers(dest="command", required=True)

    # ── backtest ──────────────────────────────────────────────────────────
    bt = subs.add_parser("backtest", help="Backtest a strategy on historical data")
    bt.add_argument("--symbol",   default="AAPL",    help="Ticker symbol")
    bt.add_argument("--strategy", default="ma",      choices=STRATEGIES.keys())
    bt.add_argument("--period",   default="2y",      help="Data period (e.g. 1y, 2y)")
    bt.add_argument("--interval", default="1d",      help="Bar interval (e.g. 1d, 1wk)")
    bt.add_argument("--capital",  default=config.INITIAL_CAPITAL, type=float)
    bt.add_argument("--trades",   action="store_true", help="Print trade log")

    # ── scan ──────────────────────────────────────────────────────────────
    sc = subs.add_parser("scan", help="Scan symbols for current signals")
    sc.add_argument("--symbols",  nargs="+", default=config.DEFAULT_SYMBOLS)
    sc.add_argument("--strategy", default="ma", choices=STRATEGIES.keys())
    sc.add_argument("--period",   default=config.DEFAULT_PERIOD)
    sc.add_argument("--interval", default=config.DEFAULT_INTERVAL)

    # ── paper ─────────────────────────────────────────────────────────────
    pp = subs.add_parser("paper", help="Single-cycle paper trading evaluation")
    pp.add_argument("--symbols",  nargs="+", default=config.DEFAULT_SYMBOLS)
    pp.add_argument("--strategy", default="ma", choices=STRATEGIES.keys())
    pp.add_argument("--period",   default=config.DEFAULT_PERIOD)
    pp.add_argument("--interval", default=config.DEFAULT_INTERVAL)
    pp.add_argument("--capital",  default=config.INITIAL_CAPITAL, type=float)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "backtest": cmd_backtest,
        "scan":     cmd_scan,
        "paper":    cmd_paper,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()

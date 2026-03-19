"""
Backtesting engine.

Replays historical OHLCV data bar-by-bar through a strategy and
the paper trader, then produces a performance report.
"""

from typing import List
import pandas as pd
from strategies.base import BaseStrategy
from execution.paper_trader import PaperTrader
from config import INITIAL_CAPITAL


class BacktestEngine:
    def __init__(self, strategy: BaseStrategy,
                 initial_capital: float = INITIAL_CAPITAL):
        self.strategy = strategy
        self.initial_capital = initial_capital

    def run(self, symbol: str, df: pd.DataFrame) -> dict:
        """
        Run a backtest for a single symbol.

        Args:
            symbol: Ticker symbol
            df: Full OHLCV history (sorted ascending)

        Returns:
            Result dict with trades, equity curve, and statistics.
        """
        trader = PaperTrader(self.initial_capital)
        equity_curve: List[dict] = []

        for i in range(1, len(df)):
            window = df.iloc[: i + 1]
            timestamp = window.index[-1].to_pydatetime()
            price = float(window["Close"].iloc[-1])
            prices = {symbol: price}

            # Check risk exits first
            trader.check_risk_exits(prices, timestamp)

            # Generate and execute strategy signal
            signal = self.strategy.generate_signal(window, symbol)
            trade = trader.execute(signal, timestamp)

            equity_curve.append({
                "date": timestamp,
                "price": price,
                "portfolio_value": trader.portfolio_value(prices),
                "cash": trader.cash,
                "signal": signal.signal.value,
            })

        # Close any remaining open position at last price
        last_price = float(df["Close"].iloc[-1])
        prices = {symbol: last_price}
        for sym in list(trader.positions.keys()):
            from strategies.base import Signal, TradeSignal
            trader._close_position(
                TradeSignal(Signal.SELL, sym, last_price, "End of backtest"),
                df.index[-1].to_pydatetime()
            )

        summary = trader.summary({symbol: last_price})
        summary["strategy"] = self.strategy.name
        summary["symbol"] = symbol
        summary["bars"] = len(df)
        summary["start"] = str(df.index[0].date())
        summary["end"] = str(df.index[-1].date())
        summary["equity_curve"] = pd.DataFrame(equity_curve).set_index("date")
        summary["trades"] = trader.trades

        # Sharpe ratio (annualised, daily returns)
        eq = summary["equity_curve"]["portfolio_value"]
        daily_ret = eq.pct_change().dropna()
        if daily_ret.std() > 0:
            summary["sharpe"] = (daily_ret.mean() / daily_ret.std()) * (252 ** 0.5)
        else:
            summary["sharpe"] = 0.0

        # Max drawdown
        rolling_max = eq.cummax()
        drawdown = (eq - rolling_max) / rolling_max
        summary["max_drawdown_pct"] = float(drawdown.min() * 100)

        return summary

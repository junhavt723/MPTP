"""
RSI (Relative Strength Index) Strategy.

BUY  when RSI crosses up through the oversold threshold.
SELL when RSI crosses down through the overbought threshold.
"""

import pandas as pd
import numpy as np
from .base import BaseStrategy, Signal, TradeSignal
from config import RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT


def _compute_rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


class RSIStrategy(BaseStrategy):
    def __init__(self, period: int = RSI_PERIOD,
                 oversold: float = RSI_OVERSOLD,
                 overbought: float = RSI_OVERBOUGHT):
        super().__init__("RSI")
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> TradeSignal:
        if len(df) < self.period + 1:
            return TradeSignal(Signal.HOLD, symbol, df["Close"].iloc[-1],
                               "Insufficient data")

        df = df.copy()
        df["rsi"] = _compute_rsi(df["Close"], self.period)

        prev_rsi = df["rsi"].iloc[-2]
        curr_rsi = df["rsi"].iloc[-1]
        price = df["Close"].iloc[-1]

        if prev_rsi <= self.oversold and curr_rsi > self.oversold:
            return TradeSignal(Signal.BUY, symbol, price,
                               f"RSI crossed up through oversold ({curr_rsi:.1f})",
                               confidence=(self.oversold - prev_rsi) / self.oversold)

        if prev_rsi >= self.overbought and curr_rsi < self.overbought:
            return TradeSignal(Signal.SELL, symbol, price,
                               f"RSI crossed down through overbought ({curr_rsi:.1f})",
                               confidence=(prev_rsi - self.overbought) / (100 - self.overbought))

        return TradeSignal(Signal.HOLD, symbol, price,
                           f"RSI={curr_rsi:.1f}")

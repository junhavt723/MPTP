"""
Moving Average Crossover Strategy.

BUY  when the short MA crosses above the long MA (golden cross).
SELL when the short MA crosses below the long MA (death cross).
"""

import pandas as pd
from .base import BaseStrategy, Signal, TradeSignal
from config import MA_SHORT, MA_LONG


class MACrossoverStrategy(BaseStrategy):
    def __init__(self, short_window: int = MA_SHORT, long_window: int = MA_LONG):
        super().__init__("MA Crossover")
        self.short_window = short_window
        self.long_window = long_window

    def generate_signal(self, df: pd.DataFrame, symbol: str) -> TradeSignal:
        if len(df) < self.long_window + 1:
            return TradeSignal(Signal.HOLD, symbol, df["Close"].iloc[-1],
                               "Insufficient data")

        df = df.copy()
        df["ma_short"] = df["Close"].rolling(self.short_window).mean()
        df["ma_long"] = df["Close"].rolling(self.long_window).mean()

        prev = df.iloc[-2]
        curr = df.iloc[-1]
        price = curr["Close"]

        if prev["ma_short"] <= prev["ma_long"] and curr["ma_short"] > curr["ma_long"]:
            return TradeSignal(Signal.BUY, symbol, price,
                               f"Golden cross: MA{self.short_window} crossed above MA{self.long_window}")

        if prev["ma_short"] >= prev["ma_long"] and curr["ma_short"] < curr["ma_long"]:
            return TradeSignal(Signal.SELL, symbol, price,
                               f"Death cross: MA{self.short_window} crossed below MA{self.long_window}")

        trend = "above" if curr["ma_short"] > curr["ma_long"] else "below"
        return TradeSignal(Signal.HOLD, symbol, price,
                           f"MA{self.short_window} {trend} MA{self.long_window}")

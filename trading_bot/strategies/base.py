"""
Base strategy interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import pandas as pd


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class TradeSignal:
    signal: Signal
    symbol: str
    price: float
    reason: str
    confidence: float = 1.0  # 0.0 – 1.0


class BaseStrategy(ABC):
    """All strategies must implement generate_signal."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame, symbol: str) -> TradeSignal:
        """
        Analyse price data and return a TradeSignal.

        Args:
            df: OHLCV DataFrame (sorted ascending by date)
            symbol: Ticker symbol

        Returns:
            TradeSignal
        """

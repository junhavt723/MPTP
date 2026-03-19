"""
Paper trading execution engine.

Simulates order execution without real money.
Tracks positions, cash, P&L, and trade history.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from strategies.base import Signal, TradeSignal
from config import INITIAL_CAPITAL, MAX_POSITION_PCT, STOP_LOSS_PCT, TAKE_PROFIT_PCT


@dataclass
class Position:
    symbol: str
    shares: float
    entry_price: float
    entry_time: datetime
    stop_loss: float
    take_profit: float

    @property
    def cost_basis(self) -> float:
        return self.shares * self.entry_price

    def current_value(self, price: float) -> float:
        return self.shares * price

    def unrealized_pnl(self, price: float) -> float:
        return self.current_value(price) - self.cost_basis

    def pnl_pct(self, price: float) -> float:
        return (price - self.entry_price) / self.entry_price * 100


@dataclass
class Trade:
    symbol: str
    side: str        # "BUY" or "SELL"
    shares: float
    price: float
    time: datetime
    reason: str
    pnl: float = 0.0


class PaperTrader:
    def __init__(self, initial_capital: float = INITIAL_CAPITAL):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []

    # ------------------------------------------------------------------
    # Core order execution
    # ------------------------------------------------------------------

    def execute(self, signal: TradeSignal, timestamp: Optional[datetime] = None) -> Optional[Trade]:
        """Process a TradeSignal and execute if actionable."""
        ts = timestamp or datetime.now()

        if signal.signal == Signal.BUY:
            return self._open_position(signal, ts)
        elif signal.signal == Signal.SELL:
            return self._close_position(signal, ts)
        return None

    def _open_position(self, signal: TradeSignal, ts: datetime) -> Optional[Trade]:
        symbol = signal.symbol
        if symbol in self.positions:
            return None  # Already holding; no pyramiding

        max_spend = self.cash * MAX_POSITION_PCT
        if max_spend < signal.price:
            return None  # Not enough cash for even one share

        shares = max_spend / signal.price
        cost = shares * signal.price

        if cost > self.cash:
            return None

        self.cash -= cost
        self.positions[symbol] = Position(
            symbol=symbol,
            shares=shares,
            entry_price=signal.price,
            entry_time=ts,
            stop_loss=signal.price * (1 - STOP_LOSS_PCT),
            take_profit=signal.price * (1 + TAKE_PROFIT_PCT),
        )

        trade = Trade(symbol=symbol, side="BUY", shares=shares,
                      price=signal.price, time=ts, reason=signal.reason)
        self.trades.append(trade)
        return trade

    def _close_position(self, signal: TradeSignal, ts: datetime) -> Optional[Trade]:
        symbol = signal.symbol
        if symbol not in self.positions:
            return None

        pos = self.positions.pop(symbol)
        proceeds = pos.shares * signal.price
        pnl = proceeds - pos.cost_basis
        self.cash += proceeds

        trade = Trade(symbol=symbol, side="SELL", shares=pos.shares,
                      price=signal.price, time=ts, reason=signal.reason, pnl=pnl)
        self.trades.append(trade)
        return trade

    # ------------------------------------------------------------------
    # Stop-loss / take-profit checks
    # ------------------------------------------------------------------

    def check_risk_exits(self, prices: Dict[str, float],
                         timestamp: Optional[datetime] = None) -> List[Trade]:
        """Check all open positions for stop-loss / take-profit triggers."""
        ts = timestamp or datetime.now()
        closed: List[Trade] = []
        for symbol, pos in list(self.positions.items()):
            price = prices.get(symbol)
            if price is None:
                continue
            if price <= pos.stop_loss:
                signal = TradeSignal(Signal.SELL, symbol, price,
                                     f"Stop-loss hit @ {price:.2f}")
                trade = self._close_position(signal, ts)
                if trade:
                    closed.append(trade)
            elif price >= pos.take_profit:
                signal = TradeSignal(Signal.SELL, symbol, price,
                                     f"Take-profit hit @ {price:.2f}")
                trade = self._close_position(signal, ts)
                if trade:
                    closed.append(trade)
        return closed

    # ------------------------------------------------------------------
    # Portfolio summary
    # ------------------------------------------------------------------

    def portfolio_value(self, prices: Dict[str, float]) -> float:
        position_value = sum(
            pos.current_value(prices.get(pos.symbol, pos.entry_price))
            for pos in self.positions.values()
        )
        return self.cash + position_value

    def total_pnl(self, prices: Dict[str, float]) -> float:
        return self.portfolio_value(prices) - self.initial_capital

    def summary(self, prices: Dict[str, float]) -> dict:
        portfolio_val = self.portfolio_value(prices)
        total_pnl = self.total_pnl(prices)
        realized_pnl = sum(t.pnl for t in self.trades if t.side == "SELL")
        win_trades = [t for t in self.trades if t.side == "SELL" and t.pnl > 0]
        loss_trades = [t for t in self.trades if t.side == "SELL" and t.pnl <= 0]
        win_rate = len(win_trades) / max(len(win_trades) + len(loss_trades), 1) * 100

        return {
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "portfolio_value": portfolio_val,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl / self.initial_capital * 100,
            "realized_pnl": realized_pnl,
            "open_positions": len(self.positions),
            "total_trades": len([t for t in self.trades if t.side == "SELL"]),
            "win_rate": win_rate,
        }

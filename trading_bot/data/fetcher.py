"""
Market data fetcher using yfinance.
"""

import yfinance as yf
import pandas as pd


def fetch_ohlcv(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """
    Download OHLCV data for a symbol.

    Args:
        symbol: Ticker symbol (e.g. "AAPL")
        period: History period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        interval: Bar interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)

    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
    """
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)

    if df.empty:
        raise ValueError(f"No data returned for symbol '{symbol}'")

    df.index = pd.to_datetime(df.index)
    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.dropna(inplace=True)
    return df


def fetch_current_price(symbol: str) -> float:
    """Return the latest closing price for a symbol."""
    df = fetch_ohlcv(symbol, period="5d", interval="1d")
    return float(df["Close"].iloc[-1])

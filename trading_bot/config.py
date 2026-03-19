"""
Trading bot configuration.
"""

# Default symbols to trade
DEFAULT_SYMBOLS = ["AAPL", "MSFT", "GOOGL"]

# Paper trading initial capital
INITIAL_CAPITAL = 10_000.0

# Data settings
DEFAULT_PERIOD = "1y"      # Data history period for live mode
DEFAULT_INTERVAL = "1d"    # Candle interval

# Strategy parameters
MA_SHORT = 20              # Short moving average window
MA_LONG = 50               # Long moving average window
RSI_PERIOD = 14            # RSI calculation period
RSI_OVERSOLD = 30          # RSI oversold threshold (buy signal)
RSI_OVERBOUGHT = 70        # RSI overbought threshold (sell signal)

# Risk management
MAX_POSITION_PCT = 0.20    # Max % of capital per position
STOP_LOSS_PCT = 0.05       # Stop loss %
TAKE_PROFIT_PCT = 0.10     # Take profit %

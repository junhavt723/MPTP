# Default symbols (kept for backtest/scan fallback)
DEFAULT_SYMBOLS = ["005930.KS", "035720.KS", "000660.KS"]

# Paper trading initial capital (KRW)
INITIAL_CAPITAL = 1_000_000.0  # 100만원

# Data settings
DEFAULT_PERIOD = "3mo"
DEFAULT_INTERVAL = "1d"

# Strategy parameters
MA_SHORT = 5
MA_LONG = 20
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# Risk management
MAX_POSITION_PCT = 0.20
STOP_LOSS_PCT = 0.05
TAKE_PROFIT_PCT = 0.10

# ──── Korean market screener settings ────────────────────────────────────────
# Price range for "low-priced" stocks (KRW)
SCREEN_MAX_PRICE = 5_000       # only stocks ≤ 5,000 KRW
SCREEN_MIN_PRICE = 100         # exclude sub-100 KRW (too speculative)
SCREEN_MIN_VOLUME = 100_000    # minimum daily volume for liquidity
SCREEN_TOP_N = 30              # how many candidates to return after scoring

# Monitor refresh interval (seconds)
MONITOR_REFRESH_SEC = 30

# Markets to scan: "KOSPI", "KOSDAQ", or "ALL"
SCREEN_MARKET = "ALL"

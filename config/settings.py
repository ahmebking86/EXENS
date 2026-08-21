"""
EXENS Auto - Settings
Only TG_TOKEN comes from environment.
Everything else is stored in DB via Telegram bot.
"""

import os
from dotenv import load_dotenv

load_dotenv()

TG_TOKEN = os.getenv("TG_TOKEN", "")
TG_ADMIN_IDS = [int(x) for x in os.getenv("TG_ADMIN_IDS", "").split(",") if x.strip()]

# Default coins (can be changed later via bot)
DEFAULT_WATCH_COINS = [
    "BTC", "ETH", "SOL", "XRP", "ADA",
    "SUI", "FET", "AVAX", "RENDER", "WLD",
    "HYPE", "INJ", "HBAR", "TAO", "ONDO",
    "LINK", "NEAR", "ARB", "UNI", "ACN",
]

# Strategy defaults (also overridable from bot later)
DEFAULT_CASH_RESERVE_PCT = 20.0          # 20% cash emergency
DEFAULT_MIN_OUTFLOW_USD = 5_000_000      # minimum to consider
DEFAULT_STOP_LOSS_PCT = 2.5
DEFAULT_TAKE_PROFIT_PCT = 5.0
DEFAULT_MAX_OPEN_POSITIONS = 5
DEFAULT_MODE = "paper"                   # paper / real

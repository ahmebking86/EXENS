"""
Parse Whale Alert style messages
"""

import re
from loguru import logger
from strategy.sizing import get_strength


# Simple patterns for Whale Alert messages
OUTFLOW_PATTERNS = [
    r"transferred from\s+#?Coinbase",
    r"from\s+#?Coinbase",
    r"Coinbase.*to\s+",
]

INFLOW_PATTERNS = [
    r"transferred to\s+#?Coinbase",
    r"to\s+#?Coinbase",
]


def parse_whale_message(text: str, watch_coins: list) -> dict | None:
    """
    Returns signal dict or None
    {
        "direction": "outflow" | "inflow",
        "symbol": "BTC/USDT",
        "amount_usd": 51600000,
        "strength": "very_strong",
        "raw": "..."
    }
    """
    if not text:
        return None

    text_upper = text.upper()

    # Detect direction
    direction = None
    for p in OUTFLOW_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            direction = "outflow"
            break
    if not direction:
        for p in INFLOW_PATTERNS:
            if re.search(p, text, re.IGNORECASE):
                direction = "inflow"
                break

    if not direction:
        return None

    # Find coin
    symbol = None
    for coin in watch_coins:
        if coin.upper() in text_upper or f"#{coin.upper()}" in text_upper:
            symbol = f"{coin}/USDT"
            break

    if not symbol:
        # Try common names
        if "BITCOIN" in text_upper or " BTC " in text_upper:
            symbol = "BTC/USDT"
        elif "ETHEREUM" in text_upper or " ETH " in text_upper:
            symbol = "ETH/USDT"

    if not symbol:
        return None

    # Extract USD amount
    amount_usd = 0.0
    # Look for patterns like ($51,670,886 USD) or (51.6M USD)
    m = re.search(r"\(\$?([\d,\.]+)\s*(USD|usd)?\)", text)
    if m:
        raw = m.group(1).replace(",", "")
        try:
            amount_usd = float(raw)
        except Exception:
            pass

    if amount_usd == 0:
        m2 = re.search(r"([\d,\.]+)\s*(M|B)?\s*USD", text, re.IGNORECASE)
        if m2:
            try:
                val = float(m2.group(1).replace(",", ""))
                mult = m2.group(2)
                if mult and mult.upper() == "M":
                    val *= 1_000_000
                elif mult and mult.upper() == "B":
                    val *= 1_000_000_000
                amount_usd = val
            except Exception:
                pass

    strength = get_strength(amount_usd)

    return {
        "direction": direction,
        "symbol": symbol,
        "amount_usd": amount_usd,
        "strength": strength,
        "raw": text[:300],
    }

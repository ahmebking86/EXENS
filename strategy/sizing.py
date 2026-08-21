"""
Position Sizing - Proportional + 20% cash reserve
"""

from database.models import get_config
from loguru import logger


def get_strength(amount_usd: float) -> str:
    if amount_usd >= 50_000_000:
        return "very_strong"
    elif amount_usd >= 20_000_000:
        return "strong"
    elif amount_usd >= 5_000_000:
        return "medium"
    else:
        return "weak"


def get_buy_pct(strength: str) -> float:
    """Return percentage of *available* capital to use for buy"""
    mapping = {
        "very_strong": 0.90,   # 90% of available (after 20% reserve)
        "strong": 0.65,
        "medium": 0.40,
        "weak": 0.10,
    }
    return mapping.get(strength, 0.0)


def get_sell_pct(strength: str) -> float:
    """Return percentage of open position to sell"""
    mapping = {
        "very_strong": 0.90,
        "strong": 0.60,
        "medium": 0.35,
        "weak": 0.15,
    }
    return mapping.get(strength, 0.0)


async def calc_buy_size_usdt(strength: str, balance_usdt: float) -> float:
    """
    Calculate how much USDT to use for a buy.
    Always keeps at least 20% cash reserve.
    """
    cash_reserve_pct = float(get_config("cash_reserve_pct", "20")) / 100.0
    available = balance_usdt * (1.0 - cash_reserve_pct)

    if available <= 0:
        return 0.0

    pct = get_buy_pct(strength)
    size = available * pct

    # Safety minimum
    if size < 5:
        return 0.0

    logger.info(f"Sizing: strength={strength} | balance={balance_usdt:.1f} | available={available:.1f} | size={size:.1f}")
    return round(size, 2)

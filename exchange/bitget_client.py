"""
Bitget Client - Keys loaded from database (not from .env)
"""

import ccxt.async_support as ccxt
from loguru import logger
from database.models import get_config


class BitgetClient:
    def __init__(self):
        self.exchange = None
        self.markets_loaded = False

    def _build_exchange(self):
        api_key = get_config("bitget_api_key", "")
        secret = get_config("bitget_secret", "")
        passphrase = get_config("bitget_passphrase", "")

        if not api_key or not secret or not passphrase:
            return None

        return ccxt.bitget({
            "apiKey": api_key,
            "secret": secret,
            "password": passphrase,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })

    async def ensure_exchange(self):
        if self.exchange is None:
            self.exchange = self._build_exchange()
        return self.exchange is not None

    async def load_markets(self):
        if not await self.ensure_exchange():
            logger.warning("Bitget keys not set yet")
            return False
        try:
            await self.exchange.load_markets()
            self.markets_loaded = True
            logger.info("Bitget markets loaded")
            return True
        except Exception as e:
            logger.error(f"Failed to load markets: {e}")
            return False

    async def fetch_ticker(self, symbol: str):
        if not await self.ensure_exchange():
            return None
        try:
            return await self.exchange.fetch_ticker(symbol)
        except Exception as e:
            logger.error(f"fetch_ticker {symbol}: {e}")
            return None

    async def fetch_balance(self):
        if not await self.ensure_exchange():
            return {}
        try:
            return await self.exchange.fetch_balance()
        except Exception as e:
            logger.error(f"fetch_balance: {e}")
            return {}

    async def create_market_buy(self, symbol: str, amount: float, mode: str = "paper"):
        if mode != "real":
            logger.info(f"[PAPER] BUY {symbol} amount={amount}")
            return {"id": "paper", "symbol": symbol, "amount": amount}
        if not await self.ensure_exchange():
            return None
        try:
            order = await self.exchange.create_market_buy_order(symbol, amount)
            logger.success(f"BUY placed: {symbol}")
            return order
        except Exception as e:
            logger.error(f"BUY error: {e}")
            return None

    async def create_market_sell(self, symbol: str, amount: float, mode: str = "paper"):
        if mode != "real":
            logger.info(f"[PAPER] SELL {symbol} amount={amount}")
            return {"id": "paper", "symbol": symbol, "amount": amount}
        if not await self.ensure_exchange():
            return None
        try:
            order = await self.exchange.create_market_sell_order(symbol, amount)
            logger.success(f"SELL placed: {symbol}")
            return order
        except Exception as e:
            logger.error(f"SELL error: {e}")
            return None

    async def close(self):
        if self.exchange:
            await self.exchange.close()


bitget = BitgetClient()

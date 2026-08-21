"""
Executor with proportional sizing + cash reserve
"""

from loguru import logger
from datetime import datetime
from database.models import get_session, Trade, get_config, is_paused
from exchange.bitget_client import bitget
from strategy.sizing import calc_buy_size_usdt, get_sell_pct, get_strength


async def open_position(symbol: str, amount_usd: float, strength: str = None):
    if is_paused():
        logger.info("Paused - skip open")
        return None

    if strength is None:
        strength = get_strength(amount_usd)

    mode = get_config("mode", "paper")
    max_open = int(get_config("max_open_positions", "5"))

    session = get_session()
    try:
        open_count = session.query(Trade).filter_by(status="open").count()
        if open_count >= max_open:
            logger.warning("Max open positions reached")
            return None
    finally:
        session.close()

    # Get balance
    if mode == "real":
        balance = await bitget.fetch_balance()
        usdt_free = float(balance.get("USDT", {}).get("free", 0) or 0)
    else:
        # Paper mode simulated balance
        usdt_free = float(get_config("paper_balance", "1000"))

    size = await calc_buy_size_usdt(strength, usdt_free)
    if size <= 0:
        logger.info("Size too small - skip")
        return None

    ticker = await bitget.fetch_ticker(symbol)
    if not ticker or not ticker.get("last"):
        logger.error(f"No price for {symbol}")
        return None

    price = ticker["last"]
    quantity = size / price

    order = await bitget.create_market_buy(symbol, quantity, mode=mode)
    if not order:
        return None

    sl_pct = float(get_config("stop_loss_pct", "2.5"))
    tp_pct = float(get_config("take_profit_pct", "5.0"))
    stop_loss = price * (1 - sl_pct / 100)
    take_profit = price * (1 + tp_pct / 100)

    session = get_session()
    try:
        trade = Trade(
            symbol=symbol,
            side="buy",
            entry_price=price,
            quantity=quantity,
            usdt_size=size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            status="open",
            mode=mode,
            signal_strength=strength,
        )
        session.add(trade)
        session.commit()
        logger.success(f"Opened {symbol} | ${size:.1f} | strength={strength}")
        return trade
    except Exception as e:
        logger.error(f"Record trade error: {e}")
        session.rollback()
        return None
    finally:
        session.close()


async def close_position(symbol: str, strength: str = "medium", reason: str = "signal"):
    session = get_session()
    try:
        trade = session.query(Trade).filter_by(symbol=symbol, status="open").first()
        if not trade:
            return None

        sell_pct = get_sell_pct(strength)
        qty_to_sell = trade.quantity * sell_pct

        mode = trade.mode
        ticker = await bitget.fetch_ticker(symbol)
        exit_price = ticker["last"] if ticker else trade.entry_price

        order = await bitget.create_market_sell(symbol, qty_to_sell, mode=mode)
        if not order and mode == "real":
            return None

        # If selling full or almost full → close trade
        if sell_pct >= 0.85:
            pnl = (exit_price - trade.entry_price) * trade.quantity
            pnl_pct = ((exit_price - trade.entry_price) / trade.entry_price) * 100
            trade.exit_price = exit_price
            trade.pnl = round(pnl, 4)
            trade.pnl_pct = round(pnl_pct, 2)
            trade.status = "closed"
            trade.exit_reason = reason
            trade.exit_time = datetime.utcnow()
        else:
            # Partial sell - reduce quantity
            trade.quantity -= qty_to_sell
            trade.usdt_size = trade.quantity * trade.entry_price

        session.commit()
        logger.success(f"Closed/Reduced {symbol} | pct={sell_pct*100:.0f}% | {reason}")
        return trade
    except Exception as e:
        logger.error(f"close error: {e}")
        session.rollback()
        return None
    finally:
        session.close()


async def check_stops():
    session = get_session()
    try:
        trades = session.query(Trade).filter_by(status="open").all()
    finally:
        session.close()

    for trade in trades:
        try:
            ticker = await bitget.fetch_ticker(trade.symbol)
            if not ticker:
                continue
            current = ticker["last"]
            if trade.stop_loss and current <= trade.stop_loss:
                await close_position(trade.symbol, strength="very_strong", reason="stop_loss")
            elif trade.take_profit and current >= trade.take_profit:
                await close_position(trade.symbol, strength="very_strong", reason="take_profit")
        except Exception as e:
            logger.error(f"Stop check error {trade.symbol}: {e}")

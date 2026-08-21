"""
EXENS Auto - Fully automatic Institutional Flow Bot
- Only TG_TOKEN in .env
- All secrets requested via Telegram
- Listens to channel messages (Whale Alert forwards)
"""

import asyncio
from loguru import logger
from telegram.ext import Application, MessageHandler, filters
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config.settings as config
from database.models import init_db, get_config, set_config, is_paused
from exchange.bitget_client import bitget
from monitor.whale_parser import parse_whale_message
from strategy.executor import open_position, close_position, check_stops
from tg_bot.handlers import setup_handlers, is_admin
from utils.logger import setup_logger


async def handle_channel_post(update, context):
    """Receive messages from channels the bot is admin in (Whale Alert forwards)"""
    if is_paused():
        return

    message = update.channel_post or update.effective_message
    if not message or not message.text:
        return

    text = message.text
    watch_coins = config.DEFAULT_WATCH_COINS

    signal = parse_whale_message(text, watch_coins)
    if not signal:
        return

    logger.info(f"Signal detected: {signal['direction']} | {signal['symbol']} | ${signal['amount_usd']:,.0f} | {signal['strength']}")

    if signal["direction"] == "outflow":
        # Buy
        trade = await open_position(
            signal["symbol"],
            amount_usd=signal["amount_usd"],
            strength=signal["strength"],
        )
        if trade and config.TG_TOKEN:
            try:
                await context.bot.send_message(
                    chat_id=get_config("admin_id"),
                    text=(
                        f"🟢 *شراء*\n"
                        f"`{signal['symbol']}`\n"
                        f"القوة: `{signal['strength']}`\n"
                        f"الحجم: `${trade.usdt_size:.1f}`\n"
                        f"السعر: `{trade.entry_price}`"
                    ),
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    elif signal["direction"] == "inflow":
        # Sell proportional
        trade = await close_position(
            signal["symbol"],
            strength=signal["strength"],
            reason="coinbase_inflow",
        )
        if trade and get_config("admin_id"):
            try:
                await context.bot.send_message(
                    chat_id=get_config("admin_id"),
                    text=f"🔴 *بيع جزئي/كامل* `{signal['symbol']}` | {signal['strength']}",
                    parse_mode="Markdown",
                )
            except Exception:
                pass


async def main():
    setup_logger("INFO")
    logger.info("🚀 Starting EXENS Auto")

    if not config.TG_TOKEN:
        logger.error("TG_TOKEN is required in .env")
        return

    init_db()

    # Set defaults if missing
    if not get_config("cash_reserve_pct"):
        set_config("cash_reserve_pct", "20")
    if not get_config("mode"):
        set_config("mode", "paper")
    if not get_config("stop_loss_pct"):
        set_config("stop_loss_pct", "2.5")
    if not get_config("take_profit_pct"):
        set_config("take_profit_pct", "5.0")
    if not get_config("max_open_positions"):
        set_config("max_open_positions", "5")
    if not get_config("paper_balance"):
        set_config("paper_balance", "1000")

    app = Application.builder().token(config.TG_TOKEN).build()
    setup_handlers(app)

    # Listen to channel posts (bot must be admin in the channel)
    app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POSTS, handle_channel_post))

    # Periodic stop check
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_stops, "interval", seconds=45, id="stops", max_instances=1)
    scheduler.start()

    logger.info("Bot started. Add bot as admin to your Whale Alert forward channel.")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    stop = asyncio.Event()
    await stop.wait()


if __name__ == "__main__":
    asyncio.run(main())

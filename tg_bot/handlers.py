"""
Telegram Handlers - Secrets requested inside the bot only
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from loguru import logger
from database.models import get_session, Trade, get_config, set_config, is_paused, set_paused
from strategy.executor import open_position, close_position, check_stops
from exchange.bitget_client import bitget
import config.settings as config


def is_admin(user_id: int) -> bool:
    admins = config.TG_ADMIN_IDS
    if not admins:
        # First user becomes admin
        stored = get_config("admin_id")
        if stored:
            return str(user_id) == stored
        set_config("admin_id", str(user_id))
        return True
    return user_id in admins


def main_kb():
    paused = is_paused()
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 الحالة", callback_data="status"),
         InlineKeyboardButton("📈 المراكز", callback_data="positions")],
        [InlineKeyboardButton("🔑 إعدادات Bitget", callback_data="setup_bitget")],
        [InlineKeyboardButton("⚙️ إعدادات الاستراتيجية", callback_data="setup_strategy")],
        [InlineKeyboardButton("⏸ إيقاف" if not paused else "▶️ تشغيل", callback_data="toggle_pause")],
        [InlineKeyboardButton("🔄 فحص الـ Stops", callback_data="check_stops")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("غير مصرح.")
        return

    mode = get_config("mode", "paper")
    await update.message.reply_text(
        f"🏦 *EXENS Auto*\n\n"
        f"الوضع: `{mode}`\n"
        f"الكاش المحجوز: `{get_config('cash_reserve_pct', '20')}%`\n\n"
        "كل المفاتيح السرية بتتضبط من هنا فقط.",
        reply_markup=main_kb(),
        parse_mode="Markdown",
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    data = query.data

    if data == "status":
        session = get_session()
        try:
            open_c = session.query(Trade).filter_by(status="open").count()
            closed_c = session.query(Trade).filter_by(status="closed").count()
        finally:
            session.close()

        has_keys = bool(get_config("bitget_api_key"))
        text = (
            f"🏦 *الحالة*\n\n"
            f"الوضع: `{'⏸ متوقف' if is_paused() else '▶️ يعمل'}`\n"
            f"Mode: `{get_config('mode', 'paper')}`\n"
            f"مفاتيح Bitget: `{'✅ موجودة' if has_keys else '❌ ناقصة'}`\n"
            f"مراكز مفتوحة: `{open_c}`\n"
            f"صفقات مغلقة: `{closed_c}`\n"
            f"كاش طوارئ: `{get_config('cash_reserve_pct', '20')}%`"
        )
        await query.edit_message_text(text, reply_markup=main_kb(), parse_mode="Markdown")

    elif data == "positions":
        session = get_session()
        try:
            trades = session.query(Trade).filter_by(status="open").all()
        finally:
            session.close()
        if not trades:
            text = "لا توجد مراكز مفتوحة."
        else:
            lines = [f"`{t.symbol}` | {t.entry_price:.6g} | ${t.usdt_size:.1f} | {t.signal_strength}" for t in trades]
            text = "📈 *المراكز المفتوحة*\n\n" + "\n".join(lines)
        await query.edit_message_text(text, reply_markup=main_kb(), parse_mode="Markdown")

    elif data == "toggle_pause":
        cur = is_paused()
        set_paused(not cur)
        await query.edit_message_text(
            "⏸ تم الإيقاف" if not cur else "▶️ تم التشغيل",
            reply_markup=main_kb(),
        )

    elif data == "setup_bitget":
        context.user_data["setup_step"] = "api_key"
        await query.edit_message_text(
            "🔑 *إعداد Bitget*\n\n"
            "ابعت دلوقتي **API Key**:",
            parse_mode="Markdown",
        )

    elif data == "setup_strategy":
        await query.edit_message_text(
            "⚙️ *إعدادات الاستراتيجية الحالية*\n\n"
            f"Mode: `{get_config('mode', 'paper')}`\n"
            f"كاش طوارئ: `{get_config('cash_reserve_pct', '20')}%`\n"
            f"Stop Loss: `{get_config('stop_loss_pct', '2.5')}%`\n"
            f"Take Profit: `{get_config('take_profit_pct', '5.0')}%`\n\n"
            "لتغيير Mode ابعت:\n`mode paper` أو `mode real`",
            reply_markup=main_kb(),
            parse_mode="Markdown",
        )

    elif data == "check_stops":
        await check_stops()
        await query.edit_message_text("✅ تم فحص الـ Stop Loss / Take Profit", reply_markup=main_kb())


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    text = update.message.text.strip()
    step = context.user_data.get("setup_step")

    # Bitget setup flow
    if step == "api_key":
        set_config("bitget_api_key", text)
        context.user_data["setup_step"] = "secret"
        await update.message.reply_text("تمام. ابعت دلوقتي **Secret**:")
        return

    if step == "secret":
        set_config("bitget_secret", text)
        context.user_data["setup_step"] = "passphrase"
        await update.message.reply_text("تمام. ابعت دلوقتي **Passphrase**:")
        return

    if step == "passphrase":
        set_config("bitget_passphrase", text)
        context.user_data["setup_step"] = None
        # Try load markets
        ok = await bitget.load_markets()
        msg = "✅ تم حفظ مفاتيح Bitget بنجاح." if ok else "⚠️ تم الحفظ لكن فشل الاتصال (راجع المفاتيح)."
        await update.message.reply_text(msg, reply_markup=main_kb())
        return

    # Quick mode change
    if text.lower().startswith("mode "):
        new_mode = text.split(" ", 1)[1].strip().lower()
        if new_mode in ("paper", "real"):
            set_config("mode", new_mode)
            await update.message.reply_text(f"تم تغيير الوضع إلى `{new_mode}`", parse_mode="Markdown", reply_markup=main_kb())
        return

    # Ignore other text
    await update.message.reply_text("استخدم الأزرار للتحكم.", reply_markup=main_kb())


def setup_handlers(app):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

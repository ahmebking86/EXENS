# -*- coding: utf-8 -*-
"""
بوت تليجرام للتحكم الكامل في محرك التداول - كله بالأزرار.
النصوص بتتطلب بس لما تكون قيمة (رقم/باسورد/عنوان) لازم المستخدم يكتبها.
"""

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters,
)

import db
import ec2_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("bot")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ADMIN_ID = int(os.environ["ADMIN_TELEGRAM_ID"])

# اللي محتاج المستخدم يكتب قيمة له بدل ما يضغط زرار
PENDING_FIELD = "pending_field"

FIELD_LABELS = {
    "ec2_host": "عنوان EC2 (الـ IP أو الدومين)",
    "ec2_port": "رقم الـ Port (افتراضي 8443)",
    "ec2_api_key": "المفتاح السري (EC2_API_KEY)",
    "mt5_login": "رقم حساب MetaTrader (Login)",
    "mt5_password": "باسورد حساب MetaTrader",
    "mt5_server": "اسم السيرفر (مثلاً Exness-MT5Trial)",
    "symbol": "رمز الأداة (مثلاً EURUSD)",
    "lot": "حجم الصفقة (lot)، مثلاً 0.01",
    "target_value": "قيمة هدف الربح",
    "sl_value": "قيمة وقف الخسارة",
}


def is_admin(update: Update) -> bool:
    return update.effective_user and update.effective_user.id == ADMIN_ID


# ---------------------------- القوائم ----------------------------

def main_menu():
    kb = [
        [InlineKeyboardButton("🔌 اتصال EC2", callback_data="menu_ec2")],
        [InlineKeyboardButton("🔑 بيانات MetaTrader", callback_data="menu_mt5")],
        [InlineKeyboardButton("⚙️ إعدادات الاستراتيجية", callback_data="menu_strategy")],
        [InlineKeyboardButton("▶️ ابدأ", callback_data="action_start"),
         InlineKeyboardButton("⏹ إيقاف", callback_data="action_stop")],
        [InlineKeyboardButton("📊 الحالة", callback_data="action_status")],
    ]
    return InlineKeyboardMarkup(kb)


def ec2_menu():
    kb = [
        [InlineKeyboardButton("عنوان EC2", callback_data="set_ec2_host")],
        [InlineKeyboardButton("الـ Port", callback_data="set_ec2_port")],
        [InlineKeyboardButton("المفتاح السري", callback_data="set_ec2_api_key")],
        [InlineKeyboardButton("✅ اختبار الاتصال", callback_data="test_ec2")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(kb)


def mt5_menu():
    kb = [
        [InlineKeyboardButton("رقم الحساب", callback_data="set_mt5_login")],
        [InlineKeyboardButton("الباسورد", callback_data="set_mt5_password")],
        [InlineKeyboardButton("السيرفر", callback_data="set_mt5_server")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(kb)


def strategy_menu():
    direction = db.get("direction")
    target_type = db.get("target_type")
    sl_type = db.get("sl_type")
    kb = [
        [InlineKeyboardButton("الرمز (Symbol)", callback_data="set_symbol")],
        [InlineKeyboardButton("حجم الصفقة (Lot)", callback_data="set_lot")],
        [InlineKeyboardButton(f"الاتجاه: {direction}", callback_data="pick_direction")],
        [InlineKeyboardButton(f"نوع هدف الربح: {target_type}", callback_data="pick_target_type"),
         InlineKeyboardButton("قيمة الهدف", callback_data="set_target_value")],
        [InlineKeyboardButton(f"نوع وقف الخسارة: {sl_type}", callback_data="pick_sl_type"),
         InlineKeyboardButton("قيمة الوقف", callback_data="set_sl_value")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="menu_main")],
    ]
    return InlineKeyboardMarkup(kb)


def direction_menu():
    kb = [
        [InlineKeyboardButton("🟢 Buy فقط", callback_data="dir_BUY")],
        [InlineKeyboardButton("🔴 Sell فقط", callback_data="dir_SELL")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="menu_strategy")],
    ]
    return InlineKeyboardMarkup(kb)


def type_menu(prefix):
    kb = [
        [InlineKeyboardButton("دولار $", callback_data=f"{prefix}_usd")],
        [InlineKeyboardButton("نسبة %", callback_data=f"{prefix}_percent")],
        [InlineKeyboardButton("نقاط pips", callback_data=f"{prefix}_pips")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="menu_strategy")],
    ]
    return InlineKeyboardMarkup(kb)


# ---------------------------- الأوامر ----------------------------

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("غير مصرح لك باستخدام البوت ده.")
        return
    await update.message.reply_text(
        "أهلاً 👋\nده بوت التحكم في استراتيجية الاقتناص السريع.\nاستخدم الأزرار تحت:",
        reply_markup=main_menu(),
    )


# ---------------------------- الأزرار ----------------------------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(update):
        await query.answer("غير مصرح", show_alert=True)
        return
    await query.answer()
    data = query.data

    if data == "menu_main":
        await query.edit_message_text("القائمة الرئيسية:", reply_markup=main_menu())
        return

    if data == "menu_ec2":
        await query.edit_message_text("إعدادات الاتصال بـ EC2:", reply_markup=ec2_menu())
        return

    if data == "menu_mt5":
        await query.edit_message_text("بيانات حساب MetaTrader:", reply_markup=mt5_menu())
        return

    if data == "menu_strategy":
        await query.edit_message_text("إعدادات الاستراتيجية:", reply_markup=strategy_menu())
        return

    if data.startswith("set_"):
        field = data[len("set_"):]
        context.user_data[PENDING_FIELD] = field
        label = FIELD_LABELS.get(field, field)
        await query.edit_message_text(f"ابعت قيمة: {label}")
        return

    if data == "pick_direction":
        await query.edit_message_text("اختار اتجاه الصفقة:", reply_markup=direction_menu())
        return

    if data.startswith("dir_"):
        db.set("direction", data.split("_")[1])
        await query.edit_message_text("تم الحفظ ✅", reply_markup=strategy_menu())
        return

    if data == "pick_target_type":
        await query.edit_message_text("اختار نوع هدف الربح:", reply_markup=type_menu("tt"))
        return

    if data.startswith("tt_"):
        db.set("target_type", data.split("_")[1])
        await query.edit_message_text("تم الحفظ ✅", reply_markup=strategy_menu())
        return

    if data == "pick_sl_type":
        await query.edit_message_text("اختار نوع وقف الخسارة:", reply_markup=type_menu("sl"))
        return

    if data.startswith("sl_"):
        db.set("sl_type", data.split("_")[1])
        await query.edit_message_text("تم الحفظ ✅", reply_markup=strategy_menu())
        return

    if data == "test_ec2":
        try:
            res = ec2_client.health()
            await query.edit_message_text(f"الاتصال شغال ✅\n{res}", reply_markup=ec2_menu())
        except Exception as e:
            await query.edit_message_text(f"فشل الاتصال ❌\n{e}", reply_markup=ec2_menu())
        return

    if data == "action_start":
        await handle_start(query)
        return

    if data == "action_stop":
        await handle_stop(query)
        return

    if data == "action_status":
        await handle_status(query)
        return


async def handle_start(query):
    if not ec2_client.is_configured():
        await query.edit_message_text("لازم تظبط بيانات EC2 الأول (عنوان + مفتاح سري).", reply_markup=main_menu())
        return
    try:
        conn = ec2_client.connect()
        if not conn.get("connected"):
            await query.edit_message_text(f"فشل الاتصال بـ MetaTrader ❌\n{conn}", reply_markup=main_menu())
            return
        ec2_client.push_config()
        res = ec2_client.start()
        await query.edit_message_text(f"تم بدء الاستراتيجية ✅\n{res}", reply_markup=main_menu())
    except Exception as e:
        await query.edit_message_text(f"حصل خطأ: {e}", reply_markup=main_menu())


async def handle_stop(query):
    try:
        res = ec2_client.stop(close_position=True)
        await query.edit_message_text(f"تم الإيقاف ⏹ (وقفل أي صفقة مفتوحة)\n{res}", reply_markup=main_menu())
    except Exception as e:
        await query.edit_message_text(f"حصل خطأ: {e}", reply_markup=main_menu())


async def handle_status(query):
    try:
        s = ec2_client.status()
        acc = s.get("account") or {}
        positions = s.get("open_positions") or []
        total_profit = s.get("total_profit", 0.0)
        positions_error = s.get("positions_error")
        txt = (
            f"الحالة: {'شغال 🟢' if s.get('running') else 'متوقف 🔴'}\n"
            f"متصل بـ MT5: {'نعم' if s.get('mt5_connected') else 'لا'}\n"
            f"الرصيد: {acc.get('balance')} {acc.get('currency','')}\n"
            f"الإيكويتي: {acc.get('equity')}\n"
        )
        if positions_error:
            txt += f"\nخطأ قراءة الصفقات من MT5: {positions_error}\n"
        if positions:
            txt += f"\nصفقات مفتوحة ({len(positions)}):\n"
            for p in positions:
                txt += f"  • {p['direction']} {p['volume']} @ {p['open_price']} | ربح: {p['profit']}\n"
            txt += f"\nإجمالي الربح الحالي: {total_profit:.2f}\n"
        else:
            if not positions_error:
                txt += f"\nتشخيص MT5: raw={s.get("positions_count", 0)} | الرموز={s.get("positions_symbols") or "لا يوجد"} | أوامر معلقة={s.get("pending_orders_count", 0)}\n"
            txt += "\nمفيش صفقات مفتوحة حالياً.\n"
        txt += f"\nعدد الصفقات المسجلة: {s.get('trades_count')}"
        await query.edit_message_text(txt, reply_markup=main_menu())
    except Exception as e:
        await query.edit_message_text(f"حصل خطأ: {e}", reply_markup=main_menu())


# ---------------------------- استقبال القيم النصية ----------------------------

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    field = context.user_data.get(PENDING_FIELD)
    if not field:
        await update.message.reply_text("استخدم الأزرار من فضلك.", reply_markup=main_menu())
        return

    value = update.message.text.strip()
    db.set(field, value)
    del context.user_data[PENDING_FIELD]

    if field.startswith("ec2_"):
        markup = ec2_menu()
    elif field.startswith("mt5_"):
        markup = mt5_menu()
    else:
        markup = strategy_menu()

    await update.message.reply_text("تم الحفظ ✅", reply_markup=markup)


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    log.info("bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()

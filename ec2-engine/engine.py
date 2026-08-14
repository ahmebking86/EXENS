"""
محرك التداول - يشتغل على EC2 Windows جنب MetaTrader 5
مسؤول عن: الاتصال بـ MT5، تنفيذ استراتيجية "اقتنص أي ربح واقفل وارجع ادخل"،
وعرض API بسيط محمي بمفتاح سري عشان بوت التليجرام (على Railway) يتحكم فيه.

الاستراتيجية:
  - يفتح صفقة باتجاه ثابت (Buy فقط أو Sell فقط، حسب الإعداد).
  - يراقب الصفقة باستمرار.
  - أول ما الربح يوصل للهدف المحدد (دولار / نسبة % / نقاط) -> يقفلها فوراً.
  - يستنى فترة قصيرة (reentry_delay) ثم يفتح صفقة جديدة بنفس الإعدادات، وهكذا.
  - وقف خسارة (Stop Loss) إجباري على كل صفقة للحماية.
"""

import os
import json
import time
import threading
import logging
from datetime import datetime

import MetaTrader5 as mt5
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("engine")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
TRADES_LOG_PATH = os.path.join(os.path.dirname(__file__), "trades.json")

# المفتاح السري الوحيد اللي محتاجينه كمتغير بيئة على EC2 نفسه
API_KEY = os.environ.get("EC2_API_KEY", "CHANGE_ME")

DEFAULT_CONFIG = {
    "mt5_login": None,
    "mt5_password": None,
    "mt5_server": None,
    "symbol": "EURUSD",
    "direction": "BUY",          # BUY أو SELL - ثابت حسب اختيار المستخدم
    "lot": 0.01,
    "target_type": "usd",        # usd | percent | pips
    "target_value": 0.5,
    "sl_type": "usd",            # usd | percent | pips
    "sl_value": 2.0,
    "poll_interval": 1.5,        # ثانية بين كل فحص للصفقة
    "reentry_delay": 2.0,        # ثانية استنى قبل ما يدخل تاني بعد القفل
}

state_lock = threading.Lock()
running_event = threading.Event()
engine_thread = None
mt5_connected = False
last_error = None


# ---------------------------- إدارة الإعدادات ----------------------------

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        merged = {**DEFAULT_CONFIG, **cfg}
        return merged
    return dict(DEFAULT_CONFIG)


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def log_trade(record):
    trades = []
    if os.path.exists(TRADES_LOG_PATH):
        try:
            with open(TRADES_LOG_PATH, "r", encoding="utf-8") as f:
                trades = json.load(f)
        except Exception:
            trades = []
    trades.append(record)
    trades = trades[-200:]  # آخر 200 صفقة بس
    with open(TRADES_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(trades, f, ensure_ascii=False, indent=2)


# ---------------------------- اتصال MT5 ----------------------------

def connect_mt5(login, password, server):
    global mt5_connected, last_error
    if not mt5.initialize():
        last_error = f"initialize failed: {mt5.last_error()}"
        mt5_connected = False
        return False, last_error

    authorized = mt5.login(int(login), password=password, server=server)
    if not authorized:
        last_error = f"login failed: {mt5.last_error()}"
        mt5_connected = False
        mt5.shutdown()
        return False, last_error

    mt5_connected = True
    last_error = None
    return True, "connected"


def disconnect_mt5():
    global mt5_connected
    mt5.shutdown()
    mt5_connected = False


# ---------------------------- منطق الاستراتيجية ----------------------------

def get_point_pips_factor(symbol_info):
    # لبروكرز الـ 5/3 أرقام عشرية، النقطة الحقيقية (pip) = 10 * point
    digits = symbol_info.digits
    point = symbol_info.point
    if digits in (3, 5):
        return point * 10
    return point


def calc_profit_reached(pos, cfg):
    target_type = cfg["target_type"]
    target_value = float(cfg["target_value"])

    if target_type == "usd":
        return pos.profit >= target_value

    if target_type == "percent":
        acc = mt5.account_info()
        if acc is None:
            return False
        return pos.profit >= (acc.balance * target_value / 100.0)

    if target_type == "pips":
        symbol_info = mt5.symbol_info(pos.symbol)
        tick = mt5.symbol_info_tick(pos.symbol)
        if symbol_info is None or tick is None:
            return False
        pip = get_point_pips_factor(symbol_info)
        if pos.type == mt5.POSITION_TYPE_BUY:
            pips = (tick.bid - pos.price_open) / pip
        else:
            pips = (pos.price_open - tick.ask) / pip
        return pips >= target_value

    return False


def compute_sl_price(symbol, direction, entry_price, cfg):
    """بيحسب سعر وقف الخسارة تقريبياً بناءً على نوع الوحدة المختارة."""
    symbol_info = mt5.symbol_info(symbol)
    sl_type = cfg["sl_type"]
    sl_value = float(cfg["sl_value"])
    pip = get_point_pips_factor(symbol_info)

    if sl_type == "pips":
        distance = sl_value * pip
    else:
        # لتحويل usd أو percent لمسافة سعرية تقريبية، بنستخدم قيمة التيك (tick_value)
        tick_value = symbol_info.trade_tick_value
        tick_size = symbol_info.trade_tick_size
        lot = float(cfg["lot"])
        if sl_type == "percent":
            acc = mt5.account_info()
            target_usd = (acc.balance * sl_value / 100.0) if acc else sl_value
        else:
            target_usd = sl_value
        if tick_value <= 0:
            distance = sl_value * pip  # fallback تقريبي
        else:
            distance = (target_usd / (tick_value * lot)) * tick_size

    if direction == "BUY":
        return round(entry_price - distance, symbol_info.digits)
    else:
        return round(entry_price + distance, symbol_info.digits)


def open_position(cfg):
    symbol = cfg["symbol"]
    lot = float(cfg["lot"])
    direction = cfg["direction"]

    if not mt5.symbol_select(symbol, True):
        log.error(f"couldn't select symbol {symbol}")
        return None

    tick = mt5.symbol_info_tick(symbol)
    order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
    price = tick.ask if direction == "BUY" else tick.bid
    sl_price = compute_sl_price(symbol, direction, price, cfg)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl": sl_price,
        "deviation": 20,
        "magic": 990011,
        "comment": "sniper-bot",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        log.error(f"order_send failed: {result}")
        return None
    log.info(f"opened {direction} {lot} {symbol} @ {price} sl={sl_price}")
    return result


def close_position(pos):
    symbol = pos.symbol
    tick = mt5.symbol_info_tick(symbol)
    close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
    price = tick.bid if close_type == mt5.ORDER_TYPE_SELL else tick.ask

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": pos.volume,
        "type": close_type,
        "position": pos.ticket,
        "price": price,
        "deviation": 20,
        "magic": 990011,
        "comment": "sniper-bot-close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    profit = pos.profit
    log_trade({
        "time": datetime.utcnow().isoformat(),
        "symbol": symbol,
        "direction": "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL",
        "volume": pos.volume,
        "profit": profit,
    })
    log.info(f"closed position {pos.ticket} profit={profit}")
    return result


def strategy_loop():
    log.info("strategy loop started")
    while running_event.is_set():
        cfg = load_config()
        try:
            if not mt5_connected:
                time.sleep(2)
                continue

            positions = mt5.positions_get(symbol=cfg["symbol"])
            if not positions:
                open_position(cfg)
            else:
                pos = positions[0]
                if calc_profit_reached(pos, cfg):
                    close_position(pos)
                    time.sleep(float(cfg["reentry_delay"]))
        except Exception as e:
            log.exception(f"loop error: {e}")
            time.sleep(2)

        time.sleep(float(cfg.get("poll_interval", 1.5)))

    log.info("strategy loop stopped")


# ---------------------------- FastAPI ----------------------------

app = FastAPI()


def check_key(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="unauthorized")


class ConnectBody(BaseModel):
    login: int
    password: str
    server: str


class ConfigBody(BaseModel):
    symbol: str | None = None
    direction: str | None = None
    lot: float | None = None
    target_type: str | None = None
    target_value: float | None = None
    sl_type: str | None = None
    sl_value: float | None = None
    poll_interval: float | None = None
    reentry_delay: float | None = None


class StopBody(BaseModel):
    close_position: bool = False


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/connect")
def api_connect(body: ConnectBody, x_api_key: str = Header(None)):
    check_key(x_api_key)
    cfg = load_config()
    cfg["mt5_login"] = body.login
    cfg["mt5_password"] = body.password
    cfg["mt5_server"] = body.server
    save_config(cfg)
    ok, msg = connect_mt5(body.login, body.password, body.server)
    return {"connected": ok, "message": msg}


@app.post("/disconnect")
def api_disconnect(x_api_key: str = Header(None)):
    check_key(x_api_key)
    disconnect_mt5()
    return {"connected": False}


@app.post("/config")
def api_config(body: ConfigBody, x_api_key: str = Header(None)):
    check_key(x_api_key)
    cfg = load_config()
    updates = {k: v for k, v in body.dict().items() if v is not None}
    cfg.update(updates)
    save_config(cfg)
    return {"config": cfg}


@app.post("/start")
def api_start(x_api_key: str = Header(None)):
    check_key(x_api_key)
    global engine_thread
    if not mt5_connected:
        raise HTTPException(status_code=400, detail="MT5 not connected, call /connect first")
    if running_event.is_set():
        return {"running": True, "message": "already running"}
    running_event.set()
    engine_thread = threading.Thread(target=strategy_loop, daemon=True)
    engine_thread.start()
    return {"running": True}


@app.post("/stop")
def api_stop(body: StopBody, x_api_key: str = Header(None)):
    check_key(x_api_key)
    running_event.clear()
    if body.close_position and mt5_connected:
        cfg = load_config()
        positions = mt5.positions_get(symbol=cfg["symbol"])
        for pos in positions or []:
            close_position(pos)
    return {"running": False}


@app.get("/status")
def api_status(x_api_key: str = Header(None)):
    check_key(x_api_key)
    cfg = load_config()
    acc = mt5.account_info() if mt5_connected else None
    positions = mt5.positions_get(symbol=cfg["symbol"]) if mt5_connected else []
    open_pos = None
    if positions:
        p = positions[0]
        open_pos = {
            "ticket": p.ticket,
            "direction": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
            "volume": p.volume,
            "open_price": p.price_open,
            "profit": p.profit,
        }
    trades = []
    if os.path.exists(TRADES_LOG_PATH):
        with open(TRADES_LOG_PATH, "r", encoding="utf-8") as f:
            trades = json.load(f)

    return {
        "mt5_connected": mt5_connected,
        "running": running_event.is_set(),
        "last_error": last_error,
        "account": {
            "balance": acc.balance if acc else None,
            "equity": acc.equity if acc else None,
            "currency": acc.currency if acc else None,
        } if acc else None,
        "open_position": open_pos,
        "config": {k: v for k, v in cfg.items() if k not in ("mt5_password",)},
        "trades_count": len(trades),
        "last_trades": trades[-5:],
    }


if __name__ == "__main__":
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
    uvicorn.run(app, host="0.0.0.0", port=8443)

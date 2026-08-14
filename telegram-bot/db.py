"""
تخزين بسيط بنظام key-value في جدول واحد على قاعدة بيانات Railway (Postgres).
كل بيانات الاتصال والإعدادات بتتخزن هنا بدل متغيرات Railway، وبتتغير من البوت.
"""

import os
from sqlalchemy import create_engine, Column, String, MetaData, Table
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]
# Railway بيديك رابط بيبدأ بـ postgres:// أحياناً، SQLAlchemy محتاج postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
metadata = MetaData()

kv_table = Table(
    "kv_store", metadata,
    Column("key", String, primary_key=True),
    Column("value", String),
)

metadata.create_all(engine)
Session = sessionmaker(bind=engine)

DEFAULTS = {
    "ec2_host": "",
    "ec2_port": "8443",
    "ec2_api_key": "",
    "mt5_login": "",
    "mt5_password": "",
    "mt5_server": "",
    "symbol": "EURUSD",
    "direction": "BUY",
    "lot": "0.01",
    "target_type": "usd",
    "target_value": "0.5",
    "sl_type": "usd",
    "sl_value": "2.0",
}


def get(key, default=None):
    session = Session()
    try:
        row = session.query(kv_table).filter_by(key=key).first()
        if row:
            return row.value
        return DEFAULTS.get(key, default)
    finally:
        session.close()


def set(key, value):
    session = Session()
    try:
        row = session.query(kv_table).filter_by(key=key).first()
        if row:
            session.execute(kv_table.update().where(kv_table.c.key == key).values(value=str(value)))
        else:
            session.execute(kv_table.insert().values(key=key, value=str(value)))
        session.commit()
    finally:
        session.close()


def get_all():
    return {k: get(k) for k in DEFAULTS.keys()}

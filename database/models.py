"""
Database Models - All secrets & config stored here
"""

from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Boolean,
    DateTime, Text, JSON
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import NullPool
import os

# Use SQLite by default (easy on EC2, no extra setup)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///exens.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if "sqlite" in DATABASE_URL:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, poolclass=NullPool, echo=False)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


class Config(Base):
    """Store all settings & secrets"""
    __tablename__ = "config"

    id = Column(Integer, primary_key=True)
    key = Column(String(64), unique=True, nullable=False)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(32), nullable=False)
    side = Column(String(8), default="buy")
    entry_price = Column(Float)
    quantity = Column(Float)
    usdt_size = Column(Float)
    stop_loss = Column(Float)
    take_profit = Column(Float)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    status = Column(String(16), default="open")
    mode = Column(String(16), default="paper")
    signal_strength = Column(String(32), nullable=True)  # weak/medium/strong/very_strong
    exit_reason = Column(String(64), nullable=True)
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)


class SignalLog(Base):
    __tablename__ = "signal_logs"

    id = Column(Integer, primary_key=True)
    direction = Column(String(16))          # outflow / inflow
    symbol = Column(String(32))
    amount_usd = Column(Float, default=0)
    strength = Column(String(32))
    raw_text = Column(Text)
    acted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_session():
    return SessionLocal()


def get_config(key: str, default=None):
    session = get_session()
    try:
        row = session.query(Config).filter_by(key=key).first()
        return row.value if row else default
    finally:
        session.close()


def set_config(key: str, value: str):
    session = get_session()
    try:
        row = session.query(Config).filter_by(key=key).first()
        if row:
            row.value = str(value)
        else:
            session.add(Config(key=key, value=str(value)))
        session.commit()
    finally:
        session.close()


def is_paused() -> bool:
    return get_config("paused", "false") == "true"


def set_paused(value: bool):
    set_config("paused", "true" if value else "false")

"""SQLAlchemy 数据模型。TCB 用云数据库 MySQL 时无需改动，仅换连接串。"""
from datetime import datetime

from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "user"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    openid = mapped_column(String(64), unique=True, index=True)
    nickname = mapped_column(String(64), default="")
    role = mapped_column(String(16), default="normal")  # whitelist/normal
    created_at = mapped_column(DateTime, default=datetime.utcnow)


class Whitelist(Base):
    __tablename__ = "whitelist"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    openid = mapped_column(String(64), unique=True, index=True)
    invited_by = mapped_column(String(64), default="")
    status = mapped_column(String(16), default="active")
    created_at = mapped_column(DateTime, default=datetime.utcnow)


class Task(Base):
    __tablename__ = "task"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id = mapped_column(String(32), unique=True, index=True)
    openid = mapped_column(String(64), index=True)
    type = mapped_column(String(16), default="single")  # single/portfolio/sector
    query = mapped_column(Text, default="")
    symbols = mapped_column(Text, default="[]")  # JSON list
    status = mapped_column(String(16), default="pending")  # pending/running/done/interrupted
    created_at = mapped_column(DateTime, default=datetime.utcnow)
    finished_at = mapped_column(DateTime, nullable=True)


class Report(Base):
    __tablename__ = "report"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id = mapped_column(String(32), unique=True, index=True)
    openid = mapped_column(String(64), index=True)
    summary_json = mapped_column(Text, default="")
    report_json = mapped_column(Text, default="")
    html_url = mapped_column(String(256), default="")
    md_text = mapped_column(Text, default="")


class Portfolio(Base):
    __tablename__ = "portfolio"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    openid = mapped_column(String(64), index=True)
    symbol = mapped_column(String(16), index=True)
    name = mapped_column(String(64), default="")
    shares = mapped_column(Float, default=0)
    cost = mapped_column(Float, default=0)
    updated_at = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Watchlist(Base):
    __tablename__ = "watchlist"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    openid = mapped_column(String(64), index=True)
    symbol = mapped_column(String(16), index=True)
    alert_types = mapped_column(Text, default="[]")  # JSON list


class ScreenerResult(Base):
    __tablename__ = "screener_result"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id = mapped_column(String(32), index=True)
    openid = mapped_column(String(64), index=True)
    strategy = mapped_column(String(32), default="")
    candidates_json = mapped_column(Text, default="[]")
    created_at = mapped_column(DateTime, default=datetime.utcnow)


class Inbox(Base):
    __tablename__ = "inbox"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    openid = mapped_column(String(64), index=True)
    msg_type = mapped_column(String(32), default="")
    title = mapped_column(String(128), default="")
    task_id = mapped_column(String(32), default="")
    read = mapped_column(Boolean, default=False)
    ts = mapped_column(DateTime, default=datetime.utcnow)


class Subscription(Base):
    __tablename__ = "subscription"
    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    openid = mapped_column(String(64), index=True)
    scene = mapped_column(String(16), default="")  # close/noon/tail
    authorized = mapped_column(Boolean, default=False)

"""数据库引擎与会话。本地 SQLite，TCB 切 MySQL 仅改 DATABASE_URL。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import config

_connect_args = {"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(config.DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """建表。容器启动时调用（TCB 首次部署）。"""
    import app.models  # noqa: F401 确保模型注册
    Base.metadata.create_all(bind=engine)

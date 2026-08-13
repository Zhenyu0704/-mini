"""集中配置：所有可调项来自环境变量，方便 TCB 云托管注入。"""
import os


class Config:
    # 数据库：本地 SQLite，TCB 用云数据库 MySQL 连接串
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./roundtable.db")

    # LLM
    LLM_MOCK = os.getenv("LLM_MOCK", "true").lower() == "true"
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
    LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")

    # 取数层
    FETCHER_MOCK = os.getenv("FETCHER_MOCK", "true").lower() == "true"

    # Redis / COS
    REDIS_URL = os.getenv("REDIS_URL", "")
    COS_BUCKET = os.getenv("COS_BUCKET", "")
    COS_REGION = os.getenv("COS_REGION", "")
    COS_SECRET_ID = os.getenv("COS_SECRET_ID", "")
    COS_SECRET_KEY = os.getenv("COS_SECRET_KEY", "")

    # 对外基址 & 邮件
    BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
    EMAIL_USER = os.getenv("EMAIL_USER", "")
    EMAIL_PASS = os.getenv("EMAIL_PASS", "")

    # 单次圆桌硬约束（沿用专家包护栏）
    EXPERT_MAX_TURNS = int(os.getenv("EXPERT_MAX_TURNS", "12"))
    FETCH_BUDGET = int(os.getenv("FETCH_BUDGET", "4"))
    QUOTE_DAYS_LIMIT = int(os.getenv("QUOTE_DAYS_LIMIT", "250"))


config = Config()

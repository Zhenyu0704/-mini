"""Pydantic 请求/响应契约。"""
from typing import Optional, List
from pydantic import BaseModel


class RoundtableReq(BaseModel):
    query: str
    symbols: List[str] = []
    type: str = "single"  # single/portfolio/sector


class TaskResp(BaseModel):
    task_id: str
    status: str


class ReportResp(BaseModel):
    task_id: str
    status: str
    summary: Optional[dict] = None
    report_json: Optional[dict] = None
    report_html_url: Optional[str] = None


class PortfolioItem(BaseModel):
    symbol: str
    name: str = ""
    shares: float = 0
    cost: float = 0


class ScreenerReq(BaseModel):
    strategy: str
    watch: bool = True


class WatchReq(BaseModel):
    symbols: List[str]
    alert_types: List[str] = ["breakout", "volume", "surge", "drop"]


class InboxItem(BaseModel):
    id: int
    msg_type: str
    title: str
    task_id: str
    read: bool
    ts: str

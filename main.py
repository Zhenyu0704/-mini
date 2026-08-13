"""FastAPI 入口：路由 + 后台任务 + 健康检查。

TCB 部署：用云托管容器跑本服务（设长超时）；云函数作网关时把重任务转交容器。
本地验证：uvicorn app.main:app --port 8000，默认 mock 模式即可跑通全流程。
"""
import json
import os
import uuid
import logging
from datetime import datetime
from typing import List

from fastapi import FastAPI, Depends, BackgroundTasks, Header
from sqlalchemy.orm import Session

from app.db import get_db, init_db
from app import models
from app.schemas import (
    RoundtableReq, TaskResp, ReportResp, PortfolioItem,
    ScreenerReq, WatchReq, InboxItem,
)
from app.orchestrator import run_roundtable
from app.fetcher import screen
from app import notify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stock-roundtable")

app = FastAPI(title="股票投研圆桌 · 云端", version="0.1.0")


@app.on_event("startup")
def _startup():
    logger.info("服务启动中，监听端口=%s，初始化数据库（init_db）...", os.getenv("PORT", "8000"))
    try:
        init_db()
        logger.info("数据库初始化完成，应用就绪（health on / 与 /healthz）")
    except Exception as e:
        # 不阻断启动：建表失败也要让健康检查 / 路由可用，便于诊断
        logger.error("数据库初始化失败（不影响进程启动）: %s", e)


def _openid(x_openid: str = Header(default="demo")) -> str:
    return x_openid


def _run_and_store(task_id, openid, query, symbols, type_):
    """后台跑圆桌并落库（新 session，避免请求期 session 已关）。"""
    from app.db import SessionLocal
    db = SessionLocal()
    try:
        t = db.query(models.Task).filter_by(task_id=task_id).first()
        if t:
            t.status = "running"
            db.commit()
        try:
            compiled, md_text, html, html_url = run_roundtable(query, symbols, type_, task_id)
            rep = models.Report(
                task_id=task_id, openid=openid,
                summary_json=json.dumps(compiled["conclusion"], ensure_ascii=False),
                report_json=json.dumps(compiled, ensure_ascii=False),
                html_url=html_url, md_text=md_text,
            )
            db.add(rep)
            if t:
                t.status = "done"
                t.finished_at = datetime.utcnow()
            db.commit()
            notify.push_inbox(db, openid, "圆桌报告", f"[{type_}] {query}", task_id)
            notify.notify(db, openid, f"你的圆桌报告已生成：{query}")
        except Exception as e:
            if t:
                t.status = "interrupted"
                db.commit()
            notify.push_inbox(db, openid, "圆桌失败", str(e)[:120], task_id)
            db.commit()
    finally:
        db.close()


@app.post("/api/roundtable", response_model=TaskResp)
def create_roundtable(
    req: RoundtableReq,
    background: BackgroundTasks,
    openid: str = Depends(_openid),
    db: Session = Depends(get_db),
):
    task_id = "rt_" + uuid.uuid4().hex[:12]
    db.add(models.Task(
        task_id=task_id, openid=openid, type=req.type,
        query=req.query, symbols=json.dumps(req.symbols), status="pending",
    ))
    db.commit()
    background.add_task(_run_and_store, task_id, openid, req.query, req.symbols, req.type)
    return TaskResp(task_id=task_id, status="pending")


@app.get("/api/roundtable/{task_id}", response_model=ReportResp)
def get_roundtable(task_id: str, db: Session = Depends(get_db)):
    t = db.query(models.Task).filter_by(task_id=task_id).first()
    if not t:
        return ReportResp(task_id=task_id, status="not_found")
    rep = db.query(models.Report).filter_by(task_id=task_id).first()
    if not rep:
        return ReportResp(task_id=task_id, status=t.status)
    return ReportResp(
        task_id=task_id, status=t.status,
        summary=json.loads(rep.summary_json or "{}"),
        report_json=json.loads(rep.report_json or "{}"),
        report_html_url=rep.html_url,
    )


@app.post("/api/portfolio/import")
def import_portfolio(
    items: List[PortfolioItem],
    openid: str = Depends(_openid),
    db: Session = Depends(get_db),
):
    db.query(models.Portfolio).filter_by(openid=openid).delete()
    for it in items:
        db.add(models.Portfolio(
            openid=openid, symbol=it.symbol, name=it.name,
            shares=it.shares, cost=it.cost,
        ))
    db.commit()
    return {"ok": True, "count": len(items)}


@app.post("/api/screener", response_model=TaskResp)
def create_screener(
    req: ScreenerReq,
    openid: str = Depends(_openid),
    db: Session = Depends(get_db),
):
    task_id = "sc_" + uuid.uuid4().hex[:12]
    cands = screen(req.strategy)
    db.add(models.ScreenerResult(
        task_id=task_id, openid=openid, strategy=req.strategy,
        candidates_json=json.dumps(cands, ensure_ascii=False),
    ))
    if req.watch:
        for c in cands:
            db.add(models.Watchlist(
                openid=openid, symbol=c["symbol"],
                alert_types=json.dumps(["breakout"]),
            ))
    db.commit()
    notify.push_inbox(db, openid, "选股结果", f"[{req.strategy}] 命中 {len(cands)} 只", task_id)
    return TaskResp(task_id=task_id, status="done")


@app.post("/api/watch")
def set_watch(
    req: WatchReq,
    openid: str = Depends(_openid),
    db: Session = Depends(get_db),
):
    db.query(models.Watchlist).filter_by(openid=openid).delete()
    for s in req.symbols:
        db.add(models.Watchlist(
            openid=openid, symbol=s, alert_types=json.dumps(req.alert_types),
        ))
    db.commit()
    return {"ok": True, "count": len(req.symbols)}


@app.get("/api/inbox", response_model=List[InboxItem])
def get_inbox(openid: str = Depends(_openid), db: Session = Depends(get_db)):
    rows = (
        db.query(models.Inbox).filter_by(openid=openid)
        .order_by(models.Inbox.ts.desc()).limit(50).all()
    )
    return [InboxItem(
        id=r.id, msg_type=r.msg_type, title=r.title,
        task_id=r.task_id, read=r.read, ts=r.ts.isoformat(),
    ) for r in rows]


@app.post("/api/subscription")
def set_sub(
    scene: str, authorized: bool = True,
    openid: str = Depends(_openid), db: Session = Depends(get_db),
):
    sub = db.query(models.Subscription).filter_by(openid=openid, scene=scene).first()
    if not sub:
        db.add(models.Subscription(openid=openid, scene=scene, authorized=authorized))
    else:
        sub.authorized = authorized
    db.commit()
    return {"ok": True}


@app.post("/internal/cron/{phase}")
def cron_trigger(phase: str, background: BackgroundTasks):
    from app import cron as cronmod
    background.add_task(cronmod.run_phase, phase)
    return {"ok": True, "phase": phase}


@app.get("/")
def health():
    return {"status": "ok", "service": "stock-roundtable-cloud"}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}

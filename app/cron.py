"""定时任务：盘前/午盘/尾盘/收盘。

TCB 部署：用 SCF 定时触发器 POST /internal/cron/{phase}，
本函数跑在云托管容器（长超时），遍历用户、按持仓/自选生成报告并推送。

设计要点：
- run_phase 只「收集目标用户 → 线程池提交 → 立即返回」，HTTP 不等圆桌跑完，
  契合云函数短超时 + 容器长任务（圆桌可能几十秒~分钟级）。
- 每用户独立 session（不跨线程共享），并发上限 3 控容器压力。
- 必须写 Task 表（status=done）：否则前端 GET /api/roundtable/{task_id} 会 not_found。
"""
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from app.db import SessionLocal
from app import models
from app.orchestrator import run_roundtable
from app import notify

PHASE_PROMPT = {
    "pre": "盘前早报：隔夜消息与今日关注",
    "noon": "午盘复盘：上午主线与持仓快照",
    "tail": "尾盘信号：形态扫描与机会",
    "close": "收盘诊断：持仓组合圆桌诊断",
}

# 并发跑圆桌的用户数上限（容器侧保护，可按实例规格调大）
_exec = ThreadPoolExecutor(max_workers=3)


def run_phase(phase: str):
    """入口：收集需要跑的用户，提交到线程池后立即返回。"""
    db = SessionLocal()
    try:
        prompt = PHASE_PROMPT.get(phase, phase)
        users = db.query(models.User).all()
        targets = []
        for u in users:
            pf = db.query(models.Portfolio).filter_by(openid=u.openid).all()
            wt = db.query(models.Watchlist).filter_by(openid=u.openid).all()
            symbols = list(dict.fromkeys([p.symbol for p in pf] + [w.symbol for w in wt]))[:10]
            if not symbols:
                continue
            type_ = "portfolio" if pf else "single"
            targets.append((u.openid, symbols, type_))
    finally:
        db.close()

    for openid, symbols, type_ in targets:
        _exec.submit(_run_for_user, phase, prompt, openid, symbols, type_)


def _run_for_user(phase: str, prompt: str, openid: str, symbols: list, type_: str):
    """单用户任务：写 Task → 跑圆桌 → 写 Report → 推 inbox/邮件。"""
    db = SessionLocal()
    try:
        task_id = f"{phase}_{uuid.uuid4().hex[:8]}"
        db.add(models.Task(
            task_id=task_id, openid=openid, type=type_,
            query=prompt, symbols=json.dumps(symbols),
            status="done", finished_at=datetime.utcnow(),
        ))
        db.commit()
        try:
            compiled, md_text, html, html_url = run_roundtable(prompt, symbols, type_, task_id)
            db.add(models.Report(
                task_id=task_id, openid=openid,
                summary_json=json.dumps(compiled["conclusion"], ensure_ascii=False),
                report_json=json.dumps(compiled, ensure_ascii=False),
                html_url=html_url, md_text=md_text,
            ))
            notify.push_inbox(db, openid, prompt, f"[{type_}] 诊断", task_id)
            notify.notify(db, openid, f"{prompt} 已生成")
            db.commit()
        except Exception as e:
            # 圆桌失败也保留 Task 记录，并写一条失败 inbox 便于排查
            db.rollback()
            notify.push_inbox(db, openid, "定时任务失败", f"{prompt}：{str(e)[:120]}", task_id)
            db.commit()
    finally:
        db.close()

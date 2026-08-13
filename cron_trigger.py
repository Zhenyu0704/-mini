"""腾讯云函数 SCF 定时触发器函数：唤醒云托管容器跑圆桌定时任务。

部署步骤（控制台）：
1. TCB 环境 lwx1-d3gq2yj54ea9800e4 → 云函数 → 新建（Python3.9）→ 把本文件内容贴进函数代码。
2. 函数「环境变量」加一项：ROUNDTABLE_BASE = 云托管默认域名
   （形如 https://xxx.ap-shanghai.cloudbaseapp.com，在云托管服务详情页获取）。
3. 给函数加 4 个「定时触发器」，每个触发器在「附加参数」里填：
   {"phase":"pre"}  / {"phase":"noon"} / {"phase":"tail"} / {"phase":"close"}
4. 触发器 Cron（北京时间）：
   盘前 30 8 * * 1-5 | 午盘 35 11 * * 1-5 | 尾盘 30 14 * * 1-5 | 收盘 5 15 * * 1-5
"""
import json
import os
import requests


def main(event, context):
    base = os.getenv("ROUNDTABLE_BASE", "").rstrip("/")
    phase = "close"
    try:
        if isinstance(event, (bytes, bytearray)):
            event = event.decode("utf-8")
        if isinstance(event, str) and event.strip():
            event = json.loads(event)
        if isinstance(event, dict):
            phase = event.get("phase", "close")
    except Exception:
        pass

    if not base:
        return {"ok": False, "error": "未配置环境变量 ROUNDTABLE_BASE"}

    url = f"{base}/internal/cron/{phase}"
    try:
        r = requests.post(url, timeout=10)
        return {"ok": True, "phase": phase, "status": r.status_code, "resp": r.text[:200]}
    except Exception as e:
        return {"ok": False, "phase": phase, "error": str(e)[:200]}

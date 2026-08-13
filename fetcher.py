"""取数层：mock 返回假行情；真实模式用 akshare + tencent_provider（qt.gtimg.cn）。

设计原则：
- 所有真实取数都在函数内部「延迟 import akshare」，mock 模式（FETCHER_MOCK=true）不依赖 akshare 也能跑。
- get_quote 真实分支：tencent_provider（gtimg，轻量稳定）优先，akshare 单只 hist 兜底。
- get_kline / get_fundamentals / screen 真实分支：走 akshare。
- 任意单点取数失败都不会拖垮整场圆桌：_run_one 外层有掉队兜底（见 orchestrator）。

部署：设 FETCHER_MOCK=false 即启用真实取数；可同时设 LLM_MOCK=false 跑真实 LLM。
"""
import json
import random
import re
from datetime import datetime

from app.config import config


# ---------- 小工具 ----------

def _norm_akshare_code(symbol: str) -> str:
    """002594.SZ / 600519.SH / sz000001 / 600519 -> 600519（akshare 用纯代码）"""
    s = symbol.strip().upper()
    s = s.replace(".SZ", "").replace(".SH", "")
    return re.sub(r"[^0-9]", "", s)


def _norm_gtimg_prefix(symbol: str) -> str:
    s = symbol.strip().lower().replace(".sz", "").replace(".sh", "")
    code = re.sub(r"[^0-9]", "", s)
    return ("sh" + code) if code and code[0] == "6" else ("sz" + code)


def _clip(text, maxlen: int = 200):
    if not text:
        return text
    text = str(text)
    return text if len(text) <= maxlen else text[:maxlen] + "…"


# ---------- 实时行情 ----------

def get_quote(symbol: str) -> dict:
    """单股实时行情快照（带涨跌方向）。"""
    if config.FETCHER_MOCK:
        price = round(random.uniform(5, 200), 2)
        pct = round(random.uniform(-6, 6), 2)
        return {
            "symbol": symbol,
            "name": symbol,
            "price": price,
            "pct": pct,
            "source": "mock",
            "ts": datetime.utcnow().isoformat(),
        }

    # 真实：gtimg 首选（轻量、稳，fetcher 层再加重试），akshare 兜底
    from app.tencent_provider import get_realtime
    last_err = None
    for _ in range(3):
        try:
            r = get_realtime(symbol)
            return {
                "symbol": symbol,
                "name": r.get("name"),
                "price": r.get("price"),
                "pct": r.get("pct"),
                "source": "gtimg",
                "ts": datetime.utcnow().isoformat(),
                "extras": r,
            }
        except Exception as e:
            last_err = e
            continue
    try:
        import akshare as ak
        code = _norm_akshare_code(symbol)
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
        if df is not None and not df.empty:
            last = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else last
            price = float(last["收盘"])
            prev_close = float(prev["收盘"])
            pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0
            return {
                "symbol": symbol,
                "name": code,
                "price": price,
                "pct": pct,
                "source": "akshare",
                "ts": datetime.utcnow().isoformat(),
            }
    except Exception:
        pass

    raise RuntimeError(f"实时行情取数失败: {symbol} (last_err={last_err})")


# ---------- 历史日 K ----------

def get_kline(symbol: str, days: int = 60) -> list:
    """日 K 序列（最近 days 根，受 QUOTE_DAYS_LIMIT 约束）。用于给专家喂近期结构。"""
    days = min(days, config.QUOTE_DAYS_LIMIT)
    if config.FETCHER_MOCK:
        return [
            {"date": f"2026-08-{i:02d}", "open": round(random.uniform(10, 20), 2),
             "close": round(random.uniform(10, 20), 2),
             "high": round(random.uniform(10, 20), 2),
             "low": round(random.uniform(10, 20), 2),
             "volume": random.randint(1_000_000, 9_000_000)}
            for i in range(1, days + 1)
        ]

    # 真实：新浪日 K 优先（稳，fetcher 层再加重试），akshare 兜底
    from app.tencent_provider import get_kline_sina
    for _ in range(3):
        try:
            kl = get_kline_sina(symbol, days)
            if kl:
                return kl
        except Exception:
            continue
    try:
        import akshare as ak
        code = _norm_akshare_code(symbol)
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
        if df is not None and not df.empty:
            tail = df.tail(days)
            out = []
            for _, row in tail.iterrows():
                out.append({
                    "date": str(row["日期"]),
                    "open": float(row["开盘"]),
                    "close": float(row["收盘"]),
                    "high": float(row["最高"]),
                    "low": float(row["最低"]),
                    "volume": float(row["成交量"]),
                })
            return out
    except Exception as e:
        return [{"error": str(e)[:120]}]
    return []


# ---------- 财务 / 估值 ----------

def get_fundamentals(symbol: str) -> dict:
    """个股基本面快照：行业、市值、估值指标、主营业务（截断）。"""
    if config.FETCHER_MOCK:
        return {
            "mock": True,
            "name": symbol,
            "industry": "示例行业",
            "total_market_cap": 1.0e11,
            "pe": 20.0,
            "pb": 3.0,
            "dividend_yield": 0.01,
            "profit_yoy": 0.1,
        }

    info: dict = {}
    # 估值（pe/pb）用腾讯实时接口，稳定可靠
    try:
        from app.tencent_provider import get_realtime
        r = get_realtime(symbol)
        info["name"] = r.get("name")
        info["pe"] = r.get("pe")
        info["pb"] = r.get("pb")
        info["source"] = "gtimg"
    except Exception:
        pass
    # 行业 / 主营业务等尽力用 akshare 补充（网络不可达时忽略，不影响主流程）
    try:
        import akshare as ak
        code = _norm_akshare_code(symbol)
        ind = ak.stock_individual_info_em(symbol=code)
        if isinstance(ind, dict):
            info.update({
                "industry": ind.get("行业"),
                "total_market_cap": ind.get("总市值"),
                "float_market_cap": ind.get("流通市值"),
                "listing_date": ind.get("上市时间"),
                "business": _clip(ind.get("主营业务"), 200),
                "concepts": _clip(ind.get("股票概念"), 200),
            })
            info["source"] = "gtimg+akshare"
    except Exception as e:
        info["stock_info_error"] = str(e)[:120]
    return info


# ---------- 条件选股 ----------

def screen(strategy: str) -> list:
    """条件选股：返回候选标的列表。真实分支走 akshare 全市场快照 + 过滤。"""
    if config.FETCHER_MOCK:
        return [
            {"symbol": "600519.SH", "name": "贵州茅台", "reason": f"[{strategy}] mock 命中"},
            {"symbol": "000001.SZ", "name": "平安银行", "reason": f"[{strategy}] mock 命中"},
        ]

    try:
        import akshare as ak
        import pandas as pd
        df = ak.stock_zh_a_spot_em()
        if df is None or df.empty:
            return []

        df = df.copy()
        for col in ("涨跌幅", "量比", "换手率"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if strategy in ("涨停", "打板"):
            cond = df["涨跌幅"] >= 9.5
        elif strategy in ("放量突破", "一进二", "放量"):
            cond = (df["涨跌幅"] >= 3) & (df["涨跌幅"] <= 8) & (df["量比"] >= 2) & (df["换手率"] >= 5)
        elif strategy in ("强势", "上涨"):
            cond = df["涨跌幅"] >= 3
        else:
            # 未知策略：默认返回当日涨幅居前的标的
            cond = df["涨跌幅"] >= 3

        res = df[cond].sort_values("涨跌幅", ascending=False).head(20)
        out = []
        for _, r in res.iterrows():
            code = str(r["代码"])
            sym = f"{code}.SH" if code.startswith("6") else f"{code}.SZ"
            out.append({
                "symbol": sym,
                "name": r["名称"],
                "reason": f"[{strategy}] 涨跌幅{r['涨跌幅']}%, 量比{r.get('量比', 'NA')}, 换手{r.get('换手率', 'NA')}%",
            })
        return out
    except Exception as e:
        return [{"symbol": "", "name": "选股失败", "reason": str(e)[:120]}]

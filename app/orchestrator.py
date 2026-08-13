"""圆桌引擎：主理人编排 6 专家 → 4 模块汇编 → 渲染。

设计要点（沿用专家包护栏）：
- 并行调度：6 专家同批下发，互不看结论，避免互相带偏
- 掉队兜底：有效回传不足则标注「执行中断」，主理人不代写
- 合规护栏：渲染层强制免责声明、禁指令词（见 renderer）
"""
import concurrent.futures
import json
from datetime import datetime

from app.config import config
from app.experts import EXPERTS
from app.fetcher import get_quote, get_kline, get_fundamentals
from app.llm import LLMClient
from app.renderer import render_report


def _run_one(expert, task_text, quotes_text, context_text):
    system = (expert["system"]
              .replace("{task}", task_text)
              .replace("{quotes}", quotes_text)
              .replace("{context}", context_text))
    llm = LLMClient()
    md = llm.chat(system, f"用户问题：{task_text}\n行情与补充数据见上文。请按你的框架输出。")
    return {"key": expert["key"], "name": expert["name"], "headline": expert["headline"], "md": md}


def run_roundtable(query: str, symbols: list, type_: str, task_id: str):
    """跑一次完整圆桌。返回 (compiled_dict, md_text, html_string, html_url)。"""
    task_text = f"[{type_}] {query}  标的：{', '.join(symbols) if symbols else '无'}"
    quotes = {s: get_quote(s) for s in symbols} if symbols else {}
    quotes_text = json.dumps(quotes, ensure_ascii=False, indent=2)
    # 给专家补充 K 线 + 财务/估值（真实模式用 akshare，mock 模式用假数据）
    context = {}
    for s in symbols:
        context[s] = {
            "kline_recent": get_kline(s, days=60),
            "fundamentals": get_fundamentals(s),
        }
    context_text = (json.dumps(context, ensure_ascii=False, indent=2)
                    if context else "（无标的，无需补充数据）")

    # 并行调度 6 专家
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(_run_one, e, task_text, quotes_text, context_text) for e in EXPERTS]
        for f in concurrent.futures.as_completed(futs):
            try:
                results.append(f.result())
            except Exception as e:  # 掉队兜底
                results.append({"error": str(e)})

    valid = [r for r in results if "md" in r]
    interrupted = [EXPERTS[i]["name"] for i, r in enumerate(results) if "md" not in r]

    compiled = compile_report(query, type_, quotes, valid, interrupted)
    md_text = to_markdown(compiled)
    html, html_url = render_report(md_text, compiled, task_id)
    return compiled, md_text, html, html_url


def compile_report(query, type_, quotes, voices, interrupted):
    """汇编 4 模块：结论卡 / 子专家观点 / 深度思考 / 后续关注。"""
    conclusion = {
        "you_asked": query,
        "snapshot": [
            {"symbol": s, "price": v.get("price"), "pct": v.get("pct"), "source": v.get("source")}
            for s, v in quotes.items()
        ],
        "view": "综合视角需真实 LLM 下由主理人归纳（mock 模式为占位）",
        "key_points": [],
        "votes": {"看多": 0, "看空": 0, "观望": 0},  # 真实 LLM 下填充
    }
    expert_cards = [
        {"name": v["name"], "headline": v["headline"], "md": v["md"]} for v in voices
    ]
    deep = {
        "notes": [
            "（真实 LLM 下由主理人补充：跨成员隐含模式、易忽略暗信号等元观察）",
        ],
        "qa": [
            {"tag": "关键", "q": "什么会让本次视角被推翻？", "a": "真实 LLM 下由主理人据分歧给出可证伪阈值。"},
        ],
    }
    watch = {
        "table": [
            {"var": "关键价位（真实数据）", "trigger": "跌破→短线强度走弱"},
            {"var": "估值分位（真实数据）", "trigger": "突破历史高位→性价比下降"},
        ],
        "invalid": ["若核心支撑/估值假设与主要论据矛盾，则本次综合视角可能需重估"],
    }
    return {
        "conclusion": conclusion,
        "experts": expert_cards,
        "deep": deep,
        "watch": watch,
        "interrupted": interrupted,
    }


def to_markdown(c: dict) -> str:
    """把 compiled 结构转成 4 模块 Markdown。"""
    concl = c["conclusion"]
    lines = []
    lines.append("# 圆桌报告")
    lines.append("")
    lines.append("## 01 结论卡")
    lines.append(f"**YOU ASKED**：{concl['you_asked']}")
    if concl["snapshot"]:
        lines.append("**当前关键数据快照**：")
        for s in concl["snapshot"]:
            lines.append(f"- {s['symbol']} 现价 {s['price']}（{s['pct']:+}%）来源 {s['source']}")
    lines.append(f"**圆桌综合视角**：{concl['view']}")
    lines.append(f"**圆桌立场分布**：{concl['votes']}")
    if c["interrupted"]:
        lines.append(f"> 注：以下专家执行中断，未参与本次汇编：{', '.join(c['interrupted'])}")
    lines.append("")
    lines.append("## 02 子专家观点")
    for v in c["experts"]:
        lines.append(f"### {v['name']} · {v['headline']}")
        lines.append(v["md"])
        lines.append("")
    lines.append("## 03 深度思考")
    lines.append("### 3a 主持人札记")
    for n in c["deep"]["notes"]:
        lines.append(f"- {n}")
    lines.append("### 3b 主持人 Q&A")
    for q in c["deep"]["qa"]:
        lines.append(f"- **[{q['tag']}]** {q['q']} → {q['a']}")
    lines.append("")
    lines.append("## 04 后续关注")
    lines.append("### 4a 关键变量观察台")
    for r in c["watch"]["table"]:
        lines.append(f"- {r['var']} → {r['trigger']}")
    lines.append("### 4b 综合视角失效条件")
    for inv in c["watch"]["invalid"]:
        lines.append(f"- {inv}")
    lines.append("")
    return "\n".join(lines)

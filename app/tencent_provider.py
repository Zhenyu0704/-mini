"""腾讯财经行情兜底（qt.gtimg.cn + web.ifzq.gtimg.cn）。

轻量、稳定、无需 akshare，作为实时行情与历史 K 线的首选来源；akshare 仅作兜底。
- 实时行情：qt.gtimg.cn/q=sh600519（GBK，~ 分隔字段）
- 历史日 K：web.ifzq.gtimg.cn/appstuff/app/kline/kline（JSON）
逐字段 try 保护，避免个别索引偏差导致整体报错。
"""
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_GTIMG_URL = "https://qt.gtimg.cn/q="

# 带重试的会话：应对行情源偶发 ConnectionReset / 5xx（云端网络抖动常见）
_SESSION = requests.Session()
_RETRY = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)
_SESSION.mount("https://", HTTPAdapter(max_retries=_RETRY))


def _get(url: str, timeout: int = 10):
    return _SESSION.get(url, timeout=timeout)


def _norm_gtimg(symbol: str) -> str:
    """002594.SZ / 600519.SH / sz000001 / 600519 -> sh600519 / sz000001"""
    s = symbol.strip().lower()
    s = s.replace(".sz", "").replace(".sh", "")
    code = re.sub(r"[^0-9]", "", s)
    if not code:
        return symbol
    return ("sh" + code) if code[0] == "6" else ("sz" + code)


def get_realtime(symbol: str) -> dict:
    """实时行情快照（qt.gtimg.cn）。"""
    prefix = _norm_gtimg(symbol)
    resp = _get(_GTIMG_URL + prefix, timeout=8)
    # gtimg 返回 GBK；若已是 UTF-8 则回退解码，避免乱码
    try:
        text = resp.content.decode("utf-8")
    except UnicodeDecodeError:
        text = resp.content.decode("gbk", errors="ignore")
    m = re.search(r'="(.*)";', text)
    if not m:
        raise ValueError(f"gtimg 返回无法解析: {text[:80]}")
    f = m.group(1).split("~")
    get = lambda i: f[i] if i < len(f) else None

    def to_float(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    # 第 35 字段格式：当前价/成交量(手)/成交额
    vol = amt = None
    raw35 = get(35)
    if raw35 and "/" in raw35:
        parts = raw35.split("/")
        if len(parts) > 1:
            vol = to_float(parts[1])
        if len(parts) > 2:
            amt = to_float(parts[2])

    return {
        "symbol": symbol,
        "name": get(1),
        "code": get(2),
        "price": to_float(get(3)),
        "prev_close": to_float(get(4)),
        "open": to_float(get(5)),
        "high": to_float(get(33)),
        "low": to_float(get(34)),
        "pct": to_float(get(32)),
        "change": to_float(get(31)),
        "volume": vol,            # 手
        "amount": amt,            # 元
        "turnover_rate": get(38),  # 换手率（含 %）
        "pe": to_float(get(39)),   # 市盈率 TTM
        "pb": to_float(get(43)),   # 市净率
        "time": get(30),           # HH:MM:SS
        "source": "gtimg",
    }


def get_kline_sina(symbol: str, days: int = 60) -> list:
    """历史日 K（新浪接口，长期稳定）。返回 [{date,open,close,high,low,volume}]。

    新浪返回字段：day/open/high/low/close/volume（volume 单位：股）。
    腾讯 web.ifzq.gtimg.cn 的 kline 子路径已下线（返回 code:11），故改用新浪。
    """
    prefix = _norm_gtimg(symbol)
    url = ("https://money.finance.sina.com.cn/quotes_service/api/json_v2.php"
           "/CN_MarketData.getKLineData?symbol={prefix}&scale=240&ma=no&datalen={days}")
    url = url.format(prefix=prefix, days=days)
    resp = _get(url, timeout=10)
    arr = resp.json()
    if not isinstance(arr, list) or not arr:
        return []
    out = []
    for row in arr[-days:]:
        try:
            out.append({
                "date": row["day"],
                "open": float(row["open"]),
                "close": float(row["close"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "volume": float(row["volume"]),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return out

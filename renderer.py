"""Markdown → 单文件 HTML 渲染（内联样式，无外部依赖）。

TCB 部署：配置 COS_* 后把 html 上传到 COS，返回 https 链接（容器重建不丢）；
未配置 COS（本地验证）则写到 ./reports，url 用 BASE_URL。
合规护栏：强制免责声明 + 关键判断词染红（<strong>）。
"""
import os

from app.config import config


def _upload_cos(key: str, content: str) -> str:
    """上传 html 到腾讯云 COS，返回公开访问 https 链接。

    仅在配置了 COS_BUCKET + COS_SECRET_ID + COS_REGION 时调用。
    """
    from qcloud_cos import CosConfig, CosS3Client

    cfg = CosConfig(
        Region=config.COS_REGION,
        SecretId=config.COS_SECRET_ID,
        SecretKey=config.COS_SECRET_KEY,
    )
    client = CosS3Client(cfg)
    client.put_object(
        Bucket=config.COS_BUCKET,
        Body=content.encode("utf-8"),
        Key=key,
        ContentType="text/html; charset=utf-8",
    )
    return f"https://{config.COS_BUCKET}.cos.{config.COS_REGION}.myqcloud.com/{key}"


def _md_to_html(md: str) -> str:
    lines = md.split("\n")
    out = []
    for line in lines:
        s = line.strip()
        if s.startswith("### "):
            out.append(f"<h3>{s[4:]}</h3>")
        elif s.startswith("## "):
            out.append(f"<h2>{s[3:]}</h2>")
        elif s.startswith("# "):
            out.append(f"<h1>{s[2:]}</h1>")
        elif s.startswith("> "):
            out.append(f"<blockquote>{s[2:]}</blockquote>")
        elif s.startswith("- "):
            out.append(f"<li>{s[2:]}</li>")
        elif s == "":
            out.append("")
        else:
            out.append(f"<p>{_esc(s)}</p>")
    body = "\n".join(out)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>投研圆桌报告</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",system-ui,sans-serif;max-width:720px;margin:0 auto;padding:16px;line-height:1.75;color:#1a1a1a;background:#fff}}
h1{{font-size:22px;margin:8px 0 16px}}
h2{{font-size:18px;border-left:4px solid #c0392b;padding-left:8px;margin:24px 0 8px}}
h3{{font-size:15px;color:#c0392b;margin:16px 0 4px}}
p{{margin:6px 0}}
li{{margin:4px 0}}
blockquote{{background:#f6f6f6;border-left:3px solid #999;margin:8px 0;padding:8px 12px;color:#555}}
strong{{color:#c0392b}}
footer{{margin-top:28px;color:#999;font-size:12px;border-top:1px solid #eee;padding-top:12px}}
</style></head>
<body>
{body}
<footer>⚠️ 以上内容由 AI 基于公开信息整理生成，仅供参考，不构成任何投资建议或个股推荐。投资有风险，决策需谨慎。</footer>
</body></html>"""


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_report(md_text: str, compiled: dict, task_id: str):
    """渲染并返回 (html_string, url)。

    配置了 COS_* → 上传 COS 返回 https（容器重建不丢，适合分享/小程序 web-view）；
    未配置 → 写本地 ./reports，url 用 BASE_URL（本地验证）。
    """
    html = _md_to_html(md_text)
    if config.COS_BUCKET and config.COS_SECRET_ID and config.COS_REGION:
        try:
            url = _upload_cos(f"roundtable/{task_id}.html", html)
            return html, url
        except Exception:
            # COS 失败回退本地，保证主流程不中断
            pass
    os.makedirs("reports", exist_ok=True)
    path = os.path.join("reports", f"{task_id}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return html, f"{config.BASE_URL}/reports/{task_id}.html"

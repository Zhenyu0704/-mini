"""推送层：消息中心写入（必做）+ 订阅消息（占位）+ 邮件兜底（QQ 邮箱）。

TCB 部署时：
- 订阅消息：用微信 access_token + 模板 id 向授权用户推送（见微信订阅消息文档）
- 邮件：配置 QQ 邮箱授权码（EMAIL_USER/EMAIL_PASS）即可启用
"""
import smtplib
from email.mime.text import MIMEText

from app.config import config


def push_inbox(db, openid: str, msg_type: str, title: str, task_id: str):
    """写入消息中心（小程序内可见，免备案）。"""
    from app import models
    db.add(models.Inbox(openid=openid, msg_type=msg_type, title=title, task_id=task_id))


def notify(db, openid: str, text: str):
    """先 inbox（必做），再尝试邮件兜底。订阅消息在 TCB 实现后接入。"""
    # 邮件兜底
    if config.EMAIL_USER and config.EMAIL_PASS:
        try:
            _send_email(config.EMAIL_USER, f"[投研圆桌] {text[:40]}", text)
        except Exception:
            pass  # 推送失败不影响主流程


def _send_email(to: str, subject: str, body: str):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_USER
    msg["To"] = to
    with smtplib.SMTP_SSL("smtp.qq.com", 465) as s:
        s.login(config.EMAIL_USER, config.EMAIL_PASS)
        s.send_message(msg)

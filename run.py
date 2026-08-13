"""容器启动入口：主应用跑在 PORT（TCB 注入，默认 8000）；

同时为兼容 CloudBase Run 健康检查可能探测 80 端口，额外在 80 起一个
极简 health server 返回 200。这样无论平台探针打 80 还是 PORT，都能通过，
避免「Back-off restarting failed container」的端口错配重启。
"""
import os
import threading

import uvicorn

from app.main import app

_HEALTH = b'{"status":"ok"}'


def _serve_health_80():
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class _H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(_HEALTH)

        def log_message(self, *args):  # 静默
            pass

    HTTPServer(("0.0.0.0", 80), _H).serve_forever()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    if port != 80:
        threading.Thread(target=_serve_health_80, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=port)

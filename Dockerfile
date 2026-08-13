FROM python:3.11-slim

WORKDIR /app

# 系统依赖（akshare 等可能需要）
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 云托管容器：主应用监听 PORT（TCB 注入，默认 8000），run.py 另在 80 端口回健康检查
# 避免 TCB 探针端口错配导致的重启循环；建表交给 FastAPI startup 事件处理
ENV PORT=8000
EXPOSE 80 8000
CMD ["python", "run.py"]

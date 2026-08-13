FROM python:3.11-slim

WORKDIR /app

# 系统依赖（akshare 等可能需要）
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 云托管容器：暴露端口、设长超时（圆桌可能分钟级）
EXPOSE 8000
CMD ["sh", "-c", "python -c \"from app.db import Base, engine; import app.models; Base.metadata.create_all(bind=engine)\" && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

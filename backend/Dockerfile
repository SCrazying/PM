# 后端镜像（FastAPI + uvicorn + APScheduler 随进程）
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 离线/在线均可：优先使用本地 wheels 目录（若存在），否则走 PyPI
COPY requirements.txt .
COPY wheels/ ./wheels/
RUN pip install --no-index --find-links=./wheels -r requirements.txt || \
    pip install -r requirements.txt

COPY . .

EXPOSE 8000

# 启动：先执行迁移与种子，再起服务
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

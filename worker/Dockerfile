FROM python:3.12-slim

WORKDIR /app/worker

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Celery worker는 backend와 동일한 의존성 사용
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# worker는 backend 코드의 tasks, core 모듈을 import함
# 볼륨 마운트: ./backend → /app/backend, ./worker → /app/worker, ./common → /app/common

ENV PYTHONPATH=/app/backend:/app/worker:/app/common

CMD ["celery", "-A", "main.celery_app", "worker", \
     "--loglevel=info", \
     "--queues=test_execution,ci_cd,default", \
     "--concurrency=4"]

FROM python:3.12-slim

WORKDIR /app/backend

# 시스템 의존성
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드는 볼륨으로 마운트됨 (docker-compose.yml)
# - ./backend → /app/backend
# - ./common  → /app/common

ENV PYTHONPATH=/app/backend:/app/common

# 기본 실행: FastAPI 서버
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

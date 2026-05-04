# ══════════════════════════════════════════════
#  Worker Dockerfile (옵션 2: 워커 안에서 직접 실행)
# ══════════════════════════════════════════════
# Playwright 공식 이미지 (Ubuntu 22.04 jammy 기반) + 기본 Python 3.10
# - Node.js, Chromium, Firefox, WebKit 모두 포함
# - 별도 Docker-in-Docker 없이 워커가 직접 Playwright 실행

FROM mcr.microsoft.com/playwright:v1.47.0-jammy

WORKDIR /app/worker

# Python 3.10 + pip 설치 (Ubuntu 22.04 기본 Python 사용 — 안정적)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# python3를 python으로도 호출 가능하게
RUN ln -sf /usr/bin/python3 /usr/bin/python

# Backend의 Python 의존성 (Celery, Mongo, Redis 등)
COPY backend/requirements.txt /tmp/requirements.txt
RUN python3 -m pip install --no-cache-dir --upgrade pip \
    && python3 -m pip install --no-cache-dir -r /tmp/requirements.txt

# Playwright 테스트 실행 환경 준비
# (워커가 Task를 받을 때마다 임시 디렉토리에 spec 파일 생성 → 여기서 실행)
WORKDIR /app/playwright-runner
COPY worker/playwright-runner/package.json ./
RUN npm install

# 코드는 볼륨 마운트로 들어옴
WORKDIR /app/worker

ENV PYTHONPATH=/app/backend:/app/worker:/app/common
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV PLAYWRIGHT_RUNNER_DIR=/app/playwright-runner

CMD ["celery", "-A", "main.celery_app", "worker", \
     "--loglevel=info", \
     "--queues=test_execution,ai_generation,default", \
     "--concurrency=2"]

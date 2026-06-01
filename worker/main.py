"""
Celery Worker 진입점
─────────────────────
docker-compose의 worker 서비스가 `celery -A main.celery_app worker`로 실행하는 진입점.
backend의 Celery app과 tasks를 그대로 재사용한다.
"""

import sys
from pathlib import Path

# backend 디렉토리를 import 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from core.celery_app import celery_app  # noqa

# Celery autodiscover가 tasks 모듈을 찾을 수 있도록 import
import tasks.test_runner  # noqa
import tasks.ai_generation  # noqa

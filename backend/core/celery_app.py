"""
Celery 애플리케이션 설정
───────────────────────
Redis(broker 서비스)를 Broker와 Result Backend로 사용한다.
"""

from celery import Celery
from core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ate_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    timezone="Asia/Seoul",
    enable_utc=True,

    task_soft_time_limit=settings.WORKER_TIMEOUT,
    task_time_limit=settings.WORKER_TIMEOUT + 60,

    worker_prefetch_multiplier=1,
    worker_concurrency=4,
    worker_max_tasks_per_child=50,

    task_routes={
        "tasks.test_runner.*": {"queue": "test_execution"},
        "tasks.ai_generation.*": {"queue": "ai_generation"},
    },

    task_default_queue="default",
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    result_expires=86400,
)

celery_app.autodiscover_tasks(["tasks"])

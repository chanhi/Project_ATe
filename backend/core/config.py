"""
ATe 백엔드 설정 모듈
─────────────────────
docker-compose 환경변수와 매칭된다 (MONGO_URL, REDIS_URL, CELERY_*).
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ──
    APP_NAME: str = "ATe"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # ── MongoDB ──
    MONGO_URL: str = "mongodb://localhost:27017/ate_db"
    DB_NAME: str = "ate_db"

    # ── Redis ──
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Celery ──
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── WebSocket ──
    WS_HEARTBEAT_INTERVAL: int = 30
    WS_MAX_CONNECTIONS: int = 100

    # ── Docker Worker ──
    DOCKER_HOST: str = "unix:///var/run/docker.sock"
    WORKER_IMAGE: str = "ate-playwright-worker:latest"
    WORKER_TIMEOUT: int = 300

    # ── CI/CD ──
    WEBHOOK_SECRET: str = "change-me"

    # ── AI ──
    OPENAI_API_KEY: str = ""

    # ── Security ──
    SECRET_KEY: str = "change-me"


@lru_cache
def get_settings() -> Settings:
    return Settings()

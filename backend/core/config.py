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
        extra="ignore",  # .env의 DB_USER 등 도커용 변수 무시
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

    # ── AI ──
    OPENAI_API_KEY: str = ""
    AI_SERVICE_URL: str = "http://ai-service:9000"  # AI팀 FastAPI 서버
    AI_SERVICE_TIMEOUT: int = 60                    # LLM 호출 타임아웃 (초)
    AI_SERVICE_MOCK: bool = False                   # AI팀 미연결 시 mock 응답 사용

    # ── Security ──
    SECRET_KEY: str = "change-me"

    # ── v2 추가: 파일 업로드/내보내기 ──
    UPLOAD_DIR: str = "/tmp/ate-uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    EXPORT_DIR: str = "/tmp/ate-exports"


@lru_cache
def get_settings() -> Settings:
    return Settings()

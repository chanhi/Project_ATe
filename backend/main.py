"""
ATe Backend — FastAPI 메인
══════════════════════════

담당 범위:
- Redis/Celery 작업 큐 기반 비동기 테스트 실행
- WebSocket 실시간 로그 스트리밍
- CI/CD 파이프라인 연동 API
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import api_router
from core.config import get_settings
from core.mongo import init_mongo, close_mongo
from core.redis_client import init_redis, close_redis
from core.celery_app import celery_app  # noqa: F401 (Celery autodiscover용)
from websocket.handler import router as ws_router, get_active_connection_count

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("═" * 50)
    logger.info("  ATe Backend 시작")
    logger.info("═" * 50)

    await init_mongo()
    await init_redis()
    logger.info("✅ MongoDB + Redis 연결 완료")

    yield

    await close_redis()
    await close_mongo()
    logger.info("서버 종료 완료")


app = FastAPI(
    title="ATe API",
    description="AI 기반 자동화 소프트웨어 테스팅 플랫폼 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(ws_router, prefix="/ws/v1")


@app.get("/health", tags=["System"])
async def health_check():
    from core.redis_client import get_redis
    from core.mongo import get_db

    redis_ok = False
    mongo_ok = False
    try:
        await get_redis().ping()
        redis_ok = True
    except Exception:
        pass
    try:
        await get_db().command("ping")
        mongo_ok = True
    except Exception:
        pass

    return {
        "status": "healthy" if (redis_ok and mongo_ok) else "degraded",
        "services": {
            "mongodb": "connected" if mongo_ok else "disconnected",
            "redis": "connected" if redis_ok else "disconnected",
            "celery_broker": settings.CELERY_BROKER_URL,
        },
        "websocket": get_active_connection_count(),
        "version": "1.0.0",
    }


@app.get("/", tags=["System"])
async def root():
    return {
        "name": "ATe API",
        "version": "1.0.0",
        "docs": "/docs",
        "ws_endpoint": "ws://localhost:8000/ws/v1/tests/{test_run_id}/logs",
    }

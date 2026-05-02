"""
Redis 연결 관리 (broker 서비스)
────────────────────────────
- 테스트 상태 캐시 (Redis Hash)
- 실시간 로그 Pub/Sub
- 로그 히스토리 List
"""

import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import redis.asyncio as aioredis

from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_redis_pool: aioredis.Redis | None = None
_pubsub_redis: aioredis.Redis | None = None


async def init_redis() -> None:
    """애플리케이션 시작 시 Redis 연결 풀 초기화"""
    global _redis_pool, _pubsub_redis

    _redis_pool = aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        max_connections=20,
    )
    _pubsub_redis = aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )

    await _redis_pool.ping()
    logger.info("✅ Redis(broker) 연결 성공: %s", settings.REDIS_URL)


async def close_redis() -> None:
    global _redis_pool, _pubsub_redis
    if _redis_pool:
        await _redis_pool.aclose()
    if _pubsub_redis:
        await _pubsub_redis.aclose()
    logger.info("Redis 연결 종료")


def get_redis() -> aioredis.Redis:
    if _redis_pool is None:
        raise RuntimeError("Redis가 초기화되지 않았습니다.")
    return _redis_pool


def get_pubsub_redis() -> aioredis.Redis:
    if _pubsub_redis is None:
        raise RuntimeError("Pub/Sub Redis가 초기화되지 않았습니다.")
    return _pubsub_redis


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  테스트 실행 상태 (Redis Hash)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TEST_RUN_KEY = "test_run:{test_run_id}"
TEST_LOG_CHANNEL = "test_log:{test_run_id}"
TEST_LOG_LIST = "test_log_list:{test_run_id}"


async def set_test_run_status(
    test_run_id: str,
    status: str,
    **extra_fields: Any,
) -> None:
    """
    Args:
        test_run_id: 테스트 실행 ID (예: "run-5555")
        status: QUEUED | PENDING | RUNNING | SUCCESS | FAILED
    """
    r = get_redis()
    key = TEST_RUN_KEY.format(test_run_id=test_run_id)

    data = {"status": status, **{k: str(v) for k, v in extra_fields.items()}}
    await r.hset(key, mapping=data)
    await r.expire(key, 86400)

    logger.debug("테스트 상태 업데이트: %s → %s", test_run_id, status)


async def get_test_run_status(test_run_id: str) -> dict[str, str] | None:
    r = get_redis()
    key = TEST_RUN_KEY.format(test_run_id=test_run_id)
    data = await r.hgetall(key)
    return data if data else None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  실시간 로그 Pub/Sub
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def publish_test_log(test_run_id: str, log_entry: dict) -> None:
    r = get_redis()
    channel = TEST_LOG_CHANNEL.format(test_run_id=test_run_id)
    history_key = TEST_LOG_LIST.format(test_run_id=test_run_id)

    payload = json.dumps(log_entry, ensure_ascii=False)
    await r.publish(channel, payload)
    await r.rpush(history_key, payload)
    await r.expire(history_key, 86400)


async def get_test_log_history(test_run_id: str) -> list[dict]:
    r = get_redis()
    history_key = TEST_LOG_LIST.format(test_run_id=test_run_id)
    raw_logs = await r.lrange(history_key, 0, -1)
    return [json.loads(log) for log in raw_logs]


@asynccontextmanager
async def subscribe_test_logs(test_run_id: str) -> AsyncGenerator:
    r = get_pubsub_redis()
    channel = TEST_LOG_CHANNEL.format(test_run_id=test_run_id)
    pubsub = r.pubsub()

    await pubsub.subscribe(channel)
    logger.info("Pub/Sub 구독 시작: %s", channel)

    try:
        yield _pubsub_message_generator(pubsub)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        logger.info("Pub/Sub 구독 종료: %s", channel)


async def _pubsub_message_generator(pubsub):
    async for message in pubsub.listen():
        if message["type"] == "message":
            yield json.loads(message["data"])

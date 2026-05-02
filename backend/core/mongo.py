"""
MongoDB 연결 관리 (Motor - async driver)
────────────────────────────────────────
Collections:
- projects
- scenarios
- test_runs
- uploaded_documents
- test_cases
"""

import logging
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_mongo_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


async def init_mongo() -> None:
    """애플리케이션 시작 시 MongoDB 연결"""
    global _mongo_client, _database

    _mongo_client = AsyncIOMotorClient(
        settings.MONGO_URL,
        serverSelectionTimeoutMS=5000,
        maxPoolSize=50,
    )
    _database = _mongo_client[settings.DB_NAME]

    # 연결 테스트
    await _mongo_client.admin.command("ping")
    logger.info("✅ MongoDB 연결 성공: %s", settings.DB_NAME)

    # 인덱스 생성
    await _create_indexes()


async def close_mongo() -> None:
    """애플리케이션 종료 시 MongoDB 연결 정리"""
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
    logger.info("MongoDB 연결 종료")


def get_db() -> AsyncIOMotorDatabase:
    """MongoDB 데이터베이스 인스턴스 반환"""
    if _database is None:
        raise RuntimeError("MongoDB가 초기화되지 않았습니다.")
    return _database


async def _create_indexes() -> None:
    """컬렉션별 인덱스 생성"""
    db = get_db()

    # projects
    await db.projects.create_index("project_id", unique=True)

    # scenarios (기존 유지)
    await db.scenarios.create_index("scenario_id", unique=True)
    await db.scenarios.create_index("project_id")

    # test_runs
    await db.test_runs.create_index("test_run_id", unique=True)
    await db.test_runs.create_index("scenario_id")
    await db.test_runs.create_index([("created_at", -1)])
    await db.test_runs.create_index("run_group_id")
    await db.test_runs.create_index("test_case_id")

    # ── v2.1 추가: run_group ──
    await db.test_run_groups.create_index("run_group_id", unique=True)
    await db.test_run_groups.create_index("project_id")
    await db.test_run_groups.create_index([("created_at", -1)])

    # ── v2 추가 컬렉션 ──
    await db.uploaded_documents.create_index("document_id", unique=True)
    await db.uploaded_documents.create_index("project_id")

    await db.test_cases.create_index("test_case_id", unique=True)
    await db.test_cases.create_index("project_id")
    await db.test_cases.create_index("document_id")
    await db.test_cases.create_index("technique")

    # test_runs: test_case_id 인덱스 추가 (v2 실행용)
    await db.test_runs.create_index("test_case_id")

    logger.info("MongoDB 인덱스 생성 완료")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  컬렉션 접근 헬퍼
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_projects_collection():
    return get_db().projects


def get_scenarios_collection():
    return get_db().scenarios


def get_test_runs_collection():
    return get_db().test_runs


def get_test_run_groups_collection():
    return get_db().test_run_groups


# ── v2 추가 ──
def get_documents_collection():
    return get_db().uploaded_documents


def get_test_cases_collection():
    return get_db().test_cases

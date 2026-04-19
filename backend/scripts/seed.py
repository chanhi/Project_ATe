"""
Seed 스크립트
─────────────
팀원들이 바로 테스트할 수 있도록 데모 프로젝트 1개를 생성한다.

실행:
  # 로컬 (venv 활성화 상태)
  cd backend && python scripts/seed.py

  # Docker 환경
  docker compose exec backend python scripts/seed.py

idempotent — 여러 번 실행해도 중복 생성되지 않는다.
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# backend 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.mongo import init_mongo, close_mongo, get_projects_collection
from schemas.schemas import ProjectDoc

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


DEMO_PROJECTS = [
    {
        "project_id": "proj-demo-001",
        "name": "데모 프로젝트 (샘플)",
        "base_url": "https://example.com",
        "description": "팀 테스트용 기본 프로젝트",
    },
    {
        "project_id": "proj-saucedemo",
        "name": "SauceDemo (E2E 샘플)",
        "base_url": "https://www.saucedemo.com",
        "description": "Playwright 공식 E2E 테스트용 데모 사이트",
    },
]


async def seed():
    await init_mongo()
    projects = get_projects_collection()

    logger.info("═" * 50)
    logger.info("  ATe Seed 스크립트 시작")
    logger.info("═" * 50)

    created = 0
    skipped = 0

    for demo in DEMO_PROJECTS:
        existing = await projects.find_one({"project_id": demo["project_id"]})
        if existing:
            logger.info("⏭️  이미 존재: %s (%s)", demo["project_id"], demo["name"])
            skipped += 1
            continue

        doc = ProjectDoc(**demo)
        await projects.insert_one(doc.model_dump())
        logger.info("✅ 생성: %s (%s)", demo["project_id"], demo["name"])
        created += 1

    logger.info("─" * 50)
    logger.info("  완료: 생성 %d건, 스킵 %d건", created, skipped)
    logger.info("═" * 50)
    logger.info("")
    logger.info("팀원들에게 이 project_id로 테스트하라고 전달하세요:")
    for demo in DEMO_PROJECTS:
        logger.info("  - %s : %s", demo["project_id"], demo["base_url"])

    await close_mongo()


if __name__ == "__main__":
    asyncio.run(seed())

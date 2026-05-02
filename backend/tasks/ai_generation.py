"""
AI 생성 Celery Tasks
────────────────────
AI팀 서버 호출은 LLM 응답을 기다려야 해서 5~30초 걸린다.
HTTP 요청 안에서 동기로 처리하면 타임아웃 위험이 크므로 Celery Task로 위임.

진행상황은 기존 WebSocket 인프라(/ws/v1/tests/{job_id}/logs)를 그대로 재사용한다.
job_id가 test_run_id 자리에 들어간다고 보면 된다.

Task 2개:
- generate_test_cases_task   : 자연어/기획서 → 케이스 + Playwright 코드 (신규)
- regenerate_code_task       : 기존 케이스 + 새 URL → 새 Playwright 코드 (재사용)
"""

import json
import logging
from datetime import datetime, timezone

import redis as sync_redis
from pymongo import MongoClient

from core.celery_app import celery_app
from core.config import get_settings
from core.ai_client import (
    AIServiceError,
    call_generate_cases,
    call_regenerate_code,
)

logger = logging.getLogger(__name__)
settings = get_settings()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  공용 유틸
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _get_sync_redis():
    return sync_redis.from_url(settings.REDIS_URL, decode_responses=True)


def _get_sync_mongo():
    client = MongoClient(settings.MONGO_URL)
    return client, client[settings.DB_NAME]


def _publish_progress(r, job_id, level, message, progress):
    """
    진행상황을 Redis Pub/Sub으로 발행한다.
    프론트는 ws://.../ws/v1/tests/{job_id}/logs 로 구독하면 됨.
    """
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        "progress_percentage": progress,
    }
    payload = json.dumps(log_entry, ensure_ascii=False)
    r.publish(f"test_log:{job_id}", payload)
    r.rpush(f"test_log_list:{job_id}", payload)
    r.expire(f"test_log_list:{job_id}", 86400)


def _update_job_status(r, job_id, status, **extra):
    """job 상태를 Redis Hash에 저장 (test_run과 동일한 구조)"""
    key = f"test_run:{job_id}"
    data = {"status": status, "job_type": extra.pop("job_type", "ai_generation")}
    for k, v in extra.items():
        data[k] = str(v)
    r.hset(key, mapping=data)
    r.expire(key, 86400)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Task 1: 신규 케이스 생성 (처음 요청용)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@celery_app.task(
    name="tasks.ai_generation.generate_test_cases_task",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    queue="ai_generation",
)
def generate_test_cases_task(
    self,
    job_id: str,
    placeholder_case_ids: list[str],     # 사전에 만들어둔 빈 케이스 ID들
    project_id: str,
    nl_input: str | None,
    document_id: str | None,
    document_text: str | None,
    target_url: str,
    techniques: list[str],
) -> dict:
    """
    AI팀 서버에 신규 케이스 + Playwright 코드 생성 요청.
    응답을 받아서 사전에 만들어둔 placeholder 케이스에 채워넣는다.
    """
    r = _get_sync_redis()
    mongo_client, db = _get_sync_mongo()

    try:
        _update_job_status(r, job_id, "RUNNING", started_at=datetime.now(timezone.utc).isoformat(),
                          job_type="ai_generation")
        _publish_progress(r, job_id, "INFO", "AI 케이스 생성 요청 시작", 0)

        # 프로젝트 정보 조회
        project = db.projects.find_one({"project_id": project_id})
        project_context = {
            "name": project["name"] if project else "",
            "base_url": project["base_url"] if project else target_url,
        }

        _publish_progress(r, job_id, "INFO",
                         f"AI 서비스 호출 중... ({len(techniques)}개 기법)", 20)

        # AI팀 호출
        try:
            ai_cases = call_generate_cases(
                nl_input=nl_input,
                document_text=document_text,
                target_url=target_url,
                techniques=techniques,
                project_context=project_context,
            )
        except AIServiceError as e:
            _publish_progress(r, job_id, "ERROR", f"AI 서비스 실패: {str(e)}", 100)
            _update_job_status(r, job_id, "FAILED", error_log=str(e))
            raise self.retry(exc=e)

        _publish_progress(r, job_id, "INFO",
                         f"AI 응답 수신 ({len(ai_cases)}개 케이스). DB 저장 중...", 70)

        # 응답 케이스를 사전에 만든 placeholder에 매핑하여 업데이트
        # 케이스 수가 다를 수 있으므로 짝을 맞춤
        updated_count = 0
        for i, ai_case in enumerate(ai_cases):
            if i < len(placeholder_case_ids):
                tc_id = placeholder_case_ids[i]
            else:
                # AI가 더 많이 생성한 경우 → 새 ID 발급
                import uuid
                tc_id = f"tc-{uuid.uuid4().hex[:8]}"
                db.test_cases.insert_one({
                    "test_case_id": tc_id,
                    "project_id": project_id,
                    "document_id": document_id,
                    "target_urls": [target_url],
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                })

            update_fields = {
                "title": ai_case.get("title", "(제목 없음)"),
                "description": ai_case.get("description"),
                "precondition": ai_case.get("precondition"),
                "steps": ai_case.get("steps", []),
                "expected_result": ai_case.get("expected_result"),
                "priority": ai_case.get("priority", "medium"),
                "category": ai_case.get("category"),
                "technique": ai_case.get("technique"),
                "playwright_code": ai_case.get("playwright_code"),
                "updated_at": datetime.now(timezone.utc),
            }
            db.test_cases.update_one(
                {"test_case_id": tc_id},
                {"$set": update_fields},
            )
            updated_count += 1

        # 사용되지 않은 placeholder 정리 (AI가 적게 생성한 경우)
        unused = placeholder_case_ids[len(ai_cases):]
        if unused:
            db.test_cases.delete_many({"test_case_id": {"$in": unused}})
            _publish_progress(r, job_id, "WARN",
                            f"AI가 케이스를 적게 생성하여 {len(unused)}개 placeholder 삭제됨", 85)

        _publish_progress(r, job_id, "SUCCESS",
                         f"✅ {updated_count}개 케이스 생성 완료", 100)
        _update_job_status(r, job_id, "SUCCESS",
                          ended_at=datetime.now(timezone.utc).isoformat(),
                          generated_count=updated_count)

        return {
            "job_id": job_id,
            "status": "SUCCESS",
            "generated_test_case_ids": placeholder_case_ids[:len(ai_cases)],
            "count": updated_count,
        }

    except Exception as exc:
        logger.exception("AI 생성 실패: job_id=%s", job_id)
        _publish_progress(r, job_id, "ERROR", f"내부 에러: {str(exc)}", 100)
        _update_job_status(r, job_id, "FAILED", error_log=str(exc),
                          ended_at=datetime.now(timezone.utc).isoformat())
        raise self.retry(exc=exc)
    finally:
        mongo_client.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Task 2: 재사용용 코드 재생성
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@celery_app.task(
    name="tasks.ai_generation.regenerate_code_task",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    queue="ai_generation",
)
def regenerate_code_task(
    self,
    job_id: str,
    test_case_id: str,
    new_target_url: str,
) -> dict:
    """
    기존 테스트 케이스를 새 URL용 Playwright 코드로 재생성.

    동작:
    1. test_case 조회 (steps + 메타정보)
    2. AI팀에게 새 URL용 코드 재생성 요청
    3. 결과를 새 형태로 저장 — 기존 케이스의 target_urls에 추가하고
       playwright_code는 URL별로 보존하기 위해 별도 컬렉션 또는 dict 구조 사용
    """
    r = _get_sync_redis()
    mongo_client, db = _get_sync_mongo()

    try:
        _update_job_status(r, job_id, "RUNNING",
                          started_at=datetime.now(timezone.utc).isoformat(),
                          job_type="ai_regeneration")
        _publish_progress(r, job_id, "INFO", "재생성 요청 시작", 0)

        # 기존 케이스 조회
        tc = db.test_cases.find_one({"test_case_id": test_case_id})
        if not tc:
            raise ValueError(f"테스트 케이스 없음: {test_case_id}")

        old_url = tc.get("target_urls", [None])[0] if tc.get("target_urls") else None

        _publish_progress(r, job_id, "INFO",
                         f"AI 재생성 호출 중... ({old_url} → {new_target_url})", 30)

        # AI팀 호출
        try:
            result = call_regenerate_code(
                test_case={
                    "title": tc.get("title"),
                    "steps": tc.get("steps", []),
                    "expected_result": tc.get("expected_result"),
                    "playwright_code": tc.get("playwright_code"),
                },
                new_target_url=new_target_url,
                old_target_url=old_url,
            )
        except AIServiceError as e:
            _publish_progress(r, job_id, "ERROR", f"AI 재생성 실패: {str(e)}", 100)
            _update_job_status(r, job_id, "FAILED", error_log=str(e))
            raise self.retry(exc=e)

        _publish_progress(r, job_id, "INFO", "재생성 완료. URL별 코드 저장 중...", 80)

        # URL별 Playwright 코드를 저장
        # 구조: playwright_code_per_url = { "https://shopA.com": "...", "https://shopB.com": "..." }
        url_codes = tc.get("playwright_code_per_url", {})
        if not url_codes and tc.get("playwright_code") and old_url:
            # 처음 재생성하는 경우 기존 코드를 url_codes로 옮김
            url_codes[old_url] = tc["playwright_code"]
        url_codes[new_target_url] = result["playwright_code"]

        # target_urls 갱신
        target_urls = list(set(tc.get("target_urls", []) + [new_target_url]))

        db.test_cases.update_one(
            {"test_case_id": test_case_id},
            {"$set": {
                "playwright_code_per_url": url_codes,
                "target_urls": target_urls,
                "updated_at": datetime.now(timezone.utc),
            }},
        )

        _publish_progress(r, job_id, "SUCCESS", "✅ 재생성 완료", 100)
        _update_job_status(r, job_id, "SUCCESS",
                          ended_at=datetime.now(timezone.utc).isoformat(),
                          test_case_id=test_case_id,
                          new_target_url=new_target_url)

        return {
            "job_id": job_id,
            "status": "SUCCESS",
            "test_case_id": test_case_id,
            "new_target_url": new_target_url,
            "notes": result.get("notes"),
        }

    except Exception as exc:
        logger.exception("재생성 실패: job_id=%s", job_id)
        _publish_progress(r, job_id, "ERROR", f"내부 에러: {str(exc)}", 100)
        _update_job_status(r, job_id, "FAILED", error_log=str(exc),
                          ended_at=datetime.now(timezone.utc).isoformat())
        raise self.retry(exc=exc)
    finally:
        mongo_client.close()

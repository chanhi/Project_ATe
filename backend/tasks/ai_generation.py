"""
AI 생성 Celery Tasks
────────────────────
자연어/기획서 입력을 받아 OpenAI 기반 ATEAiEngine으로
테스트 케이스와 Playwright 코드를 생성한다.
"""

import json
import logging
import asyncio
from datetime import datetime, timezone

import redis as sync_redis
from pymongo import MongoClient

from core.celery_app import celery_app
from core.config import get_settings
from core.ai_engine2 import ATEAiEngine

logger = logging.getLogger(__name__)
settings = get_settings()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 공용 유틸
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _get_sync_redis():
    return sync_redis.from_url(settings.REDIS_URL, decode_responses=True)


def _get_sync_mongo():
    client = MongoClient(settings.MONGO_URL)
    return client, client[settings.DB_NAME]


def _publish_progress(r, job_id, level, message, progress):
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
    key = f"test_run:{job_id}"

    data = {
        "status": status,
        "job_type": extra.pop("job_type", "ai_generation"),
    }

    for k, v in extra.items():
        data[k] = str(v)

    r.hset(key, mapping=data)
    r.expire(key, 86400)


def _safe_async_run(coro):
    """
    Celery sync task 안에서 async 함수를 안전하게 실행하기 위한 헬퍼.
    """
    try:
        loop = asyncio.get_event_loop()

        if loop.is_running():
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()

        return loop.run_until_complete(coro)

    except RuntimeError:
        return asyncio.run(coro)


def _build_ai_case(
    ai_result: dict,
    technique: str,
    nl_input: str | None,
    target_url: str,
):
    generated_code = ai_result.get("generated_code", "")

    validation = ai_result.get("ai_validation", {})
    status = validation.get("status", "UNKNOWN")

    title = f"[{technique}] AI 생성 테스트"

    description = (
        f"기법: {technique} | 입력 요약: {nl_input or ''}"
    )

    return {
        "title": title,
        "description": description,
        "precondition": f"대상 URL에 접속 가능해야 함: {target_url}",
        "steps": [
            {
                "order": 1,
                "action": "goto",
                "target": target_url,
                "value": "",
            },
            {
                "order": 2,
                "action": "ai_generated",
                "target": "playwright_code",
                "value": "AI가 생성한 Playwright 코드 실행",
            },
        ],
        "expected_result": "AI가 생성한 Playwright 테스트 코드가 정상 생성되어야 함",
        "priority": "medium",
        "category": "ai_generated",
        "technique": technique,
        "playwright_code": generated_code,
        "ai_validation": validation,
        "status": status,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Task 1: 신규 케이스 생성
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
    placeholder_case_ids: list[str],
    project_id: str,
    nl_input: str | None,
    document_id: str | None,
    document_text: str | None,
    target_url: str,
    techniques: list[str],
) -> dict:
    r = _get_sync_redis()
    mongo_client, db = _get_sync_mongo()

    try:
        _update_job_status(
            r,
            job_id,
            "RUNNING",
            started_at=datetime.now(timezone.utc).isoformat(),
            job_type="ai_generation",
        )
        _publish_progress(r, job_id, "INFO", "AI 케이스 생성 요청 시작", 0)

        project = db.projects.find_one({"project_id": project_id})
        base_url = target_url or (project.get("base_url") if project else "")

        prompt_source = nl_input or document_text or ""
        if not prompt_source.strip():
            raise ValueError("자연어 입력 또는 문서 텍스트가 비어 있습니다.")

        if not techniques:
            techniques = ["scenario_based"]

        _publish_progress(
            r,
            job_id,
            "INFO",
            f"OpenAI 기반 AI 엔진 호출 중... ({len(techniques)}개 기법)",
            20,
        )

        engine = ATEAiEngine()
        ai_cases = []

        for idx, technique in enumerate(techniques):
            ai_result = _safe_async_run(
                engine.generate_playwright_test(
                    project_id=project_id,
                    base_url=base_url,
                    nl_prompt=prompt_source,
                    technique=technique,
                )
            )

            validation = ai_result.get("ai_validation", {})
            if not validation.get("is_valid"):
                raise RuntimeError(
                    validation.get("message", "AI 테스트 코드 생성 실패")
                )

            ai_case = _build_ai_case(
                ai_result=ai_result,
                technique=technique,
                nl_input=nl_input,
                target_url=base_url,
            )
            ai_cases.append(ai_case)

            progress = 20 + int(((idx + 1) / len(techniques)) * 45)
            _publish_progress(
                r,
                job_id,
                "INFO",
                f"{technique} 기법 테스트 생성 완료",
                progress,
            )

        _publish_progress(
            r,
            job_id,
            "INFO",
            f"AI 응답 수신 ({len(ai_cases)}개 케이스). DB 저장 중...",
            70,
        )

        updated_count = 0
        generated_ids = []

        for i, ai_case in enumerate(ai_cases):
            if i < len(placeholder_case_ids):
                tc_id = placeholder_case_ids[i]
            else:
                import uuid

                tc_id = f"tc-{uuid.uuid4().hex[:8]}"
                db.test_cases.insert_one(
                    {
                        "test_case_id": tc_id,
                        "project_id": project_id,
                        "document_id": document_id,
                        "target_urls": [base_url],
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                )

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
                "ai_validation": ai_case.get("ai_validation"),
                "target_urls": [base_url],
                "updated_at": datetime.now(timezone.utc),
            }

            db.test_cases.update_one(
                {"test_case_id": tc_id},
                {"$set": update_fields},
            )

            generated_ids.append(tc_id)
            updated_count += 1

        unused = placeholder_case_ids[len(ai_cases):]
        if unused:
            db.test_cases.delete_many({"test_case_id": {"$in": unused}})
            _publish_progress(
                r,
                job_id,
                "WARN",
                f"AI가 케이스를 적게 생성하여 {len(unused)}개 placeholder 삭제됨",
                85,
            )

        _publish_progress(
            r,
            job_id,
            "SUCCESS",
            f"✅ {updated_count}개 케이스 생성 완료",
            100,
        )

        _update_job_status(
            r,
            job_id,
            "SUCCESS",
            ended_at=datetime.now(timezone.utc).isoformat(),
            generated_count=updated_count,
            generated_test_case_ids=json.dumps(generated_ids),
        )

        return {
            "job_id": job_id,
            "status": "SUCCESS",
            "generated_test_case_ids": generated_ids,
            "count": updated_count,
        }

    except Exception as exc:
        logger.exception("AI 생성 실패: job_id=%s", job_id)

        _publish_progress(
            r,
            job_id,
            "ERROR",
            f"내부 에러: {str(exc)}",
            100,
        )

        _update_job_status(
            r,
            job_id,
            "FAILED",
            error_log=str(exc),
            ended_at=datetime.now(timezone.utc).isoformat(),
        )

        raise self.retry(exc=exc)

    finally:
        mongo_client.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Task 2: 코드 재생성
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
    r = _get_sync_redis()
    mongo_client, db = _get_sync_mongo()

    try:
        _update_job_status(
            r,
            job_id,
            "RUNNING",
            started_at=datetime.now(timezone.utc).isoformat(),
            job_type="ai_regeneration",
        )
        _publish_progress(r, job_id, "INFO", "재생성 요청 시작", 0)

        tc = db.test_cases.find_one({"test_case_id": test_case_id})
        if not tc:
            raise ValueError(f"테스트 케이스 없음: {test_case_id}")

        old_url = tc.get("target_urls", [None])[0] if tc.get("target_urls") else None

        _publish_progress(
            r,
            job_id,
            "INFO",
            f"AI 재생성 호출 중... ({old_url} → {new_target_url})",
            30,
        )

        engine = ATEAiEngine()

        original_code = tc.get("playwright_code") or ""
        prompt = (
            f"다음 기존 테스트 케이스를 새 URL에 맞게 Playwright 코드로 재생성해줘.\n"
            f"제목: {tc.get('title')}\n"
            f"설명: {tc.get('description')}\n"
            f"기존 URL: {old_url}\n"
            f"새 URL: {new_target_url}\n"
            f"기존 코드:\n{original_code}"
        )

        ai_result = _safe_async_run(
            engine.generate_playwright_test(
                project_id=tc.get("project_id", ""),
                base_url=new_target_url,
                nl_prompt=prompt,
                technique=tc.get("technique", "scenario_based"),
            )
        )

        validation = ai_result.get("ai_validation", {})
        if not validation.get("is_valid"):
            raise RuntimeError(validation.get("message", "AI 재생성 실패"))

        new_code = ai_result.get("generated_code", "")

        _publish_progress(r, job_id, "INFO", "재생성 완료. URL별 코드 저장 중...", 80)

        url_codes = tc.get("playwright_code_per_url", {})
        if not url_codes and original_code and old_url:
            url_codes[old_url] = original_code

        url_codes[new_target_url] = new_code

        target_urls = list(set(tc.get("target_urls", []) + [new_target_url]))

        db.test_cases.update_one(
            {"test_case_id": test_case_id},
            {
                "$set": {
                    "playwright_code": new_code,
                    "playwright_code_per_url": url_codes,
                    "target_urls": target_urls,
                    "ai_validation": validation,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

        _publish_progress(r, job_id, "SUCCESS", "✅ 재생성 완료", 100)

        _update_job_status(
            r,
            job_id,
            "SUCCESS",
            ended_at=datetime.now(timezone.utc).isoformat(),
            test_case_id=test_case_id,
            new_target_url=new_target_url,
        )

        return {
            "job_id": job_id,
            "status": "SUCCESS",
            "test_case_id": test_case_id,
            "new_target_url": new_target_url,
        }

    except Exception as exc:
        logger.exception("재생성 실패: job_id=%s", job_id)

        _publish_progress(
            r,
            job_id,
            "ERROR",
            f"내부 에러: {str(exc)}",
            100,
        )

        _update_job_status(
            r,
            job_id,
            "FAILED",
            error_log=str(exc),
            ended_at=datetime.now(timezone.utc).isoformat(),
        )

        raise self.retry(exc=exc)

    finally:
        mongo_client.close()
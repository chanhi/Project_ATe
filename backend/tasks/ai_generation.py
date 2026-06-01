"""
AI 생성 Celery Tasks (v2 - 배치 생성 + 부분 결과 처리)
"""

import json
import logging
import asyncio
import uuid
from datetime import datetime, timezone

import redis as sync_redis
from pymongo import MongoClient

from core.celery_app import celery_app
from core.config import get_settings
from core.ai_engine2 import ATEAiEngine

logger = logging.getLogger(__name__)
settings = get_settings()


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
    data = {"status": status, "job_type": extra.pop("job_type", "ai_generation")}
    for k, v in extra.items():
        data[k] = str(v)
    r.hset(key, mapping=data)
    r.expire(key, 86400)


def _safe_async_run(coro):
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Task 1: 배치 케이스 생성
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
    requested_count: int = 5,  # 새 파라미터 (기본값으로 호환성 유지)
) -> dict:
    """자연어 한 번 → 여러 테스트 케이스 일괄 생성"""
    r = _get_sync_redis()
    mongo_client, db = _get_sync_mongo()

    try:
        _update_job_status(
            r, job_id, "RUNNING",
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

        _publish_progress(r, job_id, "INFO", f"OpenAI 호출 중 ({requested_count}개 요청)", 20)

        # ── AI 배치 호출 ──
        engine = ATEAiEngine()
        ai_result = _safe_async_run(
            engine.generate_test_case_batch(
                project_id=project_id,
                base_url=base_url,
                nl_prompt=prompt_source,
                techniques=techniques,
                requested_count=requested_count,
            )
        )

        validation = ai_result.get("ai_validation", {})
        if not validation.get("is_valid"):
            raise RuntimeError(validation.get("message", "AI 테스트 케이스 생성 실패"))

        ai_test_cases = ai_result.get("test_cases", [])
        gen_count = ai_result.get("generated_count", len(ai_test_cases))
        req_count = ai_result.get("requested_count", requested_count)
        is_partial = ai_result.get("is_partial", False)

        if not ai_test_cases:
            raise RuntimeError("AI가 유효한 케이스를 하나도 생성하지 못했습니다.")

        # 부분 생성 시 사용자에게 알림
        if is_partial:
            _publish_progress(
                r, job_id, "WARN",
                f"⚠️ 요청한 {req_count}개 중 {gen_count}개만 생성되었습니다.",
                65,
            )
        else:
            _publish_progress(
                r, job_id, "INFO",
                f"✅ {gen_count}개 케이스 생성 성공. DB 저장 중...",
                70,
            )

        # ── 기존 케이스 수 (TC 번호용) ──
        existing_count = db.test_cases.count_documents({"project_id": project_id})

        # ── 케이스 저장 ──
        generated_ids = []
        for i, ai_case in enumerate(ai_test_cases):
            if i < len(placeholder_case_ids):
                tc_id = placeholder_case_ids[i]
                is_new = False
            else:
                tc_id = f"tc-{uuid.uuid4().hex[:8]}"
                is_new = True

            tc_number = existing_count + i + 1
            tc_display_id = f"TC-{tc_number:03d}"

            doc_fields = {
                "test_case_id": tc_id,
                "tc_display_id": tc_display_id,
                "project_id": project_id,
                "document_id": document_id,
                "title": ai_case.get("title", "(제목 없음)"),
                "description": ai_case.get("description", ""),
                "precondition": ai_case.get("precondition", ""),
                "steps": ai_case.get("steps", []),
                "expected_result": ai_case.get("expected_result", ""),
                "priority": ai_case.get("priority", "medium"),
                "category": ai_case.get("category", ""),
                "technique": ai_case.get("technique", techniques[0]),
                "playwright_code": ai_case.get("playwright_code", ""),
                "ai_validation": validation,
                "target_urls": [base_url],
                "updated_at": datetime.now(timezone.utc),
            }

            if is_new:
                doc_fields["created_at"] = datetime.now(timezone.utc)
                db.test_cases.insert_one(doc_fields)
            else:
                db.test_cases.update_one(
                    {"test_case_id": tc_id},
                    {"$set": doc_fields},
                )

            generated_ids.append(tc_id)

        # ── 남은 placeholder 삭제 ──
        unused = placeholder_case_ids[len(ai_test_cases):]
        if unused:
            db.test_cases.delete_many({"test_case_id": {"$in": unused}})

        # ── 최종 메시지 ──
        if is_partial:
            final_msg = f"⚠️ 테스트 케이스 중 일부({gen_count}/{req_count})만 생성되었습니다."
            final_level = "WARN"
        else:
            final_msg = f"✅ {gen_count}개 케이스 생성 완료"
            final_level = "SUCCESS"

        _publish_progress(r, job_id, final_level, final_msg, 100)

        _update_job_status(
            r, job_id, "SUCCESS",
            ended_at=datetime.now(timezone.utc).isoformat(),
            generated_count=gen_count,
            requested_count=req_count,
            is_partial=is_partial,
            generated_test_case_ids=json.dumps(generated_ids),
        )

        return {
            "job_id": job_id,
            "status": "SUCCESS",
            "generated_test_case_ids": generated_ids,
            "count": gen_count,
            "requested": req_count,
            "is_partial": is_partial,
            "message": final_msg,
        }

    except Exception as exc:
        logger.exception("AI 생성 실패: job_id=%s", job_id)
        _publish_progress(r, job_id, "ERROR", f"내부 에러: {str(exc)}", 100)
        _update_job_status(
            r, job_id, "FAILED",
            error_log=str(exc),
            ended_at=datetime.now(timezone.utc).isoformat(),
        )
        raise self.retry(exc=exc)
    finally:
        mongo_client.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Task 2: 코드 재생성 (기존 유지)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@celery_app.task(
    name="tasks.ai_generation.regenerate_code_task",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    queue="ai_generation",
)
def regenerate_code_task(self, job_id: str, test_case_id: str, new_target_url: str) -> dict:
    r = _get_sync_redis()
    mongo_client, db = _get_sync_mongo()

    try:
        _update_job_status(r, job_id, "RUNNING",
                          started_at=datetime.now(timezone.utc).isoformat(),
                          job_type="ai_regeneration")
        _publish_progress(r, job_id, "INFO", "재생성 요청 시작", 0)

        tc = db.test_cases.find_one({"test_case_id": test_case_id})
        if not tc:
            raise ValueError(f"테스트 케이스 없음: {test_case_id}")

        old_url = tc.get("target_urls", [None])[0] if tc.get("target_urls") else None
        _publish_progress(r, job_id, "INFO", f"AI 재생성 중 ({old_url} → {new_target_url})", 30)

        engine = ATEAiEngine()
        original_code = tc.get("playwright_code") or ""
        prompt = (
            f"다음 기존 테스트 케이스를 새 URL에 맞게 Playwright 코드로 재생성해줘.\n"
            f"제목: {tc.get('title')}\n설명: {tc.get('description')}\n"
            f"기존 URL: {old_url}\n새 URL: {new_target_url}\n"
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
        _publish_progress(r, job_id, "INFO", "재생성 완료. 저장 중...", 80)

        url_codes = tc.get("playwright_code_per_url", {})
        if not url_codes and original_code and old_url:
            url_codes[old_url] = original_code
        url_codes[new_target_url] = new_code

        target_urls = list(set(tc.get("target_urls", []) + [new_target_url]))

        db.test_cases.update_one(
            {"test_case_id": test_case_id},
            {"$set": {
                "playwright_code": new_code,
                "playwright_code_per_url": url_codes,
                "target_urls": target_urls,
                "ai_validation": validation,
                "updated_at": datetime.now(timezone.utc),
            }},
        )

        _publish_progress(r, job_id, "SUCCESS", "✅ 재생성 완료", 100)
        _update_job_status(r, job_id, "SUCCESS",
                          ended_at=datetime.now(timezone.utc).isoformat(),
                          test_case_id=test_case_id,
                          new_target_url=new_target_url)

        return {"job_id": job_id, "status": "SUCCESS", "test_case_id": test_case_id}

    except Exception as exc:
        logger.exception("재생성 실패: job_id=%s", job_id)
        _publish_progress(r, job_id, "ERROR", f"내부 에러: {str(exc)}", 100)
        _update_job_status(r, job_id, "FAILED",
                          error_log=str(exc),
                          ended_at=datetime.now(timezone.utc).isoformat())
        raise self.retry(exc=exc)
    finally:
        mongo_client.close()
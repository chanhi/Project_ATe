"""
AI 작업 API
───────────
POST /ai/regenerate-code     → 다른 URL용 Playwright 코드 재생성 (비동기)
GET  /ai/jobs/{job_id}       → AI 작업 상태 조회
GET  /ai/health              → AI 서비스 헬스체크
"""

import uuid

from fastapi import APIRouter, HTTPException

from core.ai_client import health_check as ai_health_check
from core.mongo import get_test_cases_collection
from core.redis_client import set_test_run_status, get_test_run_status
from schemas.schemas import (
    APIResponse,
    AIGenerationJobResponse,
    AIRegenerateRequest,
)
from tasks.ai_generation import regenerate_code_task

router = APIRouter(prefix="/ai", tags=["AI Generation"])


@router.post(
    "/regenerate-code",
    response_model=APIResponse,
    status_code=202,
    summary="다른 URL용 Playwright 코드 재생성 (재사용)",
)
async def regenerate_code(request: AIRegenerateRequest):
    """
    기존 테스트 케이스를 새 URL용 Playwright 코드로 재생성.

    동작:
    1. test_case_id 존재 확인
    2. job_id 발급
    3. Celery Task 큐 등록
    4. 즉시 202 반환 (진행상황은 WebSocket으로 구독)

    완료 시 test_case의 `playwright_code_per_url` 필드에 URL별 코드 저장:
    ```json
    {
      "playwright_code_per_url": {
        "https://shopA.com": "...",
        "https://shopB.com": "..."  ← 새로 추가됨
      }
    }
    ```
    """
    test_cases = get_test_cases_collection()

    # ── 케이스 존재 확인 ──
    tc = await test_cases.find_one({"test_case_id": request.test_case_id})
    if not tc:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "message": f"테스트 케이스를 찾을 수 없습니다: {request.test_case_id}",
                "error_code": "TEST_CASE_NOT_FOUND",
            },
        )

    if not tc.get("steps"):
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": "재생성할 steps가 없습니다. 먼저 케이스 내용을 채우세요.",
                "error_code": "NO_STEPS",
            },
        )

    # ── job_id 발급 + Celery Task 등록 ──
    job_id = f"aijob-{uuid.uuid4().hex[:8]}"
    await set_test_run_status(job_id, "QUEUED", job_type="ai_regeneration")

    task = regenerate_code_task.apply_async(
        args=[job_id, request.test_case_id, request.new_target_url],
        queue="ai_generation",
    )

    return APIResponse(
        status="success",
        data=AIGenerationJobResponse(
            job_id=job_id,
            status="QUEUED",
            celery_task_id=task.id,
            placeholder_test_case_ids=[request.test_case_id],
            ws_url=f"/ws/v1/tests/{job_id}/logs",
        ).model_dump(),
        message="재생성 작업이 큐에 등록되었습니다. WebSocket으로 진행상황을 수신하세요.",
    )


@router.get(
    "/jobs/{job_id}",
    response_model=APIResponse,
    summary="AI 작업 진행 상태 조회",
)
async def get_ai_job_status(job_id: str):
    """
    AI 작업(생성 또는 재생성)의 현재 상태를 조회한다.

    상태값: QUEUED | RUNNING | SUCCESS | FAILED
    """
    cached = await get_test_run_status(job_id)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "message": f"AI 작업을 찾을 수 없습니다: {job_id}",
                "error_code": "JOB_NOT_FOUND",
            },
        )

    return APIResponse(
        status="success",
        data={
            "job_id": job_id,
            "status": cached.get("status", "UNKNOWN"),
            "job_type": cached.get("job_type"),
            "started_at": cached.get("started_at"),
            "ended_at": cached.get("ended_at"),
            "error_log": cached.get("error_log"),
            "extra": {
                k: v for k, v in cached.items()
                if k not in {"status", "job_type", "started_at", "ended_at", "error_log"}
            },
        },
    )


@router.get(
    "/health",
    response_model=APIResponse,
    summary="AI 서비스 헬스체크",
)
async def get_ai_health():
    """AI 서비스(별도 FastAPI 서버) 연결 상태를 확인한다."""
    healthy = ai_health_check()
    return APIResponse(
        status="success",
        data={
            "ai_service_healthy": healthy,
        },
        message="AI 서비스 연결됨" if healthy else "AI 서비스 미연결 또는 mock 모드",
    )

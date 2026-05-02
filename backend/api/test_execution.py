"""
테스트 실행 API (§3 Test Execution)
───────────────────────────────────
POST /tests/run       → 시나리오 ID 기반 비동기 실행 요청
POST /tests/execute   → DB 없이 즉시 실행 (Step DSL 또는 raw code)
GET  /tests/{id}      → 결과 단건 조회
GET  /tests           → 실행 목록 조회
POST /tests/{id}/cancel → 실행 중인 테스트 취소
"""

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.mongo import (
    get_scenarios_collection,
    get_projects_collection,
    get_test_runs_collection,
)
from core.redis_client import get_test_run_status, set_test_run_status
from core.step_compiler import compile_steps_to_playwright, validate_steps
from schemas.schemas import (
    APIResponse,
    TestRunDoc,
    TestRunRequest,
    TestRunResponse,
    TestRunStatusResponse,
)
from tasks.test_runner import execute_test

router = APIRouter(prefix="/tests", tags=["Test Execution"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /tests/execute 전용 스키마
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestStep(BaseModel):
    """단일 테스트 스텝 (Step DSL)"""
    action: str = Field(
        ...,
        json_schema_extra={"example": "fill"},
        description="goto | fill | click | type | press | wait | wait_for | assert_text | assert_url | assert_visible | screenshot",
    )
    target: str | None = Field(
        None,
        json_schema_extra={"example": "#username"},
        description="셀렉터 (id/class/css/xpath)",
    )
    value: str | None = Field(
        None,
        json_schema_extra={"example": "admin"},
    )


class TestExecuteRequest(BaseModel):
    """/tests/execute 요청 — DB 거치지 않고 즉시 실행"""
    url: str = Field(..., json_schema_extra={"example": "http://localhost:3000/login"})
    # 두 가지 방식 중 하나
    steps: list[TestStep] | None = Field(
        None,
        description="Step DSL 방식 (프론트/AI팀 권장)",
    )
    generated_code: str | None = Field(
        None,
        description="Playwright 코드를 직접 넘기는 방식",
    )
    title: str = Field(
        default="Adhoc Test",
        json_schema_extra={"example": "로그인 즉시 실행"},
    )


@router.post(
    "/run",
    response_model=APIResponse,
    status_code=202,
    summary="테스트 실행 요청 (비동기)",
)
async def run_test(request: TestRunRequest):
    """
    API 명세서 §3.1

    1. 시나리오 조회
    2. test_run_id 생성
    3. MongoDB에 TestRun 저장 (status=QUEUED)
    4. Redis에 상태 캐시
    5. Celery Task 큐 등록
    6. 202 Accepted 반환
    """
    scenarios = get_scenarios_collection()
    projects = get_projects_collection()
    test_runs = get_test_runs_collection()

    # ── 시나리오 조회 ──
    scenario = await scenarios.find_one({"scenario_id": request.scenario_id})
    if not scenario:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "message": f"시나리오를 찾을 수 없습니다: {request.scenario_id}",
                "error_code": "SCENARIO_NOT_FOUND",
            },
        )

    if not scenario.get("generated_code"):
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": "테스트 코드가 아직 생성되지 않았습니다.",
                "error_code": "CODE_NOT_GENERATED",
            },
        )

    # ── 프로젝트 base_url 조회 ──
    project = await projects.find_one({"project_id": scenario["project_id"]})
    base_url = project["base_url"] if project else "http://localhost:3000"

    # ── TestRun 생성 ──
    test_run_id = f"run-{uuid.uuid4().hex[:8]}"

    test_run_doc = TestRunDoc(
        test_run_id=test_run_id,
        scenario_id=scenario["scenario_id"],
        status="QUEUED",
    )
    await test_runs.insert_one(test_run_doc.model_dump())

    # ── Redis 상태 캐시 ──
    await set_test_run_status(test_run_id, "QUEUED")

    # ── Celery Task 큐 등록 ──
    task = execute_test.apply_async(
        args=[test_run_id, scenario["scenario_id"], scenario["generated_code"], base_url],
        queue="test_execution",
    )

    # celery_task_id 업데이트
    await test_runs.update_one(
        {"test_run_id": test_run_id},
        {"$set": {"celery_task_id": task.id}},
    )

    return APIResponse(
        status="success",
        data=TestRunResponse(
            test_run_id=test_run_id,
            status="QUEUED",
            celery_task_id=task.id,
        ).model_dump(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /tests/execute — DB 거치지 않는 즉시 실행
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post(
    "/execute",
    response_model=APIResponse,
    status_code=202,
    summary="테스트 즉시 실행 (DB 우회, 프론트/AI팀 직결용)",
)
async def execute_test_adhoc(request: TestExecuteRequest):
    """
    시나리오를 DB에 등록하지 않고 바로 테스트를 실행한다.

    두 가지 입력 방식을 지원한다:

    **방식 1: Step DSL (프론트/AI팀 권장)**
    ```json
    {
      "url": "http://localhost:3000/login",
      "steps": [
        {"action": "fill", "target": "#username", "value": "admin"},
        {"action": "fill", "target": "#password", "value": "1234"},
        {"action": "click", "target": "button[type=submit]"},
        {"action": "assert_url", "value": "/dashboard"}
      ]
    }
    ```

    **방식 2: 생성된 Playwright 코드 직접 넘기기**
    ```json
    {
      "url": "http://localhost:3000",
      "generated_code": "import { test, expect } from '@playwright/test';\\ntest('...', async ({ page }) => { ... });"
    }
    ```

    실행 결과는 `/tests/{test_run_id}`로 조회하거나
    WebSocket `/ws/v1/tests/{test_run_id}/logs`로 실시간 수신할 수 있다.
    """
    # ── 입력 검증 ──
    if not request.steps and not request.generated_code:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": "steps 또는 generated_code 중 하나는 필수입니다.",
                "error_code": "MISSING_INPUT",
            },
        )

    # ── 코드 결정 ──
    if request.generated_code:
        final_code = request.generated_code
    else:
        # Step DSL 유효성 검증
        steps_raw = [s.model_dump() for s in request.steps]
        is_valid, err = validate_steps(steps_raw)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": f"Step 유효성 검증 실패: {err}",
                    "error_code": "INVALID_STEPS",
                },
            )

        # Playwright 코드 컴파일
        final_code = compile_steps_to_playwright(
            url=request.url,
            steps=steps_raw,
            test_name=request.title,
        )

    # ── test_run_id 생성 (scenario_id 없이) ──
    test_run_id = f"run-{uuid.uuid4().hex[:8]}"
    adhoc_scenario_id = f"adhoc-{uuid.uuid4().hex[:8]}"

    # ── test_runs 컬렉션에 기록 (추적용) ──
    test_runs = get_test_runs_collection()
    test_run_doc = TestRunDoc(
        test_run_id=test_run_id,
        scenario_id=adhoc_scenario_id,  # adhoc 표시
        status="QUEUED",
    )
    await test_runs.insert_one(test_run_doc.model_dump())

    # ── Redis 상태 캐시 ──
    await set_test_run_status(test_run_id, "QUEUED")

    # ── Celery Task 등록 ──
    task = execute_test.apply_async(
        args=[test_run_id, adhoc_scenario_id, final_code, request.url],
        queue="test_execution",
    )
    await test_runs.update_one(
        {"test_run_id": test_run_id},
        {"$set": {"celery_task_id": task.id}},
    )

    return APIResponse(
        status="success",
        data={
            "test_run_id": test_run_id,
            "status": "QUEUED",
            "celery_task_id": task.id,
            "adhoc_scenario_id": adhoc_scenario_id,
            "generated_code": final_code,
            "ws_url": f"/ws/v1/tests/{test_run_id}/logs",
        },
        message="테스트가 큐에 등록되었습니다. WebSocket으로 실시간 로그를 수신하세요.",
    )


@router.get("/{test_run_id}", response_model=APIResponse, summary="테스트 실행 결과 단건 조회")
async def get_test_run(test_run_id: str):
    """API 명세서 §3.2 — Redis 캐시 우선, 없으면 MongoDB"""
    # ── Redis 우선 ──
    cached = await get_test_run_status(test_run_id)
    if cached:
        return APIResponse(
            status="success",
            data={
                "test_run_id": test_run_id,
                "status": cached.get("status", "UNKNOWN"),
                "started_at": cached.get("started_at"),
                "ended_at": cached.get("ended_at"),
                "duration_ms": int(cached["duration_ms"]) if cached.get("duration_ms") else None,
                "error_log": cached.get("error_log"),
            },
        )

    # ── MongoDB 폴백 ──
    test_runs = get_test_runs_collection()
    doc = await test_runs.find_one({"test_run_id": test_run_id})

    if not doc:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "message": f"테스트 실행을 찾을 수 없습니다: {test_run_id}",
                "error_code": "TEST_RUN_NOT_FOUND",
            },
        )

    return APIResponse(
        status="success",
        data={
            "test_run_id": doc["test_run_id"],
            "scenario_id": doc["scenario_id"],
            "status": doc["status"],
            "started_at": doc.get("started_at").isoformat() if doc.get("started_at") else None,
            "ended_at": doc.get("ended_at").isoformat() if doc.get("ended_at") else None,
            "duration_ms": doc.get("duration_ms"),
            "error_log": doc.get("error_log"),
            "allure_report_url": doc.get("allure_report_url"),
        },
    )


@router.get("", response_model=APIResponse, summary="테스트 실행 목록 조회")
async def list_test_runs(
    scenario_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    test_runs = get_test_runs_collection()
    query = {}
    if scenario_id:
        query["scenario_id"] = scenario_id
    if status:
        query["status"] = status

    cursor = test_runs.find(query).sort("created_at", -1).skip(offset).limit(limit)
    docs = await cursor.to_list(length=limit)

    return APIResponse(
        status="success",
        data=[
            {
                "test_run_id": d["test_run_id"],
                "scenario_id": d["scenario_id"],
                "status": d["status"],
                "started_at": d.get("started_at").isoformat() if d.get("started_at") else None,
                "ended_at": d.get("ended_at").isoformat() if d.get("ended_at") else None,
                "duration_ms": d.get("duration_ms"),
                "created_at": d.get("created_at").isoformat() if d.get("created_at") else None,
            }
            for d in docs
        ],
    )


@router.post("/{test_run_id}/cancel", response_model=APIResponse, summary="테스트 실행 취소")
async def cancel_test_run(test_run_id: str):
    test_runs = get_test_runs_collection()
    doc = await test_runs.find_one({"test_run_id": test_run_id})

    if not doc:
        raise HTTPException(status_code=404, detail="테스트 실행을 찾을 수 없습니다.")

    if doc["status"] in ("SUCCESS", "FAILED"):
        raise HTTPException(status_code=400, detail="이미 완료된 테스트는 취소할 수 없습니다.")

    # Celery Task 취소
    if doc.get("celery_task_id"):
        from core.celery_app import celery_app
        celery_app.control.revoke(doc["celery_task_id"], terminate=True, signal="SIGTERM")

    # 상태 업데이트
    ended_at = datetime.now(timezone.utc)
    await test_runs.update_one(
        {"test_run_id": test_run_id},
        {"$set": {
            "status": "FAILED",
            "error_log": "사용자에 의해 취소됨",
            "ended_at": ended_at,
        }},
    )
    await set_test_run_status(
        test_run_id, "FAILED",
        error_log="사용자에 의해 취소됨",
        ended_at=ended_at.isoformat(),
    )

    return APIResponse(
        status="success",
        data={"test_run_id": test_run_id, "status": "FAILED"},
        message="테스트가 취소되었습니다.",
    )

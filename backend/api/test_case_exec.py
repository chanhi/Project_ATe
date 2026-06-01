"""
테스트 케이스 실행 API (v2)
───────────────────────────
test_case_id 기반으로 실행하는 새 엔드포인트.
기존 scenario_id 기반 /tests/run 과 별개로 공존한다.

POST /test-cases/{id}/execute     → 단건 실행
POST /test-cases/execute-batch    → 여러 케이스 일괄 실행
"""

import uuid

from fastapi import APIRouter, HTTPException

from core.mongo import (
    get_test_cases_collection,
    get_test_runs_collection,
    get_test_run_groups_collection,
)
from core.redis_client import set_test_run_status
from core.exporter import export_to_playwright
from schemas.schemas import (
    APIResponse,
    TestCaseRunRequest,
    TestCaseBatchRunRequest,
    TestRunResponse,
)
from tasks.test_runner import execute_test

router = APIRouter(prefix="/test-cases", tags=["Test Cases"])


@router.post(
    "/{test_case_id}/execute",
    response_model=APIResponse,
    status_code=202,
    summary="테스트 케이스 단건 실행 (지정 URL에서)",
)
async def execute_test_case(test_case_id: str, request: TestCaseRunRequest):
    """
    테스트 케이스 1건을 지정한 웹사이트(target_url)에서 실행한다.

    실행 코드 결정 우선순위:
    1. `playwright_code`가 있으면 그대로 사용
    2. 없으면 `steps`를 Playwright 코드로 컴파일

    실행 결과:
    - PASSED: 모든 스텝 통과
    - FAILED: assertion 실패 (error_log에 exception 포함)
    - ERROR: 실행 자체 실패 (타임아웃 등)
    """
    if request.test_case_id != test_case_id:
        raise HTTPException(
            status_code=400,
            detail="URL의 test_case_id와 body의 test_case_id가 일치하지 않습니다.",
        )

    test_cases = get_test_cases_collection()
    test_runs = get_test_runs_collection()

    # ── 테스트 케이스 조회 ──
    tc = await test_cases.find_one({"test_case_id": test_case_id})
    if not tc:
        raise HTTPException(status_code=404, detail="테스트 케이스를 찾을 수 없습니다.")

    # ── 실행할 코드 결정 ──
    code = tc.get("playwright_code", "")
    if not code and tc.get("steps"):
        code = export_to_playwright([tc], base_url=request.target_url)

    if not code:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": "테스트 케이스에 실행 가능한 playwright_code 또는 steps가 없습니다.",
                "error_code": "NO_EXECUTABLE_CONTENT",
            },
        )

    # ── test_run 기록 생성 ──
    test_run_id = f"run-{uuid.uuid4().hex[:8]}"
    run_doc = {
        "test_run_id": test_run_id,
        "test_case_id": test_case_id,
        "target_url": request.target_url,
        "status": "QUEUED",
        "created_at": _utcnow(),
    }
    await test_runs.insert_one(run_doc)

    # ── Redis 상태 캐시 ──
    await set_test_run_status(test_run_id, "QUEUED")

    # ── Celery Task 등록 ──
    # 기존 test_runner.execute_test를 그대로 재활용.
    # scenario_id 자리에 test_case_id를 넘긴다 (기존 워커 시그니처 유지).
    task = execute_test.apply_async(
        args=[test_run_id, test_case_id, code, request.target_url],
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
            "test_case_id": test_case_id,
            "target_url": request.target_url,
            "status": "QUEUED",
            "celery_task_id": task.id,
            "ws_url": f"/ws/v1/tests/{test_run_id}/logs",
        },
        message="테스트가 큐에 등록되었습니다. WebSocket으로 실시간 로그를 수신하세요.",
    )


@router.post(
    "/execute-batch",
    response_model=APIResponse,
    status_code=202,
    summary="여러 테스트 케이스 일괄 실행 (같은 URL 대상, run_group 자동 생성)",
)
async def execute_batch(request: TestCaseBatchRunRequest):
    """
    여러 테스트 케이스를 하나의 대상 URL에서 일괄 실행한다.

    **run_group 자동 생성:**
    이 호출 한 번이 하나의 run_group_id로 묶인다. 나중에
    `GET /dashboard/run-groups/{run_group_id}` 로 그룹 단위 결과 조회 가능.

    프론트 대시보드에서 "Total: 5 / Passed: 4 / Failed: 1 / Duration: 5.2s" 형태로 표시할 때 사용.
    """
    test_cases = get_test_cases_collection()
    test_runs = get_test_runs_collection()
    test_run_groups = get_test_run_groups_collection()

    cursor = test_cases.find({"test_case_id": {"$in": request.test_case_ids}})
    tcs = await cursor.to_list(length=None)

    if not tcs:
        raise HTTPException(status_code=404, detail="테스트 케이스를 찾을 수 없습니다.")

    # ── run_group 사전 생성 ──
    run_group_id = f"grp-{uuid.uuid4().hex[:8]}"
    project_id = tcs[0].get("project_id") if tcs else None

    group_doc = {
        "run_group_id": run_group_id,
        "project_id": project_id,
        "target_url": request.target_url,
        "triggered_by": "batch",
        "test_run_ids": [],
        "total_count": 0,
        "passed_count": 0,
        "failed_count": 0,
        "error_count": 0,
        "pending_count": 0,
        "total_duration_ms": 0,
        "overall_status": "RUNNING",
        "started_at": _utcnow(),
        "created_at": _utcnow(),
    }
    await test_run_groups.insert_one(group_doc)

    triggered = []
    skipped = []
    triggered_run_ids = []

    for tc in tcs:
        code = tc.get("playwright_code", "")
        if not code and tc.get("steps"):
            code = export_to_playwright([tc], base_url=request.target_url)

        if not code:
            skipped.append({
                "test_case_id": tc["test_case_id"],
                "reason": "no_executable_content",
            })
            continue

        test_run_id = f"run-{uuid.uuid4().hex[:8]}"
        run_doc = {
            "test_run_id": test_run_id,
            "test_case_id": tc["test_case_id"],
            "target_url": request.target_url,
            "status": "QUEUED",
            "run_group_id": run_group_id,    # ← 그룹 연결
            "created_at": _utcnow(),
        }
        await test_runs.insert_one(run_doc)
        await set_test_run_status(test_run_id, "QUEUED")

        task = execute_test.apply_async(
            args=[test_run_id, tc["test_case_id"], code, request.target_url],
            queue="test_execution",
        )
        await test_runs.update_one(
            {"test_run_id": test_run_id},
            {"$set": {"celery_task_id": task.id}},
        )
        triggered.append(TestRunResponse(
            test_run_id=test_run_id,
            status="QUEUED",
            celery_task_id=task.id,
        ))
        triggered_run_ids.append(test_run_id)

    # 그룹의 test_run_ids + total_count 갱신
    await test_run_groups.update_one(
        {"run_group_id": run_group_id},
        {"$set": {
            "test_run_ids": triggered_run_ids,
            "total_count": len(triggered_run_ids),
            "pending_count": len(triggered_run_ids),
        }},
    )

    return APIResponse(
        status="success",
        data={
            "run_group_id": run_group_id,
            "triggered_test_runs": [r.model_dump() for r in triggered],
            "total_triggered": len(triggered),
            "skipped": skipped,
            "target_url": request.target_url,
            "dashboard_url": f"/dashboard/run-groups/{run_group_id}",
        },
        message=f"Run Group {run_group_id} 생성. {len(triggered)}개 실행, {len(skipped)}개 스킵",
    )


def _utcnow():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)

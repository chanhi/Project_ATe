"""
대시보드 API
────────────
프론트엔드 대시보드에서 사용하는 요약 데이터 제공.

GET /dashboard/summary           → 전체 요약 (케이스/실행 통계)
GET /dashboard/recent-runs       → 최근 실행 목록 (테스트번호 → 성공/실패)
GET /dashboard/by-technique      → 기법별 통계
"""

from fastapi import APIRouter, Query

from core.mongo import (
    get_test_cases_collection,
    get_test_runs_collection,
)
from schemas.schemas import APIResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/summary",
    response_model=APIResponse,
    summary="대시보드 요약 통계",
)
async def get_summary(project_id: str | None = Query(None)):
    """
    프론트 대시보드 메인 지표.

    반환:
    - total_cases: 전체 테스트 케이스 수
    - total_runs: 전체 실행 수
    - passed / failed / error: 결과별 수
    - pass_rate: 성공률 (%)
    - recent_runs: 최근 10건
    """
    test_cases = get_test_cases_collection()
    test_runs = get_test_runs_collection()

    tc_query = {"project_id": project_id} if project_id else {}
    total_cases = await test_cases.count_documents(tc_query)

    # 프로젝트 기반 run 필터 (test_case → test_run 조인)
    run_query = {}
    if project_id:
        case_ids = await test_cases.distinct("test_case_id", tc_query)
        run_query = {"test_case_id": {"$in": case_ids}} if case_ids else {"test_case_id": {"$in": []}}

    total_runs = await test_runs.count_documents(run_query)

    # 기존 워커는 SUCCESS/FAILED를 사용, v2에서는 PASSED/FAILED/ERROR 사용 → 둘 다 카운트
    passed = await test_runs.count_documents({**run_query, "status": {"$in": ["PASSED", "SUCCESS"]}})
    failed = await test_runs.count_documents({**run_query, "status": "FAILED"})
    error = await test_runs.count_documents({**run_query, "status": "ERROR"})
    running = await test_runs.count_documents({**run_query, "status": {"$in": ["QUEUED", "PENDING", "RUNNING"]}})

    pass_rate = round((passed / total_runs * 100), 1) if total_runs > 0 else 0.0

    # 최근 10건
    recent_cursor = test_runs.find(run_query, {"_id": 0}).sort("created_at", -1).limit(10)
    recent = await recent_cursor.to_list(length=10)
    for r in recent:
        for k in ("created_at", "started_at", "ended_at"):
            if r.get(k):
                r[k] = r[k].isoformat()

    return APIResponse(
        status="success",
        data={
            "total_cases": total_cases,
            "total_runs": total_runs,
            "passed": passed,
            "failed": failed,
            "error": error,
            "running": running,
            "pass_rate": pass_rate,
            "recent_runs": recent,
        },
    )


@router.get(
    "/recent-runs",
    response_model=APIResponse,
    summary="최근 실행 목록 (테스트번호 → 성공/실패 페이지용)",
)
async def get_recent_runs(
    project_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    status: str | None = Query(None, description="PASSED|FAILED|ERROR|RUNNING 필터"),
):
    """
    요구사항의 "테스트 번호 → 성공 및 실패 여부 페이지"에 표시할 데이터.
    실패 건은 exception 정보(error_log)를 포함한다.
    """
    test_cases = get_test_cases_collection()
    test_runs = get_test_runs_collection()

    query = {}
    if project_id:
        case_ids = await test_cases.distinct("test_case_id", {"project_id": project_id})
        query["test_case_id"] = {"$in": case_ids} if case_ids else {"$in": []}

    if status:
        query["status"] = status

    cursor = test_runs.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    runs = await cursor.to_list(length=limit)

    # test_case 정보 조인
    case_ids_in_runs = {r.get("test_case_id") or r.get("scenario_id") for r in runs}
    case_docs = await test_cases.find(
        {"test_case_id": {"$in": list(case_ids_in_runs)}},
        {"_id": 0, "test_case_id": 1, "title": 1, "technique": 1},
    ).to_list(length=None)
    case_map = {c["test_case_id"]: c for c in case_docs}

    enriched = []
    for r in runs:
        tc_id = r.get("test_case_id") or r.get("scenario_id")
        tc_info = case_map.get(tc_id, {})
        enriched.append({
            "test_run_id": r.get("test_run_id"),
            "test_case_id": tc_id,
            "title": tc_info.get("title", "(삭제된 케이스)"),
            "technique": tc_info.get("technique"),
            "target_url": r.get("target_url"),
            "status": r.get("status"),
            "duration_ms": r.get("duration_ms"),
            "error_log": r.get("error_log") if r.get("status") in ("FAILED", "ERROR") else None,
            "started_at": r.get("started_at").isoformat() if r.get("started_at") else None,
            "ended_at": r.get("ended_at").isoformat() if r.get("ended_at") else None,
        })

    return APIResponse(
        status="success",
        data={"runs": enriched, "total": len(enriched)},
    )


@router.get(
    "/by-technique",
    response_model=APIResponse,
    summary="기법별 테스트 케이스 통계",
)
async def get_by_technique(project_id: str | None = Query(None)):
    """
    각 테스트 기법(동등 분할, 경계값 등)별로 생성된 케이스 수를 반환.
    """
    test_cases = get_test_cases_collection()

    match_stage = {"$match": {"project_id": project_id}} if project_id else {"$match": {}}
    pipeline = [
        match_stage,
        {"$group": {"_id": "$technique", "count": {"$sum": 1}}},
        {"$project": {"_id": 0, "technique": "$_id", "count": 1}},
        {"$sort": {"count": -1}},
    ]

    cursor = test_cases.aggregate(pipeline)
    stats = await cursor.to_list(length=None)

    return APIResponse(
        status="success",
        data={"by_technique": stats},
    )

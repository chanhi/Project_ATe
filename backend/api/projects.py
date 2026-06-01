"""
프로젝트 API
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.mongo import (
    get_projects_collection,
    get_documents_collection,
    get_test_cases_collection,
    get_scenarios_collection,
    get_test_runs_collection,
)
from schemas.schemas import APIResponse, ProjectDoc

router = APIRouter(prefix="/projects", tags=["Projects"])


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "사내 인트라넷 테스트"})
    base_url: str = Field(..., json_schema_extra={"example": "https://intranet.company.com"})
    description: str | None = None


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    base_url: str | None = None
    description: str | None = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  유틸: 프로젝트별 메타데이터 집계
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _enrich_projects_with_meta(docs: list[dict]) -> list[dict]:
    """
    각 프로젝트에 통계 메타데이터 추가:
    - case_count: 테스트 케이스 수
    - total_runs: 총 실행 횟수
    - passed_runs / failed_runs: 결과별 횟수
    - pass_rate: 성공률 (%)
    - last_run_status: 최근 실행 결과
    - last_run_at: 최근 실행 시각
    """
    if not docs:
        return docs

    test_cases = get_test_cases_collection()
    test_runs = get_test_runs_collection()
    project_ids = [d["project_id"] for d in docs if d.get("project_id")]

    if not project_ids:
        return docs

    # ── 케이스 수 집계 ──
    case_counts = {}
    async for entry in test_cases.aggregate([
        {"$match": {"project_id": {"$in": project_ids}}},
        {"$group": {"_id": "$project_id", "count": {"$sum": 1}}},
    ]):
        case_counts[entry["_id"]] = entry["count"]

    # ── 실행 통계 집계 ──
    # test_runs는 project_id가 없을 수 있어서 test_case_id로 매핑
    case_to_project = {}
    async for tc in test_cases.find(
        {"project_id": {"$in": project_ids}},
        {"test_case_id": 1, "project_id": 1, "_id": 0}
    ):
        case_to_project[tc["test_case_id"]] = tc["project_id"]

    run_stats = {pid: {
        "total": 0, "passed": 0, "failed": 0, "error": 0,
        "last_status": None, "last_at": None,
    } for pid in project_ids}

    if case_to_project:
        async for run in test_runs.find(
            {"test_case_id": {"$in": list(case_to_project.keys())}},
            {"test_case_id": 1, "status": 1, "created_at": 1, "_id": 0}
        ).sort("created_at", -1):
            pid = case_to_project.get(run["test_case_id"])
            if not pid:
                continue
            stat = run_stats[pid]
            stat["total"] += 1

            status = run.get("status")
            if status in ("SUCCESS", "PASSED"):
                stat["passed"] += 1
            elif status in ("FAILED", "FAILURE"):
                stat["failed"] += 1
            elif status == "ERROR":
                stat["error"] += 1

            # 가장 최근 실행 (정렬됐으니까 첫 번째만)
            if stat["last_status"] is None:
                stat["last_status"] = status
                stat["last_at"] = run["created_at"].isoformat() if run.get("created_at") else None

    # ── docs에 합치기 ──
    for doc in docs:
        pid = doc.get("project_id")
        stat = run_stats.get(pid, {})
        total = stat.get("total", 0)
        passed = stat.get("passed", 0)

        doc["case_count"] = case_counts.get(pid, 0)
        doc["total_runs"] = total
        doc["passed_runs"] = passed
        doc["failed_runs"] = stat.get("failed", 0) + stat.get("error", 0)
        doc["pass_rate"] = round((passed / total) * 100) if total > 0 else None
        doc["last_run_status"] = stat.get("last_status")
        doc["last_run_at"] = stat.get("last_at")

    return docs


@router.post("", response_model=APIResponse, status_code=201,
             summary="프로젝트 생성")
async def create_project(request: ProjectCreateRequest):
    projects = get_projects_collection()
    project_id = f"proj-{uuid.uuid4().hex[:8]}"
    doc = ProjectDoc(
        project_id=project_id,
        name=request.name,
        base_url=request.base_url,
        description=request.description,
    )
    await projects.insert_one(doc.model_dump())

    return APIResponse(
        status="success",
        data={
            "project_id": project_id,
            "name": request.name,
            "base_url": request.base_url,
            "description": request.description,
            "created_at": doc.created_at.isoformat(),
        },
    )


@router.get("/{project_id}", response_model=APIResponse,
            summary="프로젝트 상세 조회")
async def get_project(project_id: str):
    projects = get_projects_collection()
    doc = await projects.find_one({"project_id": project_id}, {"_id": 0})

    if not doc:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "message": f"프로젝트를 찾을 수 없습니다: {project_id}",
                "error_code": "PROJECT_NOT_FOUND",
            },
        )

    if doc.get("created_at"):
        doc["created_at"] = doc["created_at"].isoformat()
    if doc.get("updated_at"):
        doc["updated_at"] = doc["updated_at"].isoformat()

    enriched = await _enrich_projects_with_meta([doc])
    return APIResponse(status="success", data=enriched[0])


@router.get("", response_model=APIResponse,
            summary="프로젝트 목록 조회 (메타데이터 포함)")
async def list_projects(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    프로젝트 목록 + 각 프로젝트의 통계:
    - case_count, total_runs, pass_rate
    - last_run_status, last_run_at
    """
    projects = get_projects_collection()
    cursor = projects.find({}, {"_id": 0}).sort("created_at", -1).skip(offset).limit(limit)
    docs = await cursor.to_list(length=limit)

    for doc in docs:
        if doc.get("created_at"):
            doc["created_at"] = doc["created_at"].isoformat()
        if doc.get("updated_at"):
            doc["updated_at"] = doc["updated_at"].isoformat()

    # 메타데이터 추가
    docs = await _enrich_projects_with_meta(docs)

    total = await projects.count_documents({})

    return APIResponse(
        status="success",
        data={"items": docs, "total": total, "limit": limit, "offset": offset},
    )


@router.put("/{project_id}", response_model=APIResponse, summary="프로젝트 수정")
async def update_project(project_id: str, request: ProjectUpdateRequest):
    projects = get_projects_collection()
    update_data = {k: v for k, v in request.model_dump(exclude_none=True).items()}

    if not update_data:
        raise HTTPException(status_code=400, detail="업데이트할 필드가 없습니다.")

    update_data["updated_at"] = datetime.now(timezone.utc)

    result = await projects.update_one(
        {"project_id": project_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")

    return APIResponse(
        status="success",
        data={"project_id": project_id, "updated_fields": list(update_data.keys())},
    )


@router.delete("/{project_id}", response_model=APIResponse, summary="프로젝트 삭제")
async def delete_project(project_id: str):
    projects = get_projects_collection()
    documents = get_documents_collection()
    test_cases = get_test_cases_collection()
    scenarios = get_scenarios_collection()

    result = await projects.delete_one({"project_id": project_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")

    doc_count = await documents.count_documents({"project_id": project_id})
    tc_count = await test_cases.count_documents({"project_id": project_id})
    scen_count = await scenarios.count_documents({"project_id": project_id})

    return APIResponse(
        status="success",
        data={
            "project_id": project_id,
            "orphaned": {
                "documents": doc_count,
                "test_cases": tc_count,
                "scenarios": scen_count,
            },
        },
        message=f"프로젝트 삭제 완료. 관련 문서 {doc_count}개, 케이스 {tc_count}개는 고아로 남습니다.",
    )
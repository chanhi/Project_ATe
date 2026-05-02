"""
프로젝트 API
────────────
팀이 붙기 위한 전제 조건.
문서 업로드, 테스트 케이스 생성 모두 project_id가 필수이므로
프로젝트부터 만들 수 있어야 한다.

POST   /projects           → 프로젝트 생성
GET    /projects/{id}      → 상세 조회
GET    /projects           → 목록 조회
PUT    /projects/{id}      → 수정
DELETE /projects/{id}      → 삭제
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


@router.post(
    "",
    response_model=APIResponse,
    status_code=201,
    summary="프로젝트 생성 (팀 진입 첫 단계)",
)
async def create_project(request: ProjectCreateRequest):
    """
    테스트 대상 웹사이트 단위로 프로젝트를 만든다.
    이후 모든 문서 업로드와 테스트 케이스 생성은 이 project_id를 사용한다.
    """
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


@router.get(
    "/{project_id}",
    response_model=APIResponse,
    summary="프로젝트 상세 조회",
)
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

    return APIResponse(status="success", data=doc)


@router.get(
    "",
    response_model=APIResponse,
    summary="프로젝트 목록 조회",
)
async def list_projects(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    projects = get_projects_collection()
    cursor = projects.find({}, {"_id": 0}).sort("created_at", -1).skip(offset).limit(limit)
    docs = await cursor.to_list(length=limit)

    for doc in docs:
        if doc.get("created_at"):
            doc["created_at"] = doc["created_at"].isoformat()
        if doc.get("updated_at"):
            doc["updated_at"] = doc["updated_at"].isoformat()

    total = await projects.count_documents({})

    return APIResponse(
        status="success",
        data={"items": docs, "total": total, "limit": limit, "offset": offset},
    )


@router.put(
    "/{project_id}",
    response_model=APIResponse,
    summary="프로젝트 수정",
)
async def update_project(project_id: str, request: ProjectUpdateRequest):
    projects = get_projects_collection()
    update_data = {k: v for k, v in request.model_dump(exclude_none=True).items()}

    if not update_data:
        raise HTTPException(status_code=400, detail="업데이트할 필드가 없습니다.")

    update_data["updated_at"] = datetime.now(timezone.utc)

    result = await projects.update_one(
        {"project_id": project_id},
        {"$set": update_data},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")

    return APIResponse(
        status="success",
        data={"project_id": project_id, "updated_fields": list(update_data.keys())},
    )


@router.delete(
    "/{project_id}",
    response_model=APIResponse,
    summary="프로젝트 삭제",
)
async def delete_project(project_id: str):
    """프로젝트 삭제. 관련 문서/케이스/시나리오의 project_id는 고아로 남는다."""
    projects = get_projects_collection()
    documents = get_documents_collection()
    test_cases = get_test_cases_collection()
    scenarios = get_scenarios_collection()

    result = await projects.delete_one({"project_id": project_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")

    # 관련 통계
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

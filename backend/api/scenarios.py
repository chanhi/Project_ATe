"""
시나리오 API
────────────
AI팀이 붙는 지점. 자연어 prompt를 받아 시나리오 문서를 생성하고,
생성된 테스트 코드를 저장한다.

POST   /scenarios              → 시나리오 생성 (nl_prompt만, AI는 추후 비동기 생성)
POST   /scenarios/{id}/code    → AI팀이 생성한 code 업데이트
GET    /scenarios/{id}         → 시나리오 상세 조회
GET    /scenarios              → 목록 조회 (project_id 필터)
DELETE /scenarios/{id}         → 삭제
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from core.mongo import (
    get_projects_collection,
    get_scenarios_collection,
)
from schemas.schemas import APIResponse, ScenarioDoc


router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Request 스키마
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ScenarioCreateRequest(BaseModel):
    """시나리오 생성 요청 (AI팀 또는 프론트가 호출)"""
    project_id: str = Field(..., json_schema_extra={"example": "proj-001"})
    title: str = Field(..., json_schema_extra={"example": "로그인 성공 케이스"})
    nl_prompt: str = Field(
        ...,
        json_schema_extra={"example": "아이디 admin, 비밀번호 1234 입력 후 로그인 버튼 클릭"},
    )
    # AI가 이미 코드를 생성했다면 같이 넘길 수 있음 (선택)
    generated_code: str | None = None
    ai_validation: dict | None = None


class ScenarioCodeUpdateRequest(BaseModel):
    """AI팀이 생성한 코드를 업데이트"""
    generated_code: str
    ai_validation: dict | None = Field(
        default=None,
        json_schema_extra={"example": {
            "is_valid": True,
            "retry_count": 1,
            "message": "Self-healing applied",
        }},
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  엔드포인트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post(
    "",
    response_model=APIResponse,
    status_code=201,
    summary="시나리오 생성 (AI팀 붙는 지점)",
)
async def create_scenario(request: ScenarioCreateRequest):
    """
    자연어 prompt를 바탕으로 시나리오 문서를 생성한다.

    사용 패턴 2가지:
    1. **즉시 저장 + 추후 AI 생성** — `nl_prompt`만 넘기고 `generated_code`는 나중에 업데이트
       → 프론트가 입력 직후 scenario_id를 받고 AI 작업을 백그라운드로 돌리는 플로우
    2. **AI 결과까지 한번에 저장** — `generated_code`와 `ai_validation`까지 포함
       → AI팀이 자체 생성한 후 한번에 POST
    """
    projects = get_projects_collection()
    scenarios = get_scenarios_collection()

    # 프로젝트 존재 확인
    project = await projects.find_one({"project_id": request.project_id})
    if not project:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "message": f"프로젝트를 찾을 수 없습니다: {request.project_id}",
                "error_code": "PROJECT_NOT_FOUND",
            },
        )

    # scenario_id 생성
    scenario_id = f"scen-{uuid.uuid4().hex[:8]}"

    doc = ScenarioDoc(
        scenario_id=scenario_id,
        project_id=request.project_id,
        title=request.title,
        nl_prompt=request.nl_prompt,
        generated_code=request.generated_code,
        ai_validation=request.ai_validation,
    )
    await scenarios.insert_one(doc.model_dump())

    return APIResponse(
        status="success",
        data={
            "scenario_id": scenario_id,
            "project_id": request.project_id,
            "title": request.title,
            "nl_prompt": request.nl_prompt,
            "generated_code": request.generated_code,
            "ai_validation": request.ai_validation,
            "created_at": doc.created_at.isoformat(),
        },
    )


@router.post(
    "/{scenario_id}/code",
    response_model=APIResponse,
    summary="생성된 테스트 코드 업데이트 (AI팀이 호출)",
)
async def update_scenario_code(scenario_id: str, request: ScenarioCodeUpdateRequest):
    """
    AI팀이 자연어로부터 테스트 코드를 생성한 후 이 엔드포인트로 업데이트한다.
    Self-healing 결과, 검증 정보를 같이 저장할 수 있다.
    """
    scenarios = get_scenarios_collection()

    result = await scenarios.update_one(
        {"scenario_id": scenario_id},
        {"$set": {
            "generated_code": request.generated_code,
            "ai_validation": request.ai_validation,
            "updated_at": datetime.now(timezone.utc),
        }},
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "message": f"시나리오를 찾을 수 없습니다: {scenario_id}",
                "error_code": "SCENARIO_NOT_FOUND",
            },
        )

    return APIResponse(
        status="success",
        data={
            "scenario_id": scenario_id,
            "generated_code": request.generated_code,
            "ai_validation": request.ai_validation,
        },
        message="코드 업데이트 완료",
    )


@router.get(
    "/{scenario_id}",
    response_model=APIResponse,
    summary="시나리오 상세 조회",
)
async def get_scenario(scenario_id: str):
    scenarios = get_scenarios_collection()
    doc = await scenarios.find_one({"scenario_id": scenario_id})

    if not doc:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "message": f"시나리오를 찾을 수 없습니다: {scenario_id}",
                "error_code": "SCENARIO_NOT_FOUND",
            },
        )

    return APIResponse(
        status="success",
        data={
            "scenario_id": doc["scenario_id"],
            "project_id": doc["project_id"],
            "title": doc["title"],
            "nl_prompt": doc["nl_prompt"],
            "generated_code": doc.get("generated_code"),
            "ai_validation": doc.get("ai_validation"),
            "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
            "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
        },
    )


@router.get(
    "",
    response_model=APIResponse,
    summary="시나리오 목록 조회",
)
async def list_scenarios(
    project_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    scenarios = get_scenarios_collection()

    query = {}
    if project_id:
        query["project_id"] = project_id

    cursor = scenarios.find(query).sort("created_at", -1).skip(offset).limit(limit)
    docs = await cursor.to_list(length=limit)

    return APIResponse(
        status="success",
        data=[
            {
                "scenario_id": d["scenario_id"],
                "project_id": d["project_id"],
                "title": d["title"],
                "nl_prompt": d["nl_prompt"],
                "has_code": bool(d.get("generated_code")),
                "created_at": d.get("created_at").isoformat() if d.get("created_at") else None,
            }
            for d in docs
        ],
    )


@router.delete(
    "/{scenario_id}",
    response_model=APIResponse,
    summary="시나리오 삭제",
)
async def delete_scenario(scenario_id: str):
    scenarios = get_scenarios_collection()
    result = await scenarios.delete_one({"scenario_id": scenario_id})

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail={"status": "error", "message": "시나리오를 찾을 수 없습니다."},
        )

    return APIResponse(
        status="success",
        data={"scenario_id": scenario_id},
        message="시나리오 삭제 완료",
    )

"""
테스트 케이스 API (v2 - 배치 생성 + run 메타데이터)
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from core.mongo import (
    get_projects_collection,
    get_documents_collection,
    get_test_cases_collection,
    get_test_runs_collection,
)
from core.exporter import export_test_cases, EXPORTERS
from core.redis_client import set_test_run_status
from tasks.ai_generation import generate_test_cases_task
from schemas.schemas import (
    APIResponse,
    TestCaseDoc,
    TestCaseGenerateRequest,
    TestCaseExportRequest,
    TEST_TECHNIQUES,
)

router = APIRouter(prefix="/test-cases", tags=["Test Cases"])


class TestCaseGenerateRequestV2(BaseModel):
    project_id: str
    document_id: str | None = None
    nl_input: str | None = None
    techniques: list[str] = Field(
        default_factory=lambda: ["scenario_based"],
        description=f"적용할 테스트 기법. 지원: {TEST_TECHNIQUES}",
    )
    target_urls: list[str] = Field(default_factory=list)
    requested_count: int = Field(default=5, ge=1, le=5)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  유틸: test_case별 실행 메타데이터 계산
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _enrich_with_run_meta(docs: list[dict]) -> list[dict]:
    """각 test_case에 last_run_status, run_count, last_run_at을 붙여 반환."""
    if not docs:
        return docs

    test_runs = get_test_runs_collection()
    case_ids = [d["test_case_id"] for d in docs if d.get("test_case_id")]
    if not case_ids:
        return docs

    # MongoDB aggregation으로 한 번에 집계
    pipeline = [
        {"$match": {"test_case_id": {"$in": case_ids}}},
        {"$sort": {"created_at": -1}},
        {"$group": {
            "_id": "$test_case_id",
            "run_count": {"$sum": 1},
            "last_run_status": {"$first": "$status"},
            "last_run_at": {"$first": "$created_at"},
            "last_run_duration_ms": {"$first": "$duration_ms"},
        }},
    ]

    meta_by_case = {}
    async for entry in test_runs.aggregate(pipeline):
        meta_by_case[entry["_id"]] = {
            "run_count": entry.get("run_count", 0),
            "last_run_status": entry.get("last_run_status"),
            "last_run_at": entry["last_run_at"].isoformat() if entry.get("last_run_at") else None,
            "last_run_duration_ms": entry.get("last_run_duration_ms"),
        }

    for doc in docs:
        meta = meta_by_case.get(doc.get("test_case_id"), {})
        doc["run_count"] = meta.get("run_count", 0)
        doc["last_run_status"] = meta.get("last_run_status")
        doc["last_run_at"] = meta.get("last_run_at")
        doc["last_run_duration_ms"] = meta.get("last_run_duration_ms")

    return docs


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  테스트 케이스 생성
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/generate", response_model=APIResponse, status_code=201,
             summary="테스트 케이스 일괄 생성 (AI 배치)")
async def generate_test_cases(request: TestCaseGenerateRequestV2):
    projects = get_projects_collection()
    documents = get_documents_collection()
    test_cases = get_test_cases_collection()

    project = await projects.find_one({"project_id": request.project_id})
    if not project:
        raise HTTPException(404, detail={
            "status": "error",
            "message": f"프로젝트를 찾을 수 없습니다: {request.project_id}",
            "error_code": "PROJECT_NOT_FOUND",
        })

    if not request.document_id and not request.nl_input:
        raise HTTPException(400, detail={
            "status": "error",
            "message": "document_id 또는 nl_input 중 하나는 필수입니다.",
            "error_code": "MISSING_INPUT",
        })

    for t in request.techniques:
        if t not in TEST_TECHNIQUES:
            raise HTTPException(400, detail={
                "status": "error",
                "message": f"지원하지 않는 기법: {t}",
                "error_code": "INVALID_TECHNIQUE",
            })

    if not request.techniques:
        request.techniques = ["scenario_based"]

    source_text = request.nl_input or ""
    if request.document_id:
        doc = await documents.find_one({"document_id": request.document_id})
        if not doc:
            raise HTTPException(404, detail="문서를 찾을 수 없습니다.")
        source_text = doc.get("extracted_text") or source_text
        if not source_text:
            raise HTTPException(400, detail="문서의 extracted_text가 비어있습니다.")

    target_urls = request.target_urls or [project.get("base_url", "")]
    target_url = target_urls[0] if target_urls else ""

    placeholder_ids = []
    for i in range(request.requested_count):
        test_case_id = f"tc-{uuid.uuid4().hex[:8]}"
        tc_doc = TestCaseDoc(
            test_case_id=test_case_id,
            project_id=request.project_id,
            document_id=request.document_id,
            title=f"AI 생성 대기중 ({i+1}/{request.requested_count})",
            description=f"기법: {', '.join(request.techniques)} | 입력: {source_text[:100]}",
            technique=request.techniques[0],
            target_urls=target_urls,
        )
        await test_cases.insert_one(tc_doc.model_dump())
        placeholder_ids.append(test_case_id)

    job_id = f"aijob-{uuid.uuid4().hex[:8]}"
    await set_test_run_status(job_id, "QUEUED", job_type="ai_generation")

    task = generate_test_cases_task.apply_async(
        args=[
            job_id, placeholder_ids, request.project_id,
            request.nl_input, request.document_id, source_text,
            target_url, request.techniques, request.requested_count,
        ],
        queue="ai_generation",
    )

    return APIResponse(
        status="success",
        data={
            "job_id": job_id,
            "status": "QUEUED",
            "celery_task_id": task.id,
            "placeholder_test_case_ids": placeholder_ids,
            "requested_count": request.requested_count,
            "techniques": request.techniques,
            "source": "document" if request.document_id else "natural_language",
            "target_urls": target_urls,
            "ws_url": f"/ws/v1/tests/{job_id}/logs",
        },
        message=f"{request.requested_count}개 케이스 생성 요청 등록됨.",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  직접 생성
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("", response_model=APIResponse, status_code=201,
             summary="테스트 케이스 직접 생성")
async def create_test_case_direct(request: dict):
    test_cases = get_test_cases_collection()
    projects = get_projects_collection()

    project_id = request.get("project_id")
    title = request.get("title")
    playwright_code = request.get("playwright_code")

    if not project_id: raise HTTPException(400, "project_id 필수")
    if not title: raise HTTPException(400, "title 필수")
    if not playwright_code: raise HTTPException(400, "playwright_code 필수")

    project = await projects.find_one({"project_id": project_id})
    if not project:
        raise HTTPException(404, f"프로젝트 없음: {project_id}")

    test_case_id = f"tc-{uuid.uuid4().hex[:8]}"
    target_urls = request.get("target_urls") or [project.get("base_url", "")]

    tc_doc = {
        "test_case_id": test_case_id,
        "project_id": project_id,
        "title": title,
        "description": request.get("description"),
        "technique": request.get("technique", "scenario_based"),
        "category": request.get("category"),
        "priority": request.get("priority", "medium"),
        "precondition": request.get("precondition"),
        "steps": request.get("steps", []),
        "expected_result": request.get("expected_result"),
        "playwright_code": playwright_code,
        "target_urls": target_urls,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await test_cases.insert_one(tc_doc)

    return APIResponse(
        status="success",
        data={"test_case_id": test_case_id, "title": title, "ready_to_execute": True},
        message="케이스 생성됨",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CRUD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.put("/{test_case_id}", response_model=APIResponse)
async def update_test_case(test_case_id: str, body: dict):
    test_cases = get_test_cases_collection()
    allowed = {"title", "description", "precondition", "steps",
               "expected_result", "priority", "category",
               "playwright_code", "target_urls"}
    update_data = {k: v for k, v in body.items() if k in allowed}
    if not update_data:
        raise HTTPException(400, f"업데이트 필드 없음. 허용: {sorted(allowed)}")
    update_data["updated_at"] = datetime.now(timezone.utc)
    result = await test_cases.update_one(
        {"test_case_id": test_case_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(404, "테스트 케이스 없음")
    return APIResponse(status="success",
                       data={"test_case_id": test_case_id, "updated_fields": list(update_data.keys())},
                       message="업데이트 완료")


@router.get("/{test_case_id}", response_model=APIResponse)
async def get_test_case(test_case_id: str):
    test_cases = get_test_cases_collection()
    doc = await test_cases.find_one({"test_case_id": test_case_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "테스트 케이스 없음")
    for k in ("created_at", "updated_at"):
        if doc.get(k):
            doc[k] = doc[k].isoformat()
    # 단일 조회도 메타데이터 포함
    enriched = await _enrich_with_run_meta([doc])
    return APIResponse(status="success", data=enriched[0])


@router.get("", response_model=APIResponse)
async def list_test_cases(
    project_id: str | None = Query(None),
    document_id: str | None = Query(None),
    technique: str | None = Query(None),
    category: str | None = Query(None),
    priority: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """
    테스트 케이스 목록. 각 케이스에 run 메타데이터 포함:
    - run_count: 실행 횟수
    - last_run_status: 최근 실행 결과 (SUCCESS/FAILED/...)
    - last_run_at: 최근 실행 시간
    - last_run_duration_ms: 최근 실행 소요 시간
    """
    test_cases = get_test_cases_collection()
    query = {}
    if project_id: query["project_id"] = project_id
    if document_id: query["document_id"] = document_id
    if technique: query["technique"] = technique
    if category: query["category"] = category
    if priority: query["priority"] = priority

    cursor = test_cases.find(query, {"_id": 0}).sort("created_at", -1).skip(offset).limit(limit)
    docs = await cursor.to_list(length=limit)

    for doc in docs:
        for k in ("created_at", "updated_at"):
            if doc.get(k):
                doc[k] = doc[k].isoformat()

    # ── 실행 메타데이터 추가 ──
    docs = await _enrich_with_run_meta(docs)

    total = await test_cases.count_documents(query)

    return APIResponse(
        status="success",
        data={"items": docs, "total": total, "limit": limit, "offset": offset},
    )


@router.delete("/{test_case_id}", response_model=APIResponse)
async def delete_test_case(test_case_id: str):
    test_cases = get_test_cases_collection()
    result = await test_cases.delete_one({"test_case_id": test_case_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "테스트 케이스 없음")
    return APIResponse(status="success", data={"test_case_id": test_case_id}, message="삭제 완료")


@router.put("/{test_case_id}/target-urls", response_model=APIResponse)
async def update_target_urls(test_case_id: str, body: dict):
    test_cases = get_test_cases_collection()
    urls = body.get("target_urls", [])
    if not isinstance(urls, list):
        raise HTTPException(400, "target_urls는 리스트여야 함")
    result = await test_cases.update_one(
        {"test_case_id": test_case_id},
        {"$set": {"target_urls": urls, "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(404, "테스트 케이스 없음")
    return APIResponse(status="success",
                       data={"test_case_id": test_case_id, "target_urls": urls})


@router.post("/export")
async def export_endpoint(request: TestCaseExportRequest):
    test_cases_col = get_test_cases_collection()
    cursor = test_cases_col.find(
        {"test_case_id": {"$in": request.test_case_ids}}, {"_id": 0})
    docs = await cursor.to_list(length=None)
    if not docs:
        raise HTTPException(404, "테스트 케이스 없음")
    for doc in docs:
        for k in ("created_at", "updated_at"):
            if doc.get(k):
                doc[k] = doc[k].isoformat()
    try:
        content, content_type, ext = export_test_cases(docs, request.format)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))

    filename = f"ate_test_cases_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
    body = content if isinstance(content, bytes) else content.encode("utf-8")
    return Response(
        content=body,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
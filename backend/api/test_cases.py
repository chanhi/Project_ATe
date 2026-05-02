"""
테스트 케이스 API
────────────────
POST   /test-cases/generate        → 기획서/자연어 기반 케이스 생성 (AI 연동 지점)
PUT    /test-cases/{id}            → AI팀이 생성 내용을 업데이트
GET    /test-cases/{id}            → 케이스 상세 조회
GET    /test-cases                 → 목록 조회 (project_id/technique/category 필터)
DELETE /test-cases/{id}            → 삭제
PUT    /test-cases/{id}/target-urls→ 재사용: 적용 URL 설정
POST   /test-cases/export          → 파일 내보내기 (json/csv/xlsx/md/yaml/playwright/html)
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from core.mongo import (
    get_projects_collection,
    get_documents_collection,
    get_test_cases_collection,
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  테스트 케이스 생성 (AI 연동 지점)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post(
    "/generate",
    response_model=APIResponse,
    status_code=201,
    summary="테스트 케이스 생성 (기획서 또는 자연어 기반)",
)
async def generate_test_cases(request: TestCaseGenerateRequest):
    """
    AI팀 연동 지점. 기획서 또는 자연어로부터 테스트 케이스를 생성한다.

    **동작 흐름:**
    1. `document_id` 있으면 → 해당 문서의 `extracted_text` 사용
    2. `nl_input` 있으면 → 자연어를 직접 AI에 전달
    3. `techniques`에 따라 각 기법별로 케이스 생성 (현재는 빈 껍데기만 생성)
    4. AI팀이 PUT /test-cases/{id}로 내용을 채워넣음

    **지원 기법 (블랙박스):**
    - `equivalence_partition` — 동등 분할
    - `boundary_value` — 경계값 분석
    - `decision_table` — 결정 테이블
    - `state_transition` — 상태 전이
    - `error_guessing` — 에러 추측
    - `scenario_based` — 시나리오 기반

    요청 예:
    ```json
    {
      "project_id": "proj-001",
      "document_id": "doc-abc12345",
      "techniques": ["equivalence_partition", "boundary_value"],
      "target_urls": ["https://staging.example.com", "https://prod.example.com"]
    }
    ```
    """
    projects = get_projects_collection()
    documents = get_documents_collection()
    test_cases = get_test_cases_collection()

    # ── 프로젝트 확인 ──
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

    # ── 입력 검증 ──
    if not request.document_id and not request.nl_input:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": "document_id 또는 nl_input 중 하나는 필수입니다.",
                "error_code": "MISSING_INPUT",
            },
        )

    # ── 기법 유효성 ──
    for t in request.techniques:
        if t not in TEST_TECHNIQUES:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": f"지원하지 않는 기법: {t}. 지원: {TEST_TECHNIQUES}",
                    "error_code": "INVALID_TECHNIQUE",
                },
            )

    if not request.techniques:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": "techniques는 최소 1개 이상 지정해야 합니다.",
                "error_code": "EMPTY_TECHNIQUES",
            },
        )

    # ── 기획서 텍스트 준비 ──
    source_text = request.nl_input or ""
    if request.document_id:
        doc = await documents.find_one({"document_id": request.document_id})
        if not doc:
            raise HTTPException(
                status_code=404,
                detail={
                    "status": "error",
                    "message": f"문서를 찾을 수 없습니다: {request.document_id}",
                    "error_code": "DOCUMENT_NOT_FOUND",
                },
            )
        source_text = doc.get("extracted_text") or source_text
        if not source_text:
            raise HTTPException(
                status_code=400,
                detail={
                    "status": "error",
                    "message": "문서의 extracted_text가 비어있습니다. AI팀이 먼저 파싱 결과를 업데이트해야 합니다.",
                    "error_code": "TEXT_NOT_EXTRACTED",
                },
            )

    # ── 각 기법별 placeholder 케이스 생성 ──
    # AI팀이 채워넣을 빈 껍데기를 먼저 만든다. job_id가 발급되고,
    # AI 호출은 Celery Task로 비동기 위임된다.
    target_urls = request.target_urls or [project.get("base_url", "")]
    target_url = target_urls[0] if target_urls else ""

    placeholder_ids = []
    for technique in request.techniques:
        test_case_id = f"tc-{uuid.uuid4().hex[:8]}"
        tc_doc = TestCaseDoc(
            test_case_id=test_case_id,
            project_id=request.project_id,
            document_id=request.document_id,
            title=f"[{technique}] AI 생성 대기중",
            description=f"기법: {technique} | 입력 요약: {source_text[:100]}",
            technique=technique,
            target_urls=target_urls,
        )
        await test_cases.insert_one(tc_doc.model_dump())
        placeholder_ids.append(test_case_id)

    # ── Celery Task 큐 등록 (AI 호출 비동기 위임) ──
    job_id = f"aijob-{uuid.uuid4().hex[:8]}"
    await set_test_run_status(job_id, "QUEUED", job_type="ai_generation")

    task = generate_test_cases_task.apply_async(
        args=[
            job_id,
            placeholder_ids,
            request.project_id,
            request.nl_input,
            request.document_id,
            source_text,           # 기획서 또는 자연어 텍스트
            target_url,
            request.techniques,
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
            "techniques": request.techniques,
            "source": "document" if request.document_id else "natural_language",
            "target_urls": target_urls,
            "ws_url": f"/ws/v1/tests/{job_id}/logs",
        },
        message=(
            f"{len(placeholder_ids)}개의 placeholder가 생성되었습니다. "
            f"AI 생성 진행상황은 ws_url로 구독하세요. "
            f"완료되면 placeholder_test_case_ids에 내용이 채워집니다."
        ),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CRUD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.put(
    "/{test_case_id}",
    response_model=APIResponse,
    summary="테스트 케이스 업데이트 (AI팀이 생성 결과를 채워넣는 지점)",
)
async def update_test_case(test_case_id: str, body: dict):
    """
    AI팀이 생성한 케이스 내용을 업데이트한다.

    허용되는 필드:
    - title, description, precondition
    - steps (list of {step_no, action, target, input, expected})
    - expected_result, priority, category
    - playwright_code (자동화 코드)
    - target_urls (재사용 URL)
    """
    test_cases = get_test_cases_collection()

    allowed_fields = {
        "title", "description", "precondition", "steps",
        "expected_result", "priority", "category",
        "playwright_code", "target_urls",
    }
    update_data = {k: v for k, v in body.items() if k in allowed_fields}

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail=f"업데이트할 필드가 없습니다. 허용: {sorted(allowed_fields)}",
        )

    update_data["updated_at"] = datetime.now(timezone.utc)

    result = await test_cases.update_one(
        {"test_case_id": test_case_id},
        {"$set": update_data},
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="테스트 케이스를 찾을 수 없습니다.")

    return APIResponse(
        status="success",
        data={"test_case_id": test_case_id, "updated_fields": list(update_data.keys())},
        message="업데이트 완료",
    )


@router.get(
    "/{test_case_id}",
    response_model=APIResponse,
    summary="테스트 케이스 상세 조회",
)
async def get_test_case(test_case_id: str):
    test_cases = get_test_cases_collection()
    doc = await test_cases.find_one({"test_case_id": test_case_id}, {"_id": 0})

    if not doc:
        raise HTTPException(status_code=404, detail="테스트 케이스를 찾을 수 없습니다.")

    for k in ("created_at", "updated_at"):
        if doc.get(k):
            doc[k] = doc[k].isoformat()

    return APIResponse(status="success", data=doc)


@router.get(
    "",
    response_model=APIResponse,
    summary="테스트 케이스 목록 조회 (필터 지원)",
)
async def list_test_cases(
    project_id: str | None = Query(None),
    document_id: str | None = Query(None),
    technique: str | None = Query(None),
    category: str | None = Query(None),
    priority: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """프로젝트/기법/카테고리/우선순위로 필터링한 목록을 반환한다."""
    test_cases = get_test_cases_collection()
    query = {}
    if project_id:   query["project_id"] = project_id
    if document_id:  query["document_id"] = document_id
    if technique:    query["technique"] = technique
    if category:     query["category"] = category
    if priority:     query["priority"] = priority

    cursor = test_cases.find(query, {"_id": 0}).sort("created_at", -1).skip(offset).limit(limit)
    docs = await cursor.to_list(length=limit)

    for doc in docs:
        for k in ("created_at", "updated_at"):
            if doc.get(k):
                doc[k] = doc[k].isoformat()

    total = await test_cases.count_documents(query)

    return APIResponse(
        status="success",
        data={"items": docs, "total": total, "limit": limit, "offset": offset},
    )


@router.delete(
    "/{test_case_id}",
    response_model=APIResponse,
    summary="테스트 케이스 삭제",
)
async def delete_test_case(test_case_id: str):
    test_cases = get_test_cases_collection()
    result = await test_cases.delete_one({"test_case_id": test_case_id})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="테스트 케이스를 찾을 수 없습니다.")

    return APIResponse(
        status="success",
        data={"test_case_id": test_case_id},
        message="삭제 완료",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  재사용: 대상 URL 업데이트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.put(
    "/{test_case_id}/target-urls",
    response_model=APIResponse,
    summary="재사용 — 다른 웹사이트에 적용할 URL 목록 설정",
)
async def update_target_urls(test_case_id: str, body: dict):
    """
    생성된 테스트 케이스를 다른 웹사이트에서 재사용할 수 있도록
    target_urls를 업데이트한다.

    ```json
    { "target_urls": ["https://staging.example.com", "https://prod.example.com"] }
    ```
    """
    test_cases = get_test_cases_collection()
    urls = body.get("target_urls", [])

    if not isinstance(urls, list):
        raise HTTPException(status_code=400, detail="target_urls는 리스트여야 합니다.")

    result = await test_cases.update_one(
        {"test_case_id": test_case_id},
        {"$set": {"target_urls": urls, "updated_at": datetime.now(timezone.utc)}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="테스트 케이스를 찾을 수 없습니다.")

    return APIResponse(
        status="success",
        data={"test_case_id": test_case_id, "target_urls": urls},
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  파일 내보내기 (7가지 포맷)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post(
    "/export",
    summary="테스트 케이스 파일 내보내기",
    description="지원 포맷: " + ", ".join(EXPORTERS.keys()),
)
async def export_endpoint(request: TestCaseExportRequest):
    """
    선택한 테스트 케이스들을 파일로 내보낸다.
    응답은 파일 다운로드 형태(Content-Disposition)로 반환된다.

    포맷별 용도:
    - `json` — 구조화된 재가공용
    - `csv` — 스프레드시트 호환
    - `xlsx` — Excel (스텝별 행 분리 + 헤더 스타일)
    - `md` — 문서화/PR 리뷰용
    - `yaml` — 설정 파일로 관리할 때
    - `playwright` — 실행 가능한 TS 코드
    - `html` — 팀 내 공유용 보고서
    """
    test_cases_col = get_test_cases_collection()

    cursor = test_cases_col.find(
        {"test_case_id": {"$in": request.test_case_ids}},
        {"_id": 0},
    )
    docs = await cursor.to_list(length=None)

    if not docs:
        raise HTTPException(
            status_code=404,
            detail="요청한 ID에 해당하는 테스트 케이스가 없습니다.",
        )

    # datetime 직렬화
    for doc in docs:
        for k in ("created_at", "updated_at"):
            if doc.get(k):
                doc[k] = doc[k].isoformat()

    try:
        content, content_type, ext = export_test_cases(docs, request.format)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    filename = f"ate_test_cases_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"

    if isinstance(content, bytes):
        body = content
    else:
        body = content.encode("utf-8")

    return Response(
        content=body,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

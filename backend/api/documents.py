"""
문서(기획서) 업로드 API
───────────────────────
비개발자(기획자/PM/QA)가 기획서를 업로드하는 지점.

파일 파싱은 AI팀 담당 — 백엔드는 원본 파일만 저장한다.
AI팀이 업로드된 파일을 읽어 텍스트를 추출한 후,
PUT /documents/{id}/extract 로 `extracted_text`를 업데이트한다.

POST   /documents/upload         → 파일 업로드
PUT    /documents/{id}/extract   → AI팀이 파싱 결과 텍스트 업데이트
GET    /documents/{id}           → 문서 메타/텍스트 조회
GET    /documents                → 목록 조회
DELETE /documents/{id}           → 삭제 (DB + 파일)
"""

import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form

from core.config import get_settings
from core.mongo import (
    get_projects_collection,
    get_documents_collection,
    get_test_cases_collection,
)
from schemas.schemas import (
    APIResponse,
    UploadedDocumentDoc,
    DocumentExtractUpdateRequest,
)

settings = get_settings()
router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_EXTENSIONS = {"pdf", "docx", "xlsx", "txt", "md", "hwp", "pptx", "csv"}


@router.post(
    "/upload",
    response_model=APIResponse,
    status_code=201,
    summary="기획서/문서 업로드 (비개발자 진입점)",
)
async def upload_document(
    project_id: str = Form(...),
    file: UploadFile = File(...),
):
    """
    기획서, 요구사항 문서, 회의록 등을 업로드한다.

    **처리 흐름:**
    1. 백엔드는 원본 파일을 디스크에 저장 + document_id 발급
    2. AI팀이 파일을 파싱하여 텍스트 추출
    3. AI팀이 PUT /documents/{id}/extract 로 `extracted_text` 업데이트
    4. /test-cases/generate 에서 document_id 참조하여 케이스 생성

    지원 확장자: pdf, docx, xlsx, txt, md, hwp, pptx, csv
    """
    projects = get_projects_collection()
    documents = get_documents_collection()

    # ── 프로젝트 확인 ──
    project = await projects.find_one({"project_id": project_id})
    if not project:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "message": f"프로젝트를 찾을 수 없습니다: {project_id}",
                "error_code": "PROJECT_NOT_FOUND",
            },
        )

    # ── 확장자 검증 ──
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": f"지원하지 않는 파일 형식: .{ext}. 지원: {sorted(ALLOWED_EXTENSIONS)}",
                "error_code": "UNSUPPORTED_FILE_TYPE",
            },
        )

    # ── 파일 크기 검증 ──
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "message": f"파일 크기가 {settings.MAX_UPLOAD_SIZE_MB}MB를 초과합니다.",
                "error_code": "FILE_TOO_LARGE",
            },
        )

    # ── 파일 저장 ──
    document_id = f"doc-{uuid.uuid4().hex[:8]}"
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    # 안전한 파일명 (최소한의 sanitization)
    safe_name = "".join(c for c in file.filename if c.isalnum() or c in "._-가-힣 ").strip()
    file_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}_{safe_name}")

    with open(file_path, "wb") as f:
        f.write(content)

    # ── DB 저장 ──
    doc = UploadedDocumentDoc(
        document_id=document_id,
        project_id=project_id,
        filename=file.filename,
        file_type=ext,
        file_path=file_path,
        file_size_bytes=len(content),
    )
    await documents.insert_one(doc.model_dump())

    return APIResponse(
        status="success",
        data={
            "document_id": document_id,
            "filename": file.filename,
            "file_type": ext,
            "file_size_bytes": len(content),
            "file_path": file_path,
        },
        message="업로드 완료. AI팀이 extracted_text를 업데이트한 후 /test-cases/generate 에서 사용하세요.",
    )


@router.put(
    "/{document_id}/extract",
    response_model=APIResponse,
    summary="AI팀이 파싱한 텍스트를 문서에 저장",
)
async def update_extracted_text(
    document_id: str,
    request: DocumentExtractUpdateRequest,
):
    """
    AI팀이 업로드된 원본 파일(pdf/docx/hwp 등)을 파싱하여
    추출한 텍스트를 이 엔드포인트로 저장한다.

    이후 /test-cases/generate 호출 시 이 텍스트가 AI 프롬프트로 전달된다.
    """
    documents = get_documents_collection()

    result = await documents.update_one(
        {"document_id": document_id},
        {"$set": {"extracted_text": request.extracted_text}},
    )

    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "error",
                "message": f"문서를 찾을 수 없습니다: {document_id}",
                "error_code": "DOCUMENT_NOT_FOUND",
            },
        )

    return APIResponse(
        status="success",
        data={
            "document_id": document_id,
            "extracted_length": len(request.extracted_text),
        },
        message="extracted_text 업데이트 완료",
    )


@router.get(
    "/{document_id}",
    response_model=APIResponse,
    summary="문서 메타/텍스트 조회",
)
async def get_document(document_id: str):
    """문서 메타정보와 추출된 텍스트(있으면)를 조회한다."""
    documents = get_documents_collection()
    doc = await documents.find_one({"document_id": document_id}, {"_id": 0})

    if not doc:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")

    if doc.get("created_at"):
        doc["created_at"] = doc["created_at"].isoformat()

    return APIResponse(status="success", data=doc)


@router.get(
    "",
    response_model=APIResponse,
    summary="문서 목록 조회",
)
async def list_documents(
    project_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    documents = get_documents_collection()
    query = {}
    if project_id:
        query["project_id"] = project_id

    cursor = documents.find(query, {"_id": 0, "extracted_text": 0}).sort("created_at", -1).skip(offset).limit(limit)
    docs = await cursor.to_list(length=limit)

    for doc in docs:
        if doc.get("created_at"):
            doc["created_at"] = doc["created_at"].isoformat()

    total = await documents.count_documents(query)

    return APIResponse(
        status="success",
        data={"items": docs, "total": total, "limit": limit, "offset": offset},
    )


@router.delete(
    "/{document_id}",
    response_model=APIResponse,
    summary="문서 삭제 (DB + 파일)",
)
async def delete_document(document_id: str):
    """문서를 삭제한다. 이 문서를 참조하는 test_case는 document_id만 null로 바뀐다."""
    documents = get_documents_collection()
    test_cases = get_test_cases_collection()

    doc = await documents.find_one({"document_id": document_id})
    if not doc:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")

    # 디스크 파일 삭제
    file_path = doc.get("file_path")
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass  # 파일 삭제 실패해도 DB는 삭제

    # DB 삭제
    await documents.delete_one({"document_id": document_id})

    # 참조하던 test_cases의 document_id 제거
    await test_cases.update_many(
        {"document_id": document_id},
        {"$set": {"document_id": None}},
    )

    return APIResponse(
        status="success",
        data={"document_id": document_id},
        message="문서 삭제 완료",
    )

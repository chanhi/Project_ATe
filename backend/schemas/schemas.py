"""
ATe API 스키마 (Pydantic v2) + MongoDB 문서 스키마
──────────────────────────────────────────────────
"""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def utcnow():
    return datetime.now(timezone.utc)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  공통 응답 포맷 (API 명세서)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class APIResponse(BaseModel):
    status: Literal["success", "error"]
    data: Any | None = None
    message: str | None = None
    error_code: str | None = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MongoDB 문서 스키마
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ProjectDoc(BaseModel):
    """projects 컬렉션 문서"""
    project_id: str
    name: str
    base_url: str
    description: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ScenarioDoc(BaseModel):
    """scenarios 컬렉션 문서"""
    scenario_id: str
    project_id: str
    title: str
    nl_prompt: str
    generated_code: str | None = None
    ai_validation: dict | None = None  # {is_valid, retry_count, message}
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class FailureDetail(BaseModel):
    """
    실패한 테스트의 구조화된 정보.
    Playwright/HTTP 에러 로그를 파싱해서 만든다.
    파싱 실패 시 reason에만 raw 메시지가 들어간다.
    """
    expected: str | None = None       # "200 OK", "/dashboard"
    actual: str | None = None         # "404 Not Found", "/login"
    reason: str | None = None         # "User ID not found"
    raw_log: str | None = None        # 원본 로그 (전체)


class TestRunDoc(BaseModel):
    """test_runs 컬렉션 문서"""
    test_run_id: str
    scenario_id: str
    status: Literal["QUEUED", "PENDING", "RUNNING", "SUCCESS", "FAILED"] = "QUEUED"
    celery_task_id: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int | None = None
    error_log: str | None = None
    allure_report_url: str | None = None
    ai_analysis: dict | None = None
    created_at: datetime = Field(default_factory=utcnow)

    # ── v2.1 추가 ──
    run_group_id: str | None = None        # 같은 배치로 실행된 묶음
    test_case_id: str | None = None        # test_case 기반 실행 시
    target_url: str | None = None          # 실행 대상 URL
    failure_detail: dict | None = None     # FailureDetail 구조 (실패 시)


class TestRunGroupDoc(BaseModel):
    """
    한 번의 batch 실행으로 묶인 test_run들의 그룹.
    화면의 'Total Tests: 5 / Passed: 4 / Failed: 1 / Duration: 5.2s' 단위.
    """
    run_group_id: str
    project_id: str | None = None
    target_url: str
    triggered_by: str = "manual"           # manual | batch | ci_cd
    test_run_ids: list[str] = Field(default_factory=list)

    # 집계 결과 (실행 완료 후 채워짐)
    total_count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    error_count: int = 0
    pending_count: int = 0
    total_duration_ms: int = 0
    overall_status: Literal["RUNNING", "SUCCESS", "FAILED"] = "RUNNING"

    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  테스트 실행 API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestRunRequest(BaseModel):
    scenario_id: str = Field(..., json_schema_extra={"example": "scen-1234"})


class TestRunResponse(BaseModel):
    test_run_id: str
    status: str = "QUEUED"
    celery_task_id: str | None = None


class TestRunStatusResponse(BaseModel):
    test_run_id: str
    scenario_id: str
    status: Literal["QUEUED", "PENDING", "RUNNING", "SUCCESS", "FAILED"]
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_ms: int | None = None
    error_log: str | None = None
    allure_report_url: str | None = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  WebSocket
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestLogMessage(BaseModel):
    timestamp: str
    level: Literal["INFO", "WARN", "ERROR", "SUCCESS"]
    message: str
    progress_percentage: int = Field(ge=0, le=100)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  v2 추가: 기획서 업로드 + 테스트 기법 + 재사용
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 지원하는 블랙박스 테스트 기법
TEST_TECHNIQUES = [
    "equivalence_partition",   # 동등 분할
    "boundary_value",          # 경계값 분석
    "decision_table",          # 결정 테이블
    "state_transition",        # 상태 전이
    "error_guessing",          # 에러 추측
    "scenario_based",          # 시나리오 기반
]


class UploadedDocumentDoc(BaseModel):
    """업로드된 기획서/요구사항 문서"""
    document_id: str
    project_id: str
    filename: str
    file_type: str                      # pdf, docx, xlsx, txt, md, hwp, pptx
    file_path: str                      # 서버 저장 경로
    file_size_bytes: int
    extracted_text: str | None = None   # AI팀이 파싱 후 PUT으로 업데이트
    created_at: datetime = Field(default_factory=utcnow)


class TestCaseDoc(BaseModel):
    """
    블랙박스 테스트 케이스 (재사용 가능)
    scenarios와 별개의 새 컨셉 — 기획서/문서 기반, 기법별 생성, 다중 URL 재사용
    """
    test_case_id: str
    project_id: str
    document_id: str | None = None     # 어느 기획서에서 생성됐는지

    title: str
    description: str | None = None
    precondition: str | None = None    # 사전 조건
    steps: list[dict] = Field(default_factory=list)
    # steps 예: [{"step_no": 1, "action": "입력", "target": "#id", "input": "admin", "expected": ""}]

    expected_result: str | None = None
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    category: str | None = None        # login, search, payment 등

    technique: str | None = None       # 어느 기법으로 생성됐는지
    target_urls: list[str] = Field(default_factory=list)  # 재사용: 적용 대상 URL들

    # Playwright 자동화 코드 (AI 생성)
    playwright_code: str | None = None

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# ── API 요청/응답 ──

class TestCaseGenerateRequest(BaseModel):
    """
    테스트 케이스 생성 요청 (AI팀 연동 지점)
    - document_id 있으면 기획서 기반
    - nl_input 있으면 자연어 기반
    """
    project_id: str
    document_id: str | None = None
    nl_input: str | None = None
    techniques: list[str] = Field(
        default_factory=lambda: ["equivalence_partition", "boundary_value"],
        description=f"적용할 테스트 기법. 지원: {TEST_TECHNIQUES}",
    )
    target_urls: list[str] = Field(default_factory=list)


class TestCaseExportRequest(BaseModel):
    """테스트 케이스 파일 내보내기 요청"""
    test_case_ids: list[str]
    format: Literal["json", "csv", "xlsx", "md", "yaml", "playwright", "html"] = "json"


class TestCaseRunRequest(BaseModel):
    """test_case 기반 실행 요청 (기존 scenario 기반 /tests/run과 별개)"""
    test_case_id: str
    target_url: str                     # 실행할 웹사이트 URL


class TestCaseBatchRunRequest(BaseModel):
    """여러 test_case 일괄 실행"""
    test_case_ids: list[str]
    target_url: str


class DocumentExtractUpdateRequest(BaseModel):
    """AI팀이 파싱한 텍스트를 업로드된 문서에 반영"""
    extracted_text: str


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AI 연동 (자연어 → 케이스 + Playwright 코드)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AIGenerationJobResponse(BaseModel):
    """AI 생성 작업 응답"""
    job_id: str
    status: str = "QUEUED"
    celery_task_id: str | None = None
    placeholder_test_case_ids: list[str] = []
    ws_url: str  # WebSocket으로 진행상황 구독할 주소


class AIRegenerateRequest(BaseModel):
    """다른 URL용 Playwright 코드 재생성 요청"""
    test_case_id: str
    new_target_url: str


class AIJobStatusResponse(BaseModel):
    """AI 작업 진행 상태"""
    job_id: str
    status: Literal["QUEUED", "RUNNING", "SUCCESS", "FAILED"]
    job_type: str | None = None  # ai_generation | ai_regeneration
    started_at: str | None = None
    ended_at: str | None = None
    error_log: str | None = None
    extra: dict | None = None

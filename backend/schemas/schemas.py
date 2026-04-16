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


class WebhookConfigDoc(BaseModel):
    """webhook_configs 컬렉션 문서"""
    project_id: str
    provider: Literal["github_actions", "jenkins", "gitlab_ci", "custom"]
    webhook_url: str | None = None
    trigger_on: list[str] = Field(default_factory=lambda: ["push"])
    secret_token: str | None = None
    scenario_ids: list[str] | None = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow)


class WebhookEventDoc(BaseModel):
    """webhook_events 컬렉션 문서"""
    webhook_config_id: str
    provider: str
    event_type: str
    payload: dict | None = None
    triggered_test_run_ids: list[str] | None = None
    status: str = "received"
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
#  CI/CD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class WebhookConfigCreate(BaseModel):
    project_id: str
    provider: Literal["github_actions", "jenkins", "gitlab_ci", "custom"]
    webhook_url: str | None = None
    trigger_on: list[str] = Field(default_factory=lambda: ["push"])
    secret_token: str | None = None
    scenario_ids: list[str] | None = None

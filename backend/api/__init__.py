"""API 라우터 통합"""

from fastapi import APIRouter

# ── 기존 라우터 ──
from api.test_execution import router as test_router
from api.scenarios import router as scenarios_router

# ── v2 라우터 ──
from api.projects import router as projects_router
from api.documents import router as documents_router
from api.test_cases import router as test_cases_router
from api.test_case_exec import router as test_case_exec_router
from api.dashboard import router as dashboard_router

# ── AI 연동 ──
from api.ai import router as ai_router

api_router = APIRouter()

# 프로젝트 생성 (모든 작업의 선행 조건)
api_router.include_router(projects_router)

# 기존 v1 호환
api_router.include_router(scenarios_router)
api_router.include_router(test_router)

# v2 메인
api_router.include_router(documents_router)
api_router.include_router(test_cases_router)
api_router.include_router(test_case_exec_router)
api_router.include_router(dashboard_router)

# AI 연동
api_router.include_router(ai_router)

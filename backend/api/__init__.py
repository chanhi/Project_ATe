"""API 라우터 통합"""

from fastapi import APIRouter

# ── v1 기존 라우터 (유지) ──
from api.test_execution import router as test_router
from api.ci_cd import router as cicd_router
from api.scenarios import router as scenarios_router

# ── v2 추가 라우터 ──
from api.projects import router as projects_router
from api.documents import router as documents_router
from api.test_cases import router as test_cases_router
from api.test_case_exec import router as test_case_exec_router
from api.dashboard import router as dashboard_router

api_router = APIRouter()

# v2 신규 — 프로젝트 생성(필수 선행)
api_router.include_router(projects_router)

# v1 기존
api_router.include_router(scenarios_router)
api_router.include_router(test_router)
api_router.include_router(cicd_router)

# v2 신규 — 기획서 업로드, 케이스 생성/내보내기/재사용, 대시보드
api_router.include_router(documents_router)
api_router.include_router(test_cases_router)
api_router.include_router(test_case_exec_router)
api_router.include_router(dashboard_router)

"""API 라우터 통합"""

from fastapi import APIRouter
from api.test_execution import router as test_router
from api.ci_cd import router as cicd_router
from api.scenarios import router as scenarios_router

api_router = APIRouter()
api_router.include_router(scenarios_router)
api_router.include_router(test_router)
api_router.include_router(cicd_router)

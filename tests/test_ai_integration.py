"""
AI 연동 통합 테스트
─────────────────
- AI 클라이언트 (mock 모드)
- /test-cases/generate가 비동기로 위임되는지
- /ai/regenerate-code 동작
- /ai/jobs/{id} 상태 조회
- /ai/health
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Fixtures
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.fixture
def mock_mongo():
    try:
        from mongomock_motor import AsyncMongoMockClient
    except ImportError:
        pytest.skip("mongomock_motor 미설치")
    return AsyncMongoMockClient()["test_db"]


@pytest.fixture
def mock_ai_celery():
    """AI Celery Task의 apply_async를 mock"""
    mock_result = MagicMock()
    mock_result.id = "celery-ai-task-id"

    with patch("tasks.ai_generation.generate_test_cases_task.apply_async", return_value=mock_result), \
         patch("tasks.ai_generation.regenerate_code_task.apply_async", return_value=mock_result):
        yield mock_result


@pytest.fixture
def mock_redis_status():
    with patch("api.test_cases.set_test_run_status", new=AsyncMock()), \
         patch("api.ai.set_test_run_status", new=AsyncMock()):
        yield


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AI Client (Mock 모드)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAIClientMock:
    """AI_SERVICE_MOCK=True 일 때 mock 응답 반환"""

    def test_generate_cases_mock(self):
        with patch("core.ai_client.settings") as mock_settings:
            mock_settings.AI_SERVICE_MOCK = True

            from core.ai_client import call_generate_cases
            cases = call_generate_cases(
                nl_input="로그인 테스트",
                document_text=None,
                target_url="http://example.com",
                techniques=["equivalence_partition", "boundary_value"],
            )

            assert len(cases) == 2
            assert all("playwright_code" in c for c in cases)
            assert all("steps" in c for c in cases)
            assert cases[0]["technique"] == "equivalence_partition"
            assert cases[1]["technique"] == "boundary_value"

    def test_regenerate_code_mock(self):
        with patch("core.ai_client.settings") as mock_settings:
            mock_settings.AI_SERVICE_MOCK = True

            from core.ai_client import call_regenerate_code
            result = call_regenerate_code(
                test_case={"title": "로그인", "steps": []},
                new_target_url="https://shopB.com",
                old_target_url="https://shopA.com",
            )

            assert "playwright_code" in result
            assert "shopB.com" in result["playwright_code"]
            assert result["target_url"] == "https://shopB.com"

    def test_health_check_mock(self):
        with patch("core.ai_client.settings") as mock_settings:
            mock_settings.AI_SERVICE_MOCK = True

            from core.ai_client import health_check
            assert health_check() is True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AI Client (HTTP 모드 - mock httpx)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAIClientHTTP:
    """실제 HTTP 호출 모드 (httpx mock으로 시뮬레이션)"""

    def test_generate_cases_http_success(self):
        from core.ai_client import call_generate_cases

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "test_cases": [
                {
                    "title": "AI 생성 케이스",
                    "steps": [],
                    "technique": "boundary_value",
                    "playwright_code": "import...",
                },
            ],
        })

        with patch("core.ai_client.settings") as mock_settings, \
             patch("httpx.Client") as MockClient:
            mock_settings.AI_SERVICE_MOCK = False
            mock_settings.AI_SERVICE_URL = "http://ai:9000"
            mock_settings.AI_SERVICE_TIMEOUT = 60

            MockClient.return_value.__enter__.return_value.post.return_value = mock_response

            cases = call_generate_cases(
                nl_input="test",
                document_text=None,
                target_url="http://x.com",
                techniques=["boundary_value"],
            )

            assert len(cases) == 1
            assert cases[0]["title"] == "AI 생성 케이스"

    def test_generate_cases_http_failure(self):
        import httpx
        from core.ai_client import call_generate_cases, AIServiceError

        with patch("core.ai_client.settings") as mock_settings, \
             patch("httpx.Client") as MockClient:
            mock_settings.AI_SERVICE_MOCK = False
            mock_settings.AI_SERVICE_URL = "http://ai:9000"
            mock_settings.AI_SERVICE_TIMEOUT = 60

            MockClient.return_value.__enter__.return_value.post.side_effect = \
                httpx.RequestError("Connection refused")

            with pytest.raises(AIServiceError, match="연결 실패"):
                call_generate_cases(
                    nl_input="test",
                    document_text=None,
                    target_url="http://x.com",
                    techniques=["boundary_value"],
                )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /test-cases/generate (비동기 위임 검증)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestGenerateAsync:
    @pytest.mark.asyncio
    async def test_generate_returns_job_id(self, mock_mongo, mock_ai_celery, mock_redis_status):
        """generate가 placeholder + job_id 반환"""
        await mock_mongo.projects.insert_one({
            "project_id": "p1", "name": "T", "base_url": "http://x.com",
        })

        with patch("api.test_cases.get_projects_collection", return_value=mock_mongo.projects), \
             patch("api.test_cases.get_documents_collection", return_value=mock_mongo.uploaded_documents), \
             patch("api.test_cases.get_test_cases_collection", return_value=mock_mongo.test_cases):

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/test-cases/generate", json={
                    "project_id": "p1",
                    "nl_input": "로그인 테스트",
                    "techniques": ["equivalence_partition", "boundary_value"],
                })

        assert response.status_code == 201
        data = response.json()["data"]

        # job_id가 발급됐는지
        assert data["job_id"].startswith("aijob-")

        # placeholder가 만들어졌는지
        assert len(data["placeholder_test_case_ids"]) == 2
        assert data["status"] == "QUEUED"

        # WebSocket URL 안내
        assert data["ws_url"] == f"/ws/v1/tests/{data['job_id']}/logs"

        # Celery에 위임됐는지 (mock 호출 횟수)
        assert mock_ai_celery.id == "celery-ai-task-id"

        # DB에 placeholder가 저장됐는지
        count = await mock_mongo.test_cases.count_documents({"project_id": "p1"})
        assert count == 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /ai/regenerate-code
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestRegenerateAPI:
    @pytest.mark.asyncio
    async def test_regenerate_returns_job_id(self, mock_mongo, mock_ai_celery, mock_redis_status):
        """기존 케이스 + 새 URL → job_id 반환"""
        await mock_mongo.test_cases.insert_one({
            "test_case_id": "tc-001",
            "project_id": "p1",
            "title": "로그인",
            "steps": [{"step_no": 1, "action": "click", "target": "#x"}],
            "target_urls": ["https://shopA.com"],
        })

        with patch("api.ai.get_test_cases_collection", return_value=mock_mongo.test_cases):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/ai/regenerate-code", json={
                    "test_case_id": "tc-001",
                    "new_target_url": "https://shopB.com",
                })

        assert response.status_code == 202
        data = response.json()["data"]
        assert data["job_id"].startswith("aijob-")
        assert data["status"] == "QUEUED"

    @pytest.mark.asyncio
    async def test_regenerate_not_found(self, mock_mongo):
        """존재하지 않는 케이스 → 404"""
        with patch("api.ai.get_test_cases_collection", return_value=mock_mongo.test_cases):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/ai/regenerate-code", json={
                    "test_case_id": "tc-nonexistent",
                    "new_target_url": "https://x.com",
                })

        assert response.status_code == 404
        assert "TEST_CASE_NOT_FOUND" in response.text

    @pytest.mark.asyncio
    async def test_regenerate_no_steps(self, mock_mongo):
        """steps 없는 케이스 → 400"""
        await mock_mongo.test_cases.insert_one({
            "test_case_id": "tc-empty",
            "title": "빈 케이스",
            "steps": [],
        })

        with patch("api.ai.get_test_cases_collection", return_value=mock_mongo.test_cases):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/ai/regenerate-code", json={
                    "test_case_id": "tc-empty",
                    "new_target_url": "https://x.com",
                })

        assert response.status_code == 400
        assert "NO_STEPS" in response.text


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /ai/jobs/{id}
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAIJobStatus:
    @pytest.mark.asyncio
    async def test_get_job_status(self):
        mock_redis_data = {
            "status": "RUNNING",
            "job_type": "ai_generation",
            "started_at": "2026-04-19T10:00:00Z",
        }

        with patch("api.ai.get_test_run_status", new=AsyncMock(return_value=mock_redis_data)):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/ai/jobs/aijob-test")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "RUNNING"
        assert data["job_type"] == "ai_generation"

    @pytest.mark.asyncio
    async def test_get_job_not_found(self):
        with patch("api.ai.get_test_run_status", new=AsyncMock(return_value=None)):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/ai/jobs/aijob-nonexistent")

        assert response.status_code == 404


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /ai/health
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAIHealth:
    @pytest.mark.asyncio
    async def test_health_check_endpoint(self):
        with patch("api.ai.ai_health_check", return_value=True):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/ai/health")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["ai_service_healthy"] is True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Celery Task 등록 검증
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestAITaskRegistration:
    def test_ai_tasks_registered(self):
        from core.celery_app import celery_app
        import tasks.ai_generation  # noqa
        import tasks.test_runner  # noqa

        registered = celery_app.tasks
        assert "tasks.ai_generation.generate_test_cases_task" in registered
        assert "tasks.ai_generation.regenerate_code_task" in registered

    def test_ai_queue_routing(self):
        from core.celery_app import celery_app
        routes = celery_app.conf.task_routes
        assert routes["tasks.ai_generation.*"]["queue"] == "ai_generation"

"""
API 통합 테스트
───────────────
FastAPI 엔드포인트를 AsyncClient로 직접 호출하고 Mock MongoDB를 주입하여 검증한다.
팀 연동 관점에서 실제로 잘 동작하는지 확인한다.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Fixtures — Mock DB + Mock Celery
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.fixture
def mock_mongo():
    """AsyncMongoMockClient 기반 MongoDB 인메모리"""
    try:
        from mongomock_motor import AsyncMongoMockClient
    except ImportError:
        pytest.skip("mongomock_motor 미설치")

    client = AsyncMongoMockClient()
    return client["test_db"]


@pytest.fixture
def mock_celery_task():
    """execute_test.apply_async를 Mock으로 대체"""
    mock_result = AsyncMock()
    mock_result.id = "celery-task-mock-id"

    with patch("tasks.test_runner.execute_test.apply_async", return_value=mock_result):
        yield mock_result


@pytest.fixture
def mock_redis_set():
    """set_test_run_status를 Mock으로 대체"""
    with patch("api.test_execution.set_test_run_status", new=AsyncMock()) as m:
        yield m


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /scenarios 엔드포인트 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestScenarioCreate:
    """POST /api/v1/scenarios"""

    @pytest.mark.asyncio
    async def test_create_scenario_with_existing_project(self, mock_mongo):
        """프로젝트 있을 때 시나리오 생성 성공"""
        await mock_mongo.projects.insert_one({
            "project_id": "proj-001",
            "name": "Test Project",
            "base_url": "http://localhost:3000",
        })

        with patch("api.scenarios.get_projects_collection", return_value=mock_mongo.projects), \
             patch("api.scenarios.get_scenarios_collection", return_value=mock_mongo.scenarios):

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/scenarios", json={
                    "project_id": "proj-001",
                    "title": "로그인 테스트",
                    "nl_prompt": "admin으로 로그인",
                })

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["scenario_id"].startswith("scen-")
        assert data["data"]["title"] == "로그인 테스트"

        # 실제 DB에 저장됐는지
        saved = await mock_mongo.scenarios.find_one({"scenario_id": data["data"]["scenario_id"]})
        assert saved is not None
        assert saved["nl_prompt"] == "admin으로 로그인"

    @pytest.mark.asyncio
    async def test_create_scenario_without_project_fails(self, mock_mongo):
        """존재하지 않는 프로젝트 ID → 404"""
        with patch("api.scenarios.get_projects_collection", return_value=mock_mongo.projects), \
             patch("api.scenarios.get_scenarios_collection", return_value=mock_mongo.scenarios):

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/scenarios", json={
                    "project_id": "proj-nonexistent",
                    "title": "Test",
                    "nl_prompt": "do something",
                })

        assert response.status_code == 404
        assert "PROJECT_NOT_FOUND" in response.text

    @pytest.mark.asyncio
    async def test_create_scenario_with_ai_result(self, mock_mongo):
        """AI가 이미 코드를 생성한 경우 함께 저장"""
        await mock_mongo.projects.insert_one({
            "project_id": "proj-002",
            "name": "Test",
            "base_url": "http://localhost:3000",
        })

        with patch("api.scenarios.get_projects_collection", return_value=mock_mongo.projects), \
             patch("api.scenarios.get_scenarios_collection", return_value=mock_mongo.scenarios):

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/scenarios", json={
                    "project_id": "proj-002",
                    "title": "AI 테스트",
                    "nl_prompt": "검색하기",
                    "generated_code": "import { test } from '@playwright/test';",
                    "ai_validation": {"is_valid": True, "retry_count": 0},
                })

        assert response.status_code == 201
        data = response.json()
        assert data["data"]["generated_code"] is not None
        assert data["data"]["ai_validation"]["is_valid"] is True


class TestScenarioUpdateCode:
    """POST /api/v1/scenarios/{id}/code"""

    @pytest.mark.asyncio
    async def test_update_code(self, mock_mongo):
        """AI팀이 생성한 코드를 나중에 업데이트"""
        await mock_mongo.scenarios.insert_one({
            "scenario_id": "scen-abc",
            "project_id": "proj-001",
            "title": "Test",
            "nl_prompt": "do something",
        })

        with patch("api.scenarios.get_scenarios_collection", return_value=mock_mongo.scenarios):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/scenarios/scen-abc/code",
                    json={
                        "generated_code": "import { test } from '@playwright/test';\ntest('...', async ({ page }) => {});",
                        "ai_validation": {"is_valid": True, "retry_count": 1, "message": "ok"},
                    },
                )

        assert response.status_code == 200

        # 업데이트 확인
        updated = await mock_mongo.scenarios.find_one({"scenario_id": "scen-abc"})
        assert "import" in updated["generated_code"]
        assert updated["ai_validation"]["retry_count"] == 1


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /tests/execute 엔드포인트 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestExecuteAdhoc:
    """POST /api/v1/tests/execute"""

    @pytest.mark.asyncio
    async def test_execute_with_steps_dsl(self, mock_mongo, mock_celery_task, mock_redis_set):
        """Step DSL 방식으로 즉시 실행"""
        with patch("api.test_execution.get_test_runs_collection", return_value=mock_mongo.test_runs):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/tests/execute", json={
                    "url": "http://localhost:3000/login",
                    "title": "로그인 즉시 실행",
                    "steps": [
                        {"action": "fill", "target": "#username", "value": "admin"},
                        {"action": "fill", "target": "#password", "value": "1234"},
                        {"action": "click", "target": "button[type=submit]"},
                        {"action": "assert_url", "value": "/dashboard"},
                    ],
                })

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["test_run_id"].startswith("run-")
        assert data["data"]["celery_task_id"] == "celery-task-mock-id"
        assert "ws_url" in data["data"]

        # 컴파일된 Playwright 코드가 포함됨
        code = data["data"]["generated_code"]
        assert "await page.fill('#username', 'admin')" in code
        assert "await page.click('button[type=submit]')" in code

    @pytest.mark.asyncio
    async def test_execute_with_raw_code(self, mock_mongo, mock_celery_task, mock_redis_set):
        """Playwright 코드 직접 넘기기"""
        raw_code = "import { test } from '@playwright/test';\ntest('t', async ({ page }) => {});"

        with patch("api.test_execution.get_test_runs_collection", return_value=mock_mongo.test_runs):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/tests/execute", json={
                    "url": "http://localhost:3000",
                    "generated_code": raw_code,
                })

        assert response.status_code == 202
        data = response.json()
        assert data["data"]["generated_code"] == raw_code

    @pytest.mark.asyncio
    async def test_execute_without_steps_or_code_fails(self, mock_mongo):
        """steps, generated_code 둘 다 없으면 400"""
        with patch("api.test_execution.get_test_runs_collection", return_value=mock_mongo.test_runs):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/tests/execute", json={
                    "url": "http://localhost:3000",
                })

        assert response.status_code == 400
        assert "MISSING_INPUT" in response.text

    @pytest.mark.asyncio
    async def test_execute_with_invalid_action_fails(self, mock_mongo):
        """알 수 없는 action → 400"""
        with patch("api.test_execution.get_test_runs_collection", return_value=mock_mongo.test_runs):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/tests/execute", json={
                    "url": "http://localhost:3000",
                    "steps": [
                        {"action": "magic", "target": "#x"},
                    ],
                })

        assert response.status_code == 400
        assert "INVALID_STEPS" in response.text


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Step Compiler 단위 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestStepCompiler:
    """Step DSL → Playwright 코드 변환기 단위 테스트"""

    def test_compile_basic_login_flow(self):
        from core.step_compiler import compile_steps_to_playwright

        code = compile_steps_to_playwright(
            url="http://example.com/login",
            steps=[
                {"action": "fill", "target": "#id", "value": "admin"},
                {"action": "fill", "target": "#pw", "value": "1234"},
                {"action": "click", "target": "#submit"},
            ],
            test_name="login",
        )

        assert "import { test, expect } from '@playwright/test';" in code
        assert "test('login'," in code
        assert "await page.goto('http://example.com/login');" in code
        assert "await page.fill('#id', 'admin');" in code
        assert "await page.click('#submit');" in code

    def test_compile_with_assertions(self):
        from core.step_compiler import compile_steps_to_playwright

        code = compile_steps_to_playwright(
            url="http://example.com",
            steps=[
                {"action": "assert_url", "value": "/dashboard"},
                {"action": "assert_text", "target": ".welcome", "value": "환영합니다"},
                {"action": "assert_visible", "target": ".logout-btn"},
            ],
        )

        assert "toHaveURL('/dashboard')" in code
        assert "toContainText('환영합니다')" in code
        assert "toBeVisible()" in code

    def test_compile_escapes_quotes_and_backslashes(self):
        """셀렉터/값 안에 따옴표나 역슬래시가 있어도 안전하게 이스케이프"""
        from core.step_compiler import compile_steps_to_playwright

        code = compile_steps_to_playwright(
            url="http://example.com",
            steps=[
                {"action": "fill", "target": "#input", "value": "it's a \"test\""},
            ],
        )

        assert "it\\'s a \"test\"" in code or "it\\'s" in code

    def test_auto_selector_prefix(self):
        """target이 'username' 같은 plain 문자열이면 #username으로 자동 변환"""
        from core.step_compiler import compile_steps_to_playwright

        code = compile_steps_to_playwright(
            url="http://example.com",
            steps=[
                {"action": "fill", "target": "username", "value": "admin"},
            ],
        )

        assert "await page.fill('#username', 'admin');" in code

    def test_validate_missing_action(self):
        from core.step_compiler import validate_steps

        ok, err = validate_steps([{"target": "#x"}])
        assert ok is False
        assert "action" in err

    def test_validate_invalid_action(self):
        from core.step_compiler import validate_steps

        ok, err = validate_steps([{"action": "teleport", "target": "#x"}])
        assert ok is False
        assert "teleport" in err

    def test_validate_fill_requires_value(self):
        from core.step_compiler import validate_steps

        ok, err = validate_steps([{"action": "fill", "target": "#x"}])
        assert ok is False
        assert "value" in err

    def test_validate_click_requires_target(self):
        from core.step_compiler import validate_steps

        ok, err = validate_steps([{"action": "click"}])
        assert ok is False
        assert "target" in err

    def test_validate_valid_steps(self):
        from core.step_compiler import validate_steps

        ok, err = validate_steps([
            {"action": "fill", "target": "#id", "value": "admin"},
            {"action": "click", "target": "#submit"},
        ])
        assert ok is True
        assert err is None

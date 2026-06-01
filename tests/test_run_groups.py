"""
Run Group + Failure Detail 통합 테스트
─────────────────────────────────────
대시보드 화면 핵심 API 검증.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


@pytest.fixture
def mock_mongo():
    try:
        from mongomock_motor import AsyncMongoMockClient
    except ImportError:
        pytest.skip("mongomock_motor 미설치")
    return AsyncMongoMockClient()["test_db"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Error Parser 단위 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestErrorParser:
    """Playwright/HTTP 에러 로그 파싱"""

    def test_http_status_pattern(self):
        """Expected status: 200 / Actual status: 404"""
        from core.error_parser import parse_error_log

        log = """
        Test failed: Get User By ID
        Expected status: 200 OK
        Actual status: 404 Not Found
        Reason: User ID not found in database
        """
        result = parse_error_log(log)

        assert result["expected"] == "200 OK"
        assert result["actual"] == "404 Not Found"
        assert "raw_log" in result

    def test_playwright_assertion(self):
        """expect().toHaveURL 패턴"""
        from core.error_parser import parse_error_log

        log = """
        Error: expect(received).toHaveURL(expected)
        Expected: /dashboard
        Received: /login
            at /tests/login.spec.ts:12:34
        """
        result = parse_error_log(log)

        assert result["expected"] == "/dashboard"
        assert result["actual"] == "/login"

    def test_timeout_pattern(self):
        """Timeout exceeded"""
        from core.error_parser import parse_error_log

        log = "TimeoutError: locator.click: Timeout 30000ms exceeded."
        result = parse_error_log(log)

        assert "30000ms" in result["reason"]
        assert "Timeout" in result["actual"]

    def test_element_not_found(self):
        """locator/element 미발견"""
        from core.error_parser import parse_error_log

        log = "Error: locator.click: '#login-btn' not found"
        result = parse_error_log(log)

        assert "#login-btn" in result["reason"]
        assert "요소" in result["expected"]

    def test_unstructured_fallback(self):
        """패턴 안 맞으면 첫 줄을 reason으로"""
        from core.error_parser import parse_error_log

        log = "Something went terribly wrong\nmore details here"
        result = parse_error_log(log)

        assert result["reason"] is not None
        assert result["raw_log"] is not None

    def test_empty_log(self):
        """빈 로그"""
        from core.error_parser import parse_error_log

        result = parse_error_log("")
        assert result["expected"] is None
        assert result["actual"] is None
        assert result["reason"] is None

    def test_none_log(self):
        from core.error_parser import parse_error_log

        result = parse_error_log(None)
        assert result["expected"] is None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /test-cases/execute-batch가 run_group을 만드는지
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestBatchCreatesRunGroup:
    @pytest.mark.asyncio
    async def test_batch_creates_group(self, mock_mongo):
        """batch 실행 시 run_group이 자동 생성됨"""
        await mock_mongo.test_cases.insert_many([
            {
                "test_case_id": "tc-1",
                "project_id": "p1",
                "title": "케이스1",
                "steps": [{"step_no": 1, "action": "click", "target": "#x"}],
            },
            {
                "test_case_id": "tc-2",
                "project_id": "p1",
                "title": "케이스2",
                "steps": [{"step_no": 1, "action": "click", "target": "#y"}],
            },
        ])

        mock_celery = MagicMock()
        mock_celery.id = "celery-batch"

        with patch("api.test_case_exec.get_test_cases_collection",
                   return_value=mock_mongo.test_cases), \
             patch("api.test_case_exec.get_test_runs_collection",
                   return_value=mock_mongo.test_runs), \
             patch("api.test_case_exec.get_test_run_groups_collection",
                   return_value=mock_mongo.test_run_groups), \
             patch("api.test_case_exec.set_test_run_status", new=AsyncMock()), \
             patch("tasks.test_runner.execute_test.apply_async", return_value=mock_celery):

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/test-cases/execute-batch",
                    json={
                        "test_case_ids": ["tc-1", "tc-2"],
                        "target_url": "https://example.com",
                    },
                )

        assert response.status_code == 202
        data = response.json()["data"]

        # run_group_id 발급
        assert data["run_group_id"].startswith("grp-")
        assert data["dashboard_url"].endswith(data["run_group_id"])
        assert len(data["triggered_test_runs"]) == 2

        # DB에 그룹 생성됨
        group = await mock_mongo.test_run_groups.find_one({"run_group_id": data["run_group_id"]})
        assert group is not None
        assert group["total_count"] == 2
        assert group["target_url"] == "https://example.com"

        # 각 run에 run_group_id 박힘
        runs = await mock_mongo.test_runs.find({"run_group_id": data["run_group_id"]}).to_list(length=10)
        assert len(runs) == 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /dashboard/run-groups/{id} 핵심 API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestRunGroupDashboard:
    @pytest.mark.asyncio
    async def test_run_group_detail_matches_screen(self, mock_mongo):
        """
        화면 시나리오:
        Status: SUCCESS, Total: 5, Passed: 4, Failed: 1, Duration: 5.2s
        """
        # 그룹 생성
        await mock_mongo.test_run_groups.insert_one({
            "run_group_id": "grp-test001",
            "project_id": "p1",
            "target_url": "https://example.com",
            "overall_status": "FAILED",
            "total_count": 5,
            "passed_count": 4,
            "failed_count": 1,
            "error_count": 0,
            "total_duration_ms": 5200,
        })

        # 5개 케이스 + 5개 run
        cases = [
            {"test_case_id": "tc-1", "title": "Login Success",     "technique": "scenario_based"},
            {"test_case_id": "tc-2", "title": "Login Failed",      "technique": "boundary_value"},
            {"test_case_id": "tc-3", "title": "Signup Validation", "technique": "equivalence_partition"},
            {"test_case_id": "tc-4", "title": "Get User By ID",    "technique": "scenario_based"},
            {"test_case_id": "tc-5", "title": "Delete User",       "technique": "error_guessing"},
        ]
        await mock_mongo.test_cases.insert_many(cases)

        runs = [
            {"test_run_id": "r1", "test_case_id": "tc-1", "run_group_id": "grp-test001",
             "status": "PASSED", "duration_ms": 1000},
            {"test_run_id": "r2", "test_case_id": "tc-2", "run_group_id": "grp-test001",
             "status": "PASSED", "duration_ms": 800},
            {"test_run_id": "r3", "test_case_id": "tc-3", "run_group_id": "grp-test001",
             "status": "PASSED", "duration_ms": 1500},
            {"test_run_id": "r4", "test_case_id": "tc-4", "run_group_id": "grp-test001",
             "status": "FAILED", "duration_ms": 1200,
             "failure_detail": {
                 "expected": "200 OK",
                 "actual": "404 Not Found",
                 "reason": "User ID not found",
                 "raw_log": "...",
             }},
            {"test_run_id": "r5", "test_case_id": "tc-5", "run_group_id": "grp-test001",
             "status": "PASSED", "duration_ms": 700},
        ]
        await mock_mongo.test_runs.insert_many(runs)

        with patch("api.dashboard.get_test_run_groups_collection",
                   return_value=mock_mongo.test_run_groups), \
             patch("api.dashboard.get_test_runs_collection",
                   return_value=mock_mongo.test_runs), \
             patch("api.dashboard.get_test_cases_collection",
                   return_value=mock_mongo.test_cases):

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/dashboard/run-groups/grp-test001")

        assert response.status_code == 200
        data = response.json()["data"]

        # ── 상단 요약 (화면 윗부분) ──
        summary = data["summary"]
        assert summary["status"] == "FAILED"
        assert summary["total_tests"] == 5
        assert summary["passed"] == 4
        assert summary["failed"] == 1
        assert summary["duration_seconds"] == 5.2

        # ── 케이스별 결과 (중간 리스트) ──
        test_cases_in_group = data["test_cases"]
        assert len(test_cases_in_group) == 5

        titles = [tc["title"] for tc in test_cases_in_group]
        assert "Login Success" in titles
        assert "Get User By ID" in titles

        # 실패 케이스 식별
        failed = [tc for tc in test_cases_in_group if tc["status"] == "FAILED"]
        assert len(failed) == 1
        assert failed[0]["title"] == "Get User By ID"

        # ── 실패 상세 (하단) ──
        failures = data["failure_details"]
        assert len(failures) == 1
        assert failures[0]["title"] == "Get User By ID"
        assert failures[0]["expected"] == "200 OK"
        assert failures[0]["actual"] == "404 Not Found"
        assert failures[0]["reason"] == "User ID not found"

    @pytest.mark.asyncio
    async def test_run_group_not_found(self, mock_mongo):
        with patch("api.dashboard.get_test_run_groups_collection",
                   return_value=mock_mongo.test_run_groups), \
             patch("api.dashboard.get_test_runs_collection",
                   return_value=mock_mongo.test_runs), \
             patch("api.dashboard.get_test_cases_collection",
                   return_value=mock_mongo.test_cases):

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/dashboard/run-groups/grp-nonexistent")

        assert response.status_code == 404
        assert "RUN_GROUP_NOT_FOUND" in response.text

    @pytest.mark.asyncio
    async def test_list_run_groups(self, mock_mongo):
        """그룹 목록 조회"""
        await mock_mongo.test_run_groups.insert_many([
            {"run_group_id": "grp-1", "project_id": "p1",
             "target_url": "http://x.com", "overall_status": "SUCCESS",
             "total_count": 3, "passed_count": 3},
            {"run_group_id": "grp-2", "project_id": "p1",
             "target_url": "http://x.com", "overall_status": "FAILED",
             "total_count": 5, "passed_count": 4, "failed_count": 1},
        ])

        with patch("api.dashboard.get_test_run_groups_collection",
                   return_value=mock_mongo.test_run_groups):

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/dashboard/run-groups?project_id=p1")

        assert response.status_code == 200
        groups = response.json()["data"]["groups"]
        assert len(groups) == 2

"""
v2 추가 기능 통합 테스트
────────────────────────
기존 test_backend.py, test_api_integration.py는 그대로 두고
v2 신규 엔드포인트/기능만 테스트한다.
"""

import io
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


@pytest.fixture
def mock_mongo():
    try:
        from mongomock_motor import AsyncMongoMockClient
    except ImportError:
        pytest.skip("mongomock_motor 미설치")

    client = AsyncMongoMockClient()
    return client["test_db"]


@pytest.fixture
def mock_celery_task():
    mock_result = AsyncMock()
    mock_result.id = "celery-task-mock-id"
    with patch("tasks.test_runner.execute_test.apply_async", return_value=mock_result):
        yield mock_result


@pytest.fixture
def mock_redis_set():
    with patch("api.test_case_exec.set_test_run_status", new=AsyncMock()) as m:
        yield m


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Exporter 단위 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestExporter:
    """7가지 포맷 내보내기 단위 테스트"""

    SAMPLE_CASES = [{
        "test_case_id": "tc-001",
        "title": "로그인 성공",
        "description": "유효한 ID/PW 입력",
        "precondition": "계정 존재",
        "steps": [
            {"step_no": 1, "action": "fill", "target": "#id", "input": "admin", "expected": ""},
            {"step_no": 2, "action": "click", "target": "#submit", "input": "", "expected": "이동"},
        ],
        "expected_result": "대시보드 표시",
        "priority": "high",
        "technique": "equivalence_partition",
        "category": "login",
    }]

    def test_json(self):
        from core.exporter import export_to_json
        result = export_to_json(self.SAMPLE_CASES)
        data = json.loads(result)
        assert data[0]["test_case_id"] == "tc-001"
        assert len(data[0]["steps"]) == 2

    def test_csv(self):
        from core.exporter import export_to_csv
        result = export_to_csv(self.SAMPLE_CASES)
        assert "tc-001" in result
        assert "로그인 성공" in result
        assert "equivalence_partition" in result

    def test_xlsx(self):
        from core.exporter import export_to_xlsx
        result = export_to_xlsx(self.SAMPLE_CASES)
        # XLSX = ZIP 시그니처 'PK'
        assert result[:2] == b"PK"
        assert len(result) > 1000

    def test_markdown(self):
        from core.exporter import export_to_markdown
        result = export_to_markdown(self.SAMPLE_CASES)
        assert "## tc-001: 로그인 성공" in result
        assert "| 번호 | 액션 |" in result

    def test_yaml(self):
        from core.exporter import export_to_yaml
        result = export_to_yaml(self.SAMPLE_CASES)
        assert "tc-001" in result
        assert "로그인 성공" in result

    def test_playwright(self):
        from core.exporter import export_to_playwright
        result = export_to_playwright(self.SAMPLE_CASES, base_url="http://localhost")
        assert "import { test, expect } from '@playwright/test'" in result
        assert "await page.fill('#id', 'admin')" in result
        assert "await page.click('#submit')" in result

    def test_html(self):
        from core.exporter import export_to_html
        result = export_to_html(self.SAMPLE_CASES)
        assert "<!DOCTYPE html>" in result
        assert "로그인 성공" in result
        assert "equivalence_partition" in result

    def test_dispatcher_unsupported_format(self):
        from core.exporter import export_test_cases
        with pytest.raises(ValueError, match="지원하지 않는 포맷"):
            export_test_cases(self.SAMPLE_CASES, "xml")

    def test_dispatcher_all_formats(self):
        """7개 포맷 모두 에러 없이 실행되는지"""
        from core.exporter import export_test_cases, EXPORTERS
        for fmt in EXPORTERS.keys():
            content, ct, ext = export_test_cases(self.SAMPLE_CASES, fmt)
            assert content  # 비어있지 않음
            assert ct.startswith(("application/", "text/"))
            assert ext.startswith(".")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /documents 엔드포인트 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestDocumentUpload:
    @pytest.mark.asyncio
    async def test_upload_pdf_success(self, mock_mongo, tmp_path):
        """PDF 업로드 성공"""
        await mock_mongo.projects.insert_one({
            "project_id": "proj-001",
            "name": "Test",
            "base_url": "http://localhost",
        })

        with patch("api.documents.get_projects_collection", return_value=mock_mongo.projects), \
             patch("api.documents.get_documents_collection", return_value=mock_mongo.uploaded_documents), \
             patch("core.config.get_settings") as mock_settings:

            mock_settings.return_value.UPLOAD_DIR = str(tmp_path)
            mock_settings.return_value.MAX_UPLOAD_SIZE_MB = 10

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                fake_pdf = b"%PDF-1.4\nfake pdf content"
                response = await client.post(
                    "/api/v1/documents/upload",
                    data={"project_id": "proj-001"},
                    files={"file": ("기획서.pdf", fake_pdf, "application/pdf")},
                )

        assert response.status_code == 201
        data = response.json()
        assert data["data"]["document_id"].startswith("doc-")
        assert data["data"]["file_type"] == "pdf"

    @pytest.mark.asyncio
    async def test_upload_unsupported_extension(self, mock_mongo, tmp_path):
        """지원하지 않는 확장자 → 400"""
        await mock_mongo.projects.insert_one({
            "project_id": "proj-001", "name": "Test", "base_url": "http://localhost",
        })

        with patch("api.documents.get_projects_collection", return_value=mock_mongo.projects), \
             patch("api.documents.get_documents_collection", return_value=mock_mongo.uploaded_documents), \
             patch("core.config.get_settings") as mock_settings:
            mock_settings.return_value.UPLOAD_DIR = str(tmp_path)
            mock_settings.return_value.MAX_UPLOAD_SIZE_MB = 10

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/documents/upload",
                    data={"project_id": "proj-001"},
                    files={"file": ("malware.exe", b"fake", "application/octet-stream")},
                )

        assert response.status_code == 400
        assert "UNSUPPORTED_FILE_TYPE" in response.text

    @pytest.mark.asyncio
    async def test_upload_without_project(self, mock_mongo, tmp_path):
        with patch("api.documents.get_projects_collection", return_value=mock_mongo.projects), \
             patch("api.documents.get_documents_collection", return_value=mock_mongo.uploaded_documents), \
             patch("core.config.get_settings") as mock_settings:
            mock_settings.return_value.UPLOAD_DIR = str(tmp_path)
            mock_settings.return_value.MAX_UPLOAD_SIZE_MB = 10

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/documents/upload",
                    data={"project_id": "proj-nonexistent"},
                    files={"file": ("t.txt", b"hello", "text/plain")},
                )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_extracted_text(self, mock_mongo):
        """AI팀이 파싱 결과를 업데이트"""
        await mock_mongo.uploaded_documents.insert_one({
            "document_id": "doc-xxx",
            "project_id": "proj-001",
            "filename": "test.pdf",
            "file_type": "pdf",
            "file_path": "/tmp/x",
            "file_size_bytes": 100,
        })

        with patch("api.documents.get_documents_collection", return_value=mock_mongo.uploaded_documents):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put(
                    "/api/v1/documents/doc-xxx/extract",
                    json={"extracted_text": "이 기획서는 로그인 기능을 설명합니다..."},
                )

        assert response.status_code == 200
        updated = await mock_mongo.uploaded_documents.find_one({"document_id": "doc-xxx"})
        assert "로그인" in updated["extracted_text"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /test-cases/generate 엔드포인트 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestTestCaseGenerate:
    @pytest.mark.asyncio
    async def test_generate_from_nl_input(self, mock_mongo):
        """자연어 입력으로 케이스 생성"""
        await mock_mongo.projects.insert_one({
            "project_id": "proj-001", "name": "T", "base_url": "http://localhost",
        })

        with patch("api.test_cases.get_projects_collection", return_value=mock_mongo.projects), \
             patch("api.test_cases.get_documents_collection", return_value=mock_mongo.uploaded_documents), \
             patch("api.test_cases.get_test_cases_collection", return_value=mock_mongo.test_cases):

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/test-cases/generate", json={
                    "project_id": "proj-001",
                    "nl_input": "로그인 기능 테스트",
                    "techniques": ["equivalence_partition", "boundary_value"],
                })

        assert response.status_code == 201
        data = response.json()
        assert len(data["data"]["generated_test_case_ids"]) == 2

        # DB에 저장됐는지
        count = await mock_mongo.test_cases.count_documents({"project_id": "proj-001"})
        assert count == 2

    @pytest.mark.asyncio
    async def test_generate_invalid_technique(self, mock_mongo):
        """알 수 없는 기법 → 400"""
        await mock_mongo.projects.insert_one({
            "project_id": "proj-001", "name": "T", "base_url": "http://localhost",
        })

        with patch("api.test_cases.get_projects_collection", return_value=mock_mongo.projects), \
             patch("api.test_cases.get_documents_collection", return_value=mock_mongo.uploaded_documents), \
             patch("api.test_cases.get_test_cases_collection", return_value=mock_mongo.test_cases):

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/test-cases/generate", json={
                    "project_id": "proj-001",
                    "nl_input": "테스트",
                    "techniques": ["magic_technique"],
                })

        assert response.status_code == 400
        assert "INVALID_TECHNIQUE" in response.text

    @pytest.mark.asyncio
    async def test_generate_without_input(self, mock_mongo):
        """nl_input도 document_id도 없으면 400"""
        await mock_mongo.projects.insert_one({
            "project_id": "proj-001", "name": "T", "base_url": "http://localhost",
        })

        with patch("api.test_cases.get_projects_collection", return_value=mock_mongo.projects), \
             patch("api.test_cases.get_documents_collection", return_value=mock_mongo.uploaded_documents), \
             patch("api.test_cases.get_test_cases_collection", return_value=mock_mongo.test_cases):

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/test-cases/generate", json={
                    "project_id": "proj-001",
                    "techniques": ["equivalence_partition"],
                })

        assert response.status_code == 400
        assert "MISSING_INPUT" in response.text


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  테스트 케이스 업데이트 & 재사용
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestTestCaseUpdate:
    @pytest.mark.asyncio
    async def test_update_ai_result(self, mock_mongo):
        """AI팀이 PUT으로 내용 채우기"""
        await mock_mongo.test_cases.insert_one({
            "test_case_id": "tc-001",
            "project_id": "proj-001",
            "title": "[boundary_value] 대기중",
            "steps": [],
        })

        with patch("api.test_cases.get_test_cases_collection", return_value=mock_mongo.test_cases):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put(
                    "/api/v1/test-cases/tc-001",
                    json={
                        "title": "비밀번호 경계값 테스트",
                        "steps": [{"step_no": 1, "action": "fill", "target": "#pw", "input": "123"}],
                        "priority": "high",
                    },
                )

        assert response.status_code == 200
        updated = await mock_mongo.test_cases.find_one({"test_case_id": "tc-001"})
        assert updated["title"] == "비밀번호 경계값 테스트"
        assert updated["priority"] == "high"
        assert len(updated["steps"]) == 1

    @pytest.mark.asyncio
    async def test_update_target_urls_reuse(self, mock_mongo):
        """재사용 — 여러 URL에 적용"""
        await mock_mongo.test_cases.insert_one({
            "test_case_id": "tc-001",
            "project_id": "proj-001",
            "title": "T",
            "target_urls": ["http://dev.com"],
        })

        with patch("api.test_cases.get_test_cases_collection", return_value=mock_mongo.test_cases):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put(
                    "/api/v1/test-cases/tc-001/target-urls",
                    json={"target_urls": ["http://staging.com", "http://prod.com"]},
                )

        assert response.status_code == 200
        updated = await mock_mongo.test_cases.find_one({"test_case_id": "tc-001"})
        assert len(updated["target_urls"]) == 2


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Export 엔드포인트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestExportEndpoint:
    @pytest.mark.asyncio
    async def test_export_json(self, mock_mongo):
        await mock_mongo.test_cases.insert_one({
            "test_case_id": "tc-001",
            "title": "Test",
            "steps": [],
        })

        with patch("api.test_cases.get_test_cases_collection", return_value=mock_mongo.test_cases):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/test-cases/export",
                    json={"test_case_ids": ["tc-001"], "format": "json"},
                )

        assert response.status_code == 200
        assert "attachment" in response.headers.get("content-disposition", "")
        data = json.loads(response.text)
        assert data[0]["test_case_id"] == "tc-001"

    @pytest.mark.asyncio
    async def test_export_xlsx(self, mock_mongo):
        await mock_mongo.test_cases.insert_one({
            "test_case_id": "tc-001",
            "title": "Test",
            "steps": [{"step_no": 1, "action": "click", "target": "#x", "input": "", "expected": ""}],
        })

        with patch("api.test_cases.get_test_cases_collection", return_value=mock_mongo.test_cases):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/test-cases/export",
                    json={"test_case_ids": ["tc-001"], "format": "xlsx"},
                )

        assert response.status_code == 200
        # XLSX ZIP 시그니처
        assert response.content[:2] == b"PK"

    @pytest.mark.asyncio
    async def test_export_not_found(self, mock_mongo):
        with patch("api.test_cases.get_test_cases_collection", return_value=mock_mongo.test_cases):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/test-cases/export",
                    json={"test_case_ids": ["tc-nonexistent"], "format": "json"},
                )

        assert response.status_code == 404


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /test-cases/{id}/execute 엔드포인트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestTestCaseExecute:
    @pytest.mark.asyncio
    async def test_execute_with_steps(self, mock_mongo, mock_celery_task, mock_redis_set):
        """steps만 있는 케이스 → 자동 컴파일 후 실행"""
        await mock_mongo.test_cases.insert_one({
            "test_case_id": "tc-001",
            "project_id": "proj-001",
            "title": "로그인",
            "steps": [
                {"step_no": 1, "action": "fill", "target": "#id", "input": "admin", "expected": ""},
                {"step_no": 2, "action": "click", "target": "#submit", "input": "", "expected": ""},
            ],
        })

        with patch("api.test_case_exec.get_test_cases_collection", return_value=mock_mongo.test_cases), \
             patch("api.test_case_exec.get_test_runs_collection", return_value=mock_mongo.test_runs):

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/test-cases/tc-001/execute",
                    json={"test_case_id": "tc-001", "target_url": "http://prod.example.com"},
                )

        assert response.status_code == 202
        data = response.json()
        assert data["data"]["test_run_id"].startswith("run-")
        assert data["data"]["target_url"] == "http://prod.example.com"

    @pytest.mark.asyncio
    async def test_execute_no_content(self, mock_mongo):
        """steps도 playwright_code도 없으면 400"""
        await mock_mongo.test_cases.insert_one({
            "test_case_id": "tc-empty",
            "project_id": "proj-001",
            "title": "빈 케이스",
            "steps": [],
        })

        with patch("api.test_case_exec.get_test_cases_collection", return_value=mock_mongo.test_cases), \
             patch("api.test_case_exec.get_test_runs_collection", return_value=mock_mongo.test_runs):

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/test-cases/tc-empty/execute",
                    json={"test_case_id": "tc-empty", "target_url": "http://x.com"},
                )

        assert response.status_code == 400
        assert "NO_EXECUTABLE_CONTENT" in response.text


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /dashboard 엔드포인트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestDashboard:
    @pytest.mark.asyncio
    async def test_summary_empty(self, mock_mongo):
        """데이터 없을 때 기본값"""
        with patch("api.dashboard.get_test_cases_collection", return_value=mock_mongo.test_cases), \
             patch("api.dashboard.get_test_runs_collection", return_value=mock_mongo.test_runs):

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/dashboard/summary")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_cases"] == 0
        assert data["pass_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_summary_with_data(self, mock_mongo):
        """성공/실패 집계"""
        await mock_mongo.test_cases.insert_one({"test_case_id": "tc-1", "project_id": "p1"})
        await mock_mongo.test_runs.insert_many([
            {"test_run_id": "r1", "test_case_id": "tc-1", "status": "PASSED"},
            {"test_run_id": "r2", "test_case_id": "tc-1", "status": "PASSED"},
            {"test_run_id": "r3", "test_case_id": "tc-1", "status": "FAILED"},
        ])

        with patch("api.dashboard.get_test_cases_collection", return_value=mock_mongo.test_cases), \
             patch("api.dashboard.get_test_runs_collection", return_value=mock_mongo.test_runs):

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/dashboard/summary")

        data = response.json()["data"]
        assert data["total_cases"] == 1
        assert data["total_runs"] == 3
        assert data["passed"] == 2
        assert data["failed"] == 1
        # 2/3 = 66.7%
        assert data["pass_rate"] == 66.7

    @pytest.mark.asyncio
    async def test_recent_runs_with_failure(self, mock_mongo):
        """실패 건은 error_log 포함"""
        await mock_mongo.test_cases.insert_one({
            "test_case_id": "tc-1", "title": "로그인", "technique": "boundary_value",
        })
        await mock_mongo.test_runs.insert_one({
            "test_run_id": "r1",
            "test_case_id": "tc-1",
            "target_url": "http://x.com",
            "status": "FAILED",
            "error_log": "AssertionError: element not found",
        })

        with patch("api.dashboard.get_test_cases_collection", return_value=mock_mongo.test_cases), \
             patch("api.dashboard.get_test_runs_collection", return_value=mock_mongo.test_runs):

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/dashboard/recent-runs")

        assert response.status_code == 200
        runs = response.json()["data"]["runs"]
        assert len(runs) == 1
        assert runs[0]["status"] == "FAILED"
        assert "AssertionError" in runs[0]["error_log"]
        assert runs[0]["title"] == "로그인"

    @pytest.mark.asyncio
    async def test_by_technique_stats(self, mock_mongo):
        """기법별 집계"""
        await mock_mongo.test_cases.insert_many([
            {"test_case_id": "tc-1", "project_id": "p1", "technique": "boundary_value"},
            {"test_case_id": "tc-2", "project_id": "p1", "technique": "boundary_value"},
            {"test_case_id": "tc-3", "project_id": "p1", "technique": "equivalence_partition"},
        ])

        with patch("api.dashboard.get_test_cases_collection", return_value=mock_mongo.test_cases):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/dashboard/by-technique")

        stats = response.json()["data"]["by_technique"]
        by_tech = {s["technique"]: s["count"] for s in stats}
        assert by_tech["boundary_value"] == 2
        assert by_tech["equivalence_partition"] == 1


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  /projects 엔드포인트 (팀 진입 필수)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestProjects:
    @pytest.mark.asyncio
    async def test_create_project(self, mock_mongo):
        """프로젝트 생성"""
        with patch("api.projects.get_projects_collection", return_value=mock_mongo.projects):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/api/v1/projects", json={
                    "name": "사내 인트라넷",
                    "base_url": "https://intranet.example.com",
                    "description": "팀 내부 테스트",
                })

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["project_id"].startswith("proj-")
        assert data["name"] == "사내 인트라넷"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, mock_mongo):
        with patch("api.projects.get_projects_collection", return_value=mock_mongo.projects):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/projects/proj-nonexistent")

        assert response.status_code == 404
        assert "PROJECT_NOT_FOUND" in response.text

    @pytest.mark.asyncio
    async def test_list_projects(self, mock_mongo):
        await mock_mongo.projects.insert_many([
            {"project_id": "p1", "name": "A", "base_url": "http://a.com"},
            {"project_id": "p2", "name": "B", "base_url": "http://b.com"},
        ])

        with patch("api.projects.get_projects_collection", return_value=mock_mongo.projects):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/api/v1/projects")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_update_project(self, mock_mongo):
        await mock_mongo.projects.insert_one({
            "project_id": "p1", "name": "Old", "base_url": "http://old.com",
        })

        with patch("api.projects.get_projects_collection", return_value=mock_mongo.projects):
            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.put("/api/v1/projects/p1", json={
                    "name": "New",
                    "base_url": "http://new.com",
                })

        assert response.status_code == 200
        updated = await mock_mongo.projects.find_one({"project_id": "p1"})
        assert updated["name"] == "New"
        assert updated["base_url"] == "http://new.com"

    @pytest.mark.asyncio
    async def test_delete_project_with_orphan_report(self, mock_mongo):
        """삭제 시 고아로 남는 문서/케이스 수 리포트"""
        await mock_mongo.projects.insert_one({
            "project_id": "p-del", "name": "삭제대상", "base_url": "http://x.com",
        })
        await mock_mongo.uploaded_documents.insert_many([
            {"document_id": "d1", "project_id": "p-del"},
            {"document_id": "d2", "project_id": "p-del"},
        ])
        await mock_mongo.test_cases.insert_one({
            "test_case_id": "tc1", "project_id": "p-del",
        })

        with patch("api.projects.get_projects_collection", return_value=mock_mongo.projects), \
             patch("api.projects.get_documents_collection", return_value=mock_mongo.uploaded_documents), \
             patch("api.projects.get_test_cases_collection", return_value=mock_mongo.test_cases), \
             patch("api.projects.get_scenarios_collection", return_value=mock_mongo.scenarios):

            from main import app
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.delete("/api/v1/projects/p-del")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["orphaned"]["documents"] == 2
        assert data["orphaned"]["test_cases"] == 1

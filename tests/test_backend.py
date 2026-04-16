"""
ATe Backend 테스트 (MongoDB 버전)
──────────────────────────────────
Redis/Celery, WebSocket, CI/CD API, MongoDB 통합 테스트
"""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# backend 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from core.redis_client import (
    publish_test_log,
    get_test_log_history,
    set_test_run_status,
    get_test_run_status,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Fixtures
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.fixture
def mock_redis():
    """Redis를 Mock으로 대체"""
    storage = {}
    lists = {}
    published = []

    mock = AsyncMock()
    mock.hset = AsyncMock(side_effect=lambda key, mapping: storage.update({key: mapping}))
    mock.hgetall = AsyncMock(side_effect=lambda key: storage.get(key, {}))
    mock.expire = AsyncMock()
    mock.rpush = AsyncMock(side_effect=lambda key, val: lists.setdefault(key, []).append(val))
    mock.lrange = AsyncMock(side_effect=lambda key, s, e: lists.get(key, []))
    mock.publish = AsyncMock(side_effect=lambda ch, msg: published.append((ch, msg)))
    mock.ping = AsyncMock()

    mock._storage = storage
    mock._lists = lists
    mock._published = published

    return mock


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Redis 상태 관리 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestRedisStatusManagement:

    @pytest.mark.asyncio
    async def test_set_and_get_status(self, mock_redis):
        with patch("core.redis_client._redis_pool", mock_redis):
            await set_test_run_status("run-001", "QUEUED")
            status = await get_test_run_status("run-001")
            assert status["status"] == "QUEUED"

    @pytest.mark.asyncio
    async def test_status_transition(self, mock_redis):
        """QUEUED → RUNNING → SUCCESS 상태 전이"""
        with patch("core.redis_client._redis_pool", mock_redis):
            await set_test_run_status("run-002", "QUEUED")
            await set_test_run_status("run-002", "RUNNING", started_at="2026-04-14T10:00:00Z")
            await set_test_run_status("run-002", "SUCCESS", ended_at="2026-04-14T10:01:00Z")

            status = await get_test_run_status("run-002")
            assert status["status"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_status_with_error(self, mock_redis):
        with patch("core.redis_client._redis_pool", mock_redis):
            await set_test_run_status(
                "run-003", "FAILED",
                error_log="Timeout 30000ms exceeded",
            )
            status = await get_test_run_status("run-003")
            assert status["status"] == "FAILED"
            assert "Timeout" in status["error_log"]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Redis Pub/Sub 로그 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestRedisPubSubLogs:

    @pytest.mark.asyncio
    async def test_publish_log(self, mock_redis):
        """로그가 Pub/Sub 채널 + 히스토리 List에 동시 저장되는지"""
        with patch("core.redis_client._redis_pool", mock_redis):
            log_entry = {
                "timestamp": "2026-04-14T10:00:00Z",
                "level": "INFO",
                "message": "테스트 시작",
                "progress_percentage": 0,
            }
            await publish_test_log("run-100", log_entry)

            assert len(mock_redis._published) == 1
            channel, payload = mock_redis._published[0]
            assert channel == "test_log:run-100"
            parsed = json.loads(payload)
            assert parsed["message"] == "테스트 시작"

            assert len(mock_redis._lists.get("test_log_list:run-100", [])) == 1

    @pytest.mark.asyncio
    async def test_log_history_retrieval(self, mock_redis):
        """재접속 시 로그 히스토리 조회"""
        with patch("core.redis_client._redis_pool", mock_redis):
            for i in range(5):
                await publish_test_log("run-200", {
                    "timestamp": f"2026-04-14T10:0{i}:00Z",
                    "level": "INFO",
                    "message": f"스텝 {i+1}",
                    "progress_percentage": (i + 1) * 20,
                })

            history = await get_test_log_history("run-200")
            assert len(history) == 5
            assert history[0]["message"] == "스텝 1"
            assert history[4]["progress_percentage"] == 100


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Celery Task 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestCeleryTasks:

    def test_task_registration(self):
        """4개 Task가 Celery에 등록되어 있는지"""
        from core.celery_app import celery_app
        # autodiscover 트리거
        import tasks.test_runner  # noqa
        import tasks.ci_cd  # noqa

        registered = celery_app.tasks
        assert "tasks.test_runner.execute_test" in registered
        assert "tasks.ci_cd.send_webhook_callback" in registered
        assert "tasks.ci_cd.generate_allure_report" in registered

    def test_task_routing(self):
        """Task가 올바른 큐로 라우팅되는지"""
        from core.celery_app import celery_app
        routes = celery_app.conf.task_routes
        assert routes["tasks.test_runner.*"]["queue"] == "test_execution"
        assert routes["tasks.ci_cd.*"]["queue"] == "ci_cd"

    def test_celery_config(self):
        from core.celery_app import celery_app
        assert celery_app.conf.task_serializer == "json"
        assert celery_app.conf.worker_prefetch_multiplier == 1
        assert celery_app.conf.task_acks_late is True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MongoDB 스키마 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestMongoSchemas:

    def test_test_run_doc(self):
        """TestRunDoc 문서 생성 및 기본값"""
        from schemas.schemas import TestRunDoc

        doc = TestRunDoc(test_run_id="run-xxx", scenario_id="scen-yyy")
        assert doc.status == "QUEUED"
        assert doc.created_at is not None
        assert doc.celery_task_id is None

    def test_webhook_config_doc(self):
        """WebhookConfigDoc 기본값"""
        from schemas.schemas import WebhookConfigDoc

        doc = WebhookConfigDoc(
            project_id="proj-001",
            provider="github_actions",
        )
        assert doc.trigger_on == ["push"]
        assert doc.is_active is True
        assert doc.secret_token is None

    def test_scenario_doc(self):
        from schemas.schemas import ScenarioDoc

        doc = ScenarioDoc(
            scenario_id="scen-123",
            project_id="proj-001",
            title="로그인 테스트",
            nl_prompt="로그인하기",
        )
        assert doc.generated_code is None
        assert doc.ai_validation is None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CI/CD Webhook 서명 검증 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestWebhookSignature:

    def test_github_signature_generation(self):
        """GitHub HMAC-SHA256 서명 생성"""
        import hashlib
        import hmac

        secret = "test-secret-key"
        body = b'{"ref": "refs/heads/main"}'

        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        expected_header = f"sha256={signature}"

        assert expected_header.startswith("sha256=")
        assert len(signature) == 64

    def test_signature_comparison(self):
        """timing attack 방지 안전 비교"""
        import hashlib
        import hmac

        secret = "my-secret"
        body = b'{"test": true}'

        sig1 = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        sig2 = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        sig_wrong = "sha256=" + hmac.new(b"wrong", body, hashlib.sha256).hexdigest()

        assert hmac.compare_digest(sig1, sig2)
        assert not hmac.compare_digest(sig1, sig_wrong)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  WebSocket 메시지 포맷 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestWebSocketMessageFormat:

    def test_log_message_format(self):
        """API 명세서 §3.3 포맷"""
        from schemas.schemas import TestLogMessage

        msg = TestLogMessage(
            timestamp="2026-04-14T10:00:00Z",
            level="INFO",
            message="Navigating to login page",
            progress_percentage=25,
        )
        data = msg.model_dump()
        assert data["timestamp"] == "2026-04-14T10:00:00Z"
        assert data["level"] == "INFO"
        assert data["progress_percentage"] == 25

    def test_progress_validation(self):
        """progress_percentage 0~100 범위 검증"""
        from schemas.schemas import TestLogMessage
        from pydantic import ValidationError

        msg = TestLogMessage(
            timestamp="2026-04-14T10:00:00Z",
            level="SUCCESS",
            message="done",
            progress_percentage=100,
        )
        assert msg.progress_percentage == 100

        with pytest.raises(ValidationError):
            TestLogMessage(
                timestamp="2026-04-14T10:00:00Z",
                level="INFO",
                message="test",
                progress_percentage=150,
            )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MongoDB Mock 통합 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestMongoIntegration:
    """mongomock-motor를 사용한 MongoDB 인메모리 테스트"""

    @pytest.mark.asyncio
    async def test_insert_and_query_test_run(self):
        """TestRun 문서를 저장하고 조회할 수 있는지"""
        try:
            from mongomock_motor import AsyncMongoMockClient
        except ImportError:
            pytest.skip("mongomock_motor 미설치")

        from schemas.schemas import TestRunDoc

        client = AsyncMongoMockClient()
        db = client["test_db"]

        doc = TestRunDoc(test_run_id="run-abc", scenario_id="scen-xyz")
        await db.test_runs.insert_one(doc.model_dump())

        found = await db.test_runs.find_one({"test_run_id": "run-abc"})
        assert found is not None
        assert found["status"] == "QUEUED"
        assert found["scenario_id"] == "scen-xyz"

    @pytest.mark.asyncio
    async def test_update_status(self):
        """상태 업데이트가 반영되는지"""
        try:
            from mongomock_motor import AsyncMongoMockClient
        except ImportError:
            pytest.skip("mongomock_motor 미설치")

        from schemas.schemas import TestRunDoc

        client = AsyncMongoMockClient()
        db = client["test_db"]

        doc = TestRunDoc(test_run_id="run-update", scenario_id="scen-001")
        await db.test_runs.insert_one(doc.model_dump())

        await db.test_runs.update_one(
            {"test_run_id": "run-update"},
            {"$set": {"status": "RUNNING"}},
        )

        updated = await db.test_runs.find_one({"test_run_id": "run-update"})
        assert updated["status"] == "RUNNING"

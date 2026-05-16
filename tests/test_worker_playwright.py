"""
워커 내부 Playwright 실행 테스트
─────────────────────────────────
Docker-in-Docker 없이 워커 컨테이너 안에서 직접 실행되는지 확인.

CI 환경(npx 없음)에서도 돌아가도록 subprocess를 mock한다.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  _run_in_worker 단위 테스트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestRunInWorker:
    """워커 내부에서 직접 Playwright 실행하는 새 함수 검증"""

    def test_function_exists(self):
        """_run_in_worker 함수가 test_runner에 존재"""
        from tasks.test_runner import _run_in_worker
        assert callable(_run_in_worker)

    def test_old_docker_functions_removed(self):
        """_run_in_docker / _run_fallback 제거됨"""
        import tasks.test_runner as tr
        assert not hasattr(tr, "_run_in_docker"), "_run_in_docker는 옵션 2에서 제거됐어야 함"
        assert not hasattr(tr, "_run_fallback"), "_run_fallback도 제거됐어야 함"

    def test_run_with_mocked_subprocess_success(self, tmp_path):
        """Playwright 성공 케이스 (subprocess mock)"""
        from tasks.test_runner import _run_in_worker

        # 가짜 spec 파일
        (tmp_path / "test_generated.spec.ts").write_text("// fake spec")

        mock_redis = MagicMock()

        # subprocess.Popen 모킹: stdout 라인 + exit 0
        mock_proc = MagicMock()
        mock_proc.stdout = iter([
            "Running 1 test using 1 worker\n",
            "  ✓ login passed (1.2s)\n",
            "1 passed\n",
        ])
        mock_proc.wait.return_value = 0

        with patch.dict(os.environ, {"PLAYWRIGHT_RUNNER_DIR": str(tmp_path)}, clear=False), \
             patch("subprocess.Popen", return_value=mock_proc):

            result = _run_in_worker(
                mock_redis, "run-test", str(tmp_path), "https://example.com",
            )

        assert result["exit_code"] == 0
        assert "passed" in result["stdout"]

        # 로그가 Redis로 발행됐는지
        assert mock_redis.publish.call_count >= 1

    def test_run_with_mocked_subprocess_failure(self, tmp_path):
        """Playwright 실패 케이스 (exit code 1)"""
        from tasks.test_runner import _run_in_worker

        (tmp_path / "test_generated.spec.ts").write_text("// fake spec")

        mock_redis = MagicMock()
        mock_proc = MagicMock()
        mock_proc.stdout = iter([
            "Running 1 test\n",
            "  ✗ login failed\n",
            "Error: locator.click: '#login-btn' not found\n",
        ])
        mock_proc.wait.return_value = 1

        with patch.dict(os.environ, {"PLAYWRIGHT_RUNNER_DIR": str(tmp_path)}, clear=False), \
             patch("subprocess.Popen", return_value=mock_proc):

            result = _run_in_worker(
                mock_redis, "run-test", str(tmp_path), "https://example.com",
            )

        assert result["exit_code"] == 1
        assert result["stderr"]  # 실패 시 stderr 채워짐
        assert "not found" in result["stderr"]

    def test_run_npx_missing(self, tmp_path):
        """npx가 없으면 명확한 에러 반환"""
        from tasks.test_runner import _run_in_worker

        (tmp_path / "test_generated.spec.ts").write_text("// fake spec")

        with patch.dict(os.environ, {"PLAYWRIGHT_RUNNER_DIR": str(tmp_path)}, clear=False), \
             patch("subprocess.Popen", side_effect=FileNotFoundError("npx not found")):

            result = _run_in_worker(
                MagicMock(), "run-test", str(tmp_path), "https://example.com",
            )

        assert result["exit_code"] == 1
        assert "npx" in result["stderr"] or "playwright" in result["stderr"]

    def test_spec_file_missing(self, tmp_path):
        """spec 파일이 없으면 에러"""
        from tasks.test_runner import _run_in_worker

        # spec 파일 안 만듦 → src에 없음
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        runner_dir = tmp_path / "runner"
        runner_dir.mkdir()

        with patch.dict(os.environ, {"PLAYWRIGHT_RUNNER_DIR": str(runner_dir)}, clear=False):
            result = _run_in_worker(
                MagicMock(), "run-test", str(empty_dir), "https://example.com",
            )

        assert result["exit_code"] == 1
        assert "spec" in result["stderr"].lower() or "없음" in result["stderr"]

    def test_timeout_handled(self, tmp_path):
        """타임아웃 발생 시 명확한 에러 반환"""
        import subprocess
        from tasks.test_runner import _run_in_worker

        (tmp_path / "test_generated.spec.ts").write_text("// fake spec")

        mock_proc = MagicMock()
        mock_proc.stdout = iter([])
        mock_proc.wait.side_effect = subprocess.TimeoutExpired(cmd="npx", timeout=30)
        mock_proc.kill = MagicMock()

        with patch.dict(os.environ, {"PLAYWRIGHT_RUNNER_DIR": str(tmp_path)}, clear=False), \
             patch("subprocess.Popen", return_value=mock_proc):

            result = _run_in_worker(
                MagicMock(), "run-test", str(tmp_path), "https://example.com",
            )

        assert result["exit_code"] == 1
        assert "타임아웃" in result["stderr"]
        mock_proc.kill.assert_called_once()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Worker Dockerfile 검증
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestWorkerDockerfile:
    """Dockerfile에 Playwright 베이스 이미지가 설정됐는지"""

    def test_uses_playwright_base_image(self):
        repo_root = Path(__file__).resolve().parent.parent
        dockerfile = repo_root / "worker" / "Dockerfile"
        content = dockerfile.read_text(encoding="utf-8")

        assert "playwright" in content.lower()
        assert "FROM mcr.microsoft.com/playwright" in content

    def test_python_installed(self):
        repo_root = Path(__file__).resolve().parent.parent
        dockerfile = repo_root / "worker" / "Dockerfile"
        content = dockerfile.read_text(encoding="utf-8")

        # Playwright 이미지에 Python 추가됐는지
        assert "python3.12" in content or "python3" in content
        assert "requirements.txt" in content

    def test_playwright_runner_setup(self):
        repo_root = Path(__file__).resolve().parent.parent
        runner_pkg = repo_root / "worker" / "playwright-runner" / "package.json"
        runner_cfg = repo_root / "worker" / "playwright-runner" / "playwright.config.ts"

        assert runner_pkg.exists(), "package.json 필요"
        assert runner_cfg.exists(), "playwright.config.ts 필요"

        pkg_content = runner_pkg.read_text()
        assert "@playwright/test" in pkg_content

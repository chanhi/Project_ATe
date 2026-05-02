"""
Celery Task: 테스트 실행
────────────────────────
Docker 컨테이너에서 Playwright 실행 + Redis Pub/Sub 실시간 로그
"""

import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import redis as sync_redis
from pymongo import MongoClient

from core.celery_app import celery_app
from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_sync_redis():
    """Celery Worker는 동기 Redis 클라이언트 사용"""
    return sync_redis.from_url(settings.REDIS_URL, decode_responses=True)


def _get_sync_mongo():
    """Celery Worker는 동기 MongoDB 클라이언트 사용"""
    client = MongoClient(settings.MONGO_URL)
    return client, client[settings.DB_NAME]


def _publish_log(r, test_run_id, level, message, progress):
    """동기적으로 Redis에 로그 발행"""
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        "progress_percentage": progress,
    }
    payload = json.dumps(log_entry, ensure_ascii=False)
    r.publish(f"test_log:{test_run_id}", payload)
    r.rpush(f"test_log_list:{test_run_id}", payload)
    r.expire(f"test_log_list:{test_run_id}", 86400)


def _update_status(r, test_run_id, status, **extra):
    """Redis에 상태 캐시 업데이트"""
    key = f"test_run:{test_run_id}"
    data = {"status": status}
    for k, v in extra.items():
        data[k] = str(v)
    r.hset(key, mapping=data)
    r.expire(key, 86400)


def _update_mongo_status(db, test_run_id, status, **extra):
    """MongoDB에 상태 업데이트"""
    update_fields = {"status": status, **extra}
    db.test_runs.update_one(
        {"test_run_id": test_run_id},
        {"$set": update_fields},
    )


def _update_run_group_aggregate(db, test_run_id):
    """
    test_run이 끝나면 속한 run_group의 집계를 업데이트한다.
    PASSED/FAILED/ERROR 카운트 + duration 합산 + 전체 status 결정.
    """
    run = db.test_runs.find_one({"test_run_id": test_run_id})
    if not run or not run.get("run_group_id"):
        return

    group_id = run["run_group_id"]

    # 그룹의 모든 run을 가져와 집계
    runs = list(db.test_runs.find({"run_group_id": group_id}))
    total = len(runs)
    passed = sum(1 for r in runs if r.get("status") in ("PASSED", "SUCCESS"))
    failed = sum(1 for r in runs if r.get("status") == "FAILED")
    error = sum(1 for r in runs if r.get("status") == "ERROR")
    pending = sum(1 for r in runs if r.get("status") in ("QUEUED", "PENDING", "RUNNING"))
    total_duration = sum(r.get("duration_ms") or 0 for r in runs)

    # 전체 상태 결정
    if pending > 0:
        overall = "RUNNING"
        ended_at = None
    elif failed + error > 0:
        overall = "FAILED"
        ended_at = datetime.now(timezone.utc)
    else:
        overall = "SUCCESS"
        ended_at = datetime.now(timezone.utc)

    update_fields = {
        "total_count": total,
        "passed_count": passed,
        "failed_count": failed,
        "error_count": error,
        "pending_count": pending,
        "total_duration_ms": total_duration,
        "overall_status": overall,
    }
    if ended_at is not None:
        update_fields["ended_at"] = ended_at

    db.test_run_groups.update_one(
        {"run_group_id": group_id},
        {"$set": update_fields},
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  메인 테스트 실행 Task
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@celery_app.task(
    name="tasks.test_runner.execute_test",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    acks_late=True,
    queue="test_execution",
)
def execute_test(
    self,
    test_run_id: str,
    scenario_id: str,
    generated_code: str,
    base_url: str,
) -> dict:
    """Playwright 테스트를 Docker 컨테이너에서 실행"""
    r = _get_sync_redis()
    mongo_client, db = _get_sync_mongo()
    started_at = datetime.now(timezone.utc)

    try:
        # ── RUNNING ──
        _update_status(r, test_run_id, "RUNNING", started_at=started_at.isoformat())
        _update_mongo_status(db, test_run_id, "RUNNING", started_at=started_at)
        _publish_log(r, test_run_id, "INFO", "테스트 실행 시작", 0)

        # ── 테스트 코드 파일로 저장 ──
        _publish_log(r, test_run_id, "INFO", "테스트 코드 준비 중...", 5)
        test_dir = Path(tempfile.mkdtemp(prefix="ate_test_"))
        test_file = test_dir / "test_generated.spec.ts"
        test_file.write_text(generated_code, encoding="utf-8")
        _publish_log(r, test_run_id, "INFO", f"테스트 파일 생성: {test_file.name}", 10)

        # ── Docker 실행 ──
        _publish_log(r, test_run_id, "INFO", "Docker 컨테이너 초기화 중...", 15)
        container_result = _run_in_docker(r, test_run_id, str(test_dir), base_url)

        ended_at = datetime.now(timezone.utc)
        duration_ms = int((ended_at - started_at).total_seconds() * 1000)

        # ── 결과 처리 ──
        if container_result["exit_code"] == 0:
            _update_status(r, test_run_id, "SUCCESS",
                         ended_at=ended_at.isoformat(), duration_ms=duration_ms)
            _update_mongo_status(db, test_run_id, "SUCCESS",
                               ended_at=ended_at, duration_ms=duration_ms)
            _publish_log(r, test_run_id, "SUCCESS", "✅ 모든 테스트 통과", 100)
            _update_run_group_aggregate(db, test_run_id)
            return {"test_run_id": test_run_id, "status": "SUCCESS", "duration_ms": duration_ms}
        else:
            error_log = container_result.get("stderr", "Unknown error")
            # ── v2.1: 실패 시 구조화된 failure_detail 생성 ──
            from core.error_parser import parse_error_log
            failure_detail = parse_error_log(error_log)

            _update_status(r, test_run_id, "FAILED",
                         ended_at=ended_at.isoformat(), duration_ms=duration_ms,
                         error_log=error_log)
            _update_mongo_status(db, test_run_id, "FAILED",
                               ended_at=ended_at, duration_ms=duration_ms,
                               error_log=error_log,
                               failure_detail=failure_detail)
            _publish_log(r, test_run_id, "ERROR", f"❌ 테스트 실패: {error_log[:200]}", 100)

            # 그룹이 있으면 집계 업데이트
            _update_run_group_aggregate(db, test_run_id)

            return {"test_run_id": test_run_id, "status": "FAILED",
                    "duration_ms": duration_ms, "error_log": error_log,
                    "failure_detail": failure_detail}

    except Exception as exc:
        ended_at = datetime.now(timezone.utc)
        duration_ms = int((ended_at - started_at).total_seconds() * 1000)
        error_msg = str(exc)

        from core.error_parser import parse_error_log
        failure_detail = parse_error_log(error_msg)

        _update_status(r, test_run_id, "FAILED",
                     ended_at=ended_at.isoformat(), duration_ms=duration_ms,
                     error_log=error_msg)
        _update_mongo_status(db, test_run_id, "FAILED",
                           ended_at=ended_at, duration_ms=duration_ms,
                           error_log=error_msg,
                           failure_detail=failure_detail)
        _publish_log(r, test_run_id, "ERROR", f"❌ 실행 오류: {error_msg[:200]}", 100)
        _update_run_group_aggregate(db, test_run_id)

        logger.exception("테스트 실행 실패: %s", test_run_id)
        raise self.retry(exc=exc)
    finally:
        mongo_client.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Docker 실행 + 폴백
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _run_in_docker(r, test_run_id, test_dir, base_url):
    try:
        import docker
        client = docker.from_env()
    except Exception as e:
        logger.warning("Docker SDK 사용 불가, 폴백 모드: %s", e)
        return _run_fallback(r, test_run_id, test_dir, base_url)

    _publish_log(r, test_run_id, "INFO", "Playwright 브라우저 인스턴스 생성", 20)

    try:
        container = client.containers.run(
            image=settings.WORKER_IMAGE,
            command="npx playwright test --reporter=list",
            volumes={test_dir: {"bind": "/tests", "mode": "ro"}},
            environment={"BASE_URL": base_url},
            detach=True,
            mem_limit="512m",
            cpu_period=100000,
            cpu_quota=50000,
            network_mode="bridge",
        )

        progress = 25
        for log_line in container.logs(stream=True, follow=True):
            decoded = log_line.decode("utf-8", errors="replace").strip()
            if decoded:
                if "navigating" in decoded.lower() or "goto" in decoded.lower():
                    progress = min(progress + 10, 80)
                elif "expect" in decoded.lower():
                    progress = min(progress + 15, 90)
                else:
                    progress = min(progress + 3, 85)
                _publish_log(r, test_run_id, "INFO", decoded, progress)

        result = container.wait(timeout=settings.WORKER_TIMEOUT)
        exit_code = result.get("StatusCode", 1)

        stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
        stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

        container.remove(force=True)
        return {"exit_code": exit_code, "stdout": stdout, "stderr": stderr}

    except Exception as e:
        return {"exit_code": 1, "stderr": str(e)}


def _run_fallback(r, test_run_id, test_dir, base_url):
    """Docker 미사용 환경 폴백"""
    import subprocess

    _publish_log(r, test_run_id, "WARN", "Docker 미사용 — 로컬 폴백 모드", 20)

    try:
        result = subprocess.run(
            ["npx", "playwright", "test", "--reporter=list"],
            cwd=test_dir,
            capture_output=True,
            text=True,
            timeout=settings.WORKER_TIMEOUT,
            env={"BASE_URL": base_url, "PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp"},
        )
        _publish_log(r, test_run_id, "INFO", "테스트 실행 완료", 90)
        return {"exit_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired:
        return {"exit_code": 1, "stderr": f"타임아웃: {settings.WORKER_TIMEOUT}초"}
    except FileNotFoundError:
        return {"exit_code": 1, "stderr": "npx/playwright 미설치"}

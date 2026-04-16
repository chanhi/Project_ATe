"""
Celery Task: CI/CD 결과 콜백
────────────────────────────
"""

import json
import logging

import httpx

from core.celery_app import celery_app
from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@celery_app.task(
    name="tasks.ci_cd.send_webhook_callback",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="ci_cd",
)
def send_webhook_callback(
    self,
    callback_url: str,
    payload: dict,
    secret_token: str | None = None,
) -> dict:
    """CI/CD 파이프라인에 결과 Webhook 전송"""
    headers = {"Content-Type": "application/json"}

    if secret_token:
        import hashlib
        import hmac
        body = json.dumps(payload, ensure_ascii=False).encode()
        signature = hmac.new(secret_token.encode(), body, hashlib.sha256).hexdigest()
        headers["X-ATe-Signature"] = f"sha256={signature}"

    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(callback_url, json=payload, headers=headers)
            response.raise_for_status()

        logger.info("Webhook 콜백 전송 성공: %s (%d)", callback_url, response.status_code)
        return {"status": "sent", "http_status": response.status_code}

    except httpx.HTTPStatusError as exc:
        logger.warning("Webhook 콜백 HTTP 에러: %d", exc.response.status_code)
        raise self.retry(exc=exc)
    except httpx.RequestError as exc:
        logger.error("Webhook 콜백 네트워크 에러: %s", str(exc))
        raise self.retry(exc=exc)


@celery_app.task(
    name="tasks.ci_cd.generate_allure_report",
    queue="ci_cd",
)
def generate_allure_report(test_run_id: str) -> dict:
    """Allure 리포트 생성"""
    import subprocess
    from pathlib import Path

    results_dir = Path("/tmp/allure-results") / test_run_id
    report_dir = Path("/tmp/allure-report") / test_run_id

    if not results_dir.exists():
        return {"status": "error", "message": "결과 디렉토리 없음"}

    try:
        subprocess.run(
            ["allure", "generate", str(results_dir), "-o", str(report_dir), "--clean"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return {"status": "success", "report_url": f"/reports/{test_run_id}/index.html"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

"""
AI 서비스 HTTP 클라이언트
─────────────────────────
AI팀이 별도 FastAPI 서버로 운영하는 LLM 엔진과 통신한다.

엔드포인트 (AI팀이 구현해야 하는 API):
- POST /generate-cases     → 자연어/기획서 → 테스트 케이스 + Playwright 코드
- POST /regenerate-code    → 기존 케이스 + 새 URL → 새 Playwright 코드

환경변수:
- AI_SERVICE_URL      : AI팀 서버 베이스 URL (예: http://ai-service:9000)
- AI_SERVICE_TIMEOUT  : 호출 타임아웃 초 단위
- AI_SERVICE_MOCK     : true면 AI팀 미연결 시 mock 응답 반환 (데모용)
"""

import logging
import uuid
from typing import Any

import httpx

from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AIServiceError(Exception):
    """AI 서비스 호출 실패"""
    pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AI팀 API 인터페이스 (백엔드 ↔ AI팀)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 1) 신규 케이스 생성 요청 페이로드
GENERATE_REQUEST_EXAMPLE = {
    "nl_input": "로그인 페이지에서 admin/1234로 로그인",
    "document_text": None,                # 기획서 파싱 결과 (선택)
    "target_url": "https://shopA.com",
    "techniques": ["equivalence_partition", "boundary_value"],
    "project_context": {
        "name": "ShopA Test",
        "base_url": "https://shopA.com",
    },
}

# AI팀이 반환할 응답 형식
GENERATE_RESPONSE_EXAMPLE = {
    "test_cases": [
        {
            "title": "유효한 ID/PW로 로그인 성공",
            "description": "동등 분할 — 유효 입력 클래스",
            "precondition": "회원 계정이 존재해야 함",
            "steps": [
                {"step_no": 1, "action": "fill", "target": "#username",
                 "input": "admin", "expected": ""},
                {"step_no": 2, "action": "fill", "target": "#password",
                 "input": "1234", "expected": ""},
                {"step_no": 3, "action": "click", "target": "button[type=submit]",
                 "input": "", "expected": "대시보드로 이동"},
            ],
            "expected_result": "/dashboard 로 이동",
            "priority": "high",
            "category": "login",
            "technique": "equivalence_partition",
            "playwright_code": "import { test, expect } from '@playwright/test';\n...",
        },
    ],
}

# 2) 재생성 요청 페이로드
REGENERATE_REQUEST_EXAMPLE = {
    "test_case": {                        # 기존 케이스 정보
        "title": "...",
        "steps": [...],
        "expected_result": "...",
    },
    "new_target_url": "https://shopB.com",
    "old_target_url": "https://shopA.com",  # 참고용
}

# AI팀이 반환할 응답
REGENERATE_RESPONSE_EXAMPLE = {
    "playwright_code": "...",  # shopB 전용 새 코드
    "target_url": "https://shopB.com",
    "notes": "Selectors adapted for shopB.com structure",
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AI 서비스 호출 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def call_generate_cases(
    nl_input: str | None,
    document_text: str | None,
    target_url: str,
    techniques: list[str],
    project_context: dict | None = None,
) -> list[dict]:
    """
    AI팀에게 신규 테스트 케이스 생성을 요청한다.
    동기 호출 — Celery Task 안에서 사용한다.

    Returns:
        AI팀이 생성한 테스트 케이스 리스트.
        각 케이스는 title/steps/playwright_code 등을 포함.

    Raises:
        AIServiceError: 호출 실패 또는 형식 오류
    """
    if settings.AI_SERVICE_MOCK:
        return _mock_generate_cases(nl_input, document_text, target_url, techniques)

    url = f"{settings.AI_SERVICE_URL.rstrip('/')}/generate-cases"
    payload = {
        "nl_input": nl_input,
        "document_text": document_text,
        "target_url": target_url,
        "techniques": techniques,
        "project_context": project_context or {},
    }

    try:
        with httpx.Client(timeout=settings.AI_SERVICE_TIMEOUT) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

    except httpx.HTTPStatusError as e:
        logger.error("AI 서비스 응답 에러: status=%d body=%s", e.response.status_code, e.response.text[:500])
        raise AIServiceError(f"AI 서비스 응답 에러: {e.response.status_code}") from e
    except httpx.RequestError as e:
        logger.error("AI 서비스 연결 실패: %s", str(e))
        raise AIServiceError(f"AI 서비스 연결 실패: {str(e)}") from e

    test_cases = data.get("test_cases")
    if not isinstance(test_cases, list):
        raise AIServiceError("AI 서비스 응답 형식 오류: 'test_cases' 필드 없음")

    return test_cases


def call_regenerate_code(
    test_case: dict,
    new_target_url: str,
    old_target_url: str | None = None,
) -> dict:
    """
    AI팀에게 다른 URL용 Playwright 코드 재생성을 요청한다.

    Returns:
        {"playwright_code": "...", "target_url": "...", "notes": "..."}
    """
    if settings.AI_SERVICE_MOCK:
        return _mock_regenerate_code(test_case, new_target_url, old_target_url)

    url = f"{settings.AI_SERVICE_URL.rstrip('/')}/regenerate-code"
    payload = {
        "test_case": test_case,
        "new_target_url": new_target_url,
        "old_target_url": old_target_url,
    }

    try:
        with httpx.Client(timeout=settings.AI_SERVICE_TIMEOUT) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

    except httpx.HTTPStatusError as e:
        logger.error("AI 재생성 에러: status=%d", e.response.status_code)
        raise AIServiceError(f"AI 재생성 응답 에러: {e.response.status_code}") from e
    except httpx.RequestError as e:
        logger.error("AI 재생성 연결 실패: %s", str(e))
        raise AIServiceError(f"AI 재생성 연결 실패: {str(e)}") from e

    if "playwright_code" not in data:
        raise AIServiceError("AI 재생성 응답에 'playwright_code' 필드 없음")

    return data


def health_check() -> bool:
    """AI 서비스 헬스체크. /health 엔드포인트 호출."""
    if settings.AI_SERVICE_MOCK:
        return True

    url = f"{settings.AI_SERVICE_URL.rstrip('/')}/health"
    try:
        with httpx.Client(timeout=5) as client:
            response = client.get(url)
            return response.status_code == 200
    except Exception:
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Mock 응답 (AI팀 미연결 시 데모용)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _mock_generate_cases(
    nl_input: str | None,
    document_text: str | None,
    target_url: str,
    techniques: list[str],
) -> list[dict]:
    """AI 서비스 미연결 시 더미 케이스 반환 (데모/개발용)"""
    source = nl_input or document_text or "테스트 시나리오"

    cases = []
    for technique in techniques:
        case_id_short = uuid.uuid4().hex[:6]
        cases.append({
            "title": f"[{technique}] {source[:40]}",
            "description": f"Mock 응답 — 기법: {technique}",
            "precondition": "데모용 사전조건",
            "steps": [
                {"step_no": 1, "action": "goto", "target": target_url,
                 "input": "", "expected": "페이지 로드"},
                {"step_no": 2, "action": "fill", "target": "#username",
                 "input": "admin", "expected": ""},
                {"step_no": 3, "action": "click", "target": "button[type=submit]",
                 "input": "", "expected": "이동"},
            ],
            "expected_result": "테스트 통과",
            "priority": "medium",
            "category": "auto",
            "technique": technique,
            "playwright_code": (
                f"import {{ test, expect }} from '@playwright/test';\n\n"
                f"// Mock generated for {technique} ({case_id_short})\n"
                f"test('{technique} test', async ({{ page }}) => {{\n"
                f"  await page.goto('{target_url}');\n"
                f"  await page.fill('#username', 'admin');\n"
                f"  await page.click('button[type=submit]');\n"
                f"}});\n"
            ),
        })
    return cases


def _mock_regenerate_code(test_case: dict, new_target_url: str, old_target_url: str | None) -> dict:
    """재생성 Mock 응답"""
    title = test_case.get("title", "test")
    return {
        "playwright_code": (
            f"import {{ test, expect }} from '@playwright/test';\n\n"
            f"// Mock regenerated for {new_target_url}\n"
            f"test('{title}', async ({{ page }}) => {{\n"
            f"  await page.goto('{new_target_url}');\n"
            f"  // ... regenerated body for {new_target_url}\n"
            f"}});\n"
        ),
        "target_url": new_target_url,
        "notes": f"Mock 재생성 ({old_target_url} → {new_target_url})",
    }

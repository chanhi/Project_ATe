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

    # AI팀이 명세와 다른 형식으로 보낼 수 있으므로 정규화
    normalized = [_normalize_test_case(tc, target_url) for tc in test_cases]

    # 일부 LLM은 case별 코드 대신 전체 코드 한 덩어리 ("playwright_code" 최상위)를 보냄
    # 이런 경우 모든 case에 같은 코드를 복사
    bulk_code = data.get("playwright_code")
    if bulk_code and isinstance(bulk_code, str):
        for tc in normalized:
            if not tc.get("playwright_code"):
                tc["playwright_code"] = bulk_code

    return normalized


def _normalize_test_case(tc: dict, target_url: str) -> dict:
    """
    AI팀(또는 다른 LLM)의 응답을 백엔드 표준 스키마로 정규화한다.

    매핑 규칙:
    - test_type → technique
    - action (string) → steps (자동 변환)
    - description 누락 → action 사용
    - title 누락 → test_type 또는 첫 step의 action 사용

    이를 통해 다양한 LLM이 만든 응답을 모두 받을 수 있다.
    """
    if not isinstance(tc, dict):
        return {}

    out = dict(tc)  # 원본 보존

    # ── technique 정규화 ──
    if "technique" not in out and "test_type" in out:
        out["technique"] = _map_test_type_to_technique(out["test_type"])

    # ── title 정규화 (없으면 추론) ──
    if not out.get("title"):
        if "test_type" in out:
            out["title"] = f"[{out['test_type']}] {str(out.get('action', ''))[:60]}"
        elif "scenario_title" in out:
            out["title"] = out["scenario_title"]
        elif "action" in out and isinstance(out["action"], str):
            out["title"] = out["action"][:80]
        else:
            out["title"] = "(제목 없음)"

    # ── steps 정규화 ──
    # 일부 LLM은 'action' 문자열 하나만 주고 'steps' 배열을 안 줌
    if not out.get("steps"):
        if "action" in out and isinstance(out["action"], str):
            out["steps"] = [
                {
                    "step_no": 1,
                    "action": "describe",
                    "target": "",
                    "input": "",
                    "expected": out.get("expected_result", ""),
                    "description": out["action"],
                }
            ]
        else:
            out["steps"] = []

    # ── description 정규화 ──
    if not out.get("description"):
        if "action" in out:
            out["description"] = out["action"]
        elif "test_type" in out:
            out["description"] = f"기법: {out['test_type']}"

    # ── 기본값 보강 ──
    out.setdefault("priority", "medium")
    out.setdefault("category", None)
    out.setdefault("precondition", None)
    out.setdefault("expected_result", "")
    out.setdefault("playwright_code", "")
    out.setdefault("technique", "scenario_based")

    return out


# 한글/영문 test_type → 표준 technique 매핑
_TECHNIQUE_KEYWORDS = {
    "equivalence_partition": ["동등분할", "동등 분할", "equivalence", "equiv"],
    "boundary_value": ["경계값", "경계 값", "boundary"],
    "decision_table": ["결정테이블", "결정 테이블", "decision"],
    "state_transition": ["상태전이", "상태 전이", "state"],
    "error_guessing": ["에러추측", "에러 추측", "예외처리", "예외 처리", "error"],
    "scenario_based": ["시나리오", "통합", "단위", "scenario", "integration", "unit", "e2e"],
}


def _map_test_type_to_technique(test_type: str) -> str:
    """LLM이 보낸 자유 형식 test_type을 표준 technique으로 매핑."""
    if not test_type:
        return "scenario_based"
    lowered = test_type.lower()
    for technique, keywords in _TECHNIQUE_KEYWORDS.items():
        for kw in keywords:
            if kw in lowered or kw in test_type:
                return technique
    return "scenario_based"


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
    """
    AI 서비스 미연결 시 더미 케이스 반환 (데모/개발용)

    입력 텍스트 키워드를 분석해 도메인에 맞는 풍부한 케이스 생성:
    - 쇼핑/장바구니/가격 → 네이버 쇼핑 스타일
    - 로그인 → SauceDemo 스타일
    - 그 외 → 일반 폼 검증 스타일
    """
    source = (nl_input or document_text or "").strip()
    domain = _detect_mock_domain(source, target_url)

    if domain == "shopping":
        return _mock_shopping_cases(target_url, techniques)
    elif domain == "login":
        return _mock_login_cases(target_url, techniques)
    else:
        return _mock_generic_cases(source, target_url, techniques)


def _detect_mock_domain(source: str, target_url: str) -> str:
    """입력 텍스트와 URL을 보고 어떤 도메인의 mock을 줄지 결정"""
    text = f"{source} {target_url}".lower()
    if any(k in text for k in ["쇼핑", "장바구니", "가격", "shopping", "cart", "price", "naver"]):
        return "shopping"
    if any(k in text for k in ["로그인", "login", "signin", "saucedemo", "auth"]):
        return "login"
    return "generic"


def _mock_shopping_cases(target_url: str, techniques: list[str]) -> list[dict]:
    """네이버 쇼핑 시나리오 (가격 필터 + 장바구니 수량 변경)"""
    all_cases = [
        {
            "title": "[동등분할-유효] 정상 가격 범위 입력 및 필터링",
            "description": "동등분할 — 유효 값 그룹의 대표값으로 가격 필터 정상 동작 검증",
            "precondition": "검색 결과 페이지 로드, 좌측 가격 필터 영역 표시",
            "steps": [
                {"step_no": 1, "action": "fill", "target": 'input[name="minPrice"]', "input": "50000", "expected": "최소 가격 입력됨"},
                {"step_no": 2, "action": "fill", "target": 'input[name="maxPrice"]', "input": "100000", "expected": "최대 가격 입력됨"},
                {"step_no": 3, "action": "click", "target": 'button:has-text("적용")', "input": "", "expected": "필터 적용"},
            ],
            "expected_result": "필터 칩에 '50,000원 ~ 100,000원' 표시",
            "priority": "high",
            "category": "search_filter",
            "technique": "equivalence_partition",
            "playwright_code": _shopping_code(target_url, "[동등분할-유효] 정상 가격 범위 입력", [
                'await page.fill(\'input[name="minPrice"]\', \'50000\');',
                'await page.fill(\'input[name="maxPrice"]\', \'100000\');',
                'await page.click(\'button:has-text("적용")\');',
                'const filterChip = page.locator(\'.filter-active-chip\');',
                "await expect(filterChip).toContainText('50,000원 ~ 100,000원');",
            ]),
        },
        {
            "title": "[동등분할-무효] 숫자 외 특수문자/한글 입력 차단",
            "description": "동등분할 — 무효 값(한글, 특수문자) 차단 검증",
            "precondition": "검색 결과 페이지 로드",
            "steps": [
                {"step_no": 1, "action": "fill", "target": 'input[name="minPrice"]', "input": "오만원", "expected": "차단됨"},
                {"step_no": 2, "action": "fill", "target": 'input[name="maxPrice"]', "input": "@#$", "expected": "차단됨"},
            ],
            "expected_result": "minPrice 입력 필드 값이 빈 문자열",
            "priority": "high",
            "category": "search_filter",
            "technique": "equivalence_partition",
            "playwright_code": _shopping_code(target_url, "[동등분할-무효] 숫자 외 입력 차단", [
                'await page.fill(\'input[name="minPrice"]\', \'오만원\');',
                'await page.fill(\'input[name="maxPrice"]\', \'@#$\');',
                'await expect(page.locator(\'input[name="minPrice"]\')).toHaveValue(\'\');',
            ]),
        },
        {
            "title": "[예외처리] 최소 금액이 최대 금액보다 큰 경우",
            "description": "비즈니스 규칙 위반 케이스 (min > max)",
            "precondition": "검색 결과 페이지 로드",
            "steps": [
                {"step_no": 1, "action": "fill", "target": 'input[name="minPrice"]', "input": "50000", "expected": ""},
                {"step_no": 2, "action": "fill", "target": 'input[name="maxPrice"]', "input": "10000", "expected": ""},
                {"step_no": 3, "action": "click", "target": 'button:has-text("적용")', "input": "", "expected": "경고 표시"},
            ],
            "expected_result": "'.price-error-message' visible, 텍스트 '가격 범위를 다시 확인해주세요'",
            "priority": "medium",
            "category": "search_filter",
            "technique": "error_guessing",
            "playwright_code": _shopping_code(target_url, "[예외처리] 최소 > 최대", [
                'await page.fill(\'input[name="minPrice"]\', \'50000\');',
                'await page.fill(\'input[name="maxPrice"]\', \'10000\');',
                'await page.click(\'button:has-text("적용")\');',
                "const alertMsg = page.locator('.price-error-message');",
                'await expect(alertMsg).toBeVisible();',
                "await expect(alertMsg).toHaveText('가격 범위를 다시 확인해주세요');",
            ]),
        },
        {
            "title": "[경계값분석] 최소 수량(1) 미만 입력 시 보정",
            "description": "경계값 분석 — 하한 경계(0)에서 1로 자동 보정",
            "precondition": "장바구니에 상품 1개 이상",
            "steps": [
                {"step_no": 1, "action": "fill", "target": 'input[name="quantity"]', "input": "0", "expected": ""},
                {"step_no": 2, "action": "blur", "target": 'input[name="quantity"]', "input": "", "expected": "보정 트리거"},
            ],
            "expected_result": "quantity 입력값이 자동으로 '1'로 보정됨",
            "priority": "high",
            "category": "cart",
            "technique": "boundary_value",
            "playwright_code": _shopping_code(target_url, "[경계값] 최소 수량 보정", [
                'const qtyInput = page.locator(\'input[name="quantity"]\');',
                "await qtyInput.fill('0');",
                'await qtyInput.blur();',
                "await expect(qtyInput).toHaveValue('1');",
            ]),
        },
        {
            "title": "[경계값분석] 최대 수량(99) 초과 입력 시 보정",
            "description": "경계값 분석 — 상한 경계(100)에서 99로 자동 보정",
            "precondition": "장바구니에 상품 1개 이상",
            "steps": [
                {"step_no": 1, "action": "fill", "target": 'input[name="quantity"]', "input": "100", "expected": ""},
                {"step_no": 2, "action": "blur", "target": 'input[name="quantity"]', "input": "", "expected": ""},
            ],
            "expected_result": "quantity 입력값이 자동으로 '99'로 보정됨",
            "priority": "high",
            "category": "cart",
            "technique": "boundary_value",
            "playwright_code": _shopping_code(target_url, "[경계값] 최대 수량 보정", [
                'const qtyInput = page.locator(\'input[name="quantity"]\');',
                "await qtyInput.fill('100');",
                'await qtyInput.blur();',
                "await expect(qtyInput).toHaveValue('99');",
            ]),
        },
        {
            "title": "[단위테스트] 수량 변경 시 총 결제 금액 실시간 재계산",
            "description": "총액 = 단가 × 수량 + 배송비(3,000) 검증",
            "precondition": "장바구니에 상품 1개, 단가 추출 가능",
            "steps": [
                {"step_no": 1, "action": "fill", "target": 'input[name="quantity"]', "input": "2", "expected": ""},
                {"step_no": 2, "action": "click", "target": 'button:has-text("변경")', "input": "", "expected": "재계산 트리거"},
            ],
            "expected_result": ".total-price 텍스트의 숫자값 = (단가 * 2 + 3000)",
            "priority": "medium",
            "category": "cart",
            "technique": "scenario_based",
            "playwright_code": _shopping_code(target_url, "[단위] 총액 재계산", [
                "const unitPriceText = await page.locator('.item-price').innerText();",
                "const unitPrice = parseInt(unitPriceText.replace(/[^0-9]/g, ''));",
                'await page.fill(\'input[name="quantity"]\', \'2\');',
                'await page.click(\'button:has-text("변경")\');',
                'const expectedTotal = (unitPrice * 2) + 3000;',
                "const actualTotalText = await page.locator('.total-price').innerText();",
                "const actualTotal = parseInt(actualTotalText.replace(/[^0-9]/g, ''));",
                'expect(actualTotal).toBe(expectedTotal);',
            ]),
        },
        {
            "title": "[통합테스트] 장바구니 수량 변경 후 주문서 데이터 연동",
            "description": "장바구니→결제 페이지 데이터 유실 없이 연동되는지 E2E 검증",
            "precondition": "장바구니에 상품, 결제 진행 가능",
            "steps": [
                {"step_no": 1, "action": "fill", "target": 'input[name="quantity"]', "input": "3", "expected": ""},
                {"step_no": 2, "action": "click", "target": 'button:has-text("주문하기")', "input": "", "expected": "이동"},
                {"step_no": 3, "action": "expect_url", "target": "/checkout", "input": "", "expected": "URL에 /checkout 포함"},
            ],
            "expected_result": ".checkout-item-qty 텍스트가 '3' (수량 유지)",
            "priority": "high",
            "category": "checkout",
            "technique": "scenario_based",
            "playwright_code": _shopping_code(target_url, "[통합] 주문서 데이터 연동", [
                'await page.fill(\'input[name="quantity"]\', \'3\');',
                'await page.click(\'button:has-text("주문하기")\');',
                'await expect(page).toHaveURL(/.*\\/checkout/);',
                "const checkoutQty = page.locator('.checkout-item-qty');",
                "await expect(checkoutQty).toHaveText('3');",
            ]),
        },
    ]
    return _filter_by_techniques(all_cases, techniques)


def _mock_login_cases(target_url: str, techniques: list[str]) -> list[dict]:
    """SauceDemo 스타일 로그인 시나리오 — 진짜 PASS 가능"""
    all_cases = [
        {
            "title": "[정상] 유효한 ID/PW로 로그인 성공",
            "description": "동등분할 — 유효 입력으로 inventory 페이지 진입",
            "precondition": "회원 계정 존재 (standard_user / secret_sauce)",
            "steps": [
                {"step_no": 1, "action": "goto", "target": target_url, "input": "", "expected": "로그인 페이지"},
                {"step_no": 2, "action": "fill", "target": "#user-name", "input": "standard_user", "expected": ""},
                {"step_no": 3, "action": "fill", "target": "#password", "input": "secret_sauce", "expected": ""},
                {"step_no": 4, "action": "click", "target": "#login-button", "input": "", "expected": "이동"},
            ],
            "expected_result": "/inventory URL 리다이렉트",
            "priority": "high",
            "category": "login",
            "technique": "equivalence_partition",
            "playwright_code": (
                "import { test, expect } from '@playwright/test';\n\n"
                "test('[정상] 유효한 ID/PW 로그인', async ({ page }) => {\n"
                f"  await page.goto('{target_url}');\n"
                "  await page.fill('#user-name', 'standard_user');\n"
                "  await page.fill('#password', 'secret_sauce');\n"
                "  await page.click('#login-button');\n"
                "  await expect(page).toHaveURL(/inventory/);\n"
                "});\n"
            ),
        },
        {
            "title": "[예외] 잘못된 비밀번호 거부",
            "description": "에러 추측 — 인증 실패 시나리오",
            "precondition": "계정은 존재하지만 비밀번호만 다름",
            "steps": [
                {"step_no": 1, "action": "goto", "target": target_url, "input": "", "expected": ""},
                {"step_no": 2, "action": "fill", "target": "#user-name", "input": "standard_user", "expected": ""},
                {"step_no": 3, "action": "fill", "target": "#password", "input": "wrong_password", "expected": ""},
                {"step_no": 4, "action": "click", "target": "#login-button", "input": "", "expected": "에러 표시"},
            ],
            "expected_result": "[data-test=error] 요소에 'Username and password do not match' 텍스트",
            "priority": "high",
            "category": "login",
            "technique": "error_guessing",
            "playwright_code": (
                "import { test, expect } from '@playwright/test';\n\n"
                "test('[예외] 잘못된 비밀번호', async ({ page }) => {\n"
                f"  await page.goto('{target_url}');\n"
                "  await page.fill('#user-name', 'standard_user');\n"
                "  await page.fill('#password', 'wrong_password');\n"
                "  await page.click('#login-button');\n"
                "  await expect(page.locator('[data-test=\"error\"]')).toContainText('do not match');\n"
                "});\n"
            ),
        },
        {
            "title": "[경계] 잠긴 사용자 차단",
            "description": "비즈니스 규칙 — locked_out_user는 차단되어야 함",
            "precondition": "잠긴 계정 (locked_out_user)",
            "steps": [
                {"step_no": 1, "action": "goto", "target": target_url, "input": "", "expected": ""},
                {"step_no": 2, "action": "fill", "target": "#user-name", "input": "locked_out_user", "expected": ""},
                {"step_no": 3, "action": "fill", "target": "#password", "input": "secret_sauce", "expected": ""},
                {"step_no": 4, "action": "click", "target": "#login-button", "input": "", "expected": "에러 표시"},
            ],
            "expected_result": "[data-test=error] 요소에 'locked out' 텍스트",
            "priority": "medium",
            "category": "login",
            "technique": "boundary_value",
            "playwright_code": (
                "import { test, expect } from '@playwright/test';\n\n"
                "test('[경계] 잠긴 사용자 차단', async ({ page }) => {\n"
                f"  await page.goto('{target_url}');\n"
                "  await page.fill('#user-name', 'locked_out_user');\n"
                "  await page.fill('#password', 'secret_sauce');\n"
                "  await page.click('#login-button');\n"
                "  await expect(page.locator('[data-test=\"error\"]')).toContainText('locked out');\n"
                "});\n"
            ),
        },
    ]
    return _filter_by_techniques(all_cases, techniques)


def _mock_generic_cases(source: str, target_url: str, techniques: list[str]) -> list[dict]:
    """도메인 미상일 때 일반 폼 검증 케이스"""
    short = (source or "테스트 시나리오")[:40]
    all_cases = []
    for technique in techniques:
        case_id_short = uuid.uuid4().hex[:6]
        all_cases.append({
            "title": f"[{technique}] {short}",
            "description": f"Mock 응답 — 기법: {technique}",
            "precondition": "대상 페이지 로드",
            "steps": [
                {"step_no": 1, "action": "goto", "target": target_url, "input": "", "expected": "페이지 로드"},
                {"step_no": 2, "action": "fill", "target": "input[type=text]", "input": "test_input", "expected": ""},
                {"step_no": 3, "action": "click", "target": "button[type=submit]", "input": "", "expected": "submit"},
            ],
            "expected_result": "테스트 통과",
            "priority": "medium",
            "category": "auto",
            "technique": technique,
            "playwright_code": (
                "import { test, expect } from '@playwright/test';\n\n"
                f"// Mock generated for {technique} ({case_id_short})\n"
                f"test('{technique} test', async ({{ page }}) => {{\n"
                f"  await page.goto('{target_url}');\n"
                "  // generic form interaction\n"
                "  const input = page.locator('input[type=text]').first();\n"
                "  if (await input.count()) await input.fill('test_input');\n"
                "  const submit = page.locator('button[type=submit]').first();\n"
                "  if (await submit.count()) await submit.click();\n"
                "});\n"
            ),
        })
    return all_cases


def _filter_by_techniques(all_cases: list[dict], techniques: list[str]) -> list[dict]:
    """
    techniques 인자가 비어있으면 모든 케이스 반환.
    있으면 매칭되는 케이스만 골라서 반환 (없으면 fallback으로 전체).
    """
    if not techniques:
        return all_cases
    requested = set(techniques)
    filtered = [c for c in all_cases if c.get("technique") in requested]
    return filtered if filtered else all_cases


def _shopping_code(target_url: str, test_name: str, body_lines: list[str]) -> str:
    """쇼핑 시나리오의 Playwright 코드 빌더 — beforeEach 패턴 포함"""
    body = "\n  ".join(body_lines)
    return (
        "import { test, expect } from '@playwright/test';\n\n"
        f"test('{test_name}', async ({{ page }}) => {{\n"
        f"  await page.goto('{target_url}');\n"
        f"  {body}\n"
        "});\n"
    )


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
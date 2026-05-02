"""
에러 로그 파서
──────────────
Playwright나 HTTP 호출에서 나온 raw error_log를
프론트가 표시하기 좋은 FailureDetail 구조로 변환한다.

화면 예:
    Failure Detail
    Get User By ID
    Expected: 200 OK
    Actual: 404 Not Found
    Reason: User ID not found

매칭이 안 되면 reason에 raw 메시지의 첫 줄만 넣고,
raw_log에 전체 로그를 보존한다.
"""

import re


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  정규식 패턴들
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Playwright 표준 형식: "Expected: X" / "Received: Y" 또는 "Actual: Y"
_RE_EXPECTED = re.compile(
    r"(?:Expected|expected)[\s:]+([^\n]+?)(?=\n|$)",
    re.MULTILINE,
)
_RE_ACTUAL = re.compile(
    r"(?:Received|Actual|actual|received)[\s:]+([^\n]+?)(?=\n|$)",
    re.MULTILINE,
)

# HTTP 상태 코드 미스매치
_RE_HTTP_EXPECTED = re.compile(
    r"(?:Expected status|expected status)[\s:]+(\d{3}[^\n]*)",
)
_RE_HTTP_ACTUAL = re.compile(
    r"(?:Actual status|actual status|got status)[\s:]+(\d{3}[^\n]*)",
)

# Timeout 패턴
_RE_TIMEOUT = re.compile(r"Timeout\s+(\d+)ms\s+exceeded", re.IGNORECASE)

# Locator/element 미발견
# Playwright 형식: "locator.click: '#xxx' not found" / "element not found: 'xxx'"
_RE_NOT_FOUND = re.compile(
    r"(?:locator\.\w+|element|selector)[^'\"\n]*['\"]([^'\"]+)['\"][^\n]*?not\s+found",
    re.IGNORECASE,
)

# 기본 Reason 후보 (첫 줄 또는 핵심 메시지)
_RE_FIRST_ERROR_LINE = re.compile(
    r"^(?:Error|AssertionError|TimeoutError|page\.[a-z]+|expect\([^)]*\)\.[^\s:]+)[\s:]+([^\n]+)",
    re.MULTILINE,
)


def parse_error_log(raw: str | None) -> dict:
    """
    raw error_log를 FailureDetail dict로 변환.

    Returns:
        {"expected": str|None, "actual": str|None, "reason": str|None, "raw_log": str}
    """
    if not raw or not raw.strip():
        return {
            "expected": None,
            "actual": None,
            "reason": None,
            "raw_log": raw,
        }

    expected: str | None = None
    actual: str | None = None
    reason: str | None = None

    # ── HTTP status 패턴 우선 (정확도 높음) ──
    if m := _RE_HTTP_EXPECTED.search(raw):
        expected = m.group(1).strip()
    if m := _RE_HTTP_ACTUAL.search(raw):
        actual = m.group(1).strip()

    # ── Playwright Expected/Actual 패턴 ──
    if expected is None:
        if m := _RE_EXPECTED.search(raw):
            expected = m.group(1).strip()
    if actual is None:
        if m := _RE_ACTUAL.search(raw):
            actual = m.group(1).strip()

    # ── Reason 추출 ──
    # 1. Timeout
    if m := _RE_TIMEOUT.search(raw):
        ms = m.group(1)
        reason = f"Timeout {ms}ms exceeded"
        if not expected:
            expected = "정상 응답"
        if not actual:
            actual = f"Timeout ({ms}ms)"

    # 2. Element not found
    elif m := _RE_NOT_FOUND.search(raw):
        target = m.group(1)
        reason = f"요소를 찾을 수 없음: {target}"
        if not expected:
            expected = f"요소 {target} 존재"
        if not actual:
            actual = "요소 없음"

    # 3. 첫 번째 에러 라인
    elif m := _RE_FIRST_ERROR_LINE.search(raw):
        reason = m.group(1).strip()

    # 4. 폴백 — 첫 비어있지 않은 줄
    if reason is None:
        first_lines = [
            line.strip() for line in raw.splitlines()
            if line.strip()
        ]
        if first_lines:
            reason = first_lines[0][:200]  # 너무 길면 자름

    # raw_log는 너무 길지 않게 자름 (DB 부담)
    truncated_raw = raw[:5000] if len(raw) > 5000 else raw

    return {
        "expected": expected,
        "actual": actual,
        "reason": reason,
        "raw_log": truncated_raw,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  테스트용 샘플 케이스 (참고)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

SAMPLE_LOGS = {
    "http_404": """
Test failed: Get User By ID
Expected status: 200 OK
Actual status: 404 Not Found
Reason: User ID not found in database
    """.strip(),

    "playwright_assertion": """
Error: expect(received).toHaveURL(expected)
Expected: /dashboard
Received: /login
    at /tests/login.spec.ts:12:34
    """.strip(),

    "timeout": """
TimeoutError: locator.click: Timeout 30000ms exceeded.
=========================== logs ===========================
waiting for locator('#submit-btn')
    """.strip(),

    "element_not_found": """
Error: locator.click: '#login-btn' not found
    at LoginPage.signIn (/tests/pages/login.ts:5:23)
    """.strip(),

    "unstructured": """
Something went terribly wrong
This is just a free-form error message
without any structure at all.
    """.strip(),
}

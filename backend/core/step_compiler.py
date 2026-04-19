"""
Step DSL → Playwright 코드 컴파일러
──────────────────────────────────
프론트/AI팀이 JSON DSL 형태로 테스트를 던지면 Playwright 코드로 변환한다.

지원하는 action:
- goto        : URL 이동
- fill        : input 값 입력
- click       : 요소 클릭
- type        : 키보드 입력
- wait        : 일정 시간 대기
- wait_for    : 요소가 나타날 때까지 대기
- assert_text : 텍스트 검증
- assert_url  : URL 검증
- assert_visible : 요소 가시성 검증
- screenshot  : 스크린샷 캡처
- press       : 특정 키 누르기 (Enter 등)
"""

from typing import Any


def _escape(value: str) -> str:
    """Playwright 코드 내부에 문자열을 안전하게 삽입한다."""
    if value is None:
        return ""
    return str(value).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")


def _selector(target: str) -> str:
    """
    target이 이미 Playwright 셀렉터면 그대로,
    그렇지 않으면 id로 자동 감싸기.
    """
    if not target:
        return ""
    # 이미 Playwright 셀렉터 문법이면 그대로
    if target.startswith(("#", ".", "[", "//", "text=", "data-testid=")):
        return target
    # CSS 속성 셀렉터 포함 (예: "button[type=submit]", "input[name=x]")
    if "[" in target and "]" in target:
        return target
    # 태그명과 공백/조합자 포함 CSS (예: "div > span", "button.primary")
    if " " in target or ">" in target or "+" in target or "~" in target:
        return target
    # plain 이름이면 id로 간주
    return f"#{target}"


def compile_steps_to_playwright(
    url: str,
    steps: list[dict],
    test_name: str = "generated_test",
) -> str:
    """
    Step DSL 리스트를 Playwright TypeScript 코드로 변환한다.

    Args:
        url: 테스트 시작 URL
        steps: [{action, target, value, ...}, ...]
        test_name: test() 블록 이름

    Returns:
        Playwright TS 코드 문자열
    """
    lines = [
        "import { test, expect } from '@playwright/test';",
        "",
        f"test('{_escape(test_name)}', async ({{ page }}) => {{",
        f"  await page.goto('{_escape(url)}');",
    ]

    for step in steps:
        action = step.get("action", "").lower()
        target = step.get("target", "")
        value = step.get("value", "")
        selector = _selector(target)

        if action == "goto":
            lines.append(f"  await page.goto('{_escape(target or value)}');")

        elif action == "fill":
            lines.append(
                f"  await page.fill('{_escape(selector)}', '{_escape(value)}');"
            )

        elif action == "click":
            lines.append(f"  await page.click('{_escape(selector)}');")

        elif action == "type":
            lines.append(
                f"  await page.type('{_escape(selector)}', '{_escape(value)}');"
            )

        elif action == "press":
            key = value or "Enter"
            lines.append(
                f"  await page.press('{_escape(selector)}', '{_escape(key)}');"
            )

        elif action == "wait":
            ms = int(value) if value else 1000
            lines.append(f"  await page.waitForTimeout({ms});")

        elif action == "wait_for":
            lines.append(
                f"  await page.waitForSelector('{_escape(selector)}');"
            )

        elif action == "assert_text":
            lines.append(
                f"  await expect(page.locator('{_escape(selector)}'))"
                f".toContainText('{_escape(value)}');"
            )

        elif action == "assert_url":
            lines.append(
                f"  await expect(page).toHaveURL('{_escape(value or target)}');"
            )

        elif action == "assert_visible":
            lines.append(
                f"  await expect(page.locator('{_escape(selector)}'))"
                f".toBeVisible();"
            )

        elif action == "screenshot":
            name = value or "screenshot.png"
            lines.append(f"  await page.screenshot({{ path: '{_escape(name)}' }});")

        else:
            # 알 수 없는 action은 주석으로 남김
            lines.append(f"  // Unknown action: {action} (target={target}, value={value})")

    lines.append("});")
    lines.append("")
    return "\n".join(lines)


def validate_steps(steps: list[dict]) -> tuple[bool, str | None]:
    """
    Step 유효성 검증.

    Returns:
        (is_valid, error_message)
    """
    if not isinstance(steps, list):
        return False, "steps는 리스트여야 합니다."
    if not steps:
        return False, "steps가 비어 있습니다."

    valid_actions = {
        "goto", "fill", "click", "type", "press", "wait", "wait_for",
        "assert_text", "assert_url", "assert_visible", "screenshot",
    }

    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            return False, f"step[{i}]은 dict여야 합니다."

        action = step.get("action", "").lower()
        if not action:
            return False, f"step[{i}]에 action이 없습니다."

        if action not in valid_actions:
            return False, (
                f"step[{i}]의 action이 유효하지 않습니다: '{action}'. "
                f"지원 action: {sorted(valid_actions)}"
            )

        # action별 필수 필드
        if action in ("fill", "type") and not step.get("value"):
            return False, f"step[{i}] '{action}'은 value가 필요합니다."
        if action in ("click", "fill", "type", "press", "wait_for",
                       "assert_text", "assert_visible") and not step.get("target"):
            return False, f"step[{i}] '{action}'은 target이 필요합니다."

    return True, None

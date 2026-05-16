import os
import json
import fitz  # PyMuPDF
from openai import OpenAI

# 1. 환경 설정 로드
try:
    from core.config import get_settings

    settings = get_settings()
    final_api_key = getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")

    print("✅ backend의 core.config 설정을 성공적으로 로드했습니다.")

except Exception:
    final_api_key = os.getenv("OPENAI_API_KEY")
    print("ℹ️ 개인 로컬 환경 설정을 사용합니다.")


# 2. OpenAI 클라이언트 초기화
client = OpenAI(api_key=final_api_key)


class ATEAiEngine:
    def __init__(self):
        self.client = client

        self.dsl_guide = (
            "goto(url), fill(target, value), click(target), type(target, value), "
            "press(target), wait(value), wait_for(target), assert_text(target, value), "
            "assert_url(value), assert_visible(target), screenshot(value)"
        )

    def extract_text_from_pdf(self, file_path: str) -> str:
        text = ""

        try:
            with fitz.open(file_path) as doc:
                for page in doc:
                    text += page.get_text()

            return text

        except Exception as e:
            return f"텍스트 추출 중 오류 발생: {str(e)}"

    async def generate_playwright_test(
        self,
        project_id: str,
        base_url: str,
        nl_prompt: str,
        technique: str = "equivalence_partitioning",
    ):
        """
        자연어 요구사항을 기반으로 Playwright 테스트 코드를 생성합니다.
        반환 형식:
        {
            "generated_code": "...",
            "ai_validation": {
                "is_valid": True/False,
                "technique": "...",
                "retry_count": 0,
                "status": "PASSED" or "ERROR",
                "message": "..."
            }
        }
        """

        if os.getenv("DEMO_MODE") == "True":
            return self._get_demo_response(project_id, base_url, technique)

        if not final_api_key:
            return self._get_error_response("OPENAI_API_KEY가 설정되지 않았습니다.")

        system_message = f"""
당신은 전문 QA 엔지니어입니다.

사용자의 자연어 요구사항을 바탕으로 Playwright TypeScript 테스트 코드를 생성하세요.

반드시 아래 JSON 형식만 응답하세요.

{{
  "playwright_code": "import {{ test, expect }} from '@playwright/test';\\n\\ntest('...', async ({{ page }}) => {{\\n  await page.goto('{base_url}');\\n}});"
}}

규칙:
- JSON 외 다른 설명 금지
- playwright_code 키는 반드시 포함
- playwright_code 값은 빈 문자열이면 안 됨
- Playwright TypeScript 코드로 작성
- @playwright/test의 test, expect 사용
- base_url은 {base_url} 사용
- 테스트 기법은 {technique} 반영
- 사용 가능 액션 참고: {self.dsl_guide}
- selector를 모르면 getByRole, getByText, getByLabel을 우선 사용
- 테스트 이름은 자연어 요구사항을 요약해서 작성
"""

        user_message = f"""
프로젝트 ID: {project_id}
타겟 URL: {base_url}
테스트 기법: {technique}
자연어 요구사항: {nl_prompt}
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
            )

            raw_content = response.choices[0].message.content

            if not raw_content:
                return self._get_error_response("OpenAI 응답이 비어 있습니다.")

            result = json.loads(raw_content)

            generated_code = (
                result.get("playwright_code")
                or result.get("generated_code")
                or result.get("code")
                or result.get("test_code")
                or ""
            )

            is_valid = bool(generated_code.strip())

            return {
                "generated_code": generated_code,
                "ai_validation": {
                    "is_valid": is_valid,
                    "technique": technique,
                    "retry_count": 0,
                    "status": "PASSED" if is_valid else "ERROR",
                    "message": "Successfully generated Playwright test code"
                    if is_valid
                    else "AI 응답에 테스트 코드가 없습니다.",
                },
            }

        except Exception as e:
            return self._get_error_response(str(e))

    async def repair_test_code(self, original_code: str, error_log: str):
        if os.getenv("DEMO_MODE") == "True":
            return {
                "generated_code": original_code,
                "ai_validation": {
                    "is_valid": True,
                    "retry_count": 1,
                    "status": "PASSED",
                    "message": "Demo mode: repair skipped",
                },
            }

        system_message = """
당신은 Playwright 테스트 코드 자동 수정 전문가입니다.

에러 로그를 분석해서 수정된 Playwright TypeScript 코드를 반환하세요.

반드시 아래 JSON 형식만 응답하세요.

{
  "playwright_code": "수정된 코드"
}

JSON 외 설명은 하지 마세요.
"""

        user_message = f"""
원본 코드:
{original_code}

에러 로그:
{error_log}
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)

            generated_code = (
                result.get("playwright_code")
                or result.get("generated_code")
                or result.get("code")
                or result.get("test_code")
                or ""
            )

            is_valid = bool(generated_code.strip())

            return {
                "generated_code": generated_code,
                "ai_validation": {
                    "is_valid": is_valid,
                    "retry_count": 1,
                    "status": "PASSED" if is_valid else "ERROR",
                    "message": "Successfully repaired Playwright test code"
                    if is_valid
                    else "수정된 코드가 비어 있습니다.",
                },
            }

        except Exception as e:
            return self._get_error_response(str(e))

    def _get_demo_response(self, project_id: str, base_url: str, technique: str):
        return {
            "generated_code": (
                "import { test, expect } from '@playwright/test';\n\n"
                f"test('{technique} - Automated Test', async ({{ page }}) => {{\n"
                f"  await page.goto('{base_url}');\n"
                "  await page.getByRole('button', { name: /login|로그인/i }).click();\n"
                "  await expect(page).toHaveURL(/.*login.*/);\n"
                "});"
            ),
            "ai_validation": {
                "is_valid": True,
                "technique": technique,
                "retry_count": 1,
                "status": "PASSED",
                "message": "Demo mode: Successfully generated for dashboard integration",
            },
        }

    def _get_error_response(self, error_msg: str):
        return {
            "generated_code": "",
            "ai_validation": {
                "is_valid": False,
                "status": "ERROR",
                "message": error_msg,
            },
        }
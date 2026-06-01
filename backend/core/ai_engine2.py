import os
import json
import fitz
from openai import OpenAI

try:
    from core.config import get_settings
    settings = get_settings()
    final_api_key = getattr(settings, "OPENAI_API_KEY", None) or os.getenv("OPENAI_API_KEY")
    print("✅ backend의 core.config 설정을 성공적으로 로드했습니다.")
except Exception:
    final_api_key = os.getenv("OPENAI_API_KEY")
    print("ℹ️ 개인 로컬 환경 설정을 사용합니다.")

client = OpenAI(api_key=final_api_key)


# 안전장치: AI에게 한 번에 요청할 수 있는 최대 케이스 수
MAX_CASES_PER_REQUEST = 5
MIN_CASES_PER_REQUEST = 1


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

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  배치 생성: 자연어 한 번 → 여러 케이스
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def generate_test_case_batch(
        self,
        project_id: str,
        base_url: str,
        nl_prompt: str,
        techniques: list[str] = None,
        requested_count: int = 5,
    ):
        """
        자연어 요구사항을 받아서 여러 테스트 케이스를 한 번에 생성.

        반환:
        {
            "test_cases": [...],
            "requested_count": 5,
            "generated_count": 3,
            "is_partial": True,
            "ai_validation": {...}
        }
        """
        if not final_api_key:
            return self._get_error_response("OPENAI_API_KEY가 설정되지 않았습니다.")

        # 안전장치: 요청 개수 제한
        safe_count = max(MIN_CASES_PER_REQUEST, min(requested_count, MAX_CASES_PER_REQUEST))

        techniques = techniques or ["scenario_based"]
        techniques_str = ", ".join(techniques)

        system_message = f"""당신은 전문 QA 엔지니어이다.
사용자가 자연어로 요청한 기능에 대해 **정확히 {safe_count}개의 다양한 테스트 케이스**를 생성한다.

비개발자(기획자/QA) 입장에서 작성하라:
- 클래스명/내부 식별자가 아니라 사용자 입장의 기능을 테스트
- "로그인 버튼 클릭" 같이 사용자 행동 기준으로 작성

생성 가이드라인:
- 정확히 {safe_count}개 생성 (더도 덜도 말고)
- 각 케이스는 서로 다른 시나리오 (중복 절대 금지)
- 다양한 관점: 정상 경로, 비정상 입력, 경계값, 예외 처리 등
- 적용할 테스트 기법: {techniques_str}
  - scenario_based: 정상 사용 시나리오
  - boundary_value: 경계값 (최소/최대 길이 등)
  - equivalence_partition: 동등 분할 (유효/무효 입력)
  - decision_table: 조건 조합
  - state_transition: 상태 변화
  - error_guessing: 예외/에러 케이스

**중요**: 모든 케이스는 반드시 작동 가능한 Playwright 코드를 포함해야 한다.
코드를 만들 수 없는 케이스는 생성하지 마라.

반드시 아래 JSON 형식만 응답:
{{
  "test_cases": [
    {{
      "title": "구체적인 케이스 제목 (예: 로그인 성공 - 정상 계정)",
      "description": "이 케이스가 무엇을 검증하는지 한 문장 설명",
      "category": "login | search | navigation | payment 등",
      "priority": "low | medium | high | critical",
      "technique": "{techniques[0]}",
      "precondition": "테스트 전제 조건",
      "steps": [
        {{"step_no": 1, "action": "사용자 행동", "target": "대상", "input": "입력값", "expected": "예상 동작"}}
      ],
      "expected_result": "최종 기대 결과 (한 문장)",
      "playwright_code": "import {{ test, expect }} from '@playwright/test';\\n\\ntest('...', async ({{ page }}) => {{\\n  await page.goto('{base_url}');\\n  ...\\n}});"
    }}
  ]
}}

Playwright 코드 규칙:
- @playwright/test의 test, expect 사용
- base_url은 {base_url} 사용
- selector를 모르면 getByRole, getByText, getByLabel을 우선 사용
- 각 케이스는 독립적인 test() 블록 1개
- 사용 가능 액션: {self.dsl_guide}

JSON 외 다른 설명 절대 금지."""

        user_message = f"""프로젝트 ID: {project_id}
타겟 URL: {base_url}
적용 기법: {techniques_str}
요청 개수: 정확히 {safe_count}개

[사용자 요구사항]
{nl_prompt}

위 요구사항에 대해 {safe_count}개의 다양한 테스트 케이스를 생성해줘.
각 케이스는 반드시 작동 가능한 Playwright 코드를 포함해야 한다."""

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
            raw_test_cases = result.get("test_cases", [])

            if not raw_test_cases or not isinstance(raw_test_cases, list):
                return self._get_error_response("AI 응답에 test_cases 배열이 없습니다.")

            # ── 품질 검증: 각 케이스를 엄격하게 검사 ──
            valid_cases = []
            skipped_reasons = []

            for idx, tc in enumerate(raw_test_cases):
                if not isinstance(tc, dict):
                    skipped_reasons.append(f"케이스 #{idx+1}: dict가 아님")
                    continue

                code = (tc.get("playwright_code") or "").strip()
                title = (tc.get("title") or "").strip()

                if not code:
                    skipped_reasons.append(f"케이스 #{idx+1} '{title[:30]}': 코드 없음")
                    continue
                if not title:
                    skipped_reasons.append(f"케이스 #{idx+1}: 제목 없음")
                    continue

                # 코드 최소 길이 체크 (의미있는 코드인지)
                if len(code) < 50:
                    skipped_reasons.append(f"케이스 #{idx+1} '{title[:30]}': 코드가 너무 짧음")
                    continue

                # 필수 키워드 체크 (Playwright 기본 패턴)
                if "test(" not in code or "page" not in code:
                    skipped_reasons.append(f"케이스 #{idx+1} '{title[:30]}': Playwright 패턴 아님")
                    continue

                valid_cases.append(tc)

            generated_count = len(valid_cases)
            is_partial = generated_count < safe_count
            is_empty = generated_count == 0

            if is_empty:
                return self._get_error_response(
                    f"유효한 테스트 케이스가 생성되지 않았습니다. 스킵된 이유: {'; '.join(skipped_reasons[:3])}"
                )

            # 메시지 작성
            if is_partial:
                message = f"요청한 {safe_count}개 중 {generated_count}개만 생성되었습니다. AI가 일부 케이스의 코드를 만들지 못했습니다."
                if skipped_reasons:
                    message += f" (스킵: {len(skipped_reasons)}개)"
            else:
                message = f"{generated_count}개 케이스 생성 완료"

            return {
                "test_cases": valid_cases,
                "requested_count": safe_count,
                "generated_count": generated_count,
                "is_partial": is_partial,
                "skipped_reasons": skipped_reasons,
                "ai_validation": {
                    "is_valid": True,
                    "techniques": techniques,
                    "retry_count": 0,
                    "status": "PARTIAL" if is_partial else "PASSED",
                    "message": message,
                },
            }

        except Exception as e:
            return self._get_error_response(str(e))

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  기존 메서드 (호환성 유지)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    async def generate_playwright_test(
        self,
        project_id: str,
        base_url: str,
        nl_prompt: str,
        technique: str = "scenario_based",
    ):
        if not final_api_key:
            return self._get_error_response_legacy("OPENAI_API_KEY가 설정되지 않았습니다.")

        system_message = f"""당신은 전문 QA 엔지니어입니다.
사용자의 자연어 요구사항을 바탕으로 Playwright TypeScript 테스트 코드를 생성하세요.

반드시 아래 JSON 형식만 응답하세요.
{{
  "playwright_code": "import {{ test, expect }} from '@playwright/test';\\n\\ntest('...', async ({{ page }}) => {{\\n  await page.goto('{base_url}');\\n}});"
}}

규칙:
- JSON 외 다른 설명 금지
- base_url은 {base_url} 사용
- 테스트 기법은 {technique} 반영
- selector를 모르면 getByRole, getByText, getByLabel을 우선 사용
"""
        user_message = f"프로젝트 ID: {project_id}\n타겟 URL: {base_url}\n테스트 기법: {technique}\n자연어 요구사항: {nl_prompt}"

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
                return self._get_error_response_legacy("OpenAI 응답이 비어 있습니다.")

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
                    "message": "OK" if is_valid else "AI 응답에 코드가 없음",
                },
            }
        except Exception as e:
            return self._get_error_response_legacy(str(e))

    async def repair_test_code(self, original_code: str, error_log: str):
        system_message = """당신은 Playwright 테스트 코드 자동 수정 전문가입니다.
에러 로그를 분석해서 수정된 코드를 반환하세요.
반드시 아래 JSON 형식만 응답:
{"playwright_code": "수정된 코드"}
JSON 외 설명 금지."""
        user_message = f"원본 코드:\n{original_code}\n\n에러 로그:\n{error_log}"
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
            generated_code = result.get("playwright_code") or result.get("generated_code") or ""
            is_valid = bool(generated_code.strip())
            return {
                "generated_code": generated_code,
                "ai_validation": {
                    "is_valid": is_valid,
                    "retry_count": 1,
                    "status": "PASSED" if is_valid else "ERROR",
                    "message": "OK" if is_valid else "수정 코드 비어있음",
                },
            }
        except Exception as e:
            return self._get_error_response_legacy(str(e))

    def _get_error_response(self, error_msg: str):
        return {
            "test_cases": [],
            "requested_count": 0,
            "generated_count": 0,
            "is_partial": False,
            "ai_validation": {
                "is_valid": False,
                "status": "ERROR",
                "message": error_msg,
            },
        }

    def _get_error_response_legacy(self, error_msg: str):
        return {
            "generated_code": "",
            "ai_validation": {
                "is_valid": False,
                "status": "ERROR",
                "message": error_msg,
            },
        }
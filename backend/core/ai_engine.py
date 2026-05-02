import os
import json
import fitz  # PyMuPDF
from openai import OpenAI

# 1. 환경 설정 로드 (조장님 백엔드 설정 최우선)
try:
    from core.config import get_settings
    settings = get_settings()
    # 조장님의 .env에 키가 있으면 그걸 사용, 없으면 개인 키를 백업으로 사용
    final_api_key = settings.OPENAI_API_KEY if settings.OPENAI_API_KEY else "sk-proj-jkbKfR0-..."
    print("✅ 조장님의 core.config 설정을 로드했습니다.")
except ImportError:
    # 개인 로컬 테스트 환경 (core 폴더가 없는 경우)
    final_api_key = os.getenv("OPENAI_API_KEY", "key부분")
    print("ℹ️ 개인 환경 설정을 로드했습니다.")

# 2. OpenAI 클라이언트 초기화 (한 번만 수행)
client = OpenAI(api_key=final_api_key)

class ATEAiEngine:
    def __init__(self):
        self.client = client
        # 논문에서 정의한 11종 핵심 액션 가이드라인
        self.dsl_guide = (
            "goto(url), fill(target, value), click(target), type(target, value), "
            "press(target), wait(value), wait_for(target), assert_text(target, value), "
            "assert_url(value), assert_visible(target), screenshot(value)"
        )

    # 1. 전달받은 데이터(PDF) 텍스트화
    def extract_text_from_pdf(self, file_path: str) -> str:
        text = ""
        try:
            with fitz.open(file_path) as doc:
                for page in doc:
                    text += page.get_text()
            return text
        except Exception as e:
            return f"텍스트 추출 중 오류 발생: {str(e)}"

    # 2. LLM 모델 연결 및 Playwright 코드 생성
    async def generate_playwright_test(self, source_text: str, technique="equivalence_partition"):
        # 논문의 블랙박스 테스트 기법 지시사항
        tech_instructions = {
            "equivalence_partition": "데이터를 유효/무효 그룹으로 나눠서 대표값으로 테스트해.",
            "boundary_value": "입력값의 최소, 최대, 경계값(예: 0, 1, 99, 100)을 집중적으로 검증해.",
            "error_guessing": "사용자가 실수하기 쉬운 상황이나 시스템이 에러를 뱉을 법한 상황을 추측해서 짜.",
            "scenario_based": "실제 사용자의 여정(User Journey)을 따라가는 통합 테스트를 수행해."
        }

        system_message = f"""
        당신은 전문 QA 엔지니어입니다. 요구사항 문서를 읽고 Playwright 테스트 시나리오를 작성하세요.
        
        [필수 기법]: {tech_instructions.get(technique, "시나리오 기반 테스트 수행")}
        [사용 가능 액션]: {self.dsl_guide}
        
        결과는 반드시 아래의 JSON 형식을 엄격히 지켜서 출력하세요:
        {{
            "title": "테스트 제목",
            "description": "테스트 설명",
            "steps": [
                {{"step_no": 1, "action": "goto", "target": "", "value": "URL"}},
                {{"step_no": 2, "action": "fill", "target": "#id", "value": "test_val"}}
            ],
            "playwright_code": "async function... 실행 가능한 전체 코드"
        }}
        """

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": f"요구사항 문서 내용:\n{source_text}"}
            ],
            response_format={"type": "json_object"}
        )
        # 조장님이 강조한 '결과 리턴' 데이터
        return response.choices[0].message.content

    # 3. 에러 발생 시 자가 수정 (Self-healing)
    async def repair_test_code(self, original_code: str, error_log: str):
        system_message = f"""
        당신은 테스트 코드 자동 수정 전문가입니다.
        발생한 에러 로그를 분석하여 기존 Playwright 코드를 수정하세요.
        반드시 이전과 동일한 JSON 형식으로 수정된 코드를 반환하세요.
        """
        
        user_message = f"기존 코드:\n{original_code}\n\n발생 에러:\n{error_log}"

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            response_format={"type": "json_object"}
        )
        return response.choices[0].message.content

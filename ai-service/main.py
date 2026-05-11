import os
import uuid
import logging
from fastapi import FastAPI, Request, HTTPException, Header, Depends
from typing import Optional

# 로그 설정 (백엔드 호출 흐름 확인용)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Project ATe AI Service")

# 환경 변수 설정 (향후 운영 시 AI_SERVICE_API_KEY 설정 필요)
AI_SERVICE_API_KEY = os.getenv("AI_SERVICE_API_KEY")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 인증 미들웨어 (명세서의 '인증' 섹션 반영)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def verify_api_key(x_ai_service_key: Optional[str] = Header(None)):
    # 환경 변수에 키가 설정되어 있을 때만 인증 수행
    if AI_SERVICE_API_KEY and x_ai_service_key != AI_SERVICE_API_KEY:
        logger.warning("인증 실패: 잘못된 API Key 접근")
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return x_ai_service_key

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 신규 케이스 생성 (POST /generate-cases)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.post("/generate-cases", dependencies=[Depends(verify_api_key)])
async def generate_cases(request: Request):
    try:
        data = await request.json()
        nl_input = data.get("nl_input")
        document_text = data.get("document_text")
        target_url = data.get("target_url", "https://shopA.com")
        techniques = data.get("techniques", ["equivalence_partition"])

        # 입력 소스 결정
        source = nl_input if nl_input else (document_text[:30] if document_text else "입력 없음")
        logger.info(f"케이스 생성 시작: {source}")

        # 명세서: techniques 배열 길이만큼 케이스 생성 (1:1)
        test_cases = []
        for tech in techniques:
            case_id = uuid.uuid4().hex[:6]
            test_cases.append({
                "title": f"유효한 입력으로 {source[:15]} 성공",
                "description": f"기법: {tech} — 유효 입력 클래스 테스트",
                "precondition": "회원 계정이 존재해야 함",
                "steps": [
                    {"step_no": 1, "action": "goto", "target": target_url, "input": "", "expected": "페이지 로드"},
                    {"step_no": 2, "action": "fill", "target": "#username", "input": "admin", "expected": ""},
                    {"step_no": 3, "action": "fill", "target": "#password", "input": "1234", "expected": ""},
                    {"step_no": 4, "action": "click", "target": "button[type=submit]", "input": "", "expected": "대시보드로 이동"}
                ],
                "expected_result": "/dashboard 페이지로 리다이렉트",
                "priority": "high",
                "category": "login",
                "technique": tech,
                "playwright_code": (
                    f"import {{ test, expect }} from '@playwright/test';\n\n"
                    f"test('로그인 성공 {case_id}', async ({{ page }}) => {{\n"
                    f"  await page.goto('{target_url}/login');\n"
                    f"  await page.fill('#username', 'admin');\n"
                    f"  await page.fill('#password', '1234');\n"
                    f"  await page.click('button[type=submit]');\n"
                    f"  await expect(page).toHaveURL(/\\/dashboard/);\n"
                    f"}});"
                )
            })
        return {"test_cases": test_cases}

    except Exception as e:
        logger.error(f"Internal Error: {str(e)}")
        # 명세서: 500 에러 응답 규격 반영
        raise HTTPException(status_code=500, detail=f"LLM 호출 실패 또는 내부 에러: {str(e)}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 코드 재생성 (POST /regenerate-code)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.post("/regenerate-code", dependencies=[Depends(verify_api_key)])
async def regenerate_code(request: Request):
    try:
        data = await request.json()
        new_url = data.get("new_target_url", "https://shopB.com")
        test_case = data.get("test_case", {})
        title = test_case.get("title", "로그인 성공")

        logger.info(f"코드 재생성: {new_url}")

        return {
            "playwright_code": (
                f"import {{ test, expect }} from '@playwright/test';\n\n"
                f"test('{title} (shopB)', async ({{ page }}) => {{\n"
                f"  await page.goto('{new_url}/signin');\n"
                f"  await page.fill('input[name=email]', 'admin');\n"
                f"  await page.click('button[type=submit]');\n"
                f"  await expect(page).toHaveURL(/\\/dashboard/);\n"
                f"}});"
            ),
            "target_url": new_url,
            "notes": "Selectors adapted: #username → input[name=email] (Selector-free locator 사용 권장 반영)"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"잘못된 요청: {str(e)}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 헬스체크 (GET /health)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.get("/health")
def health():
    # 명세서: 200이면 healthy로 판단
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    # 명세서: 기본 포트 9000 사용
    uvicorn.run(app, host="0.0.0.0", port=9000)

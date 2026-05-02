import asyncio
import os
# services가 아니라 ai_part 폴더에 있으므로 아래처럼 수정합니다!
from ai_part.ai_engine import ATEAiEngine 

async def main():
    os.environ["OPENAI_API_KEY"] = "key 부분"
    # 엔진 준비
    engine = ATEAiEngine()
    
    # 샘플 입력
    sample_input = "구글 메인 페이지에 접속해서 검색창에 '날씨'라고 입력해줘."
    
    print("🚀 AI가 작업을 시작합니다...")
    
    try:
        # ai_engine.py에 있는 함수 이름과 동일하게 호출합니다.
        result = await engine.generate_playwright_test(sample_input)
        print("\n✅ [AI 생성 결과]")
        print(result)
    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from core.ai_engine2 import ATEAiEngine

async def main():
    os.environ["DEMO_MODE"] = "False"

    engine = ATEAiEngine()

    result = await engine.generate_playwright_test(
        project_id="1",
        base_url="https://example.com",
        nl_prompt="회원가입 후 로그인 테스트 생성",
        technique="scenario_based"
    )

    print(result)

if __name__ == "__main__":
    asyncio.run(main())
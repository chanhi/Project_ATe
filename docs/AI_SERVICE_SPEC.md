# AI 서비스 인터페이스 명세

> **이 문서는 AI팀이 구현해야 하는 FastAPI 서버 사양입니다.**
> 백엔드는 `AI_SERVICE_URL` 환경변수로 지정된 주소로 HTTP 호출만 합니다.

## 개요

AI팀은 별도 FastAPI 서버를 띄우고 아래 3개 엔드포인트를 구현하면 됩니다.

- `POST /generate-cases` — 자연어/기획서 → 테스트 케이스 + Playwright 코드
- `POST /regenerate-code` — 기존 케이스 + 새 URL → 새 Playwright 코드
- `GET /health` — 헬스체크

기본 포트는 `9000`이지만 환경변수로 변경 가능합니다.

---

## 1. POST /generate-cases

**Request Body:**

```json
{
  "nl_input": "로그인 페이지에서 admin/1234로 로그인",
  "document_text": null,
  "target_url": "https://shopA.com",
  "techniques": ["equivalence_partition", "boundary_value"],
  "project_context": {
    "name": "ShopA Test",
    "base_url": "https://shopA.com"
  }
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `nl_input` | string \| null | 자연어 입력 (없으면 document_text 사용) |
| `document_text` | string \| null | 기획서에서 추출한 텍스트 |
| `target_url` | string | 테스트 대상 URL (셀렉터 추론용) |
| `techniques` | string[] | 적용할 블랙박스 테스트 기법 |
| `project_context` | object | 프로젝트 메타정보 (참고용) |

**지원 techniques:**
- `equivalence_partition` (동등 분할)
- `boundary_value` (경계값 분석)
- `decision_table` (결정 테이블)
- `state_transition` (상태 전이)
- `error_guessing` (에러 추측)
- `scenario_based` (시나리오 기반)

**Response (200 OK):**

```json
{
  "test_cases": [
    {
      "title": "유효한 ID/PW로 로그인 성공",
      "description": "동등 분할 — 유효 입력 클래스",
      "precondition": "회원 계정이 존재해야 함",
      "steps": [
        {
          "step_no": 1,
          "action": "fill",
          "target": "#username",
          "input": "admin",
          "expected": ""
        },
        {
          "step_no": 2,
          "action": "fill",
          "target": "#password",
          "input": "1234",
          "expected": ""
        },
        {
          "step_no": 3,
          "action": "click",
          "target": "button[type=submit]",
          "input": "",
          "expected": "대시보드로 이동"
        }
      ],
      "expected_result": "/dashboard 페이지로 리다이렉트",
      "priority": "high",
      "category": "login",
      "technique": "equivalence_partition",
      "playwright_code": "import { test, expect } from '@playwright/test';\n\ntest('로그인 성공', async ({ page }) => {\n  await page.goto('https://shopA.com/login');\n  await page.fill('#username', 'admin');\n  await page.fill('#password', '1234');\n  await page.click('button[type=submit]');\n  await expect(page).toHaveURL(/\\/dashboard/);\n});"
    }
  ]
}
```

**중요:**
- `techniques` 배열의 길이만큼 케이스를 만드는 게 권장 (1:1)
- `playwright_code`는 즉시 실행 가능한 완전한 코드여야 함
- 불가능한 기법이면 빈 응답 대신 해당 기법은 건너뛰고 가능한 것만 반환 OK

---

## 2. POST /regenerate-code

**Request Body:**

```json
{
  "test_case": {
    "title": "유효한 ID/PW로 로그인 성공",
    "steps": [...],
    "expected_result": "...",
    "playwright_code": "..."
  },
  "new_target_url": "https://shopB.com",
  "old_target_url": "https://shopA.com"
}
```

| 필드 | 설명 |
|------|------|
| `test_case` | 기존 케이스의 모든 정보 (steps + 기존 코드) |
| `new_target_url` | 새 대상 URL |
| `old_target_url` | 원본 URL (참고용, null 가능) |

**Response (200 OK):**

```json
{
  "playwright_code": "import { test, expect } from '@playwright/test';\n\ntest('로그인 성공 (shopB)', async ({ page }) => {\n  await page.goto('https://shopB.com/signin');\n  await page.fill('input[name=email]', 'admin');\n  ...\n});",
  "target_url": "https://shopB.com",
  "notes": "Selectors adapted: #username → input[name=email]"
}
```

**중요:**
- `notes`는 어떤 부분이 어떻게 바뀌었는지 사람이 읽을 수 있는 설명
- 새 URL의 셀렉터 구조를 모르면 `getByRole`/`getByText` 등 selector-free locator 사용 권장

---

## 3. GET /health

```json
{ "status": "ok" }
```

200이면 healthy, 아니면 백엔드는 mock 모드로 폴백합니다.

---

## 인증

현재는 인증 없음. 같은 Docker 네트워크(`backend_net`) 안에서만 접근 가능합니다.

향후 운영 시:
- API Key를 `X-AI-Service-Key` 헤더로 추가
- 환경변수 `AI_SERVICE_API_KEY`로 백엔드/AI팀 양쪽 공유

---

## 에러 응답

```json
{
  "detail": "에러 메시지"
}
```

상태 코드:
- `400` — 잘못된 요청 (필수 필드 누락 등)
- `500` — LLM 호출 실패, 내부 에러

백엔드는 4xx/5xx를 받으면 Celery 재시도 (최대 2회).

---

## 백엔드 호출 흐름

```
사용자
  ↓ POST /api/v1/test-cases/generate
백엔드 FastAPI
  ↓ placeholder DB 저장 + job_id 발급
  ↓ Celery Task 큐 등록
  ↓ 즉시 202 반환
  
Celery Worker
  ↓ POST /generate-cases   ← AI팀 서버 호출
AI팀 FastAPI (별도 서버)
  ↓ LLM 호출 (OpenAI/Claude/etc)
  ↓ JSON 응답
Celery Worker
  ↓ 응답을 DB의 placeholder에 채워넣음
  ↓ Redis Pub/Sub으로 진행상황 발행
사용자 (WebSocket 구독 중)
  ← /ws/v1/tests/{job_id}/logs 로 실시간 수신
```

---

## 개발 시 mock 모드

AI팀 서버가 아직 없을 때는 백엔드 환경변수에서:

```bash
AI_SERVICE_MOCK=true
```

설정하면 백엔드 안에서 더미 응답을 자동 생성합니다. 데모와 개발이 가능해요.

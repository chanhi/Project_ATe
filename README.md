# ATe — AI Tester Backend

**AI 기반 자동화 소프트웨어 테스팅 플랫폼** 백엔드 서버

자연어(한국어/영어) 입력을 바탕으로 AI가 Playwright 테스트 코드를 생성하고,
Docker 격리 환경에서 실행한 뒤 실시간 로그를 WebSocket으로 스트리밍하는 플랫폼.

> **담당 범위** — Redis/Celery 작업 큐, WebSocket 실시간 통신, 테스트 케이스 관리/실행 API
> 팀: **경기대학교 소프트웨어경영대학 / TQ7** 

---

## 🚀 지금 바로 실행되게 만드는 체크리스트 (5단계)

처음 세팅하거나 Mongo 인증 문제가 났을 때 이 순서대로 하면 됩니다.

```bash
# 1. 환경변수 파일 생성
cp .env.example .env
# (필요하면 .env 내부 DB_PASSWORD, SECRET_KEY 수정)

# 2. (재실행 시만) 기존 볼륨 초기화 — Mongo 인증 실패 해결
docker compose down -v

# 3. 전체 스택 빌드 & 실행
docker compose up --build -d

# 4. 데모 프로젝트 Seed (팀원 누구나 바로 사용 가능)
docker compose exec backend python scripts/seed.py

# 5. 헬스체크
curl http://localhost/health
# → {"status":"healthy", ...}
```

**Seed 후 사용 가능한 project_id:**
- `proj-demo-001` (https://example.com)
- `proj-saucedemo` (https://www.saucedemo.com)

---


## 목차

- [주요 기능](#주요-기능)
- [아키텍처](#아키텍처)
- [빠른 시작](#빠른-시작)
- [프로젝트 구조](#프로젝트-구조)
- [API 레퍼런스](#api-레퍼런스)
- [WebSocket 실시간 로그](#websocket-실시간-로그)
- [개발 가이드](#개발-가이드)
- [테스트](#테스트)
- [환경 변수](#환경-변수)

---

## 주요 기능

- **자연어 → 테스트 코드** — 사용자의 한국어/영어 prompt를 AI가 Playwright 테스트로 변환
- **비동기 테스트 실행** — Redis/Celery 작업 큐로 대량 테스트를 병렬 처리
- **실시간 로그 스트리밍** — WebSocket + Redis Pub/Sub으로 진행 상황을 즉시 전달
- **Step DSL 지원** — DB 등록 없이 JSON 한 번으로 즉시 실행
- **Docker 격리 실행** — 모든 테스트는 격리된 컨테이너 내부에서 수행
- **블랙박스 테스트 기법** — 동등 분할, 경계값 분석 등 6가지 기법 지원
- **다양한 포맷 내보내기** — JSON, CSV, XLSX, MD, YAML, Playwright, HTML

---

## 아키텍처

```
┌─────────────┐      HTTP/WS       ┌─────────────────┐
│  Frontend   │◄──────────────────►│  Nginx (Proxy)  │
│  (React)    │                    └────────┬────────┘
└─────────────┘                             │
                                            ▼
                            ┌───────────────────────────────┐
                            │   Backend (FastAPI)           │
                            │   - REST API                  │
                            │   - WebSocket Handler         │
                            └──┬─────────────┬──────────────┘
                               │             │
                    enqueue    │             │  cache/pub
                               ▼             ▼
                    ┌──────────────┐  ┌──────────────┐
                    │ Redis Broker │  │   MongoDB    │
                    │  - Queue     │  │  - test_cases│
                    │  - Pub/Sub   │  │  - test_runs │
                    │  - Cache     │  │  - documents │
                    └──────┬───────┘  └──────────────┘
                           │
                           ▼
                   ┌───────────────┐
                   │ Celery Worker │
                   │  - Docker     │     ┌──────────────────┐
                   │  - Playwright │────►│  Test Container  │
                   └───────────────┘     │  (isolated)      │
                                         └──────────────────┘
```

### 컴포넌트 역할

| 서비스 | 역할 | 포트 |
|--------|------|------|
| `database` | MongoDB 6.0 — 시나리오/실행 기록 영구 저장 | 27017 (internal) |
| `broker` | Redis 7 — Celery 큐 + Pub/Sub + 상태 캐시 | 6379 (internal) |
| `backend` | FastAPI — REST + WebSocket API | 8000 (internal) |
| `worker` | Celery worker — 격리 컨테이너에서 Playwright 실행 | - |
| `frontend` | Nginx — SPA 호스팅 + 백엔드 프록시 | **80** |

---

## 빠른 시작

### 사전 요구사항

- Docker & Docker Compose v2
- (개발 시) Python 3.12+

### 1. 클론 및 환경 설정

```bash
git clone <repo-url> ate
cd ate

# 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 DB_PASSWORD, SECRET_KEY, OPENAI_API_KEY 등을 수정
```

### 2. 전체 스택 실행

```bash
docker compose up --build
```

처음 실행 시 이미지 빌드 때문에 3~5분 정도 소요됩니다.

### 3. 접속 확인

- **메인**: http://localhost/
- **API 문서**: http://localhost/docs
- **헬스체크**: http://localhost/health

### 4. 로컬 개발 모드 (Docker 없이)

```bash
# Redis + MongoDB만 Docker로 실행
docker compose up -d database broker

# Python 가상환경
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# FastAPI 서버
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 별도 터미널에서 Celery Worker
celery -A main.celery_app worker --loglevel=info -Q test_execution,default
```

---

## 프로젝트 구조

```
ate/
├── docker-compose.yml          # 전체 스택 오케스트레이션
├── nginx.conf                  # Nginx 설정 (SPA + API + WebSocket 프록시)
├── .env.example                # 환경 변수 템플릿
│
├── backend/                    # FastAPI 애플리케이션
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                 # 앱 진입점 + lifespan
│   │
│   ├── api/                    # REST 엔드포인트
│   │   ├── projects.py         #   /projects   (필수 선행)
│   │   ├── documents.py        #   /documents  (기획서 업로드)
│   │   ├── test_cases.py       #   /test-cases (생성/내보내기/재사용)
│   │   ├── test_case_exec.py   #   /test-cases/{id}/execute (실행)
│   │   ├── scenarios.py        #   /scenarios  (v1 호환)
│   │   ├── test_execution.py   #   /tests/*    (v1 호환)
│   │   └── dashboard.py        #   /dashboard
│   │
│   ├── core/                   # 인프라
│   │   ├── config.py           #   Pydantic Settings
│   │   ├── mongo.py            #   MongoDB (Motor) 연결 + 인덱스
│   │   ├── redis_client.py     #   Redis Pub/Sub + 상태 캐시
│   │   ├── celery_app.py       #   Celery 앱 + 큐 라우팅
│   │   ├── exporter.py         #   7가지 포맷 내보내기
│   │   └── step_compiler.py    #   Step DSL → Playwright 코드 변환
│   │
│   ├── schemas/schemas.py      # Pydantic 문서/API 스키마
│   │
│   ├── tasks/                  # Celery 백그라운드 작업
│   │   └── test_runner.py      #   Docker 컨테이너 테스트 실행
│   │
│   └── websocket/handler.py    # WebSocket 핸들러 (실시간 로그)
│
├── worker/                     # Celery Worker 컨테이너
│   ├── Dockerfile
│   └── main.py                 # backend의 Celery app 재사용
│
├── common/                     # 팀 공유 상수/유틸 (플레이스홀더)
│
└── tests/                      # 테스트 스위트 (34개)
    ├── test_backend.py         # Redis/Celery/WebSocket 단위 테스트
    └── test_api_integration.py # FastAPI 엔드포인트 통합 테스트
```

---

## API 레퍼런스

**Base URL**: `http://localhost/api/v1`

모든 응답은 다음 포맷을 따릅니다:

```json
// 성공
{ "status": "success", "data": { ... }, "message": null }

// 에러
{ "status": "error", "data": null, "message": "...", "error_code": "..." }
```

---

### Scenarios — AI팀 진입점

#### `POST /scenarios` — 시나리오 생성

두 가지 플로우 모두 지원:
1. **`nl_prompt`만 먼저 저장** → 나중에 `/scenarios/{id}/code`로 업데이트
2. **AI 결과까지 한번에 저장** — `generated_code`, `ai_validation` 포함

```json
POST /api/v1/scenarios
{
  "project_id": "proj-001",
  "title": "로그인 성공 케이스",
  "nl_prompt": "아이디 admin, 비밀번호 1234 입력 후 로그인 버튼 클릭"
}
```

```json
// 응답 (201)
{
  "status": "success",
  "data": {
    "scenario_id": "scen-a3f2c1d8",
    "project_id": "proj-001",
    "title": "로그인 성공 케이스",
    "created_at": "2026-04-14T10:00:00Z"
  }
}
```

#### `POST /scenarios/{id}/code` — AI 생성 코드 업데이트

```json
{
  "generated_code": "import { test, expect } from '@playwright/test';\n...",
  "ai_validation": {
    "is_valid": true,
    "retry_count": 1,
    "message": "AI 검증 완료"
  }
}
```

#### 그 외

- `GET /scenarios/{id}` — 시나리오 상세 조회
- `GET /scenarios?project_id=proj-001` — 목록 조회
- `DELETE /scenarios/{id}` — 삭제

---

### Test Execution — 실행 파이프라인

#### `POST /tests/run` — 시나리오 기반 비동기 실행

```json
{ "scenario_id": "scen-a3f2c1d8" }
```

```json
// 응답 (202 Accepted)
{
  "status": "success",
  "data": {
    "test_run_id": "run-5a9f8c2d",
    "status": "QUEUED",
    "celery_task_id": "..."
  }
}
```

#### `POST /tests/execute` — DB 우회 즉시 실행 (프론트/AI팀 직결용)

**방식 1: Step DSL** (권장)

```json
{
  "url": "http://localhost:3000/login",
  "title": "로그인 즉시 실행",
  "steps": [
    {"action": "fill",  "target": "#username", "value": "admin"},
    {"action": "fill",  "target": "#password", "value": "1234"},
    {"action": "click", "target": "button[type=submit]"},
    {"action": "assert_url", "value": "/dashboard"}
  ]
}
```

**방식 2: Playwright 코드 직접 전달**

```json
{
  "url": "http://localhost:3000",
  "generated_code": "import { test } from '@playwright/test';\ntest('t', async ({ page }) => { ... });"
}
```

**지원 action 11종**

| action | 설명 | 필수 필드 |
|--------|------|-----------|
| `goto` | URL 이동 | `target` 또는 `value` |
| `fill` | input 값 입력 | `target`, `value` |
| `click` | 요소 클릭 | `target` |
| `type` | 키보드 입력 | `target`, `value` |
| `press` | 특정 키 누르기 (기본 `Enter`) | `target` |
| `wait` | ms 단위 대기 | `value` (ms) |
| `wait_for` | 요소 나타날 때까지 대기 | `target` |
| `assert_text` | 텍스트 포함 검증 | `target`, `value` |
| `assert_url` | URL 검증 | `value` |
| `assert_visible` | 가시성 검증 | `target` |
| `screenshot` | 스크린샷 캡처 | `value` (파일명) |

셀렉터 자동 추론: `"username"` → `"#username"`, `"button[type=submit]"` → 그대로 사용.

#### `GET /tests/{test_run_id}` — 결과 단건 조회

```json
{
  "status": "success",
  "data": {
    "test_run_id": "run-5a9f8c2d",
    "status": "FAILED",
    "started_at": "2026-04-14T10:00:00Z",
    "ended_at": "2026-04-14T10:01:15Z",
    "duration_ms": 75000,
    "error_log": "Timeout 30000ms exceeded. Cannot find element: '#submit-btn'"
  }
}
```

Status 값: `QUEUED` | `PENDING` | `RUNNING` | `SUCCESS` | `FAILED`

#### `GET /tests?scenario_id=...&status=...` — 실행 목록

#### `POST /tests/{id}/cancel` — 실행 취소 (Celery revoke)

---

## WebSocket 실시간 로그

### Endpoint

```
ws://localhost/ws/v1/tests/{test_run_id}/logs
```

### 메시지 포맷 (Server → Client)

```json
// 1) 현재 상태
{ "type": "status", "data": { "test_run_id": "run-xxx", "status": "RUNNING" } }

// 2) 재접속 시 이전 로그 히스토리
{ "type": "history", "data": { "logs": [...], "count": 5 } }

// 3) 실시간 로그
{
  "type": "log",
  "data": {
    "timestamp": "2026-04-14T10:00:05Z",
    "level": "INFO",
    "message": "Navigating to /login",
    "progress_percentage": 25
  }
}

// 4) 테스트 완료
{ "type": "complete", "data": { "test_run_id": "run-xxx", "status": "SUCCESS" } }

// 5) 주기적 heartbeat
{ "type": "heartbeat", "data": { "timestamp": "..." } }
```

### 메시지 포맷 (Client → Server)

```json
// ping
{ "type": "ping" }

// 실행 취소 요청
{ "type": "cancel" }
```

### 프론트 연동 예시 (JavaScript)

```javascript
const ws = new WebSocket(`ws://localhost/ws/v1/tests/${testRunId}/logs`);

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  switch (msg.type) {
    case "log":
      console.log(`[${msg.data.level}] ${msg.data.message}`);
      updateProgress(msg.data.progress_percentage);
      break;
    case "complete":
      alert(`테스트 ${msg.data.status}`);
      ws.close();
      break;
    case "heartbeat":
      ws.send(JSON.stringify({ type: "ping" }));
      break;
  }
};
```

---

## 개발 가이드

### 코드 스타일

- Python 3.12+ 문법 활용 (`str | None`, `list[dict]`)
- 타입 힌트 필수
- 한국어 주석 환영 (팀 맥락 공유용)

### 새 API 엔드포인트 추가

1. `backend/api/<module>.py`에 `APIRouter` 작성
2. `backend/api/__init__.py`에 `include_router` 추가
3. `tests/test_api_integration.py`에 통합 테스트 추가

### 새 Celery Task 추가

1. `backend/tasks/<module>.py`에 `@celery_app.task(name="tasks.<module>.<func>")` 작성
2. `backend/core/celery_app.py`의 `task_routes`에 큐 지정
3. worker가 autodiscover하므로 별도 등록 불필요

### MongoDB 컬렉션 추가

1. `backend/schemas/schemas.py`에 `XxxDoc` Pydantic 모델 작성
2. `backend/core/mongo.py`의 `_create_indexes()`에 인덱스 추가
3. `get_xxx_collection()` 헬퍼 함수 추가

---

## 테스트

### 전체 테스트 실행

```bash
cd ate
pip install -r backend/requirements.txt mongomock-motor
python -m pytest tests/ -v
```

```
============================== 34 passed in 2.46s ==============================
```

### 테스트 구성

| 파일 | 개수 | 범위 |
|------|------|------|
| `test_backend.py` | 17 | Redis, Celery, 스키마, 서명 검증 |
| `test_api_integration.py` | 17 | FastAPI 엔드포인트 E2E (HTTP 레벨) |

### 특정 그룹만 실행

```bash
pytest tests/test_api_integration.py::TestScenarioCreate -v
pytest tests/test_backend.py::TestCeleryTasks -v
```

---

## 환경 변수

`.env` 파일에 다음 항목을 설정:

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `DB_USER` | MongoDB 유저 | `ate_user` |
| `DB_PASSWORD` | MongoDB 비밀번호 | - (필수) |
| `DB_NAME` | MongoDB 데이터베이스명 | `ate_db` |
| `SECRET_KEY` | JWT 서명용 시크릿 | - (필수) |
| `OPENAI_API_KEY` | AI 엔진용 (AI팀 사용) | - |

도커 내부 연결용 URL은 `docker-compose.yml`에 하드코딩되어 있습니다:
- `MONGO_URL=mongodb://...@database:27017/...`
- `REDIS_URL=redis://broker:6379/0`
- `CELERY_BROKER_URL=redis://broker:6379/1`

---

## 문제 해결

### "MongoDB 인증 실패 / backend가 startup에서 죽음"

**가장 흔한 원인**: `.env`의 `DB_USER`/`DB_PASSWORD`를 나중에 바꿨는데,
기존 `mongo_data` 볼륨이 옛날 계정을 들고 있어서 인증이 안 맞는 경우.

`MONGO_INITDB_ROOT_USERNAME/PASSWORD`는 **볼륨이 처음 생성될 때만** 반영됩니다.

해결:
```bash
docker compose down -v           # 볼륨까지 삭제 (주의: 모든 데이터 손실)
docker compose up --build -d     # 새 볼륨으로 재시작
docker compose exec backend python scripts/seed.py  # 데모 프로젝트 다시 생성
```

운영 중인 DB라면 볼륨 삭제 대신 `mongosh`로 접속해서 유저를 수동 생성:
```bash
docker compose exec database mongosh -u admin --authenticationDatabase admin
```

```javascript
use admin
db.createUser({user: "새유저", pwd: "새비밀번호", roles: [{role: "root", db: "admin"}]})
```

### "MongoDB 연결 실패 (단순)"

```bash
docker compose ps                    # database 상태 확인
docker compose logs database         # 로그 확인
docker compose restart database backend
```

### "Celery Task가 실행되지 않음"

```bash
docker compose logs worker           # worker 로그 확인

# Celery 이름 충돌 — broker URL 확인
docker compose exec worker \
  celery -A main.celery_app inspect active
```

### "WebSocket 연결 불가"

Nginx proxy 설정 확인 (`nginx.conf`의 `/ws/` 블록):
```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```

### "테스트 실행이 즉시 실패한다"

워커 컨테이너 안에서 Playwright가 제대로 설치됐는지 확인:
```bash
docker compose exec worker npx playwright --version
docker compose exec worker which node
```

응답이 안 나오면 워커 이미지를 다시 빌드:
```bash
docker compose build --no-cache worker
docker compose up -d
```

### "워커 빌드가 너무 느리다"

Playwright 베이스 이미지(약 1.5GB) 다운로드 때문에 첫 빌드만 5~15분 걸립니다.
이후 빌드는 캐시 덕분에 1분 미만입니다.

---

## 라이선스

Internal project — 경기대학교 산학협력 프로젝트 (NHN CLOUD)

---

## 기여자

**TQ7 팀** — 경기대학교 소프트웨어경영대학

| 이름 | 역할 |
|------|------|
| 정찬희 | 팀장 |
| 홍예준, 양재성, 서세연, 박새길, 응우옌뀐옌, 우정호 | 팀원 |

**지도**: 이한용 교수 / **기업 멘토**: NHN CLOUD 정선일 선임

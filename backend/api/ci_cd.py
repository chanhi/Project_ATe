"""
CI/CD 연동 API
──────────────
GitHub Actions, Jenkins, GitLab CI 연동
"""

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Header, Request

from core.config import get_settings
from core.mongo import (
    get_projects_collection,
    get_scenarios_collection,
    get_test_runs_collection,
    get_webhook_configs_collection,
    get_webhook_events_collection,
)
from core.redis_client import set_test_run_status
from schemas.schemas import (
    APIResponse,
    TestRunDoc,
    TestRunResponse,
    WebhookConfigCreate,
    WebhookConfigDoc,
    WebhookEventDoc,
)
from tasks.test_runner import execute_test
from tasks.ci_cd import send_webhook_callback

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/cicd", tags=["CI/CD Integration"])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Webhook 설정 관리
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/webhooks", response_model=APIResponse, status_code=201,
             summary="CI/CD Webhook 설정 등록")
async def create_webhook_config(config: WebhookConfigCreate):
    """CI/CD 파이프라인과 연동할 Webhook 설정을 등록한다."""
    projects = get_projects_collection()
    webhook_configs = get_webhook_configs_collection()

    # 프로젝트 존재 확인
    project = await projects.find_one({"project_id": config.project_id})
    if not project:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")

    # 문서 저장
    doc = WebhookConfigDoc(
        project_id=config.project_id,
        provider=config.provider,
        webhook_url=config.webhook_url,
        trigger_on=config.trigger_on,
        secret_token=config.secret_token,
        scenario_ids=config.scenario_ids,
    )
    result = await webhook_configs.insert_one(doc.model_dump())

    trigger_url = f"/api/v1/cicd/trigger/{config.provider}"

    return APIResponse(
        status="success",
        data={
            "id": str(result.inserted_id),
            "project_id": config.project_id,
            "provider": config.provider,
            "trigger_url": trigger_url,
            "webhook_url": config.webhook_url,
            "trigger_on": config.trigger_on,
            "is_active": True,
            "scenario_ids": config.scenario_ids,
            "created_at": doc.created_at.isoformat(),
        },
        message=f"Webhook 설정 완료. CI/CD에서 {trigger_url} 로 POST 요청을 보내세요.",
    )


@router.get("/webhooks", response_model=APIResponse, summary="Webhook 설정 목록 조회")
async def list_webhook_configs(project_id: str | None = None):
    webhook_configs = get_webhook_configs_collection()
    query = {}
    if project_id:
        query["project_id"] = project_id

    cursor = webhook_configs.find(query).sort("created_at", -1)
    docs = await cursor.to_list(length=100)

    return APIResponse(
        status="success",
        data=[
            {
                "id": str(d["_id"]),
                "project_id": d["project_id"],
                "provider": d["provider"],
                "webhook_url": d.get("webhook_url"),
                "trigger_on": d.get("trigger_on", []),
                "is_active": d.get("is_active", True),
                "scenario_ids": d.get("scenario_ids"),
            }
            for d in docs
        ],
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  공통 헬퍼: 테스트 실행 등록
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _trigger_tests_for_config(config: dict, payload: dict, event_type: str, provider: str):
    """
    Webhook 설정에 따라 시나리오들의 테스트 실행을 큐에 등록한다.
    event 문서를 생성하고 triggered_test_run_ids를 반환한다.
    """
    projects = get_projects_collection()
    scenarios = get_scenarios_collection()
    test_runs = get_test_runs_collection()
    webhook_events = get_webhook_events_collection()

    # 시나리오 목록 결정
    scenario_ids = config.get("scenario_ids")
    if scenario_ids:
        cursor = scenarios.find({"scenario_id": {"$in": scenario_ids}})
    else:
        cursor = scenarios.find({"project_id": config["project_id"]})
    scenario_list = await cursor.to_list(length=None)

    # 프로젝트 base_url
    project = await projects.find_one({"project_id": config["project_id"]})
    base_url = project["base_url"] if project else "http://localhost:3000"

    # 이벤트 문서 생성
    event_doc = WebhookEventDoc(
        webhook_config_id=str(config["_id"]),
        provider=provider,
        event_type=event_type,
        payload=payload,
        status="processing",
    )
    event_result = await webhook_events.insert_one(event_doc.model_dump())
    event_id = str(event_result.inserted_id)

    # 각 시나리오를 Celery 큐에 등록
    triggered_runs = []
    event_run_ids = []

    for scenario in scenario_list:
        if not scenario.get("generated_code"):
            continue

        test_run_id = f"run-{uuid.uuid4().hex[:8]}"
        test_run_doc = TestRunDoc(
            test_run_id=test_run_id,
            scenario_id=scenario["scenario_id"],
            status="QUEUED",
        )
        await test_runs.insert_one(test_run_doc.model_dump())
        await set_test_run_status(test_run_id, "QUEUED")

        task = execute_test.apply_async(
            args=[test_run_id, scenario["scenario_id"],
                  scenario["generated_code"], base_url],
            queue="test_execution",
        )
        await test_runs.update_one(
            {"test_run_id": test_run_id},
            {"$set": {"celery_task_id": task.id}},
        )

        event_run_ids.append(test_run_id)
        triggered_runs.append(
            TestRunResponse(
                test_run_id=test_run_id,
                status="QUEUED",
                celery_task_id=task.id,
            )
        )

    # 이벤트에 트리거된 run ID 저장
    await webhook_events.update_one(
        {"_id": event_result.inserted_id},
        {"$set": {
            "triggered_test_run_ids": event_run_ids,
            "status": "completed",
        }},
    )

    return event_id, triggered_runs


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GitHub Actions Webhook
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/trigger/github", response_model=APIResponse, status_code=202,
             summary="GitHub Webhook 수신 (자동 테스트 트리거)")
async def trigger_from_github(
    request: Request,
    x_github_event: str = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
):
    """GitHub Actions Webhook 수신 후 HMAC 검증 및 테스트 큐 등록"""
    body = await request.body()
    payload = await request.json()

    event_type = x_github_event or "push"

    webhook_configs = get_webhook_configs_collection()
    cursor = webhook_configs.find({
        "provider": "github_actions",
        "is_active": True,
    })
    configs = await cursor.to_list(length=100)

    if not configs:
        raise HTTPException(status_code=404, detail="활성화된 GitHub Webhook 설정이 없습니다.")

    all_triggered = []

    for config in configs:
        # 이벤트 타입 필터
        if config.get("trigger_on") and event_type not in config["trigger_on"]:
            continue

        # 서명 검증
        if config.get("secret_token") and x_hub_signature_256:
            expected_sig = "sha256=" + hmac.new(
                config["secret_token"].encode(),
                body,
                hashlib.sha256,
            ).hexdigest()

            if not hmac.compare_digest(expected_sig, x_hub_signature_256):
                logger.warning("GitHub Webhook 서명 불일치: %s", config["_id"])
                continue

        event_id, triggered = await _trigger_tests_for_config(
            config, payload, event_type, "github_actions"
        )
        all_triggered.extend(triggered)

        # 결과 콜백 예약
        if config.get("webhook_url"):
            send_webhook_callback.apply_async(
                args=[
                    config["webhook_url"],
                    {
                        "event_id": event_id,
                        "project_id": config["project_id"],
                        "provider": "github_actions",
                        "event_type": event_type,
                        "triggered_test_run_ids": [r.test_run_id for r in triggered],
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                    config.get("secret_token"),
                ],
                queue="ci_cd",
                countdown=5,
            )

    if not all_triggered:
        return APIResponse(
            status="success",
            data={"triggered_test_runs": []},
            message="트리거 조건에 맞는 시나리오가 없습니다.",
        )

    return APIResponse(
        status="success",
        data={
            "event_type": event_type,
            "triggered_test_runs": [r.model_dump() for r in all_triggered],
            "total": len(all_triggered),
        },
        message=f"{len(all_triggered)}개의 테스트가 큐에 등록되었습니다.",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Jenkins Webhook
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/trigger/jenkins", response_model=APIResponse, status_code=202,
             summary="Jenkins Webhook 수신")
async def trigger_from_jenkins(request: Request):
    payload = await request.json()
    event_type = payload.get("event", "build_completed")

    webhook_configs = get_webhook_configs_collection()
    cursor = webhook_configs.find({
        "provider": "jenkins",
        "is_active": True,
    })
    configs = await cursor.to_list(length=100)

    if not configs:
        raise HTTPException(status_code=404, detail="활성화된 Jenkins Webhook 설정이 없습니다.")

    all_triggered = []
    for config in configs:
        if config.get("trigger_on") and event_type not in config["trigger_on"]:
            continue

        _, triggered = await _trigger_tests_for_config(
            config, payload, event_type, "jenkins"
        )
        all_triggered.extend(triggered)

    return APIResponse(
        status="success",
        data={
            "event_type": event_type,
            "triggered_test_runs": [r.model_dump() for r in all_triggered],
            "total": len(all_triggered),
        },
        message=f"{len(all_triggered)}개의 테스트가 큐에 등록되었습니다.",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  범용 Webhook
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.post("/trigger/custom", response_model=APIResponse, status_code=202,
             summary="범용 Webhook 수신")
async def trigger_custom(request: Request):
    payload = await request.json()
    project_id = payload.get("project_id")
    scenario_ids = payload.get("scenario_ids")
    event_type = payload.get("event", "custom_trigger")

    if not project_id:
        raise HTTPException(status_code=400, detail="project_id가 필요합니다.")

    projects = get_projects_collection()
    scenarios = get_scenarios_collection()
    test_runs = get_test_runs_collection()

    project = await projects.find_one({"project_id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")

    # 시나리오 조회
    if scenario_ids:
        cursor = scenarios.find({"scenario_id": {"$in": scenario_ids}})
    else:
        cursor = scenarios.find({"project_id": project_id})
    scenario_list = await cursor.to_list(length=None)

    triggered_runs = []
    for scenario in scenario_list:
        if not scenario.get("generated_code"):
            continue

        test_run_id = f"run-{uuid.uuid4().hex[:8]}"
        test_run_doc = TestRunDoc(
            test_run_id=test_run_id,
            scenario_id=scenario["scenario_id"],
            status="QUEUED",
        )
        await test_runs.insert_one(test_run_doc.model_dump())
        await set_test_run_status(test_run_id, "QUEUED")

        task = execute_test.apply_async(
            args=[test_run_id, scenario["scenario_id"],
                  scenario["generated_code"], project["base_url"]],
            queue="test_execution",
        )
        await test_runs.update_one(
            {"test_run_id": test_run_id},
            {"$set": {"celery_task_id": task.id}},
        )

        triggered_runs.append(
            TestRunResponse(test_run_id=test_run_id, status="QUEUED", celery_task_id=task.id)
        )

    return APIResponse(
        status="success",
        data={
            "event_type": event_type,
            "triggered_test_runs": [r.model_dump() for r in triggered_runs],
            "total": len(triggered_runs),
        },
        message=f"{len(triggered_runs)}개의 테스트가 큐에 등록되었습니다.",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Webhook 이벤트 상태 조회
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.get("/events/{event_id}", response_model=APIResponse,
            summary="Webhook 이벤트 상태 조회")
async def get_webhook_event(event_id: str):
    """CI/CD 트리거된 테스트들의 전체 상태를 조회한다."""
    webhook_events = get_webhook_events_collection()
    test_runs = get_test_runs_collection()

    try:
        event = await webhook_events.find_one({"_id": ObjectId(event_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="잘못된 event_id 형식")

    if not event:
        raise HTTPException(status_code=404, detail="이벤트를 찾을 수 없습니다.")

    # 트리거된 테스트 상태 조회
    run_ids = event.get("triggered_test_run_ids", [])
    test_runs_data = []
    if run_ids:
        cursor = test_runs.find({"test_run_id": {"$in": run_ids}})
        runs = await cursor.to_list(length=None)

        for run in runs:
            test_runs_data.append({
                "test_run_id": run["test_run_id"],
                "scenario_id": run["scenario_id"],
                "status": run["status"],
                "started_at": run.get("started_at").isoformat() if run.get("started_at") else None,
                "ended_at": run.get("ended_at").isoformat() if run.get("ended_at") else None,
                "duration_ms": run.get("duration_ms"),
                "error_log": run.get("error_log"),
            })

    # 전체 상태 판정
    statuses = [r["status"] for r in test_runs_data]
    if all(s == "SUCCESS" for s in statuses) and statuses:
        overall = "SUCCESS"
    elif any(s == "FAILED" for s in statuses):
        overall = "FAILED"
    elif any(s in ("RUNNING", "QUEUED", "PENDING") for s in statuses):
        overall = "IN_PROGRESS"
    else:
        overall = "UNKNOWN"

    return APIResponse(
        status="success",
        data={
            "event_id": event_id,
            "provider": event.get("provider"),
            "event_type": event.get("event_type"),
            "overall_status": overall,
            "test_runs": test_runs_data,
            "total": len(test_runs_data),
            "created_at": event.get("created_at").isoformat() if event.get("created_at") else None,
        },
    )

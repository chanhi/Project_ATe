"""
WebSocket 실시간 통신 모듈
──────────────────────────
Endpoint: ws://localhost:8000/ws/v1/tests/{test_run_id}/logs
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.config import get_settings
from core.redis_client import (
    get_test_log_history,
    get_test_run_status,
    subscribe_test_logs,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

_active_connections: dict[str, set[WebSocket]] = {}


def _get_connections(test_run_id: str) -> set[WebSocket]:
    if test_run_id not in _active_connections:
        _active_connections[test_run_id] = set()
    return _active_connections[test_run_id]


def _remove_connection(test_run_id: str, ws: WebSocket) -> None:
    conns = _active_connections.get(test_run_id, set())
    conns.discard(ws)
    if not conns:
        _active_connections.pop(test_run_id, None)


@router.websocket("/tests/{test_run_id}/logs")
async def websocket_test_logs(websocket: WebSocket, test_run_id: str):
    """테스트 실행 실시간 로그 스트리밍"""
    await websocket.accept()
    connections = _get_connections(test_run_id)
    connections.add(websocket)

    logger.info("WebSocket 연결: %s (활성: %d)", test_run_id, len(connections))

    try:
        # ── 현재 상태 전송 ──
        status = await get_test_run_status(test_run_id)
        if status:
            await _send_json(websocket, {
                "type": "status",
                "data": {"test_run_id": test_run_id, "status": status.get("status", "UNKNOWN")},
            })
        else:
            await _send_json(websocket, {
                "type": "error",
                "data": {"message": f"테스트 실행을 찾을 수 없습니다: {test_run_id}"},
            })

        # ── 로그 히스토리 전송 ──
        history = await get_test_log_history(test_run_id)
        if history:
            await _send_json(websocket, {
                "type": "history",
                "data": {"logs": history, "count": len(history)},
            })

        # ── 이미 완료된 테스트 ──
        if status and status.get("status") in ("SUCCESS", "FAILED"):
            await _send_json(websocket, {
                "type": "complete",
                "data": {
                    "test_run_id": test_run_id,
                    "status": status["status"],
                    "message": "테스트가 이미 완료되었습니다.",
                },
            })
            await _handle_client_messages(websocket, test_run_id)
            return

        # ── 실시간 로그 스트리밍 ──
        await _stream_logs(websocket, test_run_id)

    except WebSocketDisconnect:
        logger.info("WebSocket 종료 (클라이언트): %s", test_run_id)
    except Exception as e:
        logger.error("WebSocket 에러: %s — %s", test_run_id, str(e))
        try:
            await _send_json(websocket, {
                "type": "error",
                "data": {"message": f"서버 에러: {str(e)}"},
            })
        except Exception:
            pass
    finally:
        _remove_connection(test_run_id, websocket)


async def _stream_logs(websocket: WebSocket, test_run_id: str) -> None:
    async with subscribe_test_logs(test_run_id) as subscriber:
        pubsub_task = asyncio.create_task(
            _forward_pubsub_to_ws(websocket, test_run_id, subscriber)
        )
        receive_task = asyncio.create_task(
            _handle_client_messages(websocket, test_run_id)
        )

        done, pending = await asyncio.wait(
            [pubsub_task, receive_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


async def _forward_pubsub_to_ws(websocket: WebSocket, test_run_id: str, subscriber):
    async for log_entry in subscriber:
        await _send_json(websocket, {"type": "log", "data": log_entry})

        if log_entry.get("progress_percentage", 0) >= 100:
            status = await get_test_run_status(test_run_id)
            final_status = status.get("status", "UNKNOWN") if status else "UNKNOWN"
            await _send_json(websocket, {
                "type": "complete",
                "data": {"test_run_id": test_run_id, "status": final_status},
            })
            break


async def _handle_client_messages(websocket: WebSocket, test_run_id: str):
    while True:
        try:
            raw = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=settings.WS_HEARTBEAT_INTERVAL,
            )
            data = json.loads(raw)

            if data.get("type") == "ping":
                await _send_json(websocket, {
                    "type": "pong",
                    "data": {"timestamp": datetime.now(timezone.utc).isoformat()},
                })
            elif data.get("type") == "cancel":
                await _send_json(websocket, {
                    "type": "ack",
                    "data": {"message": "취소 요청 접수됨"},
                })

        except asyncio.TimeoutError:
            try:
                await websocket.send_json({
                    "type": "heartbeat",
                    "data": {"timestamp": datetime.now(timezone.utc).isoformat()},
                })
            except Exception:
                break
        except (WebSocketDisconnect, RuntimeError):
            break


async def _send_json(websocket: WebSocket, data: dict):
    try:
        await websocket.send_json(data)
    except (WebSocketDisconnect, RuntimeError):
        raise WebSocketDisconnect()


def get_active_connection_count() -> dict:
    return {
        "total": sum(len(conns) for conns in _active_connections.values()),
        "by_test_run": {
            run_id: len(conns) for run_id, conns in _active_connections.items()
        },
    }

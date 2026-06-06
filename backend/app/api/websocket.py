"""WebSocket 处理器 — 实时推送 Pipeline 进度、Token 流、HITL 通知"""

import json
from fastapi import WebSocket, WebSocketDisconnect
from state.sqlite_store import SQLiteStateStore


class ConnectionManager:
    """管理 WebSocket 连接，支持序列号追踪和断线重放"""

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._seq_counters: dict[str, int] = {}

    async def connect(self, thread_id: str, websocket: WebSocket):
        await websocket.accept()
        if thread_id not in self._connections:
            self._connections[thread_id] = []
            self._seq_counters[thread_id] = 0
        self._connections[thread_id].append(websocket)

    def disconnect(self, thread_id: str, websocket: WebSocket):
        if thread_id in self._connections:
            self._connections[thread_id].remove(websocket)

    def _next_seq(self, thread_id: str) -> int:
        self._seq_counters[thread_id] = self._seq_counters.get(thread_id, 0) + 1
        return self._seq_counters[thread_id]

    async def send_progress(self, thread_id: str, agent: str, percent: float):
        await self._broadcast(thread_id, {
            "type": "progress", "agent": agent, "percent": percent,
            "seq": self._next_seq(thread_id),
        })

    async def send_token(self, thread_id: str, agent: str, chunk: str):
        await self._broadcast(thread_id, {
            "type": "token_stream", "agent": agent, "chunk": chunk,
            "seq": self._next_seq(thread_id),
        })

    async def send_hitl_pause(self, thread_id: str, agent: str, data: dict, reason: str, confidence: float):
        await self._broadcast(thread_id, {
            "type": "hitl_pause", "agent": agent, "data": data,
            "reason": reason, "confidence": confidence,
            "seq": self._next_seq(thread_id),
        })

    async def send_stage_complete(self, thread_id: str, agent: str, summary: dict):
        await self._broadcast(thread_id, {
            "type": "stage_complete", "agent": agent, "summary": summary,
            "seq": self._next_seq(thread_id),
        })

    async def send_error(self, thread_id: str, agent: str, message: str, recoverable: bool = True):
        await self._broadcast(thread_id, {
            "type": "error", "agent": agent, "message": message,
            "recoverable": recoverable,
            "seq": self._next_seq(thread_id),
        })

    async def send_complete(self, thread_id: str, result: dict):
        await self._broadcast(thread_id, {
            "type": "complete", "result": result,
            "seq": self._next_seq(thread_id),
        })

    async def handle_resync(self, thread_id: str, websocket: WebSocket, last_seq: int):
        """客户端重连后回放遗漏的事件（简化实现：仅回复当前状态）"""
        store = SQLiteStateStore()
        state = await store.load(thread_id)
        if state:
            await websocket.send_json({
                "type": "resync_complete",
                "thread_id": thread_id,
                "current_agent": state.pipeline_state.current_agent,
                "progress": state.pipeline_state.progress,
                "pending_hitl": bool(state.pending_hitl),
            })

    async def _broadcast(self, thread_id: str, message: dict):
        if thread_id not in self._connections:
            return
        dead = []
        for ws in self._connections[thread_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections[thread_id].remove(ws)


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, thread_id: str):
    await manager.connect(thread_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "resync":
                await manager.handle_resync(
                    thread_id, websocket, data.get("last_seq", 0)
                )
            elif msg_type == "hitl_resolved":
                # HITL 编辑已提交 → 通知其他连接
                pass
            elif msg_type == "request_pause":
                pass
            elif msg_type == "request_skip":
                pass

    except WebSocketDisconnect:
        manager.disconnect(thread_id, websocket)

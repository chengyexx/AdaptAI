"""REST API 端点 — 会话管理、HITL、导出"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import PlainTextResponse
from state.models import SessionState, PipelineStatus, Artifacts
from state.sqlite_store import SQLiteStateStore
from orchestrator.pipeline import Pipeline

router = APIRouter(prefix="/api")

_state_store = SQLiteStateStore()


def get_state_store() -> SQLiteStateStore:
    return _state_store


@router.post("/sessions")
async def create_session(
    text: str = Form(""),
    file: UploadFile | None = File(None),
):
    """创建新会话——上传文本或文件"""
    content = text
    if file:
        raw = await file.read()
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            content = raw.decode("gbk", errors="ignore")

    if not content.strip():
        raise HTTPException(status_code=400, detail="文本内容不能为空")

    state = SessionState(
        status=PipelineStatus.CREATED,
        artifacts=Artifacts(chapters=[
            {"index": 1, "title": "全文", "text": content, "summary": content[:200], "char_count": len(content)}
        ]),
    )
    await _state_store.save(state)
    return {"thread_id": state.thread_id, "status": state.status.value}


@router.get("/sessions/{thread_id}")
async def get_session(thread_id: str):
    """获取完整会话状态（冷启动恢复）"""
    state = await _state_store.load(thread_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "thread_id": state.thread_id,
        "status": state.status.value,
        "artifacts": {
            "chapters": state.artifacts.chapters,
            "characters": state.artifacts.characters,
            "scenes": state.artifacts.scenes,
            "adaptation_notes": state.artifacts.adaptation_notes,
        },
        "pipeline_state": {
            "current_agent": state.pipeline_state.current_agent,
            "progress": state.pipeline_state.progress,
        },
        "pending_hitl": {
            "node": state.pending_hitl.node,
            "reason": state.pending_hitl.reason,
            "confidence": state.pending_hitl.confidence,
        } if state.pending_hitl else None,
        "errors": state.errors,
    }


@router.post("/sessions/{thread_id}/start")
async def start_pipeline(thread_id: str):
    """启动 Pipeline 执行"""
    state = await _state_store.load(thread_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    pipeline = Pipeline(_state_store)
    state = await pipeline.execute(state)
    return {"thread_id": thread_id, "status": state.status.value}


@router.post("/sessions/{thread_id}/hitl/submit")
async def submit_hitl(thread_id: str, edits: dict):
    """提交 HITL 编辑结果"""
    state = await _state_store.load(thread_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 将编辑合并到 artifacts
    if "characters" in edits:
        state.artifacts.characters = edits["characters"]
    if "scenes" in edits:
        state.artifacts.scenes = edits["scenes"]

    # 清除 HITL 挂起状态
    state.pending_hitl = None

    # 恢复到对应 Agent 的完成状态
    hitl_to_done = {
        PipelineStatus.CHAR_HITL: PipelineStatus.CHAR_DONE,
        PipelineStatus.SCENE_HITL: PipelineStatus.SCENE_DONE,
        PipelineStatus.SCRIPT_HITL: PipelineStatus.SCRIPT_DONE,
    }
    state.status = hitl_to_done.get(state.status, state.status)
    await _state_store.save(state)

    return {"thread_id": thread_id, "status": state.status.value}


@router.get("/sessions/{thread_id}/export")
async def export_yaml(thread_id: str):
    """下载最终 YAML"""
    state = await _state_store.load(thread_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    if not state.artifacts.script_yaml:
        raise HTTPException(status_code=400, detail="剧本尚未生成")
    return PlainTextResponse(content=state.artifacts.script_yaml, media_type="text/yaml")


@router.get("/sessions")
async def list_sessions(limit: int = 20):
    """列出最近会话"""
    sessions = await _state_store.list_sessions(limit)
    return [
        {"thread_id": s.thread_id, "status": s.status.value, "updated_at": s.updated_at}
        for s in sessions
    ]

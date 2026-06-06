"""REST API 端点 — 会话管理、HITL 审阅、导出、动态路由

动态路由策略:
  - 总字数 < 2万  → Simple Pipeline (快、便宜、连贯性好)
  - 总字数 >= 2万 → Scout-Map-Reduce (切片稳健、大规模适配)
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import PlainTextResponse
from state.models import SessionState, PipelineStatus, Artifacts
from state.sqlite_store import SQLiteStateStore
from agents.chapter_parser import ChapterParser
from orchestrator.scout_map_pipeline import ScoutMapReducePipeline
from orchestrator.pipeline import HappyPathPipeline

router = APIRouter(prefix="/api")

_state_store = SQLiteStateStore()
_chapter_parser = ChapterParser()

# 动态路由阈值: 2万字
ROUTING_THRESHOLD = 20_000


def get_state_store() -> SQLiteStateStore:
    return _state_store


def _get_ws_manager():
    from .websocket import manager
    return manager


# ── 帮助函数 ──────────────────────────────────────────────

def _total_chars(state: SessionState) -> int:
    """计算会话的总字符数"""
    return sum(c.get("char_count", len(c.get("text", ""))) for c in state.artifacts.chapters)

def _should_use_smr(state: SessionState) -> bool:
    """动态路由: 超过阈值使用 Scout-Map-Reduce"""
    return _total_chars(state) >= ROUTING_THRESHOLD

# ── 创建会话 ──────────────────────────────────────────────

@router.post("/sessions")
async def create_session(
    text: str = Form(""),
    file: UploadFile | None = File(None),
):
    """创建新会话——上传文本或文件，自动分章"""
    content = text
    if file:
        raw = await file.read()
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            content = raw.decode("gbk", errors="ignore")

    if not content.strip():
        raise HTTPException(status_code=400, detail="文本内容不能为空")

    chapters = _chapter_parser.parse(content)

    state = SessionState(
        status=PipelineStatus.CREATED,
        artifacts=Artifacts(chapters=chapters),
    )
    await _state_store.save(state)

    total_chars = _total_chars(state)
    use_smr = _should_use_smr(state)

    return {
        "thread_id": state.thread_id,
        "status": state.status.value,
        "chapters_detected": len(chapters),
        "total_chars": total_chars,
        "pipeline_mode": "scout-map-reduce" if use_smr else "simple",
    }


# ── 获取会话状态 ──────────────────────────────────────────

@router.get("/sessions/{thread_id}")
async def get_session(thread_id: str):
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


# ── 后台执行 ──────────────────────────────────────────────

async def _run_pipeline_background(thread_id: str):
    """后台执行 Pipeline — 动态选择 HappyPath 或 ScoutMapReduce"""
    state = await _state_store.load(thread_id)
    if state is None:
        return

    ws_manager = _get_ws_manager()
    total = _total_chars(state)

    if _should_use_smr(state):
        pipeline = ScoutMapReducePipeline(_state_store, ws_manager=ws_manager)
        mode = "scout-map-reduce"
    else:
        pipeline = HappyPathPipeline(_state_store, ws_manager=ws_manager)
        mode = "happy-path"

    await pipeline.execute(state)


async def _run_pipeline_resume(thread_id: str, resume_from: PipelineStatus):
    """从指定检查点恢复 Pipeline"""
    state = await _state_store.load(thread_id)
    if state is None:
        return

    ws_manager = _get_ws_manager()

    if _should_use_smr(state):
        pipeline = ScoutMapReducePipeline(_state_store, ws_manager=ws_manager)
    else:
        pipeline = HappyPathPipeline(_state_store, ws_manager=ws_manager)

    await pipeline.execute(state, resume_from=resume_from)


# ── 启动 Pipeline ─────────────────────────────────────────

@router.post("/sessions/{thread_id}/start")
async def start_pipeline(thread_id: str, background_tasks: BackgroundTasks):
    """启动 Pipeline（后台异步执行）"""
    state = await _state_store.load(thread_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    allowed = (
        PipelineStatus.CREATED,
        PipelineStatus.ERROR,
        PipelineStatus.PAUSED,
    )
    if state.status not in allowed:
        return {
            "thread_id": thread_id,
            "status": state.status.value,
            "message": "Pipeline 已在运行中",
        }

    pipeline_mode = "scout-map-reduce" if _should_use_smr(state) else "happy-path"
    background_tasks.add_task(_run_pipeline_background, thread_id)

    return {
        "thread_id": thread_id,
        "status": "running",
        "pipeline_mode": pipeline_mode,
        "message": "Pipeline 已在后台启动",
    }


# ── HITL 审阅（通用检查点）──────────────────────────────

@router.post("/sessions/{thread_id}/hitl/continue")
async def hitl_continue(
    thread_id: str,
    edits: dict,
    background_tasks: BackgroundTasks,
):
    """提交 HITL 编辑并继续执行（适配所有 Agent 的 HITL 检查点）"""
    state = await _state_store.load(thread_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 合并用户编辑
    if "characters" in edits:
        state.artifacts.characters = edits["characters"]
    if "scenes" in edits:
        state.artifacts.scenes = edits["scenes"]

    # 确定当前 HITL 类型 → 恢复状态
    hitl_to_done = {
        PipelineStatus.SCOUT_HITL:  PipelineStatus.CHAR_DONE,
        PipelineStatus.CHAR_HITL:   PipelineStatus.CHAR_DONE,
        PipelineStatus.SCENE_HITL:  PipelineStatus.SCENE_DONE,
        PipelineStatus.SCRIPT_HITL: PipelineStatus.SCRIPT_DONE,
    }
    resume_from = state.status
    state.status = hitl_to_done.get(state.status, state.status)
    state.pending_hitl = None
    await _state_store.save(state)

    background_tasks.add_task(_run_pipeline_resume, thread_id, resume_from)

    return {
        "thread_id": thread_id,
        "status": state.status.value,
        "message": "已应用编辑，继续执行",
    }


@router.post("/sessions/{thread_id}/hitl/skip-continue")
async def hitl_skip_continue(
    thread_id: str,
    background_tasks: BackgroundTasks,
):
    """跳过任何 HITL 审阅，直接继续执行"""
    state = await _state_store.load(thread_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    hitl_to_done = {
        PipelineStatus.SCOUT_HITL:  PipelineStatus.CHAR_DONE,
        PipelineStatus.CHAR_HITL:   PipelineStatus.CHAR_DONE,
        PipelineStatus.SCENE_HITL:  PipelineStatus.SCENE_DONE,
        PipelineStatus.SCRIPT_HITL: PipelineStatus.SCRIPT_DONE,
    }
    resume_from = state.status
    state.status = hitl_to_done.get(state.status, state.status)
    state.pending_hitl = None
    await _state_store.save(state)

    background_tasks.add_task(_run_pipeline_resume, thread_id, resume_from)

    return {
        "thread_id": thread_id,
        "status": state.status.value,
        "message": "已跳过审阅，继续执行",
    }


# ── 导出 ──────────────────────────────────────────────────

@router.get("/sessions/{thread_id}/export")
async def export_yaml(thread_id: str):
    state = await _state_store.load(thread_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    if not state.artifacts.script_yaml:
        raise HTTPException(status_code=400, detail="剧本尚未生成")
    return PlainTextResponse(content=state.artifacts.script_yaml, media_type="text/yaml")


@router.get("/sessions")
async def list_sessions(limit: int = 20):
    sessions = await _state_store.list_sessions(limit)
    return [
        {"thread_id": s.thread_id, "status": s.status.value, "updated_at": s.updated_at}
        for s in sessions
    ]

"""REST API 端点 — 会话管理、HITL 审阅、导出、动态路由

动态路由策略:
  - 总字数 < 2万  → Simple Pipeline (快、便宜、连贯性好)
  - 总字数 >= 2万 → Scout-Map-Reduce (切片稳健、大规模适配)
"""

import asyncio
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
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
        "pipeline_mode": "scout-map-reduce" if use_smr else "happy-path",
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
            "locations": state.artifacts.locations,
            "scenes": state.artifacts.scenes,
            "script_yaml": state.artifacts.script_yaml,
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
    import logging, traceback
    _log = logging.getLogger("adaptai")
    _log.warning(f"[BG] Started: {thread_id[:8]}")

    state = await _state_store.load(thread_id)
    if state is None:
        _log.warning(f"[BG] No state!")
        return

    # 不在此处修改 status — 让 Pipeline 内部自己管理状态流转
    # （否则 Pipeline.execute() 的 start 检查会因 status=PARSING 而直接跳过执行）
    state.pipeline_state.current_agent = "pipeline"
    state.pipeline_state.progress = 0.0
    _log.warning(f"[BG] Starting with status={state.status}, total_chars={_total_chars(state)}")

    ws_manager = _get_ws_manager()
    _log.warning(f"[BG] ws_manager={'OK' if ws_manager else 'None'}")

    if _should_use_smr(state):
        pipeline = ScoutMapReducePipeline(_state_store, ws_manager=ws_manager)
        mode = "scout-map-reduce"
    else:
        pipeline = HappyPathPipeline(_state_store, ws_manager=ws_manager)
        mode = "happy-path"
    _log.warning(f"[BG] Pipeline={mode}, calling execute()...")

    try:
        await pipeline.execute(state)
        _log.warning(f"[BG] execute done: status={state.status}")
    except Exception as e:
        _log.warning(f"[BG] CRASH: {type(e).__name__}: {e}")
        traceback.print_exc()
        # 后台任务异常兜底 — 确保错误状态被持久化
        state.status = PipelineStatus.ERROR
        state.errors.append({"type": "background_crash", "message": str(e)})
        await _state_store.save(state)
        if ws_manager:
            try:
                await ws_manager.send_error(thread_id, "pipeline", str(e))
            except Exception:
                pass


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

    try:
        await pipeline.execute(state, resume_from=resume_from)
    except Exception as e:
        state.status = PipelineStatus.ERROR
        state.errors.append({"type": "resume_crash", "message": str(e)})
        await _state_store.save(state)
        if ws_manager:
            try:
                await ws_manager.send_error(thread_id, "pipeline", str(e))
            except Exception:
                pass


# ── 启动 Pipeline ─────────────────────────────────────────

@router.post("/sessions/{thread_id}/start")
async def start_pipeline(thread_id: str):
    """启动 Pipeline（后台异步执行）"""
    state = await _state_store.load(thread_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    allowed = (
        PipelineStatus.CREATED,
        PipelineStatus.ERROR,
        PipelineStatus.PAUSED,
    )
    # 允许从任何卡住的状态恢复（如服务器重启/自动重载中断了后台任务）
    stuck_statuses = {
        PipelineStatus.PARSING, PipelineStatus.PARSED,
        PipelineStatus.CHAR_EXTRACTING, PipelineStatus.CHAR_DONE,
        PipelineStatus.SCENE_SEGMENTING, PipelineStatus.SCENE_DONE,
        PipelineStatus.SCRIPT_GENERATING, PipelineStatus.SCRIPT_DONE,
        PipelineStatus.VALIDATING,
    }
    if state.status not in allowed:
        if state.status in stuck_statuses:
            # 后台任务已被中断，重置为错误状态允许重新启动
            state.status = PipelineStatus.ERROR
            state.errors.append({
                "type": "recovery",
                "message": f"从 {state.status.value} 状态恢复 — 上次执行可能因服务重启而中断",
            })
            await _state_store.save(state)
        else:
            return {
                "thread_id": thread_id,
                "status": state.status.value,
                "message": "Pipeline 已在运行中",
            }

    pipeline_mode = "scout-map-reduce" if _should_use_smr(state) else "happy-path"
    # 使用 asyncio.create_task 立即启动，避免 BackgroundTasks 在 Windows 上的延迟问题
    asyncio.create_task(_run_pipeline_background(thread_id))

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

    asyncio.create_task(_run_pipeline_resume(thread_id, resume_from))

    return {
        "thread_id": thread_id,
        "status": state.status.value,
        "message": "已应用编辑，继续执行",
    }


@router.post("/sessions/{thread_id}/hitl/skip-continue")
async def hitl_skip_continue(
    thread_id: str,
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

    asyncio.create_task(_run_pipeline_resume(thread_id, resume_from))

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
    result = []
    for s in sessions:
        chapters = s.artifacts.chapters
        first_title = ""
        if chapters and len(chapters) > 0:
            first_title = chapters[0].get("title", "") or ""
            # 去掉 markdown 标记
            first_title = first_title.lstrip("#").strip()[:50]
        total_chars = sum(c.get("char_count", len(c.get("text", ""))) for c in chapters)
        result.append({
            "thread_id": s.thread_id,
            "status": s.status.value,
            "updated_at": s.updated_at,
            "title": first_title or "(无标题)",
            "chapter_count": len(chapters),
            "total_chars": total_chars,
            "pipeline_mode": "scout-map-reduce" if total_chars >= ROUTING_THRESHOLD else "happy-path",
        })
    return result


@router.delete("/sessions/{thread_id}")
async def delete_session(thread_id: str):
    deleted = await _state_store.delete(thread_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"thread_id": thread_id, "deleted": True}

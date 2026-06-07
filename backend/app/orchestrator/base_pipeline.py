"""BasePipeline — Pipeline 基类，提供共享持久化/推送/日志方法"""

from state.models import SessionState
from state.sqlite_store import SQLiteStateStore


class BasePipeline:
    """所有 Pipeline 共享的基类"""

    def __init__(self, state_store: SQLiteStateStore | None = None, ws_manager=None):
        self.state_store = state_store or SQLiteStateStore()
        self.ws_manager = ws_manager

    # ═══════════════════════════════════════════════════════
    # Shared Helpers
    # ═══════════════════════════════════════════════════════

    async def _persist(self, state: SessionState) -> None:
        try:
            await self.state_store.save(state)
        except Exception:
            pass

    async def _push_progress(self, tid: str, agent: str, percent: float) -> None:
        if self.ws_manager:
            try:
                await self.ws_manager.send_progress(tid, agent, percent)
            except Exception:
                pass

    async def _push_stage_complete(self, tid: str, agent: str) -> None:
        if self.ws_manager:
            try:
                await self.ws_manager.send_stage_complete(tid, agent, {"agent": agent})
            except Exception:
                pass

    async def _push_error(self, tid: str, agent: str, message: str) -> None:
        if self.ws_manager:
            try:
                await self.ws_manager.send_error(tid, agent, message, recoverable=True)
            except Exception:
                pass

    async def _push_complete(self, tid: str, state: SessionState) -> None:
        if self.ws_manager:
            try:
                await self.ws_manager.send_complete(tid, {
                    "thread_id": state.thread_id,
                    "status": state.status.value,
                    "script_yaml": state.artifacts.script_yaml,
                    "characters": state.artifacts.characters,
                    "scenes": state.artifacts.scenes,
                })
            except Exception:
                pass

    async def _log(self, tid: str, level: str, message: str) -> None:
        if self.ws_manager:
            try:
                await self.ws_manager.send_log(tid, level, message)
            except Exception:
                pass

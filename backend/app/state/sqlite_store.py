"""SQLite 实现 — 基于 aiosqlite 的会话状态持久化，支持 Checkpointer 回溯"""

import aiosqlite
import json
from dataclasses import asdict
from pathlib import Path
from datetime import datetime, UTC

from .repository import StateRepository
from .models import SessionState, PipelineStatus, Artifacts, PipelineMeta, HITLRequest
from config import settings


class SQLiteStateStore(StateRepository):
    """SQLite 持久化实现

    设计要点：
    - 大文本字段以文件指针存储，仅摘要/元数据内联于 SQLite 行中
    - 每个 thread_id 对应一行，save() 为 upsert 语义
    - 数据库文件路径由 settings.database_path 控制，默认 data/state.db
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or settings.database_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    async def _get_db(self) -> aiosqlite.Connection:
        db = await aiosqlite.connect(self.db_path)
        db.row_factory = aiosqlite.Row
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                thread_id       TEXT PRIMARY KEY,
                status          TEXT NOT NULL DEFAULT 'created',
                artifacts_json  TEXT DEFAULT '{}',
                pipeline_json   TEXT DEFAULT '{}',
                pending_hitl_json TEXT,
                errors_json     TEXT DEFAULT '[]',
                created_at      TEXT,
                updated_at      TEXT
            )
        """)
        await db.commit()
        return db

    async def save(self, state: SessionState) -> None:
        state.updated_at = datetime.now(UTC).isoformat()
        db = await self._get_db()
        await db.execute("""
            INSERT OR REPLACE INTO sessions
                (thread_id, status, artifacts_json, pipeline_json,
                 pending_hitl_json, errors_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            state.thread_id,
            state.status.value,
            self._serialize(state.artifacts),
            self._serialize(state.pipeline_state),
            self._serialize(state.pending_hitl) if state.pending_hitl else None,
            json.dumps(state.errors, ensure_ascii=False),
            state.created_at,
            state.updated_at,
        ))
        await db.commit()
        await db.close()

    async def load(self, thread_id: str) -> SessionState | None:
        db = await self._get_db()
        cursor = await db.execute(
            "SELECT * FROM sessions WHERE thread_id = ?", (thread_id,))
        row = await cursor.fetchone()
        await db.close()
        if row is None:
            return None
        return self._row_to_state(row)

    async def list_sessions(self, limit: int = 20) -> list[SessionState]:
        db = await self._get_db()
        cursor = await db.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,))
        rows = await cursor.fetchall()
        await db.close()
        return [self._row_to_state(r) for r in rows]

    async def delete(self, thread_id: str) -> bool:
        db = await self._get_db()
        cursor = await db.execute(
            "DELETE FROM sessions WHERE thread_id = ?", (thread_id,))
        await db.commit()
        affected = cursor.rowcount
        await db.close()
        return affected > 0

    # ── 内部辅助 ──

    @staticmethod
    def _serialize(obj) -> str:
        """将 dataclass 序列化为 JSON，支持嵌套对象。
        优先使用 dataclasses.asdict，回退到 vars + repr 用于未知类型。"""
        try:
            return json.dumps(asdict(obj), ensure_ascii=False, default=str)
        except TypeError:
            # asdict 失败（非 dataclass），回退到 vars
            return json.dumps(obj, default=vars, ensure_ascii=False)

    @staticmethod
    def _row_to_state(row) -> SessionState:
        """将数据库行反序列化为 SessionState"""
        artifacts_dict = json.loads(row["artifacts_json"])
        pipeline_dict = json.loads(row["pipeline_json"])

        artifacts = Artifacts(
            chapters=artifacts_dict.get("chapters", []),
            characters=artifacts_dict.get("characters", []),
            locations=artifacts_dict.get("locations", []),
            scenes=artifacts_dict.get("scenes", []),
            script_yaml=artifacts_dict.get("script_yaml"),
            adaptation_notes=artifacts_dict.get("adaptation_notes", []),
            chapter_boundaries=artifacts_dict.get("chapter_boundaries", []),
        )
        pipeline_meta = PipelineMeta(
            current_agent=pipeline_dict.get("current_agent", ""),
            progress=pipeline_dict.get("progress", 0.0),
            checkpoint_stack=pipeline_dict.get("checkpoint_stack", []),
        )

        hitl = None
        hitl_json = row["pending_hitl_json"]
        if hitl_json:
            hitl_dict = json.loads(hitl_json)
            hitl = HITLRequest(**hitl_dict)

        return SessionState(
            thread_id=row["thread_id"],
            status=PipelineStatus(row["status"]),
            artifacts=artifacts,
            pipeline_state=pipeline_meta,
            pending_hitl=hitl,
            errors=json.loads(row["errors_json"]),
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
        )

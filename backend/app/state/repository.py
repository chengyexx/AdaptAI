"""State Repository 抽象接口 — 定义持久化层契约，支持 SQLite → Redis/Postgres 迁移"""

from abc import ABC, abstractmethod
from .models import SessionState


class StateRepository(ABC):
    """会话状态持久化的抽象接口"""

    @abstractmethod
    async def save(self, state: SessionState) -> None:
        """保存或更新会话状态（upsert）"""
        ...

    @abstractmethod
    async def load(self, thread_id: str) -> SessionState | None:
        """根据 thread_id 加载完整会话状态，不存在返回 None"""
        ...

    @abstractmethod
    async def list_sessions(self, limit: int = 20) -> list[SessionState]:
        """列出最近的会话，按更新时间倒序"""
        ...

    @abstractmethod
    async def delete(self, thread_id: str) -> bool:
        """删除指定会话，返回是否成功"""
        ...

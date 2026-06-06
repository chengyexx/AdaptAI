"""State Store 单元测试 — SQLite 持久化的完整功能验证"""

import pytest
from state.sqlite_store import SQLiteStateStore
from state.models import (
    SessionState, PipelineStatus, Artifacts, PipelineMeta, HITLRequest
)


@pytest.fixture
def store(tmp_path):
    """每次测试使用独立的临时数据库"""
    db_path = tmp_path / "test_state.db"
    s = SQLiteStateStore(str(db_path))
    yield s


# ── 基本 CRUD ──

@pytest.mark.asyncio
async def test_save_and_load(store):
    """保存后应能通过 thread_id 完整加载"""
    state = SessionState(
        thread_id="test-save-001",
        status=PipelineStatus.CREATED,
        artifacts=Artifacts(chapters=[
            {"index": 1, "title": "第一章：相遇", "summary": "晨雾...", "char_count": 1200}
        ]),
    )
    await store.save(state)

    loaded = await store.load("test-save-001")
    assert loaded is not None
    assert loaded.thread_id == "test-save-001"
    assert loaded.status == PipelineStatus.CREATED
    assert len(loaded.artifacts.chapters) == 1
    assert loaded.artifacts.chapters[0]["title"] == "第一章：相遇"


@pytest.mark.asyncio
async def test_load_nonexistent_returns_none(store):
    """加载不存在的会话应返回 None"""
    loaded = await store.load("does-not-exist")
    assert loaded is None


@pytest.mark.asyncio
async def test_save_is_upsert(store):
    """重复 save 同一 thread_id 应更新而非报错"""
    state = SessionState(thread_id="upsert-test", status=PipelineStatus.CREATED)
    await store.save(state)

    state.status = PipelineStatus.PARSED
    await store.save(state)

    loaded = await store.load("upsert-test")
    assert loaded.status == PipelineStatus.PARSED


@pytest.mark.asyncio
async def test_list_sessions(store):
    """list_sessions 应按更新时间倒序返回"""
    for i in range(5):
        await store.save(SessionState(thread_id=f"list-{i:03d}"))
    sessions = await store.list_sessions(limit=3)
    assert len(sessions) == 3


@pytest.mark.asyncio
async def test_delete(store):
    """删除后 load 应返回 None"""
    await store.save(SessionState(thread_id="to-delete"))
    deleted = await store.delete("to-delete")
    assert deleted is True
    assert await store.load("to-delete") is None


@pytest.mark.asyncio
async def test_delete_nonexistent(store):
    """删除不存在的会话应返回 False"""
    deleted = await store.delete("ghost")
    assert deleted is False


# ── HITL 持久化 ──

@pytest.mark.asyncio
async def test_hitl_roundtrip(store):
    """HITL 挂起状态应完整持久化和恢复"""
    state = SessionState(
        thread_id="hitl-test",
        status=PipelineStatus.CHAR_HITL,
        pending_hitl=HITLRequest(
            node="character_agent",
            data={"characters": [
                {"id": "c1", "name": "林墨"},
                {"id": "c2", "name": "小禾"},
            ]},
            reason="low_confidence",
            confidence=0.55,
        ),
    )
    await store.save(state)

    loaded = await store.load("hitl-test")
    assert loaded.pending_hitl is not None
    assert loaded.pending_hitl.node == "character_agent"
    assert loaded.pending_hitl.confidence == 0.55
    assert len(loaded.pending_hitl.data["characters"]) == 2
    assert loaded.status == PipelineStatus.CHAR_HITL


# ── Pipeline 进度持久化 ──

@pytest.mark.asyncio
async def test_pipeline_meta_roundtrip(store):
    """Pipeline 进度元数据应完整持久化"""
    state = SessionState(
        thread_id="pipeline-test",
        pipeline_state=PipelineMeta(
            current_agent="scene_agent",
            progress=0.6,
            checkpoint_stack=["parser_done", "character_done"],
        ),
    )
    await store.save(state)

    loaded = await store.load("pipeline-test")
    assert loaded.pipeline_state.current_agent == "scene_agent"
    assert loaded.pipeline_state.progress == 0.6
    assert "character_done" in loaded.pipeline_state.checkpoint_stack


# ── 状态枚举 ──

@pytest.mark.asyncio
async def test_all_pipeline_statuses_persist(store):
    """每个 PipelineStatus 枚举值都应能正确持久化"""
    for status in PipelineStatus:
        state = SessionState(thread_id=f"status-{status.value}", status=status)
        await store.save(state)
        loaded = await store.load(f"status-{status.value}")
        assert loaded.status == status


# ── updated_at 自动更新 ──

@pytest.mark.asyncio
async def test_updated_at_changes_on_save(store):
    """每次 save 应自动更新 updated_at 时间戳"""
    state = SessionState(thread_id="time-test")
    await store.save(state)
    first_ts = (await store.load("time-test")).updated_at

    import asyncio
    await asyncio.sleep(0.1)

    state.status = PipelineStatus.PARSED
    await store.save(state)
    second_ts = (await store.load("time-test")).updated_at

    assert second_ts != first_ts

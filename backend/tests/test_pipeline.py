"""Pipeline 单元测试"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from state.models import SessionState, Artifacts
from state.sqlite_store import SQLiteStateStore
from orchestrator.pipeline import Pipeline


@pytest.fixture
def state_store(tmp_path):
    return SQLiteStateStore(str(tmp_path / "pipe_test.db"))


def test_chapter_parsing_step(state_store, sample_novel_text):
    state = SessionState(thread_id="pipe-test")
    state.artifacts.chapters = [{"index": 1, "title": "第一章", "text": sample_novel_text}]

    mock_adapter = AsyncMock()
    mock_adapter.complete.return_value = MagicMock(
        text='{"characters":[],"self_assessment":{"completeness":1,"character_consistency":1,"format_compliance":1}}',
        token_usage={"output": 10},
    )

    with patch("orchestrator.pipeline.AdapterFactory") as factory:
        factory.from_env.return_value = mock_adapter
        pipeline = Pipeline(state_store)
        import asyncio
        result = asyncio.run(pipeline.execute(state))
        assert len(result.artifacts.chapters) >= 1

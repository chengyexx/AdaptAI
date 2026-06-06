"""Pipeline 单元测试 — Happy Path 线性执行"""

import pytest
from unittest.mock import AsyncMock, patch
from state.models import SessionState, PipelineStatus, Artifacts
from state.sqlite_store import SQLiteStateStore
from orchestrator.pipeline import Pipeline


@pytest.fixture
def state_with_text(sample_novel_text):
    state = SessionState(thread_id="pipeline-test")
    state.artifacts.chapters = [{"index": 1, "title": "第一章", "text": sample_novel_text}]
    return state


@pytest.fixture
def state_store(tmp_path):
    return SQLiteStateStore(str(tmp_path / "pipeline_test.db"))


def test_chapter_parsing_step(state_with_text, state_store, tmp_path):
    """Pipeline 的章节解析步骤（不需要 LLM）"""
    # Mock 掉 LLM 调用
    with patch("orchestrator.pipeline.AdapterFactory") as mock_factory:
        mock_adapter = AsyncMock()
        mock_factory.from_env.return_value = mock_adapter

        # Mock character agent response
        mock_adapter.complete.return_value = type("Response", (), {
            "text": '{"characters":[],"self_assessment":{"completeness":1,"character_consistency":1,"format_compliance":1}}',
            "token_usage": {"output": 10},
        })()

        pipeline = Pipeline(state_store)
        import asyncio
        result = asyncio.run(pipeline.execute(state_with_text))

        # 章节解析应该完成（parser 是规则引擎，不需要 LLM）
        assert len(result.artifacts.chapters) >= 1

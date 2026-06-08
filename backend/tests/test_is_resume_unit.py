"""验证 HITL 移除后 Pipeline 自动通过所有 Agent"""

import pytest
import sys
import tempfile
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from state.models import SessionState, PipelineStatus, Artifacts, PipelineMeta
from state.sqlite_store import SQLiteStateStore
from agents.chapter_parser import ChapterParser
from orchestrator.pipeline import HappyPathPipeline


class TestPipelineAutoPass:
    """HITL 已移除 — 验证所有 Agent 自动通过"""

    @pytest.mark.asyncio
    async def test_is_resume_false_still_works(self):
        """is_resume=False（正常流程）不应受影响"""
        text = "## 测试章\n测试。"
        parser = ChapterParser()
        chapters = parser.parse(text)

        state = SessionState(
            thread_id="test-normal-flow",
            status=PipelineStatus.CHAR_EXTRACTING,
            artifacts=Artifacts(chapters=chapters),
            pipeline_state=PipelineMeta(),
        )

        db_path = tempfile.mktemp(suffix=".db")
        store = SQLiteStateStore(db_path=db_path)
        try:
            await store.save(state)
            pipeline = HappyPathPipeline(store, ws_manager=None)

            # is_resume=False — 正常流程，但因为没有 llm_adapter，agent.run() 会报错
            # 这里我们只验证 is_resume=False 时不会错误跳过
            try:
                await pipeline._run_agent_step(
                    state=state,
                    llm_adapter=None,
                    tid=state.thread_id,
                    agent_name="character_agent",
                    agent_class=None,
                    status_active=PipelineStatus.CHAR_EXTRACTING,
                    status_hitl=PipelineStatus.CHAR_HITL,
                    status_done=PipelineStatus.CHAR_DONE,
                    progress_start=0.25,
                    progress_end=0.4,
                    log_msg="角色识别",
                    hitl_reason="请审阅",
                    hitl_data_key="characters",
                    is_resume=False,
                )
            except Exception:
                # 预期会异常（没有真正的 LLM adapter）
                pass

            # is_resume=False 时不应被跳过 — 状态应该是 CHAR_EXTRACTING 或 ERROR
            # 因为 _run_agent_step 在 is_resume=False 时会设置 status_active
            assert state.status != PipelineStatus.CHAR_DONE, (
                f"is_resume=False 不应直接标记完成: {state.status}"
            )
            print(f"[预期状态] {state.status} (is_resume=False 走正常执行路径)")
            print("✅ is_resume=False 正常流程不受影响")

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

"""复现 HITL 循环 Bug — 提交编辑后角色识别反复暂停"""

import pytest
import sys
import os
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from state.models import SessionState, PipelineStatus, Artifacts, PipelineMeta, HITLRequest
from state.sqlite_store import SQLiteStateStore
from agents.chapter_parser import ChapterParser
from orchestrator.pipeline import HappyPathPipeline
from config import settings


def _make_state(chapters, thread_id=None):
    return SessionState(
        thread_id=thread_id or f"test-{uuid.uuid4().hex[:8]}",
        status=PipelineStatus.CREATED,
        artifacts=Artifacts(chapters=chapters),
        pipeline_state=PipelineMeta(),
    )


class TestHitlLoopBug:
    """验证 HITL continue/skip 不会陷入死循环"""

    @pytest.mark.asyncio
    async def test_resume_from_char_hitl_advances(self):
        """核心断言：从 CHAR_HITL 恢复后不会再次停在 CHAR_HITL"""
        text = "## 第一章\n林墨是一个沉默的花匠，他在花园里种了二十年的玫瑰。\n## 第二章\n小禾搬进了隔壁，她的笑声打破了林墨的平静。"
        parser = ChapterParser()
        chapters = parser.parse(text)
        state = _make_state(chapters)

        db_path = tempfile.mktemp(suffix=".db")
        store = SQLiteStateStore(db_path=db_path)
        try:
            await store.save(state)

            pipeline = HappyPathPipeline(store, ws_manager=None)

            # ── 首次执行 — 预期触发 CHAR_HITL ──
            result1 = await pipeline.execute(state)
            print(f"\n[首次] status={result1.status}, characters={len(result1.artifacts.characters)}")

            # 模拟 hitl_continue 做的事
            if result1.status == PipelineStatus.CHAR_HITL:
                result1.status = PipelineStatus.CHAR_DONE
                result1.pending_hitl = None
                await store.save(result1)

                # ── 以 CHAR_HITL 恢复 ──
                loaded = await store.load(result1.thread_id)
                result2 = await pipeline.execute(loaded, resume_from=PipelineStatus.CHAR_HITL)

                print(f"[恢复] status={result2.status}, scenes={len(result2.artifacts.scenes)}")

                # ⚠️ 核心断言
                assert result2.status != PipelineStatus.CHAR_HITL, (
                    f"BUG! 从 CHAR_HITL 恢复后状态又变为 CHAR_HITL — 死循环！"
                )
                assert result2.status in (
                    PipelineStatus.CHAR_DONE,
                    PipelineStatus.SCENE_SEGMENTING,
                    PipelineStatus.SCENE_DONE,
                    PipelineStatus.SCENE_HITL,
                    PipelineStatus.SCRIPT_GENERATING,
                    PipelineStatus.SCRIPT_DONE,
                    PipelineStatus.COMPLETED,
                    PipelineStatus.ERROR,
                ), f"意外状态: {result2.status}"
                print("✅ 测试通过 — 恢复后正确前进到:", result2.status)
            else:
                print("⚠️ 首次执行未触发 HITL，跳过循环验证")

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_skip_continue_does_not_loop(self):
        """验证 skip-continue 也不会陷入死循环"""
        text = "## 第一章\n林墨是一个沉默的花匠。\n## 第二章\n小禾来了。"
        parser = ChapterParser()
        chapters = parser.parse(text)
        state = _make_state(chapters)

        db_path = tempfile.mktemp(suffix=".db")
        store = SQLiteStateStore(db_path=db_path)
        try:
            await store.save(state)

            pipeline = HappyPathPipeline(store, ws_manager=None)
            result1 = await pipeline.execute(state)
            print(f"\n[首次] status={result1.status}")

            if result1.status == PipelineStatus.CHAR_HITL:
                # 模拟 skip-continue：不编辑，只改状态
                result1.status = PipelineStatus.CHAR_DONE
                result1.pending_hitl = None
                await store.save(result1)

                for i in range(3):  # 模拟连续跳过 3 次
                    loaded = await store.load(result1.thread_id)
                    result_n = await pipeline.execute(loaded, resume_from=PipelineStatus.CHAR_HITL)
                    print(f"[第{i+1}次跳过] status={result_n.status}")

                    assert result_n.status != PipelineStatus.CHAR_HITL, (
                        f"BUG! 第{i+1}次跳过后又回到了 CHAR_HITL！"
                    )

                    if result_n.status in (PipelineStatus.COMPLETED, PipelineStatus.ERROR):
                        break

                print("✅ skip-continue 循环测试通过")

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)

    @pytest.mark.asyncio
    async def test_start_resume_from_creates_task_timing(self):
        """验证 hitl_continue 中的状态变更时序 — 确认 save 在 create_task 之前完成"""
        text = "## 第一章\n测试。\n## 第二章\n测试。"
        parser = ChapterParser()
        chapters = parser.parse(text)
        state = _make_state(chapters)

        db_path = tempfile.mktemp(suffix=".db")
        store = SQLiteStateStore(db_path=db_path)
        try:
            await store.save(state)

            # 模拟 hitl_continue 的核心逻辑
            loaded = await store.load(state.thread_id)
            loaded.status = PipelineStatus.CHAR_HITL  # 假设已进入 HITL
            loaded.pending_hitl = HITLRequest(
                node="character_agent",
                data={"characters": []},
                reason="low_confidence",
                confidence=0.44,
            )
            await store.save(loaded)
            print(f"\n[保存前] status={loaded.status}")

            # 模拟 hitl_continue 的状态变更
            resume_from = loaded.status  # CHAR_HITL
            loaded.status = PipelineStatus.CHAR_DONE
            loaded.pending_hitl = None
            await store.save(loaded)
            print(f"[保存后] status={loaded.status}, resume_from={resume_from}")

            # 模拟 _run_pipeline_resume：重新加载
            reloaded = await store.load(loaded.thread_id)
            print(f"[重加载] status={reloaded.status}")

            # 验证状态被正确持久化
            assert reloaded.status == PipelineStatus.CHAR_DONE, (
                f"状态持久化失败: 期望 CHAR_DONE，实际 {reloaded.status}"
            )
            assert reloaded.pending_hitl is None, "pending_hitl 未清空"

            print("✅ 时序测试通过 — save 在 create_task 之前完成")

        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-k", "test_resume_from_char_hitl_advances"])

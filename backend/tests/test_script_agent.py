"""ScriptAgent 单元测试 — 剧本生成与改编建议"""

import pytest
from unittest.mock import AsyncMock
from llm.adapter import LLMResponse
from agents.script_agent import ScriptAgent


SCRIPT_JSON = """{
  "scenes": [
    {
      "scene_id": "s1",
      "chapter": 1,
      "heading": { "location": "INT. ROOM", "time_of_day": "MORNING" },
      "characters_present": ["c1"],
      "mood": "宁静",
      "action": [{"type": "action", "text": "He enters and looks around."}],
      "dialogue": [
        {"character_id": "c1", "emotion": "calm", "delivery": "", "text": "Hello.", "parenthetical": ""}
      ],
      "shots": [],
      "transition": null
    }
  ],
  "adaptation_notes": [
    {"scene_id": "s1", "category": "pacing", "severity": "suggestion", "content": "Slow opening."}
  ],
  "self_assessment": {"completeness": 8, "dialogue_quality": 7, "format_compliance": 9}
}"""


@pytest.fixture
def mock_adapter():
    adapter = AsyncMock()
    adapter.complete.return_value = LLMResponse(
        text=SCRIPT_JSON, model="mock", token_usage={"output": 300}
    )
    return adapter


@pytest.fixture
def state_full():
    return {
        "artifacts": {
            "chapters": [{"index": 1, "title": "Ch1", "text": "..."}],
            "characters": [
                {"id": "c1", "name": "John", "aliases": [], "description": {"role": "protagonist"}},
            ],
            "scenes": [
                {"scene_id": "s1", "chapter": 1, "heading": {"location": "ROOM", "time_of_day": "MORNING"}, "characters_present": ["c1"], "mood": "calm", "summary": "Entering."},
            ],
        }
    }


# ── Prompt 构建 ──

@pytest.mark.asyncio
async def test_build_prompt_with_characters(state_full):
    agent = ScriptAgent()
    _, user = agent.build_prompt(state_full)
    assert "John" in user
    assert "protagonist" in user


@pytest.mark.asyncio
async def test_build_prompt_with_scenes(state_full):
    agent = ScriptAgent()
    _, user = agent.build_prompt(state_full)
    assert "s1" in user
    assert "ROOM" in user


# ── Agent 运行 ──

@pytest.mark.asyncio
async def test_script_agent_run(mock_adapter, state_full):
    agent = ScriptAgent()
    result = await agent.run(state_full, mock_adapter)

    assert result.success
    assert len(result.output["scenes"]) == 1
    assert result.output["scenes"][0]["dialogue"][0]["text"] == "Hello."
    assert result.confidence > 0.5


@pytest.mark.asyncio
async def test_script_agent_generates_adaptation_notes(mock_adapter, state_full):
    agent = ScriptAgent()
    result = await agent.run(state_full, mock_adapter)

    notes = result.output.get("adaptation_notes", [])
    assert len(notes) >= 1
    assert "category" in notes[0]
    assert "severity" in notes[0]
    assert "content" in notes[0]


# ── 错误处理 ──

@pytest.mark.asyncio
async def test_script_agent_handles_error():
    agent = ScriptAgent()
    adapter = AsyncMock()
    adapter.complete.side_effect = Exception("API down")

    result = await agent.run(
        {"artifacts": {"chapters": [], "characters": [], "scenes": []}}, adapter
    )
    assert not result.success
    assert len(result.warnings) > 0


# ── 空输入 ──

@pytest.mark.asyncio
async def test_empty_state():
    agent = ScriptAgent()
    adapter = AsyncMock()
    adapter.complete.return_value = LLMResponse(
        text='{"scenes":[],"adaptation_notes":[],"self_assessment":{"completeness":1,"dialogue_quality":1,"format_compliance":1}}',
        model="mock", token_usage={}
    )
    result = await agent.run(
        {"artifacts": {"chapters": [], "characters": [], "scenes": []}}, adapter
    )
    assert result.success
    assert result.output["scenes"] == []

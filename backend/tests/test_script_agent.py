"""Script Agent 单元测试 — 剧本生成逻辑验证"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from agents.script_agent import ScriptAgent


MOCK_LLM_RESPONSE = """
{
  "场景列表": [
    {
      "场景编号": "s1",
      "来源章节": 1,
      "场景标题": { "地点": "INT. ROOM", "时段": "早晨" },
      "出场角色": ["c1"],
      "动作列表": [
        { "类型": "动作", "内容": "John enters the room slowly." }
      ],
      "对白": [
        { "角色编号": "c1", "情绪": "平静", "表演提示": "", "台词内容": "Hello.", "行为提示": "" }
      ],
      "镜头建议": [
        { "镜头类型": "全景", "镜头描述": "Wide shot of room", "可选": true }
      ],
      "转场方式": null
    }
  ],
  "改编说明": [
    { "场景编号": "s1", "分类": "节奏", "严重程度": "建议", "内容": "Slow opening." }
  ],
  "自评": {
    "完整性": 8,
    "对白质量": 7,
    "格式合规": 9
  }
}
"""


@pytest.fixture
def mock_llm_adapter():
    adapter = MagicMock()
    adapter.complete = AsyncMock()
    return adapter


@pytest.fixture
def state_with_chars_and_scenes():
    return {
        "artifacts": {
            "chapters": [{"title": "Ch1", "text": "..."}],
            "characters": [
                {"id": "c1", "name": "John", "aliases": [], "description": {"role": "protagonist"}},
            ],
            "scenes": [
                {"场景编号": "s1", "来源章节": 1, "场景标题": {"地点": "ROOM", "时段": "早晨"}, "出场角色": ["c1"], "情绪基调": "calm", "摘要": "Entering."},
            ],
        }
    }


@pytest.mark.asyncio
async def test_script_agent_success(mock_llm_adapter, state_with_chars_and_scenes):
    mock_llm_adapter.complete.return_value = MagicMock(
        text=MOCK_LLM_RESPONSE, token_usage={"output": 200}
    )
    agent = ScriptAgent()
    result = await agent.run(state_with_chars_and_scenes, mock_llm_adapter)

    assert result.success is True
    assert len(result.output["场景列表"]) == 1
    assert result.output["场景列表"][0]["对白"][0]["台词内容"] == "Hello."


@pytest.mark.asyncio
async def test_script_agent_empty_input(mock_llm_adapter):
    """空输入时不崩溃"""
    mock_llm_adapter.complete.return_value = MagicMock(
        text='{"场景列表":[],"改编说明":[],"自评":{"完整性":1,"对白质量":1,"格式合规":1}}',
        token_usage={"output": 50},
    )
    agent = ScriptAgent()
    result = await agent.run(
        {"artifacts": {"chapters": [], "characters": [], "scenes": []}}, mock_llm_adapter
    )
    assert result.success is True
    assert result.output["场景列表"] == []

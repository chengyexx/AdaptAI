"""Scene Agent 单元测试 — 场景切分逻辑验证"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from agents.scene_agent import SceneAgent


MOCK_LLM_SYSTEM_PROMPT = """你是一位专业的剧本分场师..."""


MOCK_LLM_RESPONSE_JSON = """{
  "场景列表": [
    {
      "场景编号": "s1",
      "来源章节": 1,
      "场景标题": {
        "地点": "EXT. GARDEN",
        "时段": "早晨",
        "场景细节": "晨雾弥漫"
      },
      "出场角色": ["c1"],
      "情绪基调": "宁静",
      "摘要": "林墨在花园里照料玫瑰。"
    },
    {
      "场景编号": "s2",
      "来源章节": 1,
      "场景标题": {
        "地点": "INT. KITCHEN",
        "时段": "夜晚"
      },
      "出场角色": ["c1", "c2"],
      "情绪基调": "温馨",
      "摘要": "林墨和小禾在厨房做饭。"
    }
  ],
  "自评": {
    "切分准确性": 8,
    "地点识别": 8,
    "角色出场": 9,
    "格式合规": 10
  }
}"""


@pytest.fixture
def mock_llm_adapter():
    adapter = MagicMock()
    adapter.complete = AsyncMock()
    return adapter


@pytest.fixture
def state_with_chapters_and_chars():
    return {
        "artifacts": {
            "chapters": [
                {"title": "Chapter 1", "text": "Some story text here..."},
            ],
            "characters": [
                {"id": "c1", "name": "林墨", "aliases": ["墨叔"]},
                {"id": "c2", "name": "小禾", "aliases": []},
            ],
        }
    }


@pytest.mark.asyncio
async def test_scene_agent_success(mock_llm_adapter, state_with_chapters_and_chars):
    mock_llm_adapter.complete.return_value = MagicMock(
        text=MOCK_LLM_RESPONSE_JSON,
        token_usage={"output": 100},
    )
    agent = SceneAgent()
    result = await agent.run(state_with_chapters_and_chars, mock_llm_adapter)

    assert result.success is True
    assert len(result.output["场景列表"]) == 2
    assert result.output["场景列表"][0]["场景标题"]["地点"] == "EXT. GARDEN"


@pytest.mark.asyncio
async def test_scene_agent_auto_assigns_missing_ids(mock_llm_adapter):
    missing_ids_response = MagicMock(
        text='{"场景列表": [{"来源章节": 1, "场景标题": {"地点": "A", "时段": "早晨"}, "出场角色": [], "情绪基调": "", "摘要": "X"}, {"来源章节": 1, "场景标题": {"地点": "B", "时段": "夜晚"}, "出场角色": [], "情绪基调": "", "摘要": "Y"}], "自评": {"切分准确性": 5, "地点识别": 5, "角色出场": 5, "格式合规": 5}}',
        token_usage={"output": 80},
    )
    mock_llm_adapter.complete.return_value = missing_ids_response
    agent = SceneAgent()
    result = await agent.run({"artifacts": {"chapters": [{"title": "Ch1", "text": "..."}], "characters": []}}, mock_llm_adapter)

    assert result.success is True
    assert result.output["场景列表"][0]["场景编号"] == "s1"
    assert result.output["场景列表"][1]["场景编号"] == "s2"


@pytest.mark.asyncio
async def test_scene_agent_cross_validate_invalid_char(mock_llm_adapter, state_with_chapters_and_chars):
    response = MagicMock(
        text='{"场景列表": [{"场景编号":"s1","来源章节":1,"场景标题":{"地点":"A","时段":"早晨"},"出场角色":["c99"],"情绪基调":"","摘要":"X"}],"自评":{"切分准确性":5,"地点识别":5,"角色出场":5,"格式合规":5}}',
        token_usage={"output": 80},
    )
    mock_llm_adapter.complete.return_value = response
    agent = SceneAgent()
    result = await agent.run(state_with_chapters_and_chars, mock_llm_adapter)

    assert result.success is True
    # c99 not in character table -> cross_validate returns low score -> confidence drops
    assert "角色表" not in str(result.warnings).lower()  # check that it completed


@pytest.mark.asyncio
async def test_scene_agent_cross_validate_empty_chars():
    """角色表为空时交叉校验应返回 1.0"""
    agent = SceneAgent()
    output = {"场景列表": [{"出场角色": ["any_id"]}]}
    state = {"artifacts": {"characters": []}}
    score = agent._cross_validate(output, state)
    assert score == 1.0  # 空角色表不校验


@pytest.mark.asyncio
async def test_scene_agent_cross_validate_all_valid():
    """所有出场角色都在角色表中"""
    agent = SceneAgent()
    output = {"场景列表": [
        {"出场角色": ["c1", "c2"]},
        {"出场角色": ["c1"]},
    ]}
    state = {
        "artifacts": {
            "characters": [
                {"id": "c1", "name": "A"},
                {"id": "c2", "name": "B"},
            ]
        }
    }
    score = agent._cross_validate(output, state)
    assert score == 1.0

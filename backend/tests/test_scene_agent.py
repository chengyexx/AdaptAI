"""SceneAgent 单元测试 — 场景切分与交叉验证"""

import pytest
from unittest.mock import AsyncMock
from llm.adapter import LLMResponse
from agents.scene_agent import SceneAgent


SCENE_JSON = """{
  "scenes": [
    {
      "scene_id": "s1",
      "chapter": 1,
      "heading": {
        "location": "EXT. GARDEN",
        "time_of_day": "MORNING",
        "setting_detail": "晨雾弥漫"
      },
      "characters_present": ["c1"],
      "mood": "宁静",
      "summary": "林墨在花园照料玫瑰。"
    },
    {
      "scene_id": "s2",
      "chapter": 1,
      "heading": {
        "location": "INT. LIVING ROOM",
        "time_of_day": "EVENING"
      },
      "characters_present": ["c1", "c2"],
      "mood": "温暖",
      "summary": "小禾来访。"
    }
  ],
  "self_assessment": {
    "segmentation_accuracy": 8,
    "location_identification": 8,
    "character_attendance": 9,
    "format_compliance": 10
  }
}"""


@pytest.fixture
def mock_adapter():
    adapter = AsyncMock()
    adapter.complete.return_value = LLMResponse(
        text=SCENE_JSON, model="mock", token_usage={"output": 200}
    )
    return adapter


@pytest.fixture
def state_with_chapters_and_chars():
    return {
        "artifacts": {
            "chapters": [
                {"index": 1, "title": "第一章", "text": "林墨在花园浇水。小禾来访。"}
            ],
            "characters": [
                {"id": "c1", "name": "林墨", "aliases": ["老林"]},
                {"id": "c2", "name": "小禾", "aliases": []},
            ],
        }
    }


# ── Prompt 构建 ──

@pytest.mark.asyncio
async def test_build_prompt_includes_characters(state_with_chapters_and_chars):
    agent = SceneAgent()
    _, user = agent.build_prompt(state_with_chapters_and_chars)
    assert "c1" in user
    assert "林墨" in user
    assert "c2" in user


@pytest.mark.asyncio
async def test_build_prompt_includes_chapter_text(state_with_chapters_and_chars):
    agent = SceneAgent()
    _, user = agent.build_prompt(state_with_chapters_and_chars)
    assert "第一章" in user


# ── Agent 运行 ──

@pytest.mark.asyncio
async def test_scene_agent_run(mock_adapter, state_with_chapters_and_chars):
    agent = SceneAgent()
    result = await agent.run(state_with_chapters_and_chars, mock_adapter)

    assert result.success
    assert len(result.output["scenes"]) == 2
    assert result.output["scenes"][0]["heading"]["location"] == "EXT. GARDEN"
    assert result.confidence > 0.5


@pytest.mark.asyncio
async def test_scene_agent_auto_assigns_ids(mock_adapter):
    json_without_ids = """{
      "scenes": [
        {"chapter": 1, "heading": {"location": "A", "time_of_day": "MORNING"}, "characters_present": [], "mood": "", "summary": "X"},
        {"chapter": 1, "heading": {"location": "B", "time_of_day": "NIGHT"}, "characters_present": [], "mood": "", "summary": "Y"}
      ],
      "self_assessment": {"segmentation_accuracy": 5, "location_identification": 5, "character_attendance": 5, "format_compliance": 5}
    }"""
    adapter = AsyncMock()
    adapter.complete.return_value = LLMResponse(
        text=json_without_ids, model="mock", token_usage={"output": 50}
    )
    agent = SceneAgent()
    result = await agent.run(
        {"artifacts": {"chapters": [{"title": "T", "text": "X"}], "characters": []}}, adapter
    )
    assert result.output["scenes"][0]["scene_id"] == "s1"
    assert result.output["scenes"][1]["scene_id"] == "s2"


# ── 交叉验证 ──

@pytest.mark.asyncio
async def test_cross_validate_detects_invalid_character(mock_adapter):
    """场景引用不存在的角色时置信度降低"""
    json_with_bad_char = """{
      "scenes": [
        {"scene_id":"s1","chapter":1,"heading":{"location":"A","time_of_day":"MORNING"},"characters_present":["c99"],"mood":"","summary":"X"}
      ],
      "self_assessment": {"segmentation_accuracy": 8, "location_identification": 8, "character_attendance": 8, "format_compliance": 8}
    }"""
    adapter = AsyncMock()
    adapter.complete.return_value = LLMResponse(
        text=json_with_bad_char, model="mock", token_usage={"output": 50}
    )
    agent = SceneAgent()
    state = {
        "artifacts": {
            "chapters": [{"title": "T", "text": "X"}],
            "characters": [{"id": "c1", "name": "林墨"}],
        }
    }
    result = await agent.run(state, adapter)
    assert result.confidence < 0.8  # cross_validate 扣分


def test_cross_validate_empty_characters():
    """无角色表时交叉验证不扣分"""
    agent = SceneAgent()
    output = {"scenes": [{"characters_present": ["any_id"]}]}
    state = {"artifacts": {"characters": []}}
    score = agent._cross_validate(output, state)
    assert score == 1.0


def test_cross_validate_perfect_match():
    """所有引用都在角色表中"""
    agent = SceneAgent()
    output = {"scenes": [
        {"characters_present": ["c1", "c2"]},
        {"characters_present": ["c1"]},
    ]}
    state = {"artifacts": {"characters": [
        {"id": "c1", "name": "A"},
        {"id": "c2", "name": "B"},
    ]}}
    score = agent._cross_validate(output, state)
    assert score == 1.0

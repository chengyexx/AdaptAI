"""CharacterAgent 单元测试 — 角色识别与 Prompt 构建"""

import pytest
from unittest.mock import AsyncMock
from llm.adapter import LLMResponse
from agents.character_agent import CharacterAgent


CHAR_JSON = """{
  "characters": [
    {
      "id": "c1",
      "name": "林墨",
      "aliases": ["老林", "墨叔"],
      "description": {
        "physical": "50岁左右，瘦高，手上有老茧",
        "personality": "沉默寡言但内心炽热",
        "role": "protagonist"
      },
      "relationships": [
        {
          "target_id": "c2",
          "type": "mentor_student",
          "note": "林墨教会了小禾园艺"
        }
      ]
    },
    {
      "id": "c2",
      "name": "小禾",
      "aliases": ["禾禾"],
      "description": {
        "physical": "12岁女孩，梳双马尾",
        "personality": "好奇、乐观",
        "role": "supporting"
      },
      "relationships": []
    }
  ],
  "self_assessment": {
    "completeness": 8,
    "character_consistency": 9,
    "format_compliance": 10
  }
}"""


@pytest.fixture
def mock_adapter():
    adapter = AsyncMock()
    adapter.complete.return_value = LLMResponse(
        text=CHAR_JSON,
        model="mock",
        token_usage={"output": 150},
    )
    return adapter


@pytest.fixture
def state_with_chapters():
    return {
        "artifacts": {
            "chapters": [
                {
                    "index": 1,
                    "title": "第一章：相遇",
                    "text": "林墨蹲在花圃边。小禾坐在石凳上问道：墨叔，你怎么不离开？",
                }
            ]
        }
    }


# ── Prompt 构建 ──

@pytest.mark.asyncio
async def test_build_prompt_includes_chapter_titles(state_with_chapters):
    agent = CharacterAgent()
    system, user = agent.build_prompt(state_with_chapters)
    assert "第一章：相遇" in user


@pytest.mark.asyncio
async def test_build_prompt_includes_character_names(state_with_chapters):
    agent = CharacterAgent()
    system, user = agent.build_prompt(state_with_chapters)
    assert "林墨" in user
    assert "小禾" in user


# ── Agent 运行 ──

@pytest.mark.asyncio
async def test_character_agent_run_success(mock_adapter, state_with_chapters):
    agent = CharacterAgent()
    result = await agent.run(state_with_chapters, mock_adapter)

    assert result.success
    assert result.agent_id == "character_agent"
    assert len(result.output["characters"]) == 2
    assert result.output["characters"][0]["name"] == "林墨"
    assert result.confidence > 0.5


@pytest.mark.asyncio
async def test_character_agent_extracts_aliases(mock_adapter, state_with_chapters):
    agent = CharacterAgent()
    result = await agent.run(state_with_chapters, mock_adapter)
    c1 = result.output["characters"][0]
    assert "老林" in c1["aliases"] or "墨叔" in c1["aliases"]


@pytest.mark.asyncio
async def test_character_agent_extracts_relationships(mock_adapter, state_with_chapters):
    agent = CharacterAgent()
    result = await agent.run(state_with_chapters, mock_adapter)
    c1 = result.output["characters"][0]
    assert len(c1["relationships"]) >= 1
    assert c1["relationships"][0]["target_id"] == "c2"


@pytest.mark.asyncio
async def test_character_agent_auto_assigns_ids(mock_adapter):
    """无 id 的角色自动分配 c1, c2..."""
    json_without_ids = """{
      "characters": [
        {"name": "角色A", "aliases": [], "description": {"role": "minor"}, "relationships": []},
        {"name": "角色B", "aliases": [], "description": {"role": "minor"}, "relationships": []}
      ],
      "self_assessment": {"completeness": 5, "character_consistency": 5, "format_compliance": 5}
    }"""
    adapter = AsyncMock()
    adapter.complete.return_value = LLMResponse(
        text=json_without_ids, model="mock", token_usage={"output": 50}
    )

    agent = CharacterAgent()
    result = await agent.run(
        {"artifacts": {"chapters": [{"title": "T", "text": "X"}]}}, adapter
    )
    assert result.output["characters"][0]["id"] == "c1"
    assert result.output["characters"][1]["id"] == "c2"


# ── 错误处理 ──

@pytest.mark.asyncio
async def test_character_agent_handles_api_error():
    """API 连续失败返回不成功结果"""
    agent = CharacterAgent()
    adapter = AsyncMock()
    adapter.complete.side_effect = Exception("API timeout")

    result = await agent.run(
        {"artifacts": {"chapters": [{"title": "T", "text": "X"}]}}, adapter
    )
    assert not result.success
    assert len(result.warnings) > 0


# ── JSON 提取 ──

def test_extract_json_from_text():
    """从混合文本中提取 JSON 对象"""
    agent = CharacterAgent()
    raw = agent._extract_json('前缀文本 {"key": "value"} 后缀文本')
    assert raw == {"key": "value"}


def test_extract_json_pure_json():
    agent = CharacterAgent()
    raw = agent._extract_json('{"a": 1, "b": [2, 3]}')
    assert raw == {"a": 1, "b": [2, 3]}


def test_extract_json_invalid_raises():
    agent = CharacterAgent()
    with pytest.raises(ValueError, match="无法从 LLM 响应中提取 JSON"):
        agent._extract_json("这不是 JSON")

"""Validator 单元测试 — 四维校验逻辑验证"""

import pytest
from agents.validator import Validator


@pytest.fixture
def valid_screenplay():
    return {
        "scenes": [
            {
                "scene_id": "s1",
                "heading": {"location": "ROOM", "time_of_day": "MORNING"},
                "characters_present": ["c1"],
                "action": [{"text": "Test action."}],
                "dialogue": [
                    {"character_id": "c1", "text": "Hello."}
                ],
            },
            {
                "scene_id": "s2",
                "heading": {"location": "PARK", "time_of_day": "AFTERNOON"},
                "characters_present": ["c1", "c2"],
                "action": [{"text": "More action."}],
                "dialogue": [],
            },
        ],
        "dramatis_personae": [
            {"id": "c1", "name": "John", "description": {"role": "protagonist"}},
            {"id": "c2", "name": "Jane", "description": {"role": "supporting"}},
        ],
    }


# ── 通过场景 ──

def test_valid_screenplay_passes(valid_screenplay):
    validator = Validator()
    result = validator.validate(valid_screenplay)
    assert result["passed"] is True
    assert len(result["errors"]) == 0


# ── Schema 结构校验 ──

def test_missing_scene_id_fails():
    validator = Validator()
    screenplay = {
        "scenes": [{"heading": {"location": "X", "time_of_day": "MORNING"}, "action": [{"text": "t"}]}],
        "dramatis_personae": [],
    }
    result = validator.validate(screenplay)
    assert result["passed"] is False


def test_missing_heading_fails():
    validator = Validator()
    screenplay = {
        "scenes": [{"scene_id": "s1", "action": [{"text": "t"}]}],
        "dramatis_personae": [],
    }
    result = validator.validate(screenplay)
    assert result["passed"] is False
    assert any("heading" in e for e in result["errors"])


def test_missing_action_fails():
    validator = Validator()
    screenplay = {
        "scenes": [{"scene_id": "s1", "heading": {"location": "X", "time_of_day": "MORNING"}}],
        "dramatis_personae": [],
    }
    result = validator.validate(screenplay)
    assert result["passed"] is False
    assert any("action" in e or "动作" in e for e in result["errors"])


def test_empty_scenes_fails():
    validator = Validator()
    result = validator.validate({"scenes": [], "dramatis_personae": []})
    assert result["passed"] is False


# ── 交叉引用校验 ──

def test_invalid_character_reference_fails(valid_screenplay):
    valid_screenplay["scenes"][0]["characters_present"] = ["c99"]
    validator = Validator()
    result = validator.validate(valid_screenplay)
    assert result["passed"] is False
    assert any("c99" in e for e in result["errors"])


def test_dialogue_references_unknown_character_fails(valid_screenplay):
    valid_screenplay["scenes"][0]["dialogue"] = [
        {"character_id": "c_ghost", "text": "Boo."}
    ]
    validator = Validator()
    result = validator.validate(valid_screenplay)
    assert result["passed"] is False


# ── 场景编号连续性 ──

def test_non_sequential_scene_ids_warns():
    validator = Validator()
    screenplay = {
        "scenes": [
            {"scene_id": "s3", "heading": {"location": "A", "time_of_day": "MORNING"}, "characters_present": [], "action": [{"text": "t"}], "dialogue": []},
            {"scene_id": "s1", "heading": {"location": "B", "time_of_day": "NIGHT"}, "characters_present": [], "action": [{"text": "t"}], "dialogue": []},
        ],
        "dramatis_personae": [],
    }
    result = validator.validate(screenplay)
    assert result["passed"] is True  # 只是 warning，不阻止通过
    assert len(result["warnings"]) >= 1


# ── 对白覆盖率 ──

def test_low_dialogue_coverage_warns():
    validator = Validator()
    scenes = []
    for i in range(10):
        scenes.append({
            "scene_id": f"s{i+1}",
            "heading": {"location": "X", "time_of_day": "MORNING"},
            "characters_present": [],
            "action": [{"text": "t"}],
            "dialogue": [],
        })
    scenes[0]["dialogue"] = [{"character_id": None, "text": "hi"}]  # 仅1个有对白
    result = validator.validate({"scenes": scenes, "dramatis_personae": []})
    assert result["passed"] is True
    assert any("对白" in w for w in result["warnings"])


# ── 空角色表（允许） ──

def test_empty_char_table_allows_any_reference():
    """空角色表时不进行交叉引用校验"""
    validator = Validator()
    screenplay = {
        "scenes": [{
            "scene_id": "s1",
            "heading": {"location": "X", "time_of_day": "MORNING"},
            "characters_present": ["any_id"],
            "action": [{"text": "t"}],
            "dialogue": [{"character_id": "whatever", "text": "hi"}],
        }],
        "dramatis_personae": [],
    }
    result = validator.validate(screenplay)
    assert result["passed"] is True

"""Validator 单元测试 — 四维校验逻辑验证"""

import pytest
from agents.validator import Validator


@pytest.fixture
def valid_screenplay():
    return {
        "场景列表": [
            {
                "场景编号": "s1",
                "场景标题": {"地点": "ROOM", "时段": "白天"},
                "出场角色": ["c1"],
                "动作列表": [{"类型": "动作", "内容": "Test action."}],
                "对白": [
                    {"角色编号": "c1", "台词内容": "Hello."}
                ],
            },
            {
                "场景编号": "s2",
                "场景标题": {"地点": "PARK", "时段": "下午"},
                "出场角色": ["c1", "c2"],
                "动作列表": [{"类型": "动作", "内容": "More action."}],
                "对白": [],
            },
        ],
        "角色表": [
            {"id": "c1", "name": "John", "description": {"role": "protagonist"}},
            {"id": "c2", "name": "Jane", "description": {"role": "supporting"}},
        ],
    }


# -- 通过场景 --

def test_valid_screenplay_passes(valid_screenplay):
    validator = Validator()
    result = validator.validate(valid_screenplay)
    assert result["passed"] is True
    assert len(result["errors"]) == 0


# -- Schema 结构校验 --

def test_missing_scene_id_fails():
    validator = Validator()
    screenplay = {
        "场景列表": [{"场景标题": {"地点": "X", "时段": "白天"}, "动作列表": [{"内容": "t"}]}],
        "角色表": [],
    }
    result = validator.validate(screenplay)
    assert result["passed"] is False


def test_missing_heading_fails():
    validator = Validator()
    screenplay = {
        "场景列表": [{"场景编号": "s1", "动作列表": [{"内容": "t"}]}],
        "角色表": [],
    }
    result = validator.validate(screenplay)
    assert result["passed"] is False
    assert any("场景标题" in e for e in result["errors"])


def test_missing_action_fails():
    validator = Validator()
    screenplay = {
        "场景列表": [{"场景编号": "s1", "场景标题": {"地点": "X", "时段": "白天"}}],
        "角色表": [],
    }
    result = validator.validate(screenplay)
    assert result["passed"] is False
    assert any("动作" in e for e in result["errors"])


def test_empty_scenes_fails():
    validator = Validator()
    result = validator.validate({"场景列表": [], "角色表": []})
    assert result["passed"] is False


# -- 交叉引用校验 --

def test_invalid_character_reference_fails(valid_screenplay):
    valid_screenplay["场景列表"][0]["出场角色"] = ["c99"]
    validator = Validator()
    result = validator.validate(valid_screenplay)
    assert result["passed"] is False
    assert any("c99" in e for e in result["errors"])


def test_dialogue_references_unknown_character_fails(valid_screenplay):
    valid_screenplay["场景列表"][0]["对白"] = [
        {"角色编号": "c_ghost", "台词内容": "Boo."}
    ]
    validator = Validator()
    result = validator.validate(valid_screenplay)
    assert result["passed"] is False


# -- 场景编号连续性 --

def test_non_sequential_scene_ids_warns():
    validator = Validator()
    screenplay = {
        "场景列表": [
            {"场景编号": "s3", "场景标题": {"地点": "A", "时段": "白天"}, "出场角色": [], "动作列表": [{"内容": "t"}], "对白": []},
            {"场景编号": "s1", "场景标题": {"地点": "B", "时段": "夜晚"}, "出场角色": [], "动作列表": [{"内容": "t"}], "对白": []},
        ],
        "角色表": [],
    }
    result = validator.validate(screenplay)
    assert result["passed"] is True  # 只是 warning，不阻止通过
    assert len(result["warnings"]) >= 1


# -- 对白覆盖率 --

def test_low_dialogue_coverage_warns():
    validator = Validator()
    scenes = []
    for i in range(10):
        scenes.append({
            "场景编号": f"s{i+1}",
            "场景标题": {"地点": "X", "时段": "白天"},
            "出场角色": [],
            "动作列表": [{"内容": "t"}],
            "对白": [],
        })
    scenes[0]["对白"] = [{"角色编号": None, "台词内容": "hi"}]  # 仅1个有对白
    result = validator.validate({"场景列表": scenes, "角色表": []})
    assert result["passed"] is True
    assert any("对白" in w for w in result["warnings"])


# -- 空角色表（允许） --

def test_empty_char_table_allows_any_reference():
    """空角色表时不进行交叉引用校验"""
    validator = Validator()
    screenplay = {
        "场景列表": [{
            "场景编号": "s1",
            "场景标题": {"地点": "X", "时段": "白天"},
            "出场角色": ["any_id"],
            "动作列表": [{"内容": "t"}],
            "对白": [{"角色编号": "whatever", "台词内容": "hi"}],
        }],
        "角色表": [],
    }
    result = validator.validate(screenplay)
    assert result["passed"] is True

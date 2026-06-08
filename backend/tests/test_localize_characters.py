"""验证角色表中文化输出"""

import sys
sys.path.insert(0, ".")
from orchestrator.scout_map_pipeline import ScoutMapReducePipeline


def test_localize_protagonist():
    chars = [{
        "id": "c1", "name": "路明非", "aliases": [],
        "description": {
            "physical": "普通少年",
            "personality": "自卑但善良",
            "role": "protagonist",
        },
        "importance": "10",
        "relationships": [
            {"target_id": "c2", "type": "friend", "note": "诺诺引导他"},
            {"target_id": "c4", "type": "mentor", "note": "校长给予使命"},
            {"target_id": "c5", "type": "potential_opponent", "note": "竞争"},
            {"target_id": "c8", "type": "subordinate", "note": "副手"},
        ],
        "first_appearance": "第7章",
    }]

    result = ScoutMapReducePipeline._localize_characters(chars)
    assert len(result) == 1
    c = result[0]

    # 字段名全部中文化
    assert "编号" in c
    assert "姓名" in c
    assert "外貌" in c
    assert "性格" in c
    assert "角色身份" in c
    assert "重要度" in c
    assert "关系" in c
    assert "首次出场" in c

    # 枚举值中文化
    assert c["角色身份"] == "主角"
    assert c["关系"][0]["关系"] == "朋友"
    assert c["关系"][1]["关系"] == "导师"
    assert c["关系"][2]["关系"] == "潜在对手"
    assert c["关系"][3]["关系"] == "下属"

    # 无英文残留
    assert "id" not in c
    assert "name" not in c
    assert "protagonist" not in str(result)


def test_localize_supporting_with_aliases():
    chars = [{
        "id": "c4", "name": "昂热", "aliases": ["校长"],
        "description": {
            "physical": "花白头发",
            "personality": "温和深邃",
            "role": "supporting",
        },
        "importance": "8",
        "relationships": [
            {"target_id": "c1", "type": "mentor_student", "note": "师生关系"},
        ],
        "first_appearance": "第7章",
    }]

    result = ScoutMapReducePipeline._localize_characters(chars)
    c = result[0]

    assert c["角色身份"] == "配角"
    assert c["别名"] == ["校长"]
    assert c["关系"][0]["关系"] == "师徒"


def test_handles_missing_description():
    chars = [{"id": "c1", "name": "路人", "importance": "1"}]
    result = ScoutMapReducePipeline._localize_characters(chars)
    c = result[0]
    assert c["外貌"] == ""
    assert c["性格"] == ""
    assert c["角色身份"] == ""


def test_no_english_enum_values_in_output():
    """确保输出 YAML 中不出现英文枚举值"""
    chars = [
        {"id": "c1", "name": "角色A", "description": {"physical": "", "personality": "", "role": "minor"}, "importance": "3", "relationships": [], "first_appearance": ""},
        {"id": "c2", "name": "角色B", "description": {"physical": "", "personality": "", "role": "antagonist"}, "importance": "7", "relationships": [], "first_appearance": ""},
        {"id": "c3", "name": "角色C", "description": {"physical": "", "personality": "", "role": "cameo"}, "importance": "1", "relationships": [], "first_appearance": ""},
    ]

    result = ScoutMapReducePipeline._localize_characters(chars)
    import json
    output_text = json.dumps(result, ensure_ascii=False)

    assert "protagonist" not in output_text
    assert "supporting" not in output_text
    assert "minor" in output_text or "龙套" in output_text  # value should be 龙套
    assert "antagonist" not in output_text
    assert "cameo" not in output_text
    assert "friend" not in output_text

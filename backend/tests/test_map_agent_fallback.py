"""验证 MapAgent 的降级恢复能力：宽松解析 + 修复提示"""

from agents.map_agent import MapAgent


def test_repair_scene_fills_all_missing_fields():
    agent = MapAgent()
    scene = {"场景编号": "", "来源章节": None}
    repaired = agent._repair_scene(scene, 0, 5)
    assert repaired["场景编号"] == "s1"
    assert repaired["来源章节"] == 5
    assert repaired["场景标题"]["地点"] == "未知"
    assert repaired["场景标题"]["时段"] == "白天"
    assert repaired["动作描述"] == []
    assert repaired["对白"] == []
    assert repaired["镜头建议"] == []
    assert repaired["转场方式"] is None
    assert repaired["出场角色"] == []
    assert repaired["情绪基调"] == ""


def test_lenient_parse_valid_yaml():
    agent = MapAgent()
    yaml_text = """
场景列表:
  - 场景编号: s1
    来源章节: 7
    场景标题:
      地点: 走廊
      时段: 夜晚
    出场角色:
      - c1
      - c2
    情绪基调: 紧张
    动作描述:
      - 路明非靠在墙上
    对白:
      - 角色编号: c2
        台词: 喝点这个
    镜头建议: []
"""
    scenes = agent._lenient_parse(yaml_text, 0)
    assert len(scenes) == 1
    assert scenes[0]["场景编号"] == "s1"
    assert scenes[0]["场景标题"]["地点"] == "走廊"


def test_lenient_parse_partial_fields_auto_filled():
    agent = MapAgent()
    partial = """
场景列表:
  - 场景编号: s1
    场景标题:
      时段: 白天
    动作描述:
      - 他们走进了房间
  - 场景标题:
      地点: 教室
    对白:
      - 台词: 你好
"""
    scenes = agent._lenient_parse(partial, 3)
    assert len(scenes) == 2
    # scene 1: missing 来源章节, 地点 → filled
    assert scenes[0]["来源章节"] == 3
    assert scenes[0]["场景标题"]["地点"] == "未知"
    # scene 2: missing 场景编号 → auto s2
    assert scenes[1]["场景编号"] == "s2"
    assert scenes[1]["场景标题"]["地点"] == "教室"


def test_lenient_parse_natural_language_with_yaml_embedded():
    agent = MapAgent()
    mixed = """这是一段叙事文字，描述了路明非走进校长办公室的场景。

场景列表:
  - 场景编号: s1
    来源章节: 7
    场景标题:
      地点: 校长办公室
      时段: 白天
    动作描述:
      - 路明非走进办公室
"""
    scenes = agent._lenient_parse(mixed, 0)
    assert len(scenes) >= 1
    assert scenes[0]["场景标题"]["地点"] == "校长办公室"


def test_clean_yaml_strips_triple_backticks():
    agent = MapAgent()
    dirty = "```yaml\n场景列表:\n  - 场景编号: s1\n    来源章节: 1\n    场景标题:\n      地点: 测试\n```"
    clean = agent._clean_yaml(dirty)
    assert clean.startswith("场景列表")
    assert "```" not in clean


def test_lenient_parse_bare_scene_blocks():
    """Embedded scene blocks without outer wrapper — best-effort extraction"""
    agent = MapAgent()
    embedded = """- 场景编号: s1
  来源章节: 7
  场景标题:
    地点: 走廊
    时段: 夜晚
  动作描述:
    - 路明非靠在墙上

- 场景编号: s2
  来源章节: 7
  场景标题:
    地点: 医务室
    时段: 稍后
  动作描述:
    - 护士检查路明非的眼睛
"""
    scenes = agent._lenient_parse(embedded, 0)
    # Best-effort: at least one scene extracted
    assert len(scenes) >= 1


def test_lenient_parse_completely_broken_returns_empty():
    agent = MapAgent()
    scenes = agent._lenient_parse("这是完全无法解析的纯文本", 0)
    assert scenes == []


def test_parse_and_validate_returns_error_details():
    agent = MapAgent()
    # Missing 场景标题.地点
    bad_yaml = """
场景列表:
  - 场景编号: s1
    来源章节: 1
    场景标题:
      时段: 白天
"""
    scenes, errors = agent._parse_and_validate(bad_yaml)
    assert scenes == []
    assert errors is not None
    assert "地点" in errors[0] or "Pydantic" in errors[0]


def test_parse_and_validate_missing_scene_list_key():
    agent = MapAgent()
    bad = "其他键: 值"
    scenes, errors = agent._parse_and_validate(bad)
    assert scenes == []
    assert "场景列表" in errors[0]


def test_build_fix_prompt_includes_errors():
    agent = MapAgent()
    prompt = agent._build_fix_prompt(
        "原始prompt", "上次失败的输出", ["错误1", "错误2"]
    )
    assert "校验错误" in prompt
    assert "错误1" in prompt
    assert "错误2" in prompt
    assert "上次失败的输出" in prompt
    assert "场景列表" in prompt  # fix instructions mention this

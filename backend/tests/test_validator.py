"""Validator 单元测试"""

import pytest
from agents.validator import Validator


@pytest.fixture
def valid_screenplay():
    return {
        "scenes": [
            {"scene_id":"s1","heading":{"location":"ROOM","time_of_day":"MORNING"},"characters_present":["c1"],"action":[{"text":"t"}],"dialogue":[{"character_id":"c1","text":"hi"}]},
            {"scene_id":"s2","heading":{"location":"PARK","time_of_day":"AFTERNOON"},"characters_present":["c1","c2"],"action":[{"text":"t"}],"dialogue":[]},
        ],
        "dramatis_personae":[
            {"id":"c1","name":"John","description":{"role":"protagonist"}},
            {"id":"c2","name":"Jane","description":{"role":"supporting"}},
        ],
    }


def test_valid_passes(valid_screenplay):
    r = Validator().validate(valid_screenplay)
    assert r["passed"]


def test_missing_scene_id_fails():
    r = Validator().validate({"scenes":[{"heading":{"location":"X","time_of_day":"MORNING"},"action":[{"text":"t"}]}],"dramatis_personae":[]})
    assert not r["passed"]


def test_invalid_character_fails(valid_screenplay):
    valid_screenplay["scenes"][0]["characters_present"]=["c99"]
    r = Validator().validate(valid_screenplay)
    assert not r["passed"]


def test_empty_scenes_fails():
    r = Validator().validate({"scenes":[],"dramatis_personae":[]})
    assert not r["passed"]


def test_non_sequential_warns():
    v = Validator()
    r = v.validate({"scenes":[
        {"scene_id":"s3","heading":{"location":"A","time_of_day":"MORNING"},"characters_present":[],"action":[{"text":"t"}],"dialogue":[]},
        {"scene_id":"s1","heading":{"location":"B","time_of_day":"NIGHT"},"characters_present":[],"action":[{"text":"t"}],"dialogue":[]},
    ],"dramatis_personae":[]})
    assert r["passed"]
    assert any("不连续" in w for w in r["warnings"])


def test_low_dialogue_warns():
    v = Validator()
    scenes = [{"scene_id":f"s{i}","heading":{"location":"X","time_of_day":"MORNING"},"characters_present":[],"action":[{"text":"t"}],"dialogue":[]} for i in range(1,11)]
    scenes[0]["dialogue"] = [{"character_id":"x","text":"hi"}]
    r = v.validate({"scenes":scenes,"dramatis_personae":[]})
    assert any("对白" in w for w in r["warnings"])


def test_missing_heading_fails():
    r = Validator().validate({"scenes":[{"scene_id":"s1","action":[{"text":"t"}]}],"dramatis_personae":[]})
    assert not r["passed"]


def test_missing_action_fails():
    r = Validator().validate({"scenes":[{"scene_id":"s1","heading":{"location":"X","time_of_day":"MORNING"}}],"dramatis_personae":[]})
    assert not r["passed"]


def test_dialogue_unknown_char_fails(valid_screenplay):
    valid_screenplay["scenes"][0]["dialogue"]=[{"character_id":"c_ghost","text":"boo"}]
    r = Validator().validate(valid_screenplay)
    assert not r["passed"]

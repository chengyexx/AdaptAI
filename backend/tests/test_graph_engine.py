"""GraphEngine 单元测试"""

import pytest
from state.models import SessionState, PipelineStatus, PipelineMeta
from orchestrator.graph_engine import GraphEngine


@pytest.fixture
def engine():
    return GraphEngine()


@pytest.fixture
def state():
    s = SessionState(thread_id="test")
    s.pipeline_state = PipelineMeta(checkpoint_stack=["parser_done"])
    return s


def test_low_confidence_triggers_hitl(engine, state):
    r = engine.evaluate_agent_result(state, "character_agent", 0.5, [])
    assert r == PipelineStatus.CHAR_HITL


def test_high_confidence_proceeds(engine, state):
    r = engine.evaluate_agent_result(state, "character_agent", 0.85, [])
    assert r == PipelineStatus.CHAR_DONE


def test_fatal_error_stops(engine, state):
    r = engine.evaluate_agent_result(state, "character_agent", 0.9, ["Invalid API key"])
    assert r == PipelineStatus.ERROR


def test_create_hitl_request(engine):
    req = engine.create_hitl_request("char_agent", {}, "low", 0.5)
    assert req.node == "char_agent"
    assert req.confidence == 0.5


def test_should_retry(engine, state):
    state.status = PipelineStatus.ERROR
    assert engine.should_retry(state, "x", 0) is True
    assert engine.should_retry(state, "x", 3) is False


def test_backtrack(engine, state):
    state.pipeline_state.checkpoint_stack = ["parser_done", "char_done"]
    r = engine.backtrack(state)
    assert r.status == PipelineStatus.PARSED


def test_backtrack_empty(engine, state):
    state.pipeline_state.checkpoint_stack = []
    r = engine.backtrack(state)
    assert r.status == PipelineStatus.CREATED


def test_validation_failure_retries_script(engine, state):
    state.pipeline_state.checkpoint_stack = ["parser_done", "char_done", "scene_done", "script_done"]
    r = engine.handle_validation_failure(state)
    assert r.status == PipelineStatus.SCRIPT_GENERATING


def test_scene_low_to_hitl(engine, state):
    r = engine.evaluate_agent_result(state, "scene_agent", 0.4, [])
    assert r == PipelineStatus.SCENE_HITL


def test_script_low_to_hitl(engine, state):
    r = engine.evaluate_agent_result(state, "script_agent", 0.3, [])
    assert r == PipelineStatus.SCRIPT_HITL

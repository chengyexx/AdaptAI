"""GraphEngine 单元测试 — HITL 分支、重试、回溯"""

import pytest
from state.models import SessionState, PipelineStatus, PipelineMeta
from orchestrator.graph_engine import GraphEngine


@pytest.fixture
def engine():
    return GraphEngine(confidence_threshold=0.7, max_retries=3)


@pytest.fixture
def state_in_progress():
    state = SessionState(thread_id="test-graph")
    state.status = PipelineStatus.CHAR_EXTRACTING
    state.pipeline_state = PipelineMeta(
        current_agent="character_agent",
        progress=0.2,
        checkpoint_stack=["parser_done"],
    )
    return state


# ── 置信度评估 ──

def test_low_confidence_triggers_hitl(engine, state_in_progress):
    result = engine.evaluate_agent_result(
        state_in_progress, "character_agent", confidence=0.5, errors=[]
    )
    assert result == PipelineStatus.CHAR_HITL


def test_high_confidence_proceeds(engine, state_in_progress):
    result = engine.evaluate_agent_result(
        state_in_progress, "character_agent", confidence=0.85, errors=[]
    )
    assert result == PipelineStatus.CHAR_DONE


def test_fatal_error_stops(engine, state_in_progress):
    result = engine.evaluate_agent_result(
        state_in_progress, "character_agent", confidence=0.9,
        errors=["Invalid API key: unauthorized"]
    )
    assert result == PipelineStatus.ERROR


# ── HITL 请求 ──

def test_create_hitl_request(engine):
    request = engine.create_hitl_request(
        "character_agent", {"characters": []}, "low_confidence", 0.55
    )
    assert request.node == "character_agent"
    assert request.confidence == 0.55
    assert request.reason == "low_confidence"


# ── 重试判断 ──

def test_should_retry_within_limit(engine, state_in_progress):
    state_in_progress.status = PipelineStatus.ERROR
    assert engine.should_retry(state_in_progress, "script_agent", retries_used=0) is True


def test_should_not_retry_exceeded(engine, state_in_progress):
    state_in_progress.status = PipelineStatus.ERROR
    assert engine.should_retry(state_in_progress, "script_agent", retries_used=3) is False


# ── 回溯 ──

def test_backtrack_to_previous_checkpoint(engine, state_in_progress):
    state_in_progress.pipeline_state.checkpoint_stack = ["parser_done", "char_done"]
    state_in_progress.status = PipelineStatus.SCENE_SEGMENTING

    result = engine.backtrack(state_in_progress)
    # 移除 "char_done" 后，上次检查点是 "parser_done" → PARSED
    assert result.status == PipelineStatus.PARSED


def test_backtrack_empty_stack(engine, state_in_progress):
    state_in_progress.pipeline_state.checkpoint_stack = []
    result = engine.backtrack(state_in_progress)
    assert result.status == PipelineStatus.CREATED


# ── 校验失败处理 ──

def test_validation_failure_retries_script(engine, state_in_progress):
    state_in_progress.pipeline_state.checkpoint_stack = [
        "parser_done", "char_done", "scene_done", "script_done"
    ]
    state_in_progress.status = PipelineStatus.VALIDATING

    result = engine.handle_validation_failure(state_in_progress)
    assert result.status == PipelineStatus.SCRIPT_GENERATING
    assert result.pipeline_state.current_agent == "script_agent"


# ── 场景→HITL 映射 ──

def test_scene_agent_low_confidence_to_hitl(engine, state_in_progress):
    state_in_progress.status = PipelineStatus.SCENE_SEGMENTING
    result = engine.evaluate_agent_result(
        state_in_progress, "scene_agent", confidence=0.4, errors=[]
    )
    assert result == PipelineStatus.SCENE_HITL


def test_script_agent_low_confidence_to_hitl(engine, state_in_progress):
    state_in_progress.status = PipelineStatus.SCRIPT_GENERATING
    result = engine.evaluate_agent_result(
        state_in_progress, "script_agent", confidence=0.3, errors=[]
    )
    assert result == PipelineStatus.SCRIPT_HITL

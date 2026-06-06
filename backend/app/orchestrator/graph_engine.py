"""图引擎 — HITL 分支、重试循环、条件边、回溯"""

from state.models import SessionState, PipelineStatus, HITLRequest


class GraphEngine:
    def __init__(self, confidence_threshold: float = 0.7, max_retries: int = 3):
        self.confidence_threshold = confidence_threshold
        self.max_retries = max_retries

    def evaluate_agent_result(self, state: SessionState, agent_id: str, confidence: float, errors: list[str]) -> PipelineStatus:
        if errors and not self._is_recoverable(errors):
            return PipelineStatus.ERROR
        if confidence < self.confidence_threshold:
            hitl_map = {
                "character_agent": PipelineStatus.CHAR_HITL,
                "scene_agent": PipelineStatus.SCENE_HITL,
                "script_agent": PipelineStatus.SCRIPT_HITL,
            }
            return hitl_map.get(agent_id, PipelineStatus.ERROR)
        done_map = {
            "character_agent": PipelineStatus.CHAR_DONE,
            "scene_agent": PipelineStatus.SCENE_DONE,
            "script_agent": PipelineStatus.SCRIPT_DONE,
        }
        return done_map.get(agent_id, PipelineStatus.ERROR)

    def create_hitl_request(self, agent_id: str, data: dict, reason: str, confidence: float) -> HITLRequest:
        return HITLRequest(node=agent_id, data=data, reason=reason, confidence=confidence)

    def should_retry(self, state: SessionState, agent_id: str, retries_used: int) -> bool:
        if retries_used >= self.max_retries:
            return False
        return state.status == PipelineStatus.ERROR

    def backtrack(self, state: SessionState) -> SessionState:
        stack = state.pipeline_state.checkpoint_stack
        if not stack:
            state.status = PipelineStatus.CREATED
            return state
        stack.pop()
        if not stack:
            state.status = PipelineStatus.CREATED
            return state
        last = stack[-1]
        rollback_map = {
            "parser_done": PipelineStatus.PARSED,
            "char_done": PipelineStatus.CHAR_DONE,
            "scene_done": PipelineStatus.SCENE_DONE,
            "script_done": PipelineStatus.SCRIPT_DONE,
        }
        state.status = rollback_map.get(last, PipelineStatus.CREATED)
        return state

    def handle_validation_failure(self, state: SessionState) -> SessionState:
        stack = state.pipeline_state.checkpoint_stack
        if stack and stack[-1] == "script_done":
            stack.pop()
        state.status = PipelineStatus.SCRIPT_GENERATING
        state.pipeline_state.current_agent = "script_agent"
        return state

    @staticmethod
    def _is_recoverable(errors: list[str]) -> bool:
        fatal_keywords = ["invalid api key", "authentication", "unauthorized", "403", "401"]
        for err in errors:
            for kw in fatal_keywords:
                if kw in err.lower():
                    return False
        return True

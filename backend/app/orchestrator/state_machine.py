"""Pipeline 状态机 — 管理状态转换规则"""

from state.models import PipelineStatus

# 合法的状态转换映射
TRANSITIONS: dict[PipelineStatus, set[PipelineStatus]] = {
    PipelineStatus.CREATED:           {PipelineStatus.PARSING, PipelineStatus.ERROR},
    PipelineStatus.PARSING:           {PipelineStatus.PARSED, PipelineStatus.SCOUT_HITL, PipelineStatus.ERROR},
    PipelineStatus.PARSED:            {PipelineStatus.CHAR_EXTRACTING, PipelineStatus.ERROR},
    PipelineStatus.SCOUT_HITL:        {PipelineStatus.CHAR_DONE, PipelineStatus.SCENE_SEGMENTING, PipelineStatus.ERROR},
    PipelineStatus.CHAR_EXTRACTING:   {PipelineStatus.CHAR_DONE, PipelineStatus.CHAR_HITL, PipelineStatus.ERROR, PipelineStatus.PAUSED},
    PipelineStatus.CHAR_HITL:         {PipelineStatus.CHAR_EXTRACTING, PipelineStatus.CHAR_DONE, PipelineStatus.ERROR},
    PipelineStatus.CHAR_DONE:         {PipelineStatus.SCENE_SEGMENTING, PipelineStatus.ERROR},
    PipelineStatus.SCENE_SEGMENTING:  {PipelineStatus.SCENE_DONE, PipelineStatus.SCENE_HITL, PipelineStatus.ERROR, PipelineStatus.PAUSED},
    PipelineStatus.SCENE_HITL:        {PipelineStatus.SCENE_SEGMENTING, PipelineStatus.SCENE_DONE, PipelineStatus.ERROR},
    PipelineStatus.SCENE_DONE:        {PipelineStatus.SCRIPT_GENERATING, PipelineStatus.VALIDATING, PipelineStatus.ERROR},
    PipelineStatus.SCRIPT_GENERATING: {PipelineStatus.SCRIPT_DONE, PipelineStatus.SCRIPT_HITL, PipelineStatus.ERROR, PipelineStatus.PAUSED},
    PipelineStatus.SCRIPT_HITL:       {PipelineStatus.SCRIPT_GENERATING, PipelineStatus.SCRIPT_DONE, PipelineStatus.ERROR},
    PipelineStatus.SCRIPT_DONE:       {PipelineStatus.VALIDATING, PipelineStatus.ERROR},
    PipelineStatus.VALIDATING:        {PipelineStatus.COMPLETED, PipelineStatus.SCRIPT_GENERATING, PipelineStatus.ERROR},
    PipelineStatus.COMPLETED:         {PipelineStatus.ERROR},
    PipelineStatus.ERROR:             {PipelineStatus.CREATED, PipelineStatus.PARSING, PipelineStatus.CHAR_EXTRACTING, PipelineStatus.SCENE_SEGMENTING, PipelineStatus.SCRIPT_GENERATING, PipelineStatus.VALIDATING},
    PipelineStatus.PAUSED:            {PipelineStatus.CHAR_EXTRACTING, PipelineStatus.SCENE_SEGMENTING, PipelineStatus.SCRIPT_GENERATING, PipelineStatus.ERROR},
}


class StateMachine:
    """管理 Pipeline 状态转换"""

    @staticmethod
    def can_transition(current: PipelineStatus, target: PipelineStatus) -> bool:
        return target in TRANSITIONS.get(current, set())

    @staticmethod
    def transition(current: PipelineStatus, target: PipelineStatus) -> PipelineStatus:
        if not StateMachine.can_transition(current, target):
            allowed = TRANSITIONS.get(current, set())
            raise ValueError(
                f"非法状态转换: {current.value} → {target.value}。"
                f"允许: {[s.value for s in allowed]}"
            )
        return target

    @staticmethod
    def is_terminal(status: PipelineStatus) -> bool:
        return status in {PipelineStatus.COMPLETED, PipelineStatus.ERROR}

    @staticmethod
    def is_hitl_status(status: PipelineStatus) -> bool:
        return status in {
            PipelineStatus.SCOUT_HITL, PipelineStatus.CHAR_HITL,
            PipelineStatus.SCENE_HITL, PipelineStatus.SCRIPT_HITL,
        }

    @staticmethod
    def agent_for_status(status: PipelineStatus) -> str:
        """返回该状态下应执行的 Agent ID"""
        agent_map = {
            PipelineStatus.PARSING: "chapter_parser",
            PipelineStatus.SCOUT_HITL: "scout_agent",
            PipelineStatus.CHAR_EXTRACTING: "character_agent",
            PipelineStatus.SCENE_SEGMENTING: "scene_agent",
            PipelineStatus.SCRIPT_GENERATING: "script_agent",
            PipelineStatus.VALIDATING: "validator",
        }
        return agent_map.get(status, "")

"""State Store 数据模型 — 会话状态、Pipeline 元数据、Artifacts"""

from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
import uuid


class PipelineStatus(str, Enum):
    """Pipeline 生命周期状态"""
    CREATED = "created"
    PARSING = "parsing"
    PARSED = "parsed"
    SCOUT_HITL = "scout_hitl"            # ⏸ Scout 后暂停，等待人类审阅
    CHAR_EXTRACTING = "char_extracting"
    CHAR_HITL = "char_hitl"
    CHAR_DONE = "char_done"
    SCENE_SEGMENTING = "scene_segmenting"
    SCENE_HITL = "scene_hitl"
    SCENE_DONE = "scene_done"
    SCRIPT_GENERATING = "script_generating"
    SCRIPT_HITL = "script_hitl"
    SCRIPT_DONE = "script_done"
    VALIDATING = "validating"
    COMPLETED = "completed"
    ERROR = "error"
    PAUSED = "paused"


@dataclass
class HITLRequest:
    """HITL 挂起请求 — 等待用户编辑时存储在 State 中"""
    node: str                              # 触发 HITL 的 Agent ID
    data: dict                             # 待用户编辑的数据（如角色列表）
    reason: str                            # 触发原因：low_confidence / user_requested / error
    confidence: float = 0.5


@dataclass
class Artifacts:
    """Pipeline 中间产物 — 轻量字段内联，大文本存指针"""
    chapters: list = field(default_factory=list)     # [{index, title, summary, char_count, text_ptr}]
    characters: list = field(default_factory=list)   # [{id, name, ...}]
    locations: list = field(default_factory=list)    # [{id, name, type, description}]
    scenes: list = field(default_factory=list)       # [{scene_id, ...}]
    script_yaml: str | None = None                   # 最终剧本 YAML
    adaptation_notes: list = field(default_factory=list)


@dataclass
class PipelineMeta:
    """Pipeline 进度元数据"""
    current_agent: str = ""                # 当前正在执行的 Agent ID
    progress: float = 0.0                  # 0.0 ~ 1.0
    checkpoint_stack: list[str] = field(default_factory=list)  # 支持回溯


@dataclass
class SessionState:
    """完整的会话状态 — 一次「小说→剧本」转换的全量快照"""
    thread_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: PipelineStatus = PipelineStatus.CREATED
    artifacts: Artifacts = field(default_factory=Artifacts)
    pipeline_state: PipelineMeta = field(default_factory=PipelineMeta)
    pending_hitl: HITLRequest | None = None
    errors: list[dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

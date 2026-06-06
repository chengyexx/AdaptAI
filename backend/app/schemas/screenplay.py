"""剧本 YAML Schema — Pydantic 数据模型（对应 docs/superpowers/specs/...screenplay-yaml-schema.md）"""

from pydantic import BaseModel, Field
from typing import Literal
from enum import Enum


# ═══════════════════════════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════════════════════════

class CharacterRole(str, Enum):
    PROTAGONIST = "protagonist"
    ANTAGONIST = "antagonist"
    SUPPORTING = "supporting"
    MINOR = "minor"
    CAMEO = "cameo"


class RelationType(str, Enum):
    FAMILY = "family"
    FRIEND = "friend"
    RIVAL = "rival"
    ROMANTIC = "romantic"
    MENTOR_STUDENT = "mentor_student"
    COLLEAGUE = "colleague"
    ENEMY = "enemy"
    OTHER = "other"


class TimeOfDay(str, Enum):
    DAWN = "DAWN"
    MORNING = "MORNING"
    AFTERNOON = "AFTERNOON"
    EVENING = "EVENING"
    NIGHT = "NIGHT"
    LATER = "LATER"
    CONTINUOUS = "CONTINUOUS"


class ShotType(str, Enum):
    WIDE = "wide"
    CLOSE_UP = "close-up"
    MEDIUM = "medium"
    TRACKING = "tracking"
    PAN = "pan"
    TILT = "tilt"
    DOLLY = "dolly"
    AERIAL = "aerial"
    POV = "pov"
    OVER_THE_SHOULDER = "over-the-shoulder"
    INSERT = "insert"
    CUTAWAY = "cutaway"


class TransitionType(str, Enum):
    CUT_TO = "CUT TO"
    FADE_IN = "FADE IN"
    FADE_OUT = "FADE OUT"
    DISSOLVE_TO = "DISSOLVE TO"
    SMASH_CUT_TO = "SMASH CUT TO"
    MATCH_CUT_TO = "MATCH CUT TO"


class NoteCategory(str, Enum):
    PACING = "pacing"
    DIALOGUE = "dialogue"
    STRUCTURE = "structure"
    CHARACTER = "character"
    VISUAL = "visual"


class NoteSeverity(str, Enum):
    SUGGESTION = "suggestion"
    RECOMMENDATION = "recommendation"
    WARNING = "warning"


# ═══════════════════════════════════════════════════════════════
# 角色相关
# ═══════════════════════════════════════════════════════════════

class CharacterDescription(BaseModel):
    physical: str = ""
    personality: str = ""
    role: CharacterRole


class Relationship(BaseModel):
    target_id: str
    type: RelationType
    note: str = ""


class Character(BaseModel):
    id: str                                    # c1, c2, ...
    name: str
    aliases: list[str] = Field(default_factory=list)
    description: CharacterDescription
    relationships: list[Relationship] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# 场景相关
# ═══════════════════════════════════════════════════════════════

class SceneHeading(BaseModel):
    location: str                              # "INT. COFFEE SHOP" 或 "EXT. PARK"
    time_of_day: TimeOfDay
    setting_detail: str = ""


class ActionBlock(BaseModel):
    type: Literal["action", "parenthetical"] = "action"
    text: str


class DialogueBlock(BaseModel):
    character_id: str                          # 说话角色 ID
    emotion: str = ""                          # 情绪状态
    delivery: str = ""                         # 表演提示（whispering, shouting...）
    text: str                                  # 对白原文
    parenthetical: str = ""                    # 行为提示 "(to himself)"


class ShotSuggestion(BaseModel):
    type: ShotType
    description: str
    optional: bool = True                      # 始终 true——AI建议非强制


class Scene(BaseModel):
    scene_id: str                              # s1, s2, ...
    chapter: int                               # 来源章节编号
    heading: SceneHeading
    characters_present: list[str] = Field(default_factory=list)
    mood: str = ""
    action: list[ActionBlock]                  # 至少一个
    dialogue: list[DialogueBlock] = Field(default_factory=list)
    shots: list[ShotSuggestion] = Field(default_factory=list)
    transition: TransitionType | None = None   # None = 默认硬切


# ═══════════════════════════════════════════════════════════════
# 改编建议 + 统计
# ═══════════════════════════════════════════════════════════════

class AdaptationNote(BaseModel):
    scene_id: str | None = None                # 作用于特定场景
    chapter: int | None = None                 # 作用于特定章节
    category: NoteCategory
    severity: NoteSeverity
    content: str


class Stats(BaseModel):
    scene_count: int = 0
    character_count: int = 0
    total_dialogue_blocks: int = 0
    estimated_runtime_minutes: float = 0.0


# ═══════════════════════════════════════════════════════════════
# 元数据 + 根模型
# ═══════════════════════════════════════════════════════════════

class Metadata(BaseModel):
    title: str
    original_author: str = ""
    converted_by: str = "AI"
    model: str = ""
    conversion_date: str = ""
    source_chapters: int = 0


class Screenplay(BaseModel):
    """剧本根模型 — 对应完整的 YAML 输出"""
    schema_version: str = "1.0.0"
    metadata: Metadata
    dramatis_personae: list[Character]
    scenes: list[Scene]
    adaptation_notes: list[AdaptationNote] = Field(default_factory=list)
    stats: Stats = Field(default_factory=Stats)

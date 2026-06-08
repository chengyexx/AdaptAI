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
    DAWN = "黎明"
    MORNING = "早晨"
    AFTERNOON = "下午"
    EVENING = "傍晚"
    NIGHT = "夜晚"
    LATER = "稍后"
    CONTINUOUS = "连续"


class ShotType(str, Enum):
    WIDE = "全景"
    CLOSE_UP = "特写"
    MEDIUM = "中景"
    TRACKING = "跟拍"
    PAN = "横摇"
    TILT = "俯仰"
    DOLLY = "滑轨"
    AERIAL = "航拍"
    POV = "主观视角"
    OVER_THE_SHOULDER = "过肩"
    INSERT = "插入镜头"
    CUTAWAY = "切出"


class TransitionType(str, Enum):
    CUT_TO = "切至"
    FADE_IN = "淡入"
    FADE_OUT = "淡出"
    DISSOLVE_TO = "叠化至"
    SMASH_CUT_TO = "跳切至"
    MATCH_CUT_TO = "匹配切至"


class NoteCategory(str, Enum):
    PACING = "节奏"
    DIALOGUE = "对白"
    STRUCTURE = "结构"
    CHARACTER = "角色"
    VISUAL = "视觉"


class NoteSeverity(str, Enum):
    SUGGESTION = "建议"
    RECOMMENDATION = "推荐"
    WARNING = "警告"


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
    location: str                              # "内景 咖啡店" 或 "外景 公园"
    time_of_day: TimeOfDay
    setting_detail: str = ""


class ActionBlock(BaseModel):
    type: Literal["动作", "行为提示"] = "动作"
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


# ═══════════════════════════════════════════════════════════════
# Chunk Output — LLM 每块输出 YAML 的校验模型（升级版：含镜头/转场/情绪）
# ═══════════════════════════════════════════════════════════════

class ChunkDialogueLine(BaseModel):
    """单条对白 — 匹配 LLM 输出"""
    character_id: str = ""               # c1, c2（优先用 ID）
    character: str = ""                  # 回退用角色名
    emotion_or_action: str | None = None
    line: str
    type: Literal["普通", "画外音", "画外"] = "普通"


class ChunkShotSuggestion(BaseModel):
    """镜头建议 — 匹配 LLM 输出"""
    type: str = "全景"                   # 全景, 特写, 中景, 跟拍, 横摇, 主观视角...
    description: str = ""
    optional: bool = True


class ChunkSceneHeading(BaseModel):
    """场景标题"""
    location: str
    time_of_day: Literal["白天", "夜晚", "黎明", "黄昏"] = "白天"
    setting_detail: str = ""


class ChunkScene(BaseModel):
    """单块输出的场景 — 升级版，匹配完整 Screenplay 字段"""
    scene_id: str
    chapter: int | str
    heading: ChunkSceneHeading
    characters_present: list[str] = Field(default_factory=list)
    mood: str = ""                                         # 情绪基调
    plot_actions: list[str] = Field(description="纯动作与视觉描写", default_factory=list)
    dialogues: list[ChunkDialogueLine] = Field(default_factory=list)
    shots: list[ChunkShotSuggestion] = Field(default_factory=list)  # 镜头建议
    transition: str | None = None                          # CUT TO / FADE IN / ...


class ScriptDocument(BaseModel):
    """LLM 输出的完整文档模型 — 用于 Pydantic 校验"""
    scenes: list[ChunkScene]


# ═══════════════════════════════════════════════════════════════
# Final Output — 最终交付的完整剧本模型
# ═══════════════════════════════════════════════════════════════

class FinalStats(BaseModel):
    """剧本统计"""
    scene_count: int = 0
    character_count: int = 0
    total_dialogue_blocks: int = 0
    estimated_runtime_minutes: float = 0.0


class FinalScreenplay(BaseModel):
    """最终交付的完整剧本"""
    schema_version: str = "1.0.0"
    title: str = ""
    original_author: str = ""
    conversion_date: str = ""
    dramatis_personae: list = Field(default_factory=list)
    scenes: list[ChunkScene] = Field(default_factory=list)
    adaptation_notes: list[str] = Field(default_factory=list)
    stats: FinalStats = Field(default_factory=FinalStats)

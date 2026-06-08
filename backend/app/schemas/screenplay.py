"""剧本 YAML Schema — Pydantic 数据模型（全中文字段名）"""

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
    地点: str                                   # "内景 咖啡店" 或 "外景 公园"
    时段: TimeOfDay
    场景细节: str = ""


class ActionBlock(BaseModel):
    类型: Literal["动作", "行为提示"] = "动作"
    内容: str


class DialogueBlock(BaseModel):
    角色编号: str                               # 说话角色 ID
    情绪: str = ""                             # 情绪状态
    表演提示: str = ""                          # 表演提示
    台词内容: str                              # 对白原文
    行为提示: str = ""                          # 行为提示


class ShotSuggestion(BaseModel):
    镜头类型: ShotType
    镜头描述: str
    可选: bool = True                           # 始终 true——AI建议非强制


class Scene(BaseModel):
    场景编号: str                               # s1, s2, ...
    来源章节: int                              # 来源章节编号
    场景标题: SceneHeading
    出场角色: list[str] = Field(default_factory=list)
    情绪基调: str = ""
    动作列表: list[ActionBlock]                 # 至少一个
    对白: list[DialogueBlock] = Field(default_factory=list)
    镜头建议: list[ShotSuggestion] = Field(default_factory=list)
    转场方式: TransitionType | None = None      # None = 默认硬切


# ═══════════════════════════════════════════════════════════════
# 改编建议 + 统计
# ═══════════════════════════════════════════════════════════════

class AdaptationNote(BaseModel):
    场景编号: str | None = None                 # 作用于特定场景
    来源章节: int | None = None                # 作用于特定章节
    分类: NoteCategory
    严重程度: NoteSeverity
    内容: str


class Stats(BaseModel):
    场景数量: int = 0
    角色数量: int = 0
    对白总数: int = 0
    预估时长分钟: float = 0.0


# ═══════════════════════════════════════════════════════════════
# 元数据 + 根模型
# ═══════════════════════════════════════════════════════════════

class Metadata(BaseModel):
    剧本标题: str
    原著作者: str = ""
    转换工具: str = "AI"
    使用模型: str = ""
    转换日期: str = ""
    来源章节数: int = 0


class Screenplay(BaseModel):
    """剧本根模型 — 对应完整的 YAML 输出"""
    格式版本: str = "1.0.0"
    元数据: Metadata
    角色表: list[Character]
    场景列表: list[Scene]
    改编说明: list[AdaptationNote] = Field(default_factory=list)
    统计信息: Stats = Field(default_factory=Stats)


# ═══════════════════════════════════════════════════════════════
# Chunk Output — LLM 每块输出 YAML 的校验模型（升级版：含镜头/转场/情绪）
# ═══════════════════════════════════════════════════════════════

class ChunkDialogueLine(BaseModel):
    """单条对白 — 匹配 LLM 输出"""
    角色编号: str = ""                          # c1, c2（优先用 ID）
    角色名称: str = ""                          # 回退用角色名
    情绪动作: str | None = None
    台词: str
    对白类型: Literal["普通", "画外音", "画外"] = "普通"


class ChunkShotSuggestion(BaseModel):
    """镜头建议 — 匹配 LLM 输出"""
    镜头类型: str = "全景"                      # 全景, 特写, 中景, 跟拍, 横摇, 主观视角...
    镜头描述: str = ""
    可选: bool = True


class ChunkSceneHeading(BaseModel):
    """场景标题"""
    地点: str
    时段: Literal["白天", "夜晚", "黎明", "黄昏"] = "白天"
    场景细节: str = ""


class ChunkScene(BaseModel):
    """单块输出的场景 — 升级版，匹配完整 Screenplay 字段"""
    场景编号: str
    来源章节: int | str
    场景标题: ChunkSceneHeading
    出场角色: list[str] = Field(default_factory=list)
    情绪基调: str = ""                                         # 情绪基调
    动作描述: list[str] = Field(description="纯动作与视觉描写", default_factory=list)
    对白: list[ChunkDialogueLine] = Field(default_factory=list)
    镜头建议: list[ChunkShotSuggestion] = Field(default_factory=list)  # 镜头建议
    转场方式: str | None = None                          # 切至 / 淡入 / ...


class ScriptDocument(BaseModel):
    """LLM 输出的完整文档模型 — 用于 Pydantic 校验"""
    场景列表: list[ChunkScene]


# ═══════════════════════════════════════════════════════════════
# Final Output — 最终交付的完整剧本模型
# ═══════════════════════════════════════════════════════════════

class FinalStats(BaseModel):
    """剧本统计"""
    场景数量: int = 0
    角色数量: int = 0
    对白总数: int = 0
    预估时长分钟: float = 0.0


class FinalScreenplay(BaseModel):
    """最终交付的完整剧本"""
    格式版本: str = "1.0.0"
    剧本标题: str = ""
    原著作者: str = ""
    转换日期: str = ""
    角色表: list = Field(default_factory=list)
    场景列表: list[ChunkScene] = Field(default_factory=list)
    改编说明: list[str] = Field(default_factory=list)
    统计信息: FinalStats = Field(default_factory=FinalStats)

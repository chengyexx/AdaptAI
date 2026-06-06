"""剧本 YAML Schema — Pydantic 数据模型"""

from .screenplay import (
    Screenplay, Metadata, Character, Scene, SceneHeading,
    ActionBlock, DialogueBlock, ShotSuggestion, AdaptationNote, Stats,
    CharacterRole, RelationType, TimeOfDay, ShotType, TransitionType,
    NoteCategory, NoteSeverity,
)

__all__ = [
    "Screenplay", "Metadata", "Character", "Scene", "SceneHeading",
    "ActionBlock", "DialogueBlock", "ShotSuggestion", "AdaptationNote", "Stats",
    "CharacterRole", "RelationType", "TimeOfDay", "ShotType", "TransitionType",
    "NoteCategory", "NoteSeverity",
]

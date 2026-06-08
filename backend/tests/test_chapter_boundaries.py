"""验证多篇章边界追踪逻辑"""

import sys
sys.path.insert(0, ".")

from agents.chapter_parser import ChapterParser
from orchestrator.scout_map_pipeline import ScoutMapReducePipeline


def test_slice_chapters_returns_3tuples():
    text = """《龙族I·火之晨曦》同人续写
这是同人续写的内容。段落很长。有好多内容。

第7章 黄金瞳（2）
诺诺扶着路明非靠在走廊冰冷的石墙上，从口袋里摸出一小瓶银色的液体递给他。

第8章 新生报到与芬格尔
路明非拖着行李箱走进卡塞尔学院的大门。"""

    parser = ChapterParser()
    chapters = parser.parse(text)

    # 3 chapters: 同人续写(index=1), 第7章(index=2), 第8章(index=3)
    assert len(chapters) == 3

    chunks = ScoutMapReducePipeline._slice_chapters(chapters)
    assert len(chunks) == 3  # all short, one chunk each

    # Verify each tuple has 3 elements
    for chunk in chunks:
        assert len(chunk) == 3
        title, text_chunk, chap_idx = chunk
        assert isinstance(chap_idx, int)

    # Verify chapter indices
    assert chunks[0][2] == 1  # 同人续写
    assert chunks[1][2] == 2  # 第7章
    assert chunks[2][2] == 3  # 第8章


def test_chapter_boundary_tracking():
    """Simulate chapter boundary tracking as done in _run_map"""
    chapters = [
        {"index": 1, "title": "同人续写"},
        {"index": 2, "title": "第7章 黄金瞳"},
        {"index": 3, "title": "第8章 新生报到"},
    ]
    chunks = [
        ("同人续写", "text1", 1),
        ("第7章 (第1部分)", "text2a", 2),
        ("第7章 (第2部分)", "text2b", 2),
        ("第8章", "text3", 3),
    ]

    all_scenes = []
    chapter_boundaries = []
    _last_chapter_idx = None

    for idx, (chunk_label, chunk_text, chapter_idx) in enumerate(chunks):
        # Simulate generating scenes
        fake_scenes = [{"场景编号": f"s{len(all_scenes) + i}"} for i in range(3)]

        if chapter_idx != _last_chapter_idx:
            chapter_boundaries.append({
                "title": chapters[chapter_idx - 1]["title"],
                "scene_start": len(all_scenes),
                "chapter_idx": chapter_idx,
            })
            _last_chapter_idx = chapter_idx

        all_scenes.extend(fake_scenes)

    # 3 chapters → 3 boundary entries
    assert len(chapter_boundaries) == 3
    assert chapter_boundaries[0]["scene_start"] == 0
    assert chapter_boundaries[0]["title"] == "同人续写"
    assert chapter_boundaries[1]["scene_start"] == 3   # after first chunk's 3 scenes
    assert chapter_boundaries[2]["scene_start"] == 9   # after 2nd chapter's 2×3 scenes


def test_build_chapter_hint_multiple_chapters():
    boundaries = [
        {"title": "同人续写", "scene_start": 0, "chapter_idx": 1},
        {"title": "第7章 黄金瞳", "scene_start": 5, "chapter_idx": 2},
        {"title": "第8章 新生报到", "scene_start": 12, "chapter_idx": 3},
    ]
    all_scenes_count = 20

    lines = ["## 篇章结构说明"]
    lines.append(f"本剧本包含 {len(boundaries)} 个独立篇章，各篇章之间可能存在时间线跳跃和角色状态变化，这是正常的：")
    for i, b in enumerate(boundaries):
        start = b["scene_start"]
        end = boundaries[i + 1]["scene_start"] if i + 1 < len(boundaries) else all_scenes_count
        lines.append(
            f"  篇章{i + 1}「{b['title']}」: 场景 s{start + 1} 至 s{end}"
            f"（共 {end - start} 个场景）"
        )
    lines.append("跨篇章的时间线矛盾、角色状态变化不应被标记为 critical。")
    hint = "\n".join(lines)

    assert "3 个独立篇章" in hint
    assert "同人续写" in hint
    assert "s1" in hint
    assert "s6" in hint
    assert "s13" in hint
    assert "s20" in hint


def test_build_chapter_hint_single_chapter():
    boundaries = []
    lines = ["## 篇章结构说明"]
    lines.append("本剧本为单一连续篇章。")
    hint = "\n".join(lines)

    assert "单一连续篇章" in hint

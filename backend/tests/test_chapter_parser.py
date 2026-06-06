"""ChapterParser 单元测试 — 章节边界检测与提取"""

import pytest
from agents.chapter_parser import ChapterParser


def test_parse_chinese_markdown_chapters():
    text = """## 第一章：相遇
竹林晨雾弥漫。林墨蹲在花圃边。

## 第二章：对峙
赵建国走进了花园，手里拿着信封。

## 第三章：秘密
小禾发现了一本旧日记，翻开第一页。"""
    parser = ChapterParser()
    result = parser.parse(text)
    assert len(result) == 3
    assert result[0]["title"] == "第一章：相遇"
    assert result[0]["index"] == 1
    assert result[1]["index"] == 2


def test_parse_pure_chinese_numbers():
    text = """第一章 开始
这里是一些内容。

第二章 中间
更多内容。

第三章 结尾
最后的内容。"""
    parser = ChapterParser()
    result = parser.parse(text)
    assert len(result) == 3


def test_parse_english_chapters():
    text = """Chapter 1: The Meeting
Morning fog settled over the bamboo grove.

Chapter 2: The Confrontation
The door swung open with a creak.

Chapter 3: The Secret
She found the diary beneath the floorboards."""
    parser = ChapterParser()
    result = parser.parse(text)
    assert len(result) == 3
    assert result[0]["index"] == 1


def test_empty_text():
    parser = ChapterParser()
    result = parser.parse("")
    assert result == []


def test_single_block_no_chapter_markers():
    text = "只有一段文字，没有任何章节标记。"
    parser = ChapterParser()
    result = parser.parse(text)
    assert len(result) == 1
    assert result[0]["index"] == 1


def test_chapter_has_summary():
    text = "## 第一章\n" + "长" * 500
    parser = ChapterParser()
    result = parser.parse(text)
    assert "summary" in result[0]
    assert len(result[0]["summary"]) > 0


def test_chapter_has_char_count():
    text = "## 第一章\n" + "长" * 1000
    parser = ChapterParser()
    result = parser.parse(text)
    assert result[0]["char_count"] >= 1000


def test_chapter_has_full_text():
    body = "这是一段测试内容。\n包含两行。"
    text = "## 第一章\n" + body
    parser = ChapterParser()
    result = parser.parse(text)
    assert body in result[0]["text"]


def test_parse_sample_novel(sample_novel_text):
    parser = ChapterParser()
    result = parser.parse(sample_novel_text)
    assert len(result) == 3
    assert "相遇" in result[0]["title"]
    assert "对峙" in result[1]["title"]
    assert "秘密" in result[2]["title"]

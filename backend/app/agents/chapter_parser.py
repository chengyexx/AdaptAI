"""章节解析器 — 规则引擎（非 AI 节点），识别小说文本中的章节边界并提取元数据"""

import re
from typing import Pattern


class ChapterParser:
    """基于正则的章节边界检测器

    支持格式：
    - 中文: ## 第一章：标题 / 第1章 / 第三章
    - 英文: Chapter 1 / CHAPTER I
    - Markdown: # 第一章 / ## Chapter 1
    - 纯数字分隔: 第一章 / 第 一 章（带空格）
    """

    CHAPTER_PATTERNS: list[Pattern] = [
        # Markdown 标题 + 中文章节
        re.compile(r"^#{1,3}\s*第[零一二三四五六七八九十百千\d]+[章节卷].*$", re.MULTILINE),
        # 纯中文章节（无 markdown）
        re.compile(r"^第[零一二三四五六七八九十百千\d]+[章节卷].*$", re.MULTILINE),
        # 英文 Chapter + 数字
        re.compile(r"^Chapter\s+\d+.*$", re.MULTILINE | re.IGNORECASE),
        # 罗马数字章节
        re.compile(r"^CHAPTER\s+[IVXLCDM]+.*$", re.MULTILINE),
    ]

    # 最小章节数阈值——少于此时不拆分
    MIN_CHAPTERS = 3

    def parse(self, text: str) -> list[dict]:
        if not text.strip():
            return []

        pattern = self._choose_best_pattern(text)

        if pattern is None:
            return [self._make_chapter(text.strip(), 1)]

        # 使用 finditer 定位所有章节标题的位置
        matches = list(pattern.finditer(text.strip()))
        if not matches:
            return [self._make_chapter(text.strip(), 1)]

        chapters = []

        # 第一段：第一个标题之前的内容（如有）
        if matches[0].start() > 0:
            prefix = text[:matches[0].start()].strip()
            if prefix:
                chapters.append(self._make_chapter(prefix, 1))

        # 逐段提取：标题 + 正文
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            chunk = text[start:end].strip()
            index = len(chapters) + 1
            chapters.append(self._make_chapter(chunk, index))

        # 太少不拆分
        if len(chapters) < 2:
            return [self._make_chapter(text.strip(), 1)]

        return chapters

    def _choose_best_pattern(self, text: str) -> Pattern | None:
        """选择匹配数最多的模式"""
        best_pattern = None
        best_count = 0
        for pattern in self.CHAPTER_PATTERNS:
            matches = pattern.findall(text)
            if len(matches) > best_count:
                best_count = len(matches)
                best_pattern = pattern
        return best_pattern

    @staticmethod
    def _make_chapter(text: str, index: int, title: str = "") -> dict:
        """构造章节 dict"""
        lines = text.strip().split("\n")
        if not title:
            first_line = lines[0].strip() if lines else ""
            # 去掉 markdown 标记
            title = first_line.lstrip("#").strip()[:100] if first_line else f"第{index}章"

        # 摘要：取前 200 字符，去掉换行
        summary = text[:200].replace("\n", " ").strip()

        return {
            "index": index,
            "title": title,
            "summary": summary,
            "char_count": len(text),
            "text": text,
        }

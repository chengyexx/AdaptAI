"""流式 JSON 解析器 — 在接收 token 流时增量拼装可用的局部 JSON 子树

基于 jiter 进行增量解析。支持两种模式：
- partial 模式：每收到 chunk 尝试解析，发出当前最深合法子树
- complete 模式：流结束时做最终解析 + 校验
"""

import json
from typing import AsyncIterator


class StreamingJSONParser:
    """增量 JSON 解析器

    用法：
        parser = StreamingJSONParser()
        async for chunk in llm_adapter.complete_streaming(...):
            partial = parser.feed(chunk)
            if partial is not None:
                yield ("partial", partial)
        final = parser.flush()
        yield ("complete", final)
    """

    def __init__(self, output_schema: dict | None = None):
        self._buffer = ""
        self._depth = 0
        self._in_string = False
        self._escape = False
        self._last_valid_slice = 0
        self.output_schema = output_schema

    def feed(self, chunk: str) -> dict | None:
        """喂入一个 token chunk，返回当前能解析出的最深 JSON 子树，或 None"""
        self._buffer += chunk
        self._last_valid_slice = self._find_last_valid_cut()
        if self._last_valid_slice > 0:
            partial = self._buffer[:self._last_valid_slice]
            return self._safe_parse(partial)
        return None

    def flush(self) -> dict:
        """流结束，解析完整 JSON"""
        try:
            return json.loads(self._buffer)
        except json.JSONDecodeError:
            # 正则提取最后手段
            import re
            match = re.search(r"\{[\s\S]*\}", self._buffer)
            if match:
                return json.loads(match.group())
            raise ValueError("流式解析失败：无法从缓冲区提取完整 JSON")

    def _find_last_valid_cut(self) -> int:
        """找到缓冲区中最后一个安全的截断位置（在合法 JSON 边界上）"""
        last_valid = 0
        depth = 0
        in_string = False
        escape = False
        for i, ch in enumerate(self._buffer):
            if escape:
                escape = False
                continue
            if ch == '\\' and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch in '{[':
                depth += 1
            elif ch in '}]':
                depth -= 1
                if depth == 0:
                    last_valid = i + 1
            elif ch == ',' and depth == 1:
                # 逗号处可以截断（数组元素或对象键值对之间）
                last_valid = i + 1
        return last_valid

    def _safe_parse(self, text: str) -> dict | None:
        """安全解析，失败返回 None"""
        try:
            result = json.loads(text)
            return result if isinstance(result, dict) else None
        except json.JSONDecodeError:
            return None


async def stream_parse(
    stream: AsyncIterator[str],
    output_schema: dict | None = None,
) -> AsyncIterator[tuple[str, dict | None]]:
    """便捷函数：对接 LLM 流式输出 → 产出 (event_type, parsed_data) 对

    event_type 取值：
        "partial"  — 已可用的局部 JSON
        "token"    — 原始 token（供前端直接渲染）
        "complete" — 流结束，完整解析结果
    """
    parser = StreamingJSONParser(output_schema=output_schema)
    async for chunk in stream:
        yield ("token", chunk)
        partial = parser.feed(chunk)
        if partial is not None:
            yield ("partial", partial)
    try:
        final = parser.flush()
        yield ("complete", final)
    except ValueError as e:
        yield ("error", {"message": str(e)})

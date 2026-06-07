"""StreamingJSONParser 单元测试 — 增量 JSON 解析与边界处理"""

import pytest
from llm.streaming_parser import StreamingJSONParser, stream_parse


class MockStream:
    """模拟 LLM 流式输出"""
    def __init__(self, chunks: list[str]):
        self.chunks = chunks

    def __aiter__(self):
        self._iter = iter(self.chunks)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


# ── 基本解析 ──

def test_feed_single_complete_json():
    parser = StreamingJSONParser()
    result = parser.feed('{"key": "value"}')
    assert result == {"key": "value"}


def test_feed_partial_then_complete():
    parser = StreamingJSONParser()
    r1 = parser.feed('{"key": ')
    assert r1 is None  # 不完整，无法解析

    r2 = parser.feed('"value"}')
    assert r2 is not None


def test_flush_complete():
    parser = StreamingJSONParser()
    parser.feed('{"a": 1, ')
    parser.feed('"b": 2}')
    result = parser.flush()
    assert result == {"a": 1, "b": 2}


# ── 数组中的逗号截断 ──

def test_comma_in_array_is_cut_point():
    parser = StreamingJSONParser()
    r = parser.feed('{"items": [{"id": 1}, {"id": 2}]}')
    assert r is not None


# ── 嵌套对象 ──

def test_nested_object_partial():
    parser = StreamingJSONParser()
    r = parser.feed('{"outer": {"inner": "value"}}')
    assert r == {"outer": {"inner": "value"}}


def test_nested_deep_partial_cut():
    parser = StreamingJSONParser()
    r = parser.feed('{"data": {"items": [{"n": 1}')
    assert r is None  # 深度不为0，不能截断


# ── 字符串中包含特殊字符 ──

def test_string_with_braces():
    parser = StreamingJSONParser()
    r = parser.feed('{"text": "hello { world }"}')
    assert r == {"text": "hello { world }"}


def test_string_with_escaped_quotes():
    parser = StreamingJSONParser()
    r = parser.feed('{"msg": "she said \\"hi\\""}')
    assert r == {"msg": 'she said "hi"'}


# ── 流式便捷函数 ──

@pytest.mark.asyncio
async def test_stream_parse_partial_events():
    stream = MockStream(['{"characters": [', '{"name": "John"}', "]}"])
    events = []
    async for evt_type, data in stream_parse(stream):
        events.append((evt_type, data is not None))

    event_types = [e[0] for e in events]
    assert "token" in event_types      # 有原始 token 事件
    assert "complete" in event_types   # 有完成事件


# ── 错误处理 ──

def test_flush_invalid_json_raises():
    parser = StreamingJSONParser()
    parser.feed("not json at all")
    with pytest.raises(ValueError, match="流式解析失败"):
        parser.flush()


def test_empty_buffer_returns_none():
    parser = StreamingJSONParser()
    assert parser.feed("") is None

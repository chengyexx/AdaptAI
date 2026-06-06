"""LLM Adapter 层单元测试"""

import pytest
from llm.adapter import LLMAdapter, LLMResponse
from llm.factory import AdapterFactory


# ── Mock Adapter 用于协议符合性测试 ──

class DummyAdapter:
    model_name = "dummy"
    context_window = 4096

    async def complete(self, prompt, system_prompt="", output_schema=None, temperature=0.7):
        return LLMResponse(text='{"key": "value"}', model="dummy", parsed_output={"key": "value"})

    async def complete_streaming(self, prompt, system_prompt="", output_schema=None, temperature=0.7):
        yield '{"key": '
        yield '"value"}'

    def token_count(self, text):
        return len(text) // 4


# ── 协议兼容性测试 ──

def test_dummy_adapter_satisfies_protocol():
    """任何实现了 LLMAdapter 协议的类都应该通过 isinstance 检查"""
    adapter = DummyAdapter()
    assert isinstance(adapter, LLMAdapter)


@pytest.mark.asyncio
async def test_dummy_adapter_complete():
    """非流式 complete 返回 LLMResponse"""
    adapter = DummyAdapter()
    response = await adapter.complete("test prompt")
    assert response.text == '{"key": "value"}'
    assert response.parsed_output == {"key": "value"}
    assert response.model == "dummy"


@pytest.mark.asyncio
async def test_dummy_adapter_streaming():
    """流式 complete_streaming 逐个产出 chunk"""
    adapter = DummyAdapter()
    chunks = []
    async for chunk in adapter.complete_streaming("test prompt"):
        chunks.append(chunk)
    assert len(chunks) == 2
    assert "".join(chunks) == '{"key": "value"}'


# ── AdapterFactory 测试 ──

def test_factory_registry():
    """注册后的 Provider 应该在工厂中可查"""
    assert "claude" in AdapterFactory._registry
    assert "deepseek" in AdapterFactory._registry
    assert AdapterFactory._registry["claude"].__name__ == "ClaudeAdapter"
    assert AdapterFactory._registry["deepseek"].__name__ == "DeepSeekAdapter"


def test_factory_create_claude():
    """通过 factory.create 创建 ClaudeAdapter 实例"""
    adapter = AdapterFactory.create("claude", api_key="test-key", model="claude-sonnet-4-6")
    assert adapter.model_name == "claude-sonnet-4-6"
    assert adapter.api_key == "test-key"
    assert adapter.context_window == 200000


def test_factory_create_deepseek():
    """通过 factory.create 创建 DeepSeekAdapter 实例"""
    adapter = AdapterFactory.create("deepseek", api_key="sk-test", model="deepseek-v4-pro")
    assert adapter.model_name == "deepseek-v4-pro"
    assert adapter.api_key == "sk-test"
    assert adapter.context_window == 1_000_000


def test_factory_unknown_provider_raises():
    """未注册的 Provider 应抛出 ValueError 并给出提示"""
    with pytest.raises(ValueError, match="未知的 LLM Provider"):
        AdapterFactory.create("unknown", "key", "model")


def test_empty_api_key_raises():
    """空 API key 应抛出错误"""
    with pytest.raises(ValueError, match="API key 不能为空"):
        AdapterFactory.create("claude", api_key="", model="claude-sonnet-4-6")
    with pytest.raises(ValueError, match="API key 不能为空"):
        AdapterFactory.create("deepseek", api_key="", model="deepseek-v4-pro")


# ── LLMResponse 数据类测试 ──

def test_llm_response_defaults():
    """LLMResponse 的默认值应合理"""
    resp = LLMResponse(text="hello", model="test")
    assert resp.token_usage == {}
    assert resp.parsed_output is None


def test_llm_response_with_usage():
    """带 token 用量的响应"""
    resp = LLMResponse(text="hi", model="test", token_usage={"input": 10, "output": 5})
    assert resp.token_usage["input"] == 10
    assert resp.token_usage["output"] == 5


# ── Token 计数测试 ──

def test_token_count():
    """各 Adapter 应提供 token 估算方法"""
    from llm.claude_adapter import ClaudeAdapter
    from llm.deepseek_adapter import DeepSeekAdapter

    claude = ClaudeAdapter(api_key="test", model="test")
    deepseek = DeepSeekAdapter(api_key="test", model="test")

    text = "Hello World" * 100
    assert claude.token_count(text) > 0
    assert deepseek.token_count(text) > 0

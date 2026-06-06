"""BaseAgent — AI Agent 抽象基类，定义置信度计算与重试机制"""

import json
import re
from dataclasses import dataclass, field
from abc import ABC, abstractmethod


@dataclass
class AgentResult:
    """Agent 执行结果 — 所有 Agent 的统一返回契约"""
    agent_id: str
    success: bool
    output: dict                              # 结构化输出
    confidence: float                         # 0.0 ~ 1.0
    token_usage: int = 0
    raw_response_ptr: str | None = None       # 原始响应的文件指针（非内联文本）
    retries_used: int = 0
    warnings: list[str] = field(default_factory=list)


class BaseAgent(ABC):
    """所有 AI Agent 的抽象基类"""

    agent_id: str = "base"
    confidence_threshold: float = 0.7
    max_retries: int = 3

    @abstractmethod
    async def run(self, state: dict, llm_adapter) -> AgentResult:
        """执行 Agent，返回 AgentResult"""
        ...

    @abstractmethod
    def build_prompt(self, state: dict) -> tuple[str, str]:
        """根据 State 构建 (system_prompt, user_prompt)"""
        ...

    def validate_output(self, raw: dict, state: dict) -> tuple[bool, list[str]]:
        """校验输出是否合法，返回 (是否通过, 错误列表)"""
        return True, []

    def compute_confidence(
        self,
        output: dict,
        state: dict,
        schema_compliance: float,
        self_assessment: float,
        cross_consistency: float,
    ) -> float:
        """三维复合置信度计算（详见设计文档 §5.3）

        schema_compliance: 输出是否符合 output_schema    (权重 0.3)
        self_assessment:   LLM 自评分数 (1-10 → 0-1)     (权重 0.4)
        cross_consistency: 交叉引用验证分数                (权重 0.3)
        """
        return round(
            schema_compliance * 0.3 +
            self_assessment * 0.4 +
            cross_consistency * 0.3,
            2,
        )

    def _extract_json(self, text: str) -> dict:
        """从 LLM 响应文本中提取 JSON 对象"""
        # 优先尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # 正则提取 {...}
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group())
        raise ValueError("无法从 LLM 响应中提取 JSON")

    def _check_schema(self, output: dict, required_fields: list[str]) -> float:
        """计算 Schema 合规度"""
        missing = [f for f in required_fields if f not in output]
        if not missing:
            return 1.0
        return max(0.0, 1.0 - len(missing) / len(required_fields))

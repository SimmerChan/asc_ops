# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
LLM Response Types

统一响应格式
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMUsage:
    """Token 使用量"""
    input_tokens: int
    output_tokens: int
    total_tokens: int

    @classmethod
    def from_dict(cls, data: dict, provider: str) -> "LLMUsage":
        """从不同 provider 的 usage 格式解析"""
        if provider == "anthropic":
            return cls(
                input_tokens=data.get("input_tokens", 0),
                output_tokens=data.get("output_tokens", 0),
                total_tokens=data.get("input_tokens", 0) + data.get("output_tokens", 0),
            )
        elif provider in ("openai", "zhipu", "minimax"):
            return cls(
                input_tokens=data.get("prompt_tokens", 0),
                output_tokens=data.get("completion_tokens", 0),
                total_tokens=data.get("total_tokens", 0),
            )
        else:
            return cls(
                input_tokens=data.get("prompt_tokens", 0),
                output_tokens=data.get("completion_tokens", 0),
                total_tokens=data.get("total_tokens", 0),
            )


@dataclass
class LLMResponse:
    """统一 LLM 响应格式"""
    content: str  # 解析后的文本内容
    model: str  # 实际使用的模型
    provider: str  # provider 名称
    usage: Optional[LLMUsage] = None  # token 使用量
    raw_response: dict = field(default_factory=dict)  # 原始响应

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "model": self.model,
            "provider": self.provider,
            "usage": {
                "input_tokens": self.usage.input_tokens if self.usage else 0,
                "output_tokens": self.usage.output_tokens if self.usage else 0,
                "total_tokens": self.usage.total_tokens if self.usage else 0,
            } if self.usage else None,
        }

# Copyright 2026 SimmerChan
# Apache 2.0 License

"""
LLM Message Types

统一消息格式，内部使用 Anthropic 兼容格式
"""

from dataclasses import dataclass, field
from typing import List, Optional, Literal
from enum import Enum


class MessageRole(Enum):
    """消息角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """统一消息格式"""
    role: MessageRole
    content: str

    def to_dict(self) -> dict:
        return {
            "role": self.role.value,
            "content": self.content,
        }


@dataclass
class ClaudeMessage:
    """
    Anthropic 格式消息

    Anthropic 只支持 user 和 assistant 两种角色
    system 消息通过单独的 system 参数传递
    """
    role: Literal["user", "assistant"]
    content: str

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
        }


@dataclass
class ClaudeRequest:
    """
    Anthropic 格式请求

    作为内部标准格式，各 Provider 需要适配到此格式
    """
    model: str
    messages: List[ClaudeMessage]
    max_tokens: int
    system: Optional[str] = None
    stream: bool = False
    temperature: Optional[float] = None
    top_p: Optional[float] = None

    def to_dict(self) -> dict:
        result = {
            "model": self.model,
            "messages": [msg.to_dict() for msg in self.messages],
            "max_tokens": self.max_tokens,
            "stream": self.stream,
        }
        if self.system:
            result["system"] = self.system
        if self.temperature is not None:
            result["temperature"] = self.temperature
        if self.top_p is not None:
            result["top_p"] = self.top_p
        return result


def messages_to_claude_format(
    messages: List[Message],
    system_message: Optional[str] = None,
) -> ClaudeRequest:
    """
    将统一 Message 列表转换为 Anthropic 格式

    Args:
        messages: 统一格式消息列表
        system_message: 独立的 system 消息（如有）

    Returns:
        ClaudeRequest: Anthropic 格式请求
    """
    claude_messages = []
    system = system_message or ""

    for msg in messages:
        if msg.role == MessageRole.SYSTEM:
            # 使用独立的 system 参数
            system = msg.content
        elif msg.role == MessageRole.USER:
            claude_messages.append(ClaudeMessage(role="user", content=msg.content))
        elif msg.role == MessageRole.ASSISTANT:
            claude_messages.append(ClaudeMessage(role="assistant", content=msg.content))

    return claude_messages

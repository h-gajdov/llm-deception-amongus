from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class LLMResponse:
    content: str
    thinking: str = ""

    def combined(self) -> str:
        if self.thinking:
            return f"<think>{self.thinking}</think>\n{self.content}"
        return self.content


@runtime_checkable
class LLMClient(Protocol):
    model: str
    pass

    def chat(self, system: str, user: str) -> LLMResponse: ...


__all__ = ["LLMClient", "LLMResponse"]

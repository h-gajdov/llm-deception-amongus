

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class LLMResponse:
    pass

    content: str
    thinking: str = ""

    def combined(self) -> str:
        pass
        if self.thinking:
            return f"<think>{self.thinking}</think>\n{self.content}"
        return self.content


@runtime_checkable
class LLMClient(Protocol):
    pass

    model: str
    pass

    def chat(self, system: str, user: str) -> LLMResponse:
        pass
        ...


__all__ = ["LLMClient", "LLMResponse"]

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict


LABEL_HONEST = 0
LABEL_DISHONEST = 1

LABEL_NAMES = {LABEL_HONEST: "honest", LABEL_DISHONEST: "dishonest"}


class Axis(str, Enum):
    LYING = "lying"
    DECEPTION = "deception"


class Source(str, Enum):
    TQA = "tqa"
    DQA = "dqa"
    REPENG = "repeng"


class ContrastiveExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source: Source
    axis: Axis
    system_prompt: str
    question: str
    answer: str
    label: int
    label_name: str
    category: str | None = None

    def render_plain(self) -> str:
        parts = []
        if self.system_prompt:
            parts.append(f"System: {self.system_prompt}")
        if self.question:
            parts.append(f"User: {self.question}")
        parts.append(f"Assistant: {self.answer}")
        return "\n".join(parts)

    def to_row(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source.value,
            "axis": self.axis.value,
            "system_prompt": self.system_prompt,
            "question": self.question,
            "answer": self.answer,
            "label": self.label,
            "label_name": self.label_name,
            "category": self.category,
            "text": self.render_plain(),
        }


__all__ = [
    "LABEL_DISHONEST",
    "LABEL_HONEST",
    "LABEL_NAMES",
    "Axis",
    "ContrastiveExample",
    "Source",
]

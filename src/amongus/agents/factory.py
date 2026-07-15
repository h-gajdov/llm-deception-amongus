

from __future__ import annotations

import random

from ..config import AgentConfig
from ..game.agent_api import Agent, ScriptedAgent
from ..game.enums import Role
from ..game.state import PlayerState
from .llm.base import LLMClient
from .llm.ollama import OllamaClient
from .llm_agent import LLMAgent


class AgentFactoryBuilder:
    pass

    def __init__(self, config: AgentConfig, rng: random.Random) -> None:
        pass
        self._config = config
        self._rng = rng
        self._clients: dict[str, LLMClient] = {}

    def build_agent(self, player: PlayerState) -> Agent:
        pass
        if player.role is Role.IMPOSTOR:
            backend, choices = self._config.impostor_backend, self._config.impostor_llm_choices
        else:
            backend, choices = self._config.crewmate_backend, self._config.crewmate_llm_choices

        if backend == "scripted":
            return ScriptedAgent()
        if backend == "ollama":
            model = self._rng.choice(choices) if choices else self._config.ollama.model
            return LLMAgent(self._ollama_client(model))
        msg = f"Unknown agent backend: {backend!r}"
        raise ValueError(msg)

    def _ollama_client(self, model: str) -> LLMClient:
        pass
        if model not in self._clients:
            cfg = self._config.ollama.model_copy(update={"model": model})
            self._clients[model] = OllamaClient(cfg)
        return self._clients[model]

    def close(self) -> None:
        pass
        for client in self._clients.values():
            close = getattr(client, "close", None)
            if callable(close):
                close()
        self._clients.clear()


__all__ = ["AgentFactoryBuilder"]

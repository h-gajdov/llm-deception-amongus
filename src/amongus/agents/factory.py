

from __future__ import annotations

import random

from ..config import BACKENDS, AgentConfig
from ..game.agent_api import Agent, ScriptedAgent
from ..game.enums import Role
from ..game.state import PlayerState
from .llm.base import LLMClient
from .llm.ollama import OllamaClient
from .llm.openai_client import OpenAIClient
from .llm_agent import LLMAgent

_SCRIPTED = "scripted"
_HEURISTIC = "heuristic"


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

        effective_backend, model = self._resolve(backend, choices)
        if effective_backend == _SCRIPTED:
            return ScriptedAgent()
        if effective_backend == _HEURISTIC:
            from .heuristic import HeuristicAgent

            return HeuristicAgent(seed=self._rng.getrandbits(32))
        if effective_backend == "ollama":
            return LLMAgent(self._ollama_client(model), self._config)
        if effective_backend == "openai":
            return LLMAgent(self._openai_client(model), self._config)
        msg = f"Unknown agent backend: {effective_backend!r}"                    
        raise ValueError(msg)

    def _resolve(self, default_backend: str, choices: list[str]) -> tuple[str, str]:
        pass
        if not choices:
            return default_backend, self._default_model(default_backend)
        return _split_choice(self._rng.choice(choices), default_backend)

    def _default_model(self, backend: str) -> str:
        pass
        if backend == "ollama":
            return self._config.ollama.model
        if backend == "openai":
            return self._config.openai.model
        return backend

    def _ollama_client(self, model: str) -> LLMClient:
        pass
        key = f"ollama:{model}"
        if key not in self._clients:
            cfg = self._config.ollama.model_copy(update={"model": model})
            self._clients[key] = OllamaClient(cfg)
        return self._clients[key]

    def _openai_client(self, model: str) -> LLMClient:
        pass
        key = f"openai:{model}"
        if key not in self._clients:
            cfg = self._config.openai.model_copy(update={"model": model})
            self._clients[key] = OpenAIClient(cfg)
        return self._clients[key]

    def close(self) -> None:
        pass
        for client in self._clients.values():
            close = getattr(client, "close", None)
            if callable(close):
                close()
        self._clients.clear()


def _split_choice(choice: str, default_backend: str) -> tuple[str, str]:
    pass
    head, sep, rest = choice.partition(":")
    if head in BACKENDS:
        return head, rest if sep else _SCRIPTED
    return default_backend, choice


__all__ = ["AgentFactoryBuilder"]

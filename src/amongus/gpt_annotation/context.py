

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..data.ingest import iter_games, iter_turns
from ..data.schema_v2 import EVENTS_FILE, METADATA_FILE, WORLD_STATES_FILE, TurnRecordModel

                                                                            
                                                         
WORLD_STATE_HISTORY_LOOKBACK = 3


class DatasetContext:
    pass

    def __init__(self, dataset_dir: str | Path) -> None:
        pass
        self.dataset_dir = Path(dataset_dir)
        self.turns: list[TurnRecordModel] = list(iter_turns(self.dataset_dir))
        self.events_by_game = _load_events(self.dataset_dir)
        self.world_states_by_game = _load_world_states(self.dataset_dir)
        self.roster_by_game = {
            game.game_id: _roster(game.players) for game in iter_games(self.dataset_dir)
        }
        self.metadata = _load_metadata(self.dataset_dir)


def build_turn_context(turn: TurnRecordModel, ctx: DatasetContext) -> dict[str, Any]:
    pass
    game_events = ctx.events_by_game.get(turn.game_id, [])
    seq_after = _event_seq_after(turn)
    objective_events = [e for e in game_events if int(e.get("seq", -1)) < seq_after]

    snapshots = ctx.world_states_by_game.get(turn.game_id, [])
    world_before = _snapshot_at(snapshots, turn.world_state_before_ref)
    world_after = _snapshot_at(snapshots, turn.world_state_after_ref)
    history = _recent_history(snapshots, turn.world_state_before_ref)

    private = turn.private_state if isinstance(turn.private_state, dict) else {}
    model_output = turn.model_output
    actor = turn.actor

    return {
        "game_id": turn.game_id,
        "turn_id": turn.turn_id,
        "timestep": turn.timestep,
        "phase": turn.phase,
        "actor": {
            "player_id": actor.player_id,
            "role": actor.role,
            "personality": actor.personality,
            "location": _actor_location(private, actor.player_id),
        },
        "available_actions": list(turn.model_input.available_actions),
        "requested_action": {
            "text": model_output.requested_action_text,
            "action": model_output.requested_action,
            "was_available": model_output.requested_action_valid,
        },
        "executed_action": model_output.action,
        "action_execution": {
            "source": model_output.execution_source,
            "fallback_reason": model_output.fallback_reason,
        },
        "raw_model_response": model_output.raw,
        "condensed_memory": model_output.generated_condensed_memory,
        "thinking_process": model_output.generated_rationale,
        "public_utterance": model_output.speech,
        "declared_speech_intent": model_output.declared_speech,
        "perceptions_before_turn": {
            "direct_observations": private.get("direct_observations", []),
            "heard_statements": private.get("heard_statements", []),
            "public_facts": private.get("public_facts", []),
            "structured_memory": private.get("structured_memory", {}),
        },
        "objective_events": objective_events,
        "world_state_before": world_before,
        "world_state_after": world_after,
        "world_state_recent_history": history,
        "player_roster": ctx.roster_by_game.get(turn.game_id, []),
    }


def _event_seq_after(turn: TurnRecordModel) -> int:
    pass
    evaluation = turn.evaluation if isinstance(turn.evaluation, dict) else {}
    value = evaluation.get("event_seq_after")
    if isinstance(value, int):
        return value
    msg = (
        f"Turn {turn.turn_id} has no evaluation.event_seq_after; refusing to guess a bound "
        "on objective_events (would risk leaking later events into this turn's context)."
    )
    raise ValueError(msg)


def _snapshot_at(snapshots: list[dict[str, Any]], ref: int) -> dict[str, Any] | None:
    pass
    if ref is None or ref < 0:
        return None
    return next((s for s in snapshots if s.get("index") == ref), None)


def _recent_history(snapshots: list[dict[str, Any]], before_ref: int) -> list[dict[str, Any]]:
    pass
    if before_ref is None or before_ref < 0:
        return []
    prior = [s for s in snapshots if isinstance(s.get("index"), int) and s["index"] < before_ref]
    prior = prior[-WORLD_STATE_HISTORY_LOOKBACK:]
    return [
        {
            "index": s.get("index"),
            "timestep": s.get("timestep"),
            "phase": s.get("phase"),
            "dead_bodies": s.get("dead_bodies"),
            "buttons_used": s.get("buttons_used"),
        }
        for s in prior
    ]


def _actor_location(private: dict[str, Any], actor_name: str) -> str:
    pass
    memory = private.get("structured_memory")
    if isinstance(memory, dict):
        locations = memory.get("last_known_locations")
        if isinstance(locations, dict):
            belief = locations.get(actor_name)
            if isinstance(belief, dict):
                return str(belief.get("room", ""))
    return ""


def _roster(players: list[dict[str, Any]]) -> list[dict[str, str]]:
    pass
    roster = []
    for player in players:
        name = player.get("name")
        if not name:
            continue
        roster.append({"player_id": str(name), "color": str(player.get("color") or "")})
    return roster


def _load_events(dataset_dir: Path) -> dict[str, list[dict[str, Any]]]:
    pass
    path = dataset_dir / EVENTS_FILE
    if not path.exists():
        msg = f"{EVENTS_FILE} not found under {dataset_dir}; required input for GPT annotation."
        raise FileNotFoundError(msg)
    events: dict[str, list[dict[str, Any]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        obj = json.loads(stripped)
        events[str(obj["game_id"])] = list(obj.get("events", []))
    return events


def _load_world_states(dataset_dir: Path) -> dict[str, list[dict[str, Any]]]:
    pass
    path = dataset_dir / WORLD_STATES_FILE
    if not path.exists():
        msg = (
            f"{WORLD_STATES_FILE} not found under {dataset_dir}; required input for GPT annotation."
        )
        raise FileNotFoundError(msg)
    by_game: dict[str, list[dict[str, Any]]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        snapshot = json.loads(stripped)
        by_game.setdefault(str(snapshot.get("game_id")), []).append(snapshot)
    for snapshots in by_game.values():
        snapshots.sort(key=lambda s: s.get("index", 0))
    return by_game


def _load_metadata(dataset_dir: Path) -> dict[str, Any]:
    pass
    path = dataset_dir / METADATA_FILE
    if not path.exists():
        msg = f"{METADATA_FILE} not found under {dataset_dir}; required input for GPT annotation."
        raise FileNotFoundError(msg)
    return json.loads(path.read_text(encoding="utf-8"))


__all__ = ["WORLD_STATE_HISTORY_LOOKBACK", "DatasetContext", "build_turn_context"]

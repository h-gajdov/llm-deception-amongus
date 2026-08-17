from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..annotation.claims import Gazetteer, extract_claims
from ..annotation.grounding import annotate_utterance, build_context
from ..annotation.schema import (
    ClaimType,
    SpeechAct,
    StrategicIntent,
    StructuredSpeech,
    UtteranceAnnotation,
)
from ..config import SCHEMA_VERSION, AgentConfig, GameConfig
from ..logging import get_logger
from .actions import Action, available_actions
from .agent_api import Agent, Decision, DecisionContext
from .enums import PLAYER_COLORS, ActionType, Phase, Role, WinReason
from .events import EventLog, EventType, WorldEvent
from .game_map import GameMap, build_skeld
from .state import GameState, PlayerState
from .tasks import assign_crewmate_tasks, sample_common_tasks
from .validation import ActionRejection, safe_fallback, validate_action
from .view import LeakageViolation, PlayerView, build_player_view, check_view_leakage
from .visibility import camera_sightings, resolve_perceptions

logger = get_logger()

STARTING_ROOM = "Cafeteria"


AgentFactory = Callable[[PlayerState], Agent]


@dataclass
class TurnRecord:
    schema_version: str
    game_id: str
    turn_id: str
    step: int
    timestep: int
    phase: str
    timestamp: str
    actor: dict[str, object]
    world_state_before_ref: int
    world_state_after_ref: int
    private_state: dict[str, object]
    model_input: dict[str, object]
    model_output: dict[str, object]
    annotations: dict[str, object]
    evaluation: dict[str, object]
    probe_regions: dict[str, list[int]]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "game_id": self.game_id,
            "turn_id": self.turn_id,
            "step": self.step,
            "timestep": self.timestep,
            "phase": self.phase,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "world_state_before_ref": self.world_state_before_ref,
            "world_state_after_ref": self.world_state_after_ref,
            "private_state": self.private_state,
            "model_input": self.model_input,
            "model_output": self.model_output,
            "annotations": self.annotations,
            "evaluation": self.evaluation,
            "probe_regions": self.probe_regions,
        }


@dataclass
class GameResult:
    game_index: str
    config: GameConfig
    players: list[PlayerState]
    winner: int
    winner_reason: str
    turns: list[TurnRecord] = field(default_factory=list)
    world_states: list[dict[str, object]] = field(default_factory=list)
    events: list[dict[str, object]] = field(default_factory=list)
    generation_config: dict[str, object] = field(default_factory=dict)
    seed: int | None = None


class AmongUsGame:
    def __init__(
        self,
        game_index: str,
        config: GameConfig,
        agent_factory: AgentFactory,
        rng: random.Random,
        game_map: GameMap | None = None,
        agent_config: AgentConfig | None = None,
        generation_config: dict[str, object] | None = None,
        seed: int | None = None,
    ) -> None:
        self.config = config
        self.rng = rng
        self.game_map = game_map or build_skeld()
        self.agent_config = agent_config
        self.generation_config = generation_config or {}
        self.seed = seed
        self._agent_factory = agent_factory
        self.agents: dict[int, Agent] = {}
        self.events = EventLog()
        self.location_history: dict[str, list[tuple[int, str]]] = {}
        self.world_states: list[dict[str, object]] = []
        self._phase_start_timestep = 0
        self._turns: list[TurnRecord] = []
        self.state = self._init_state(game_index)
        self._gazetteer = Gazetteer.build(
            [p.name for p in self.state.players], list(self.game_map.rooms)
        )

    def _init_state(self, game_index: str) -> GameState:
        cfg = self.config
        colors = self.rng.sample(PLAYER_COLORS, cfg.num_players)
        impostor_indices = self._impostor_indices()
        common = sample_common_tasks(cfg.num_common_tasks, self.rng)
        personalities = self._personality_pool(cfg.num_players)

        players: list[PlayerState] = []
        for i in range(cfg.num_players):
            is_impostor = (i + 1) in impostor_indices
            role = Role.IMPOSTOR if is_impostor else Role.CREWMATE
            tasks = (
                list(common)
                if is_impostor
                else assign_crewmate_tasks(
                    common, cfg.num_short_tasks, cfg.num_long_tasks, self.rng
                )
            )
            player = PlayerState(
                index=i + 1,
                color=colors[i],
                role=role,
                model="unknown",
                location=STARTING_ROOM,
                tasks=tasks,
                personality=personalities[i],
                kill_cooldown_remaining=cfg.initial_kill_cooldown if is_impostor else 0,
            )
            agent = self._agent_factory(player)
            player.model = getattr(agent, "model_name", "unknown")
            self.agents[player.index] = agent
            players.append(player)

        state = GameState(
            game_index=game_index,
            players=players,
            discussion_rounds=cfg.discussion_rounds,
            max_num_buttons=cfg.max_num_buttons,
            max_timesteps=cfg.max_timesteps,
        )
        self._seed_private_state(state)
        self.events.append(
            timestep=0,
            phase=Phase.TASK,
            type=EventType.GAME_START,
            room=STARTING_ROOM,
            impostors=[p.name for p in players if p.is_impostor],
        )
        return state

    def _impostor_indices(self) -> set[int]:
        cfg = self.config
        if cfg.role_assignment == "fixed":
            return set(cfg.fixed_impostor_indices)
        return {i + 1 for i in self.rng.sample(range(cfg.num_players), cfg.num_impostors)}

    def _personality_pool(self, count: int) -> list[str | None]:
        agent_cfg = self.agent_config
        if agent_cfg is None or agent_cfg.personality_mode != "sampled":
            return [None] * count
        pool = agent_cfg.personalities
        return [self.rng.choice(pool) for _ in range(count)]

    def _seed_private_state(self, state: GameState) -> None:
        impostor_names = [p.name for p in state.players if p.is_impostor]
        for player in state.players:
            if player.is_impostor:
                player.private.teammate_names = list(impostor_names)
            player.private.memory.note_own_location(player.name, player.location, 0)
            self.location_history.setdefault(player.name, []).append((0, player.location))

    def run(self) -> GameResult:
        while not self.state.finished:
            if self.state.timestep >= self.config.max_timesteps:
                self._finish(1, WinReason.IMPOSTORS_TIME_UP)
                break
            self._run_task_timestep()
            if self.state.finished:
                break
            self.state.timestep += 1
        self.events.append(
            timestep=self.state.timestep,
            phase=self.state.phase,
            type=EventType.GAME_END,
            text=self.state.winner_reason,
            winner=self.state.winner,
        )
        return self._build_result()

    def _run_task_timestep(self) -> None:
        self._tick_cooldowns()
        for player in list(self.state.alive_players()):
            if not player.alive or self.state.finished:
                continue
            if self._take_turn(player):
                self._run_meeting()
                return
            if self._check_task_termination():
                return

    def _tick_cooldowns(self) -> None:
        for imp in self.state.alive_impostors():
            imp.kill_cooldown_remaining = max(0, imp.kill_cooldown_remaining - 1)

    def _take_turn(self, player: PlayerState) -> bool:
        if not player.alive:
            return False

        actions = available_actions(self.state, player, self.game_map)
        view = build_player_view(self.state, player, actions, self.game_map)
        leaks = check_view_leakage(view, self.state, player)
        if leaks:
            logger.error("Leakage in the view for {}: {}", player.name, [v.code for v in leaks])

        before_ref = self._snapshot()
        decision = self._decide(player, actions, view)
        action, rejection = self._enforce_legality(player, decision.action, actions)

        self._absorb_model_output(player, decision)
        annotation = self._annotate(player, action, decision)
        self._note_own_action(player, action, decision)
        triggered = self._apply_action(player, action, decision)
        after_ref = self._snapshot()

        self._record_turn(
            player=player,
            view=view,
            decision=decision,
            action=action,
            rejection=rejection,
            leaks=leaks,
            annotation=annotation,
            before_ref=before_ref,
            after_ref=after_ref,
        )
        return triggered

    def _decide(self, player: PlayerState, actions: list[Action], view: PlayerView) -> Decision:
        ctx = DecisionContext(self.state, player, actions, self.game_map, view)
        try:
            return self.agents[player.index].act(ctx)
        except Exception as exc:
            logger.warning(
                "Agent for {} raised {}; falling back to a safe action.", player.name, exc
            )
            from .agent_api import ScriptedAgent

            decision = ScriptedAgent().act(ctx)
            decision.parse_status = "fallback"
            decision.requested_action = None
            decision.requested_action_text = ""
            decision.requested_action_valid = False
            decision.execution_source = "fallback_safe_action"
            decision.fallback_reason = f"agent_error:{type(exc).__name__}"
            decision.validation_warnings.append(f"agent_error:{type(exc).__name__}")
            return decision

    def _enforce_legality(
        self, player: PlayerState, action: Action, actions: list[Action]
    ) -> tuple[Action, ActionRejection | None]:
        rejection = validate_action(self.state, player, action, self.game_map)
        if rejection is None:
            return action, None
        logger.debug("Rejected {} for {}: {}", action.render(), player.name, rejection.code)
        return safe_fallback(actions), rejection

    def _absorb_model_output(self, player: PlayerState, decision: Decision) -> None:
        private = player.private
        memory_text = decision.response.get("Condensed Memory", "").strip()
        rationale = decision.response.get("Thinking Process", "").strip()
        if memory_text:
            private.model_condensed_memory = memory_text
        if rationale:
            private.model_rationale = rationale

    def _note_own_action(self, player: PlayerState, action: Action, decision: Decision) -> None:
        label = "task phase" if self.state.phase is Phase.TASK else "meeting phase"
        rendered = action.render()
        if action.type is ActionType.SPEAK and decision.speech:
            rendered = f'SPEAK: "{decision.speech}"'
        player.private.memory.note_own_action(self.state.timestep, label, rendered)

    def _apply_action(self, player: PlayerState, action: Action, decision: Decision) -> bool:
        match action.type:
            case ActionType.MOVE:
                self._do_move(player, action)
            case ActionType.VENT:
                self._do_vent(player, action)
            case ActionType.COMPLETE_TASK | ActionType.FAKE_TASK:
                self._do_task(player, action)
            case ActionType.KILL:
                self._do_kill(player, action)
            case ActionType.CHECK_SECURITY:
                self._do_check_security(player)
            case ActionType.REPORT:
                return self._do_report(player)
            case ActionType.CALL_MEETING:
                return self._do_call_meeting(player)
            case ActionType.SPEAK:
                self._do_speak(player, decision)
            case ActionType.VOTE:
                self._do_vote(player, action)
            case ActionType.WAIT:
                self._emit(EventType.WAIT, actor=player.index, room=player.location)
        return False

    def _do_vote(self, player: PlayerState, action: Action) -> None:
        target = action.target_name or "Skip"
        player.current_vote = target
        self._emit(EventType.VOTE_CAST, actor=player.index, text=target, room=player.location)

    def _do_move(self, player: PlayerState, action: Action) -> None:
        source = player.location
        dest = action.target_room or source
        player.location = dest
        self._track_location(player)
        self._emit(EventType.MOVE, actor=player.index, room=source, to_room=dest)
        self._notice_bodies(player)

    def _do_vent(self, player: PlayerState, action: Action) -> None:
        source = player.location
        dest = action.target_room or source
        player.location = dest
        self._track_location(player)
        self._emit(EventType.VENT, actor=player.index, room=source, to_room=dest)
        self._notice_bodies(player)

    def _do_task(self, player: PlayerState, action: Action) -> None:
        if action.task is None:
            return
        index = player.tasks.index(action.task)
        if not player.is_impostor:
            player.completed_tasks.add(index)
        self._emit(
            EventType.TASK_COMPLETED if not player.is_impostor else EventType.TASK_FAKED,
            actor=player.index,
            room=player.location,
            task_name=action.task.name,
        )

    def _do_kill(self, player: PlayerState, action: Action) -> None:
        victim = self.state.player_by_name(action.target_name or "")
        if victim is None:
            return
        victim.alive = False
        player.kill_cooldown_remaining = self.config.kill_cooldown
        room = player.location
        self.state.dead_bodies.setdefault(room, []).append(victim.name)
        self._emit(
            EventType.KILL,
            actor=player.index,
            target=victim.index,
            room=room,
            victim_name=victim.name,
            killer_name=player.name,
        )
        logger.debug("{} killed {} in {}", player.name, victim.name, room)

    def _do_check_security(self, player: PlayerState) -> None:
        sightings = camera_sightings(self.state, self.config.visibility, player.index)
        self._emit(
            EventType.CAMERA_CHECK,
            actor=player.index,
            room=player.location,
            private_to=(player.index,),
            sightings=sightings,
        )

    def _do_report(self, player: PlayerState) -> bool:
        bodies = self.state.dead_bodies.get(player.location, [])
        if not bodies:
            return False
        victim_name = bodies[0]
        killer = self._killer_of(victim_name)
        self._emit(
            EventType.BODY_REPORTED,
            actor=player.index,
            room=player.location,
            victim_name=victim_name,
            killer_name=killer,
        )
        self.state.meeting_reason = f"{player.name} reported the body of {victim_name}"
        return True

    def _do_call_meeting(self, player: PlayerState) -> bool:
        self.state.buttons_used += 1
        self._emit(EventType.MEETING_CALLED, actor=player.index, room=player.location)
        self.state.meeting_reason = f"{player.name} called an emergency meeting"
        return True

    def _do_speak(self, player: PlayerState, decision: Decision) -> None:
        speech = (decision.speech or "").strip() or "(says nothing of note)"
        self.state.meeting_transcript.append(f"{player.name}: {speech}")
        self._emit(EventType.SPEECH, actor=player.index, room=player.location, text=speech)
        self._record_public_accusations(player, speech)

    def _record_public_accusations(self, speaker: PlayerState, speech: str) -> None:
        claims = extract_claims(speech, speaker.name, self._gazetteer)
        targets = {
            c.target
            for c in claims
            if c.claim_type in (ClaimType.ACCUSATION, ClaimType.VOTE_INTENT) and c.target
        }
        for target in targets:
            for listener in self.state.alive_players():
                listener.private.memory.note_accusation(speaker.name, target)

    def _run_meeting(self) -> None:
        self.state.phase = Phase.MEETING
        self.state.meeting_transcript = []
        self.state.meeting_round = 0
        self.state.meeting_number += 1
        self._teleport_all(STARTING_ROOM)
        self._emit(EventType.MEETING_STARTED, room=STARTING_ROOM, reason=self.state.meeting_reason)

        for round_idx in range(self.config.discussion_rounds):
            self.state.meeting_round = round_idx
            for player in self._speaking_order():
                if self.state.finished or not player.alive:
                    continue
                self._take_turn(player)

        self._run_vote()
        self._end_meeting()

    def _speaking_order(self) -> list[PlayerState]:
        alive = list(self.state.alive_players())
        order = self.config.meeting_order
        if order == "random":
            self.rng.shuffle(alive)
        elif order == "reporter_first":
            reason = self.state.meeting_reason or ""
            first = next((p for p in alive if reason.startswith(p.name)), None)
            if first is not None:
                alive.remove(first)
                alive.insert(0, first)
        return alive

    def _run_vote(self) -> None:
        self.state.meeting_round = self.config.discussion_rounds
        tally: Counter[str] = Counter()
        for player in self._speaking_order():
            if not player.alive:
                continue
            self._take_turn(player)
            target = player.current_vote or "Skip"
            tally[target] += 1
        self._resolve_vote(tally)

    def _resolve_vote(self, tally: Counter[str]) -> None:
        summary = ", ".join(f"{name}: {votes}" for name, votes in sorted(tally.items()))
        self._emit(EventType.VOTE_RESULT, text=summary or "no votes cast", tally=dict(tally))
        if not tally:
            return
        top, top_votes = tally.most_common(1)[0]
        tied = [name for name, votes in tally.items() if votes == top_votes]
        ejected = None if (len(tied) != 1 or top == "Skip") else self.state.player_by_name(top)
        if ejected is not None:
            ejected.alive = False
            ejected.ejected = True
            logger.debug("{} was ejected (votes={})", ejected.name, top_votes)
        self._emit(
            EventType.EJECTION,
            target=ejected.index if ejected else None,
            role=ejected.role.value if ejected else None,
        )

    def _end_meeting(self) -> None:
        self.state.dead_bodies.clear()
        self.state.meeting_reason = None
        for player in self.state.players:
            player.current_vote = None
        for imp in self.state.alive_impostors():
            imp.kill_cooldown_remaining = self.config.kill_cooldown
        self.state.phase = Phase.TASK
        self._phase_start_timestep = self.state.timestep
        self._check_meeting_termination()

    def _emit(
        self,
        event_type: EventType,
        *,
        actor: int | None = None,
        target: int | None = None,
        room: str | None = None,
        to_room: str | None = None,
        task_name: str | None = None,
        text: str | None = None,
        private_to: tuple[int, ...] = (),
        **payload: object,
    ) -> WorldEvent:
        event = self.events.append(
            timestep=self.state.timestep,
            phase=self.state.phase,
            type=event_type,
            actor=actor,
            target=target,
            room=room,
            to_room=to_room,
            task_name=task_name,
            text=text,
            private_to=private_to,
            **payload,
        )
        for perception in resolve_perceptions(event, self.state, self.config.visibility, self.rng):
            observer = self.state.player_by_index(perception.observer)
            if observer is not None:
                observer.private.receive(perception)
        return event

    def _notice_bodies(self, player: PlayerState) -> None:
        for body in self.state.dead_bodies.get(player.location, []):
            self._emit(
                EventType.BODY_SIGHTED,
                room=player.location,
                private_to=(player.index,),
                victim_name=body,
            )

    def _track_location(self, player: PlayerState) -> None:
        self.location_history.setdefault(player.name, []).append(
            (self.state.timestep, player.location)
        )
        player.private.memory.note_own_location(player.name, player.location, self.state.timestep)

    def _killer_of(self, victim_name: str) -> str | None:
        for event in self.events.of_type(EventType.KILL):
            if event.payload.get("victim_name") == victim_name:
                return str(event.payload.get("killer_name"))
        return None

    def _annotate(
        self, player: PlayerState, action: Action, decision: Decision
    ) -> UtteranceAnnotation:
        if action.type is not ActionType.SPEAK or not decision.speech:
            return UtteranceAnnotation.not_applicable(player.role.value)
        ctx = build_context(
            self.state,
            self.events,
            self.location_history,
            self._phase_start_timestep,
            list(self.game_map.rooms),
        )
        return annotate_utterance(
            decision.speech, player, ctx, _declared_speech(decision.declared_speech)
        )

    def _check_task_termination(self) -> bool:
        if self._impostors_win_by_numbers():
            self._finish(1, WinReason.IMPOSTORS_OUTNUMBER)
            return True
        if self.state.crewmate_tasks_complete(count_dead=self.config.count_dead_crewmate_tasks):
            self._finish(0, WinReason.CREWMATES_TASKS_DONE)
            return True
        return False

    def _check_meeting_termination(self) -> bool:
        if not self.state.alive_impostors():
            self._finish(0, WinReason.CREWMATES_VOTED_OUT)
            return True
        if self._impostors_win_by_numbers():
            self._finish(1, WinReason.IMPOSTORS_OUTNUMBER)
            return True
        return False

    def _impostors_win_by_numbers(self) -> bool:
        return len(self.state.alive_impostors()) >= len(self.state.alive_crewmates())

    def _finish(self, winner: int, reason: WinReason) -> None:
        self.state.finished = True
        self.state.winner = winner
        self.state.winner_reason = reason.value
        logger.info("{} finished: {}", self.state.game_index, reason.value)

    def _teleport_all(self, room: str) -> None:
        for p in self.state.alive_players():
            p.location = room

    def _snapshot(self) -> int:
        self.world_states.append(
            {
                "game_id": self.state.game_index,
                "index": len(self.world_states),
                "timestep": self.state.timestep,
                "phase": self.state.phase.value,
                "step": self.state.step,
                "dead_bodies": {k: list(v) for k, v in self.state.dead_bodies.items()},
                "buttons_used": self.state.buttons_used,
                "players": [
                    {
                        "name": p.name,
                        "role": p.role.value,
                        "alive": p.alive,
                        "ejected": p.ejected,
                        "location": p.location,
                        "tasks_completed": len(p.completed_tasks),
                        "tasks_total": len(p.tasks),
                        "kill_cooldown_remaining": p.kill_cooldown_remaining,
                    }
                    for p in self.state.players
                ],
            }
        )
        return len(self.world_states) - 1

    def _record_turn(
        self,
        *,
        player: PlayerState,
        view: PlayerView,
        decision: Decision,
        action: Action,
        rejection: ActionRejection | None,
        leaks: list[LeakageViolation],
        annotation: UtteranceAnnotation,
        before_ref: int,
        after_ref: int,
    ) -> None:
        self.state.step += 1
        warnings = list(decision.validation_warnings)
        warnings.extend(self._contradiction_warnings(player, decision))
        self._turns.append(
            TurnRecord(
                schema_version=SCHEMA_VERSION,
                game_id=self.state.game_index,
                turn_id=f"{self.state.game_index}#{self.state.step}",
                step=self.state.step,
                timestep=self.state.timestep,
                phase=self.state.phase.value,
                timestamp=datetime.now(timezone.utc).isoformat(),
                actor={
                    "player_id": player.name,
                    "player_index": player.index,
                    "role": player.role.value,
                    "alive": player.alive,
                    "model": player.model,
                    "personality": player.personality,
                },
                world_state_before_ref=before_ref,
                world_state_after_ref=after_ref,
                private_state=player.private.to_dict(),
                model_input={
                    "system_prompt": decision.system_prompt,
                    "user_prompt": decision.user_prompt,
                    "sections": decision.prompt_sections,
                    "available_actions": list(view.available_actions),
                },
                model_output={
                    "raw": decision.full_response,
                    "generated_rationale": decision.response.get("Thinking Process", ""),
                    "generated_condensed_memory": decision.response.get("Condensed Memory", ""),
                    "action": _action_dict(action),
                    "requested_action": _requested_action_dict(decision),
                    "requested_action_text": decision.requested_action_text,
                    "requested_action_valid": _requested_valid(decision, rejection),
                    "execution_source": _execution_source(decision, rejection),
                    "fallback_reason": _fallback_reason(decision, rejection),
                    "speech": decision.speech,
                    "declared_speech": decision.declared_speech,
                    "parse_status": decision.parse_status,
                    "attempts": decision.attempts,
                },
                annotations={
                    "role_label": player.role.value,
                    **annotation.to_dict(),
                    "validation_warnings": warnings,
                },
                evaluation={
                    "action_valid": rejection is None,
                    "rejection": rejection.to_dict() if rejection else None,
                    "leakage_violations": [v.to_dict() for v in leaks],
                    "event_seq_after": len(self.events.events),
                },
                probe_regions=decision.spans,
            )
        )

    def _contradiction_warnings(self, player: PlayerState, decision: Decision) -> list[str]:
        warnings: list[str] = []
        rationale = (decision.response.get("Thinking Process", "") or "").lower()
        speech = (decision.speech or "").lower()
        for teammate in player.private.teammate_names:
            if teammate == player.name:
                continue
            needle = teammate.lower()
            if needle in rationale:
                window = _around(rationale, needle)
                if "crewmate" in window or "innocent" in window or "not the impostor" in window:
                    warnings.append("rationale_calls_known_teammate_a_crewmate")
                    break
        for teammate in player.private.teammate_names:
            if teammate == player.name or teammate.lower() not in speech:
                continue
            window = _around(speech, teammate.lower())
            if any(word in window for word in ("impostor", "suspicious", "sus", "kill")):
                warnings.append("speech_names_known_teammate_as_suspect")
                break
        mentions_deceit = "lie" in rationale or "deceive" in rationale
        if speech and rationale and not player.is_impostor and mentions_deceit:
            warnings.append("crewmate_rationale_mentions_deceiving")
        return warnings

    def _build_result(self) -> GameResult:
        return GameResult(
            game_index=self.state.game_index,
            config=self.config,
            players=self.state.players,
            winner=self.state.winner if self.state.winner is not None else 1,
            winner_reason=self.state.winner_reason or WinReason.IMPOSTORS_TIME_UP.value,
            turns=self._turns,
            world_states=self.world_states,
            events=self.events.to_list(),
            generation_config=self.generation_config,
            seed=self.seed,
        )


def _action_dict(action: Action) -> dict[str, object]:
    return {
        "type": action.type.value,
        "rendered": action.render(),
        "source_room": action.source_room,
        "target_room": action.target_room,
        "target_name": action.target_name,
        "task": action.task.name if action.task else None,
    }


def _requested_action_dict(decision: Decision) -> dict[str, object]:
    requested = decision.requested_action
    if requested is None and decision.execution_source in ("model", "model_normalized"):
        requested = decision.action
    if requested is None:
        return {
            "type": None,
            "rendered": decision.requested_action_text,
            "source_room": None,
            "target_room": None,
            "target_name": None,
            "task": None,
            "text": decision.requested_action_text,
        }
    block = _action_dict(requested)
    block["text"] = decision.requested_action_text or requested.render()
    return block


def _requested_valid(decision: Decision, rejection: ActionRejection | None) -> bool:
    if not decision.requested_action_valid:
        return False
    return rejection is None or decision.execution_source not in ("model", "model_normalized")


def _execution_source(decision: Decision, rejection: ActionRejection | None) -> str:
    return "engine_safe_fallback" if rejection is not None else decision.execution_source


def _fallback_reason(decision: Decision, rejection: ActionRejection | None) -> str | None:
    if rejection is None:
        return decision.fallback_reason
    if decision.fallback_reason:
        return f"{decision.fallback_reason}+{rejection.code}"
    return rejection.code


def _declared_speech(raw: dict[str, object] | None) -> StructuredSpeech | None:
    if not raw:
        return None
    try:
        act = SpeechAct(str(raw.get("speech_act", "other")))
    except ValueError:
        act = SpeechAct.OTHER
    try:
        intent = StrategicIntent(str(raw.get("strategic_intent", "none")))
    except ValueError:
        intent = StrategicIntent.NONE
    claims = raw.get("intended_claims")
    return StructuredSpeech(
        speech_act=act,
        target_player=(str(raw["target_player"]) if raw.get("target_player") else None),
        intended_claims=list(claims) if isinstance(claims, list) else [],
        strategic_intent=intent,
        declared=True,
    )


def _around(text: str, needle: str, radius: int = 60) -> str:
    idx = text.find(needle)
    if idx == -1:
        return ""
    return text[max(0, idx - radius) : idx + len(needle) + radius]


__all__ = ["STARTING_ROOM", "AmongUsGame", "GameResult", "TurnRecord"]

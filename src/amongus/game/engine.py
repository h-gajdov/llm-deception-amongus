

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from ..config import GameConfig
from ..logging import get_logger
from .actions import Action, available_actions
from .agent_api import Agent, DecisionContext
from .enums import PLAYER_COLORS, ActionType, Phase, Role, WinReason
from .game_map import GameMap, build_skeld
from .state import GameState, Observation, PlayerState
from .tasks import assign_crewmate_tasks, sample_common_tasks

logger = get_logger()

STARTING_ROOM = "Cafeteria"

                                                                                 
                                                                               
                                                 
AgentFactory = Callable[[PlayerState], Agent]


@dataclass
class StepRecord:
    pass

    game_index: str
    step: int
    timestamp: str
    player_name: str
    player_identity: str
    player_personality: str | None
    player_model: str
    player_location: str
    system_prompt: str
    prompt: dict[str, str]
    response: dict[str, str]
    full_response: str


@dataclass
class GameResult:
    pass

    game_index: str
    config: GameConfig
    players: list[PlayerState]
    winner: int
    winner_reason: str
    steps: list[StepRecord] = field(default_factory=list)


class AmongUsGame:
    pass

    def __init__(
        self,
        game_index: str,
        config: GameConfig,
        agent_factory: AgentFactory,
        rng: random.Random,
        game_map: GameMap | None = None,
    ) -> None:
        pass
        self.config = config
        self.rng = rng
        self.game_map = game_map or build_skeld()
        self._agent_factory = agent_factory
        self.agents: dict[int, Agent] = {}
        self.state = self._init_state(game_index)
        self._records: list[StepRecord] = []

                                                                          
                    
                                                                          
    def _init_state(self, game_index: str) -> GameState:
        pass
        cfg = self.config
        colors = self.rng.sample(PLAYER_COLORS, cfg.num_players)
        impostor_indices = set(self.rng.sample(range(cfg.num_players), cfg.num_impostors))
        common = sample_common_tasks(cfg.num_common_tasks, self.rng)

        players: list[PlayerState] = []
        for i in range(cfg.num_players):
            is_impostor = i in impostor_indices
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
            )
            agent = self._agent_factory(player)
            player.model = getattr(agent, "model_name", "unknown")
            self.agents[player.index] = agent
            players.append(player)
        return GameState(
            game_index=game_index,
            players=players,
            discussion_rounds=cfg.discussion_rounds,
            max_num_buttons=cfg.max_num_buttons,
            max_timesteps=cfg.max_timesteps,
        )

                                                                          
               
                                                                          
    def run(self) -> GameResult:
        pass
        while not self.state.finished:
            if self.state.timestep >= self.config.max_timesteps:
                self._finish(1, WinReason.IMPOSTORS_TIME_UP)
                break
            self._run_task_timestep()
            if self.state.finished:
                break
            self.state.timestep += 1
        return self._build_result()

    def _run_task_timestep(self) -> None:
        pass
        self._tick_cooldowns()
        for player in list(self.state.alive_players()):
            if not player.alive or self.state.finished:
                continue
            meeting_triggered = self._take_turn(player)
            if meeting_triggered:
                self._run_meeting()
                return
            if self._check_task_termination():
                return

    def _tick_cooldowns(self) -> None:
        pass
        for imp in self.state.alive_impostors():
            imp.kill_cooldown_remaining = max(0, imp.kill_cooldown_remaining - 1)

                                                                          
                   
                                                                          
    def _take_turn(self, player: PlayerState) -> bool:
        pass
        actions = available_actions(self.state, player, self.game_map)
        decision = self._decide(player, actions)
        self._record_step(player, decision)
        self._carry_memory(player, decision)
        return self._apply_action(player, decision.action, decision)

    def _decide(self, player: PlayerState, actions: list[Action]):
        pass
        ctx = DecisionContext(self.state, player, actions, self.game_map)
        try:
            return self.agents[player.index].act(ctx)
        except Exception as exc:
            logger.warning(
                "Agent for {} raised {}; falling back to WAIT/first action.",
                player.name,
                exc,
            )
            from .agent_api import ScriptedAgent

            return ScriptedAgent().act(ctx)

    def _carry_memory(self, player: PlayerState, decision) -> None:
        pass
        player.last_memory = decision.response.get("Condensed Memory", player.last_memory)
        player.last_summarization = decision.response.get(
            "Thinking Process", player.last_summarization
        )

    def _apply_action(self, player: PlayerState, action: Action, decision) -> bool:
        pass
        self._append_own_action(player, action)
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
                self._broadcast_room(player.location, f"{player.name} REPORTED a dead body")
                self.state.meeting_reason = f"{player.name} reported a dead body"
                return True
            case ActionType.CALL_MEETING:
                self._broadcast_all(f"{player.name} CALLED an emergency meeting")
                self.state.buttons_used += 1
                self.state.meeting_reason = f"{player.name} called an emergency meeting"
                return True
            case ActionType.SPEAK:
                self._do_speak(player, decision)
            case ActionType.WAIT:
                pass
        return False

                                                                          
                    
                                                                          
    def _do_move(self, player: PlayerState, action: Action) -> None:
        pass
        dest = action.target_room or player.location
        self._broadcast_room(
            player.location,
            f"{player.name} MOVE from {player.location} to {dest}",
            exclude=player.index,
        )
        player.location = dest
        self._notice_bodies(player)

    def _do_vent(self, player: PlayerState, action: Action) -> None:
        pass
        dest = action.target_room or player.location
        self._broadcast_room(
            player.location,
            f"{player.name} VENTED from {player.location} to {dest}",
            exclude=player.index,
        )
        player.location = dest
        self._notice_bodies(player)

    def _do_task(self, player: PlayerState, action: Action) -> None:
        pass
        if action.task is None:
            return
        try:
            idx = player.tasks.index(action.task)
        except ValueError:
            return
        if not player.is_impostor:
            player.completed_tasks.add(idx)
        verb = "did a task" if not player.is_impostor else "appeared to do a task"
        self._broadcast_room(
            player.location, f"{player.name} {verb} in {player.location}", exclude=player.index
        )

    def _do_kill(self, player: PlayerState, action: Action) -> None:
        pass
        victim = self.state.player_by_name(action.target_name or "")
        if victim is None or not victim.alive:
            return
        victim.alive = False
        player.kill_cooldown_remaining = self.config.kill_cooldown
        room = player.location
        self.state.dead_bodies.setdefault(room, []).append(victim.name)
        excluded = (player.index, victim.index)
        witnesses = [p for p in self.state.players_in_room(room) if p.index not in excluded]
        if witnesses:
            for w in witnesses:
                self._observe(w, f"{player.name} KILLED {victim.name} in {room}")
        logger.debug("{} killed {} in {}", player.name, victim.name, room)

    def _do_check_security(self, player: PlayerState) -> None:
        pass
        sightings = [
            f"{p.name} in {p.location}"
            for p in self.state.alive_players()
            if p.index != player.index
        ]
        summary = "; ".join(sightings) if sightings else "no one"
        self._observe(player, f"Security cameras show: {summary}")

    def _do_speak(self, player: PlayerState, decision) -> None:
        pass
        speech = (decision.speech or "").strip() or "(says nothing of note)"
        line = f"{player.name}: {speech}"
        self.state.meeting_transcript.append(line)
        self._broadcast_all(f"{player.name} said: {speech}", exclude=player.index)

                                                                          
                   
                                                                          
    def _run_meeting(self) -> None:
        pass
        self.state.phase = Phase.MEETING
        self.state.meeting_transcript = []
        self.state.meeting_round = 0
        self._teleport_all(STARTING_ROOM)

        for round_idx in range(self.config.discussion_rounds):
            self.state.meeting_round = round_idx
            for player in list(self.state.alive_players()):
                if self.state.finished:
                    break
                actions = available_actions(self.state, player, self.game_map)
                decision = self._decide(player, actions)
                self._record_step(player, decision)
                self._carry_memory(player, decision)
                self._append_own_action(player, decision.action)
                self._do_speak(player, decision)

        self._run_vote()
        self._end_meeting()

    def _run_vote(self) -> None:
        pass
        self.state.meeting_round = self.config.discussion_rounds
        tally: Counter[str] = Counter()
        for player in list(self.state.alive_players()):
            actions = available_actions(self.state, player, self.game_map)
            decision = self._decide(player, actions)
            self._record_step(player, decision)
            self._carry_memory(player, decision)
            target = decision.action.target_name or "Skip"
            player.current_vote = target
            tally[target] += 1
            self._append_own_action(player, decision.action)

        self._resolve_vote(tally)

    def _resolve_vote(self, tally: Counter[str]) -> None:
        pass
        if not tally:
            return
        top, top_votes = tally.most_common(1)[0]
        tied = [name for name, votes in tally.items() if votes == top_votes]
        if len(tied) != 1 or top == "Skip":
            self._broadcast_all("The vote was inconclusive. No one was ejected.")
            return
        ejected = self.state.player_by_name(top)
        if ejected is None:
            return
        ejected.alive = False
        self._broadcast_all(f"{ejected.name} was ejected.")
        logger.debug("{} was ejected (votes={})", ejected.name, top_votes)

    def _end_meeting(self) -> None:
        pass
        self.state.dead_bodies.clear()
        self.state.meeting_reason = None
        for imp in self.state.alive_impostors():
            imp.kill_cooldown_remaining = self.config.kill_cooldown
        self.state.phase = Phase.TASK
        self._check_meeting_termination()

                                                                          
                               
                                                                          
    def _observe(self, player: PlayerState, text: str) -> None:
        pass
        player.observations.append(
            Observation(timestep=self.state.timestep, phase=self.state.phase, text=text)
        )

    def _broadcast_room(self, room: str, text: str, *, exclude: int | None = None) -> None:
        pass
        for p in self.state.players_in_room(room):
            if exclude is not None and p.index == exclude:
                continue
            self._observe(p, text)

    def _broadcast_all(self, text: str, *, exclude: int | None = None) -> None:
        pass
        for p in self.state.alive_players():
            if exclude is not None and p.index == exclude:
                continue
            self._observe(p, text)

    def _notice_bodies(self, player: PlayerState) -> None:
        pass
        for body in self.state.dead_bodies.get(player.location, []):
            self._observe(player, f"You see the dead body of {body} in {player.location}")

    def _append_own_action(self, player: PlayerState, action: Action) -> None:
        pass
        tag = "task phase" if self.state.phase is Phase.TASK else "meeting phase"
        player.action_history.append(f"Timestep {self.state.timestep}: [{tag}] {action.render()}")

                                                                          
                 
                                                                          
    def _check_task_termination(self) -> bool:
        pass
        if self._impostors_win_by_numbers():
            self._finish(1, WinReason.IMPOSTORS_OUTNUMBER)
            return True
        if self.state.crewmate_tasks_complete():
            self._finish(0, WinReason.CREWMATES_TASKS_DONE)
            return True
        return False

    def _check_meeting_termination(self) -> bool:
        pass
        if not self.state.alive_impostors():
            self._finish(0, WinReason.CREWMATES_VOTED_OUT)
            return True
        if self._impostors_win_by_numbers():
            self._finish(1, WinReason.IMPOSTORS_OUTNUMBER)
            return True
        return False

    def _impostors_win_by_numbers(self) -> bool:
        pass
        return len(self.state.alive_impostors()) >= len(self.state.alive_crewmates())

    def _finish(self, winner: int, reason: WinReason) -> None:
        pass
        self.state.finished = True
        self.state.winner = winner
        self.state.winner_reason = reason.value
        logger.info("{} finished: {}", self.state.game_index, reason.value)

                                                                          
                      
                                                                          
    def _teleport_all(self, room: str) -> None:
        pass
        for p in self.state.alive_players():
            p.location = room

    def _record_step(self, player: PlayerState, decision) -> None:
        pass
        self.state.step += 1
        self._records.append(
            StepRecord(
                game_index=self.state.game_index,
                step=self.state.step,
                timestamp=datetime.now().isoformat(sep=" "),
                player_name=player.name,
                player_identity=player.role.value,
                player_personality=player.personality,
                player_model=player.model,
                player_location=player.location,
                system_prompt=decision.system_prompt,
                prompt=decision.prompt,
                response=decision.response,
                full_response=decision.full_response,
            )
        )

    def _build_result(self) -> GameResult:
        pass
        return GameResult(
            game_index=self.state.game_index,
            config=self.config,
            players=self.state.players,
            winner=self.state.winner if self.state.winner is not None else 1,
            winner_reason=self.state.winner_reason or WinReason.IMPOSTORS_TIME_UP.value,
            steps=self._records,
        )


__all__ = ["STARTING_ROOM", "AmongUsGame", "GameResult", "StepRecord"]

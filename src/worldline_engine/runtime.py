"""Deterministic tick runtime for domain-neutral multi-agent simulations."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from .protocols import (
    ActionIntent,
    ActionKind,
    ActionResult,
    ActionStatus,
    BoundAction,
    Controller,
    EntitySpec,
    EventSink,
    FinishTurn,
    Scheduler,
    SimulationConfig,
    SimulationEvent,
    StateStore,
    TurnContext,
    TurnSpec,
    World,
)


@dataclass
class _EventDraft:
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    turn_id: str | None = None
    action_id: str | None = None
    entity_id: str | None = None


@dataclass
class _TurnOutcome:
    turn: TurnSpec
    turn_id: str
    writes: list[BoundAction]
    events: list[_EventDraft]


class Simulation:
    """Coordinates controllers, a world, storage, and append-only events."""

    def __init__(
        self,
        config: SimulationConfig,
        entities: Sequence[EntitySpec],
        controllers: Mapping[str, Controller],
        scheduler: Scheduler,
        world: World,
        state_store: StateStore,
        event_sink: EventSink,
    ) -> None:
        if config.max_actions_per_turn < 1 or config.max_controller_calls_per_turn < 1:
            raise ValueError("turn limits must be at least one")
        if config.max_concurrent_turns < 1:
            raise ValueError("max_concurrent_turns must be at least one")
        if config.checkpoint_every_ticks < 1:
            raise ValueError("checkpoint_every_ticks must be at least one")
        if config.max_cost_per_turn is not None and config.max_cost_per_turn < 0:
            raise ValueError("max_cost_per_turn must not be negative")
        if config.turn_timeout_seconds is not None and config.turn_timeout_seconds <= 0:
            raise ValueError("turn_timeout_seconds must be positive")
        if config.max_consecutive_failures < 1:
            raise ValueError("max_consecutive_failures must be at least one")
        if config.max_repeated_actions < 1:
            raise ValueError("max_repeated_actions must be at least one")

        self.config = config
        self.entities = tuple(sorted(entities, key=lambda entity: entity.entity_id))
        if len({entity.entity_id for entity in self.entities}) != len(self.entities):
            raise ValueError("entity_id values must be unique")
        self.controllers = dict(controllers)
        missing = {
            entity.controller_ref
            for entity in self.entities
            if entity.enabled and entity.controller_ref not in self.controllers
        }
        if missing:
            raise ValueError(f"missing controllers: {', '.join(sorted(missing))}")

        self.scheduler = scheduler
        self.world = world
        self.state_store = state_store
        self.event_sink = event_sink
        self._current_tick = config.start_tick
        self._sequence = 0
        self._started = False

    @property
    def current_tick(self) -> int:
        return self._current_tick

    async def run(self, ticks: int | None = None) -> None:
        if ticks is not None and ticks < 0:
            raise ValueError("ticks must not be negative")
        remaining = self.config.max_ticks - (self._current_tick - self.config.start_tick)
        count = remaining if ticks is None else min(ticks, remaining)
        if not self._started:
            self._started = True
            self._emit("simulation_started", self._current_tick)
        for _ in range(count):
            await self.run_tick()
        if count == remaining:
            self._emit("simulation_finished", self._current_tick)

    async def run_tick(self) -> None:
        tick_id = self._current_tick
        snapshot = self.world.snapshot()
        self._emit("tick_started", tick_id)
        turns = tuple(
            self.scheduler.select_turns(self.entities, tick_id, self.config.seed)
        )
        self._validate_turns(turns)

        semaphore = asyncio.Semaphore(self.config.max_concurrent_turns)

        async def bounded_turn(turn: TurnSpec) -> _TurnOutcome:
            async with semaphore:
                return await self._run_turn(tick_id, turn, snapshot)

        outcomes = await asyncio.gather(*(bounded_turn(turn) for turn in turns))
        ordered_outcomes = sorted(outcomes, key=lambda outcome: outcome.turn.turn_index)
        for outcome in ordered_outcomes:
            for event in outcome.events:
                self._emit_draft(tick_id, event)

        writes = sorted(
            (write for outcome in ordered_outcomes for write in outcome.writes),
            key=lambda action: action.ordering_key,
        )
        try:
            decisions = self.world.resolve_and_apply(snapshot, writes)
            if len(decisions) != len(writes):
                raise RuntimeError("World must return one commit decision per buffered action")
            if [decision.action.action_id for decision in decisions] != [
                action.action_id for action in writes
            ]:
                raise RuntimeError("World must preserve the runtime's stable action ordering")
        except BaseException as error:
            self.world.restore(snapshot)
            self._emit(
                "commit_error",
                tick_id,
                payload={"error_type": type(error).__name__, "message": str(error)},
            )
            raise
        for decision in decisions:
            status = decision.result.status
            if status is ActionStatus.ACCEPTED:
                event_type = "action_committed"
            elif status is ActionStatus.FAILED:
                event_type = "action_failed"
            else:
                event_type = "action_rejected"
            self._emit(
                event_type,
                tick_id,
                turn_id=decision.action.turn_id,
                action_id=decision.action.action_id,
                entity_id=decision.action.entity_id,
                payload={"result": self._result_payload(decision.result)},
            )

        self._current_tick += 1
        self._emit("tick_committed", tick_id)
        if (tick_id - self.config.start_tick + 1) % self.config.checkpoint_every_ticks == 0:
            self._save_checkpoint(tick_id)
            self._emit("checkpoint_created", tick_id)

    def restore_latest_checkpoint(self) -> bool:
        checkpoint = self.state_store.load_latest_checkpoint(self.config.simulation_id)
        if checkpoint is None:
            return False
        self.world.restore(checkpoint["world_state"])
        controller_states = checkpoint["controller_states"]
        for reference, state in controller_states.items():
            if reference not in self.controllers:
                raise ValueError(f"checkpoint requires unknown controller {reference}")
            self.controllers[reference].load_state(state)
        runtime_state = checkpoint["runtime_state"]
        self._current_tick = int(runtime_state["next_tick"])
        self._sequence = int(runtime_state["next_sequence"])
        self._started = True
        return True

    async def _run_turn(
        self, tick_id: int, turn: TurnSpec, snapshot: Any
    ) -> _TurnOutcome:
        if self.config.turn_timeout_seconds is None:
            return await self._run_turn_body(tick_id, turn, snapshot)
        try:
            async with asyncio.timeout(self.config.turn_timeout_seconds):
                return await self._run_turn_body(tick_id, turn, snapshot)
        except TimeoutError:
            turn_id = f"{tick_id}:{turn.turn_index}:{turn.entity_id}"
            return _TurnOutcome(
                turn,
                turn_id,
                [],
                [
                    _EventDraft("turn_started", turn_id=turn_id, entity_id=turn.entity_id),
                    _EventDraft("turn_timeout", turn_id=turn_id, entity_id=turn.entity_id),
                    _EventDraft(
                        "turn_finished",
                        {"reason": "timeout", "controller_calls": 0, "actions": 0, "cost": 0},
                        turn_id=turn_id,
                        entity_id=turn.entity_id,
                    ),
                ],
            )

    async def _run_turn_body(
        self, tick_id: int, turn: TurnSpec, snapshot: Any
    ) -> _TurnOutcome:
        entity = self._entity(turn.entity_id)
        controller = self.controllers[entity.controller_ref]
        turn_id = f"{tick_id}:{turn.turn_index}:{turn.entity_id}"
        events = [_EventDraft("turn_started", turn_id=turn_id, entity_id=turn.entity_id)]
        writes: list[BoundAction] = []
        previous_result: ActionResult | None = None
        controller_calls = 0
        action_index = 0
        total_cost = 0
        consecutive_failures = 0
        repeated_actions: dict[str, int] = {}
        discard_writes = False
        finish_reason = "action_limit"

        while action_index < self.config.max_actions_per_turn:
            if controller_calls >= self.config.max_controller_calls_per_turn:
                finish_reason = "controller_call_limit"
                break
            try:
                action_specs = tuple(
                    self.world.available_actions(turn.entity_id, snapshot)
                )
                observation = self.world.observe(turn.entity_id, snapshot, writes)
            except Exception as error:
                events.append(
                    _EventDraft(
                        "world_error",
                        {
                            "stage": "observe",
                            "error_type": type(error).__name__,
                            "message": str(error),
                        },
                        turn_id=turn_id,
                        entity_id=turn.entity_id,
                    )
                )
                finish_reason = "world_error"
                discard_writes = True
                break
            context = TurnContext(
                simulation_id=self.config.simulation_id,
                tick_id=tick_id,
                turn_id=turn_id,
                entity_id=turn.entity_id,
                observation=observation,
                available_actions=action_specs,
                previous_result=previous_result,
                remaining_actions=self.config.max_actions_per_turn - action_index,
                remaining_controller_calls=self.config.max_controller_calls_per_turn - controller_calls,
                remaining_cost=(
                    None
                    if self.config.max_cost_per_turn is None
                    else self.config.max_cost_per_turn - total_cost
                ),
                random_seed=self._turn_seed(tick_id, turn),
            )
            controller_calls += 1
            events.append(_EventDraft("controller_called", turn_id=turn_id, entity_id=turn.entity_id))
            try:
                decision = await controller.next_action(context)
            except Exception as error:  # Controller failures never create writes.
                events.append(
                    _EventDraft(
                        "controller_error",
                        {"error_type": type(error).__name__, "message": str(error)},
                        turn_id=turn_id,
                        entity_id=turn.entity_id,
                    )
                )
                finish_reason = "controller_error"
                discard_writes = True
                break

            if isinstance(decision, FinishTurn):
                finish_reason = decision.reason
                break
            if not isinstance(decision, ActionIntent):
                events.append(
                    _EventDraft(
                        "invalid_intent",
                        {"reason": "controller returned an unsupported decision type"},
                        turn_id=turn_id,
                        entity_id=turn.entity_id,
                    )
                )
                finish_reason = "invalid_intent"
                discard_writes = True
                break

            action = BoundAction(
                action_id=f"{self.config.simulation_id}:{tick_id}:{turn.turn_index}:{action_index}",
                simulation_id=self.config.simulation_id,
                tick_id=tick_id,
                turn_id=turn_id,
                entity_id=turn.entity_id,
                turn_index=turn.turn_index,
                action_index=action_index,
                intent=decision,
            )
            events.append(
                _EventDraft(
                    "action_proposed",
                    {"intent": self._intent_payload(decision)},
                    turn_id=turn_id,
                    action_id=action.action_id,
                    entity_id=turn.entity_id,
                )
            )
            fingerprint = self._intent_fingerprint(decision)
            repeated_actions[fingerprint] = repeated_actions.get(fingerprint, 0) + 1
            if repeated_actions[fingerprint] > self.config.max_repeated_actions:
                previous_result = ActionResult(
                    action.action_id,
                    ActionStatus.REJECTED,
                    error_code="repeated_action_limit",
                )
                events.append(
                    _EventDraft(
                        "action_rejected",
                        {"result": self._result_payload(previous_result)},
                        turn_id=turn_id,
                        action_id=action.action_id,
                        entity_id=turn.entity_id,
                    )
                )
                finish_reason = "repeated_action_limit"
                action_index += 1
                break
            spec = next((spec for spec in action_specs if spec.name == decision.action_type), None)
            previous_result = self._validate_envelope(action, spec)
            if previous_result is not None:
                events.append(
                    _EventDraft(
                        "action_rejected",
                        {"result": self._result_payload(previous_result)},
                        turn_id=turn_id,
                        action_id=action.action_id,
                        entity_id=turn.entity_id,
                    )
                )
                consecutive_failures += 1
                action_index += 1
                if consecutive_failures >= self.config.max_consecutive_failures:
                    finish_reason = "consecutive_failure_limit"
                    break
                continue

            assert spec is not None
            if (
                self.config.max_cost_per_turn is not None
                and total_cost + spec.cost > self.config.max_cost_per_turn
            ):
                previous_result = ActionResult(
                    action.action_id,
                    ActionStatus.REJECTED,
                    error_code="cost_budget_exceeded",
                )
                events.append(
                    _EventDraft(
                        "action_rejected",
                        {"result": self._result_payload(previous_result)},
                        turn_id=turn_id,
                        action_id=action.action_id,
                        entity_id=turn.entity_id,
                    )
                )
                finish_reason = "cost_budget_exceeded"
                action_index += 1
                break
            total_cost += spec.cost
            events.append(
                _EventDraft(
                    "action_validated",
                    {"cost": spec.cost},
                    turn_id=turn_id,
                    action_id=action.action_id,
                    entity_id=turn.entity_id,
                )
            )
            try:
                if spec.kind is ActionKind.READ:
                    previous_result = self.world.execute_read(action, snapshot, writes)
                else:
                    previous_result = self.world.validate_write(
                        action,
                        snapshot,
                        writes,
                    )
            except Exception as error:
                events.append(
                    _EventDraft(
                        "world_error",
                        {
                            "stage": "execute_read"
                            if spec.kind is ActionKind.READ
                            else "validate_write",
                            "error_type": type(error).__name__,
                            "message": str(error),
                        },
                        turn_id=turn_id,
                        action_id=action.action_id,
                        entity_id=turn.entity_id,
                    )
                )
                finish_reason = "world_error"
                discard_writes = True
                break

            if spec.kind is ActionKind.READ:
                if previous_result.cost == 0 and spec.cost != 0:
                    previous_result = replace(previous_result, cost=spec.cost)
                events.append(
                    _EventDraft(
                        "action_read" if previous_result.status is ActionStatus.ACCEPTED else "action_rejected",
                        {"result": self._result_payload(previous_result)},
                        turn_id=turn_id,
                        action_id=action.action_id,
                        entity_id=turn.entity_id,
                    )
                )
            else:
                if previous_result.cost == 0 and spec.cost != 0:
                    previous_result = replace(previous_result, cost=spec.cost)
                event_type = "action_buffered" if previous_result.status is ActionStatus.ACCEPTED else "action_rejected"
                events.append(
                    _EventDraft(
                        event_type,
                        {"result": self._result_payload(previous_result)},
                        turn_id=turn_id,
                        action_id=action.action_id,
                        entity_id=turn.entity_id,
                    )
                )
                if previous_result.status is ActionStatus.ACCEPTED:
                    writes.append(action)
            if previous_result.status is ActionStatus.ACCEPTED:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
            action_index += 1
            if consecutive_failures >= self.config.max_consecutive_failures:
                finish_reason = "consecutive_failure_limit"
                break

        events.append(
            _EventDraft(
                "turn_finished",
                {
                    "reason": finish_reason,
                    "controller_calls": controller_calls,
                    "actions": action_index,
                    "cost": total_cost,
                },
                turn_id=turn_id,
                entity_id=turn.entity_id,
            )
        )
        return _TurnOutcome(turn, turn_id, [] if discard_writes else writes, events)

    def _turn_seed(self, tick_id: int, turn: TurnSpec) -> int:
        payload = f"{self.config.seed}:{tick_id}:{turn.turn_index}:{turn.entity_id}"
        return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:8], "big")

    @staticmethod
    def _intent_fingerprint(intent: ActionIntent) -> str:
        return json.dumps(
            {
                "action_type": intent.action_type,
                "parameters": intent.parameters,
                "target_ref": intent.target_ref,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    def _save_checkpoint(self, completed_tick: int) -> None:
        self.state_store.save_checkpoint(
            self.config.simulation_id,
            completed_tick,
            self.world.snapshot(),
            {reference: controller.dump_state() for reference, controller in self.controllers.items()},
            # The following checkpoint-created event is already reserved by
            # the persisted run; a restored runtime must not reuse its id.
            {"next_tick": self._current_tick, "next_sequence": self._sequence + 1},
        )

    def _validate_turns(self, turns: Sequence[TurnSpec]) -> None:
        seen: set[str] = set()
        for expected_index, turn in enumerate(turns):
            if turn.turn_index != expected_index:
                raise ValueError("Scheduler must return contiguous turn indexes")
            if turn.entity_id in seen:
                raise ValueError("MVP scheduler permits one turn per entity per tick")
            self._entity(turn.entity_id)
            seen.add(turn.entity_id)

    def _validate_envelope(self, action: BoundAction, spec: Any) -> ActionResult | None:
        if spec is None:
            return ActionResult(action.action_id, ActionStatus.REJECTED, error_code="action_not_available")
        if not isinstance(action.intent.parameters, Mapping):
            return ActionResult(action.action_id, ActionStatus.REJECTED, error_code="parameters_not_mapping")
        required = spec.parameters_schema.get("required", ())
        missing = [name for name in required if name not in action.intent.parameters]
        if missing:
            return ActionResult(
                action.action_id,
                ActionStatus.REJECTED,
                error_code="missing_required_parameters",
                data={"missing": missing},
            )
        if not isinstance(spec.cost, int) or spec.cost < 0:
            return ActionResult(
                action.action_id,
                ActionStatus.REJECTED,
                error_code="invalid_action_cost",
            )
        return None

    def _entity(self, entity_id: str) -> EntitySpec:
        for entity in self.entities:
            if entity.entity_id == entity_id:
                return entity
        raise ValueError(f"Scheduler selected unknown entity {entity_id}")

    def _emit_draft(self, tick_id: int, draft: _EventDraft) -> None:
        self._emit(
            draft.event_type,
            tick_id,
            payload=draft.payload,
            turn_id=draft.turn_id,
            action_id=draft.action_id,
            entity_id=draft.entity_id,
        )

    def _emit(
        self,
        event_type: str,
        tick_id: int,
        payload: dict[str, Any] | None = None,
        turn_id: str | None = None,
        action_id: str | None = None,
        entity_id: str | None = None,
    ) -> None:
        self._sequence += 1
        self.event_sink.append(
            SimulationEvent(
                event_id=f"{self.config.simulation_id}:event:{self._sequence}",
                event_type=event_type,
                simulation_id=self.config.simulation_id,
                tick_id=tick_id,
                sequence=self._sequence,
                payload=payload or {},
                turn_id=turn_id,
                action_id=action_id,
                entity_id=entity_id,
            )
        )

    @staticmethod
    def _intent_payload(intent: ActionIntent) -> dict[str, Any]:
        return {
            "action_type": intent.action_type,
            "parameters": dict(intent.parameters),
            "target_ref": intent.target_ref,
            "client_ref": intent.client_ref,
        }

    @staticmethod
    def _result_payload(result: ActionResult) -> dict[str, Any]:
        return {
            "status": result.status.value,
            "data": dict(result.data),
            "error_code": result.error_code,
            "error_message": result.error_message,
            "local_ref": result.local_ref,
            "cost": result.cost,
        }

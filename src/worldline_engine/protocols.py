"""Domain-neutral contracts used by the engine runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence


JsonValue = Any


class ActionKind(str, Enum):
    READ = "read"
    WRITE = "write"


class ActionStatus(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    FAILED = "failed"


@dataclass(frozen=True)
class SimulationConfig:
    simulation_id: str
    seed: int = 0
    start_tick: int = 0
    max_ticks: int = 1
    max_actions_per_turn: int = 8
    max_controller_calls_per_turn: int = 8
    max_concurrent_turns: int = 1
    checkpoint_every_ticks: int = 1


@dataclass(frozen=True)
class EntitySpec:
    entity_id: str
    controller_ref: str
    enabled: bool = True
    metadata: Mapping[str, JsonValue] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionSpec:
    name: str
    kind: ActionKind
    description: str = ""
    parameters_schema: Mapping[str, JsonValue] = field(default_factory=dict)
    cost: int = 1


@dataclass(frozen=True)
class ActionIntent:
    """Business-only action proposed by a controller.

    The controller never supplies entity, tick, turn, or action ordering
    fields. The runtime binds those fields before validation and execution.
    """

    action_type: str
    parameters: Mapping[str, JsonValue] = field(default_factory=dict)
    target_ref: str | None = None
    client_ref: str | None = None


@dataclass(frozen=True)
class FinishTurn:
    reason: str = "controller_finished"


@dataclass(frozen=True)
class BoundAction:
    action_id: str
    simulation_id: str
    tick_id: int
    turn_id: str
    entity_id: str
    turn_index: int
    action_index: int
    intent: ActionIntent

    @property
    def ordering_key(self) -> tuple[int, int, str, int, int]:
        return (0, 0, self.entity_id, self.turn_index, self.action_index)


@dataclass(frozen=True)
class ActionResult:
    action_id: str | None
    status: ActionStatus
    data: Mapping[str, JsonValue] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    local_ref: str | None = None
    cost: int = 0


@dataclass(frozen=True)
class TurnContext:
    simulation_id: str
    tick_id: int
    turn_id: str
    entity_id: str
    observation: JsonValue
    available_actions: Sequence[ActionSpec]
    previous_result: ActionResult | None
    remaining_actions: int
    remaining_controller_calls: int


@dataclass(frozen=True)
class SimulationEvent:
    event_id: str
    event_type: str
    simulation_id: str
    tick_id: int
    sequence: int
    payload: Mapping[str, JsonValue] = field(default_factory=dict)
    turn_id: str | None = None
    action_id: str | None = None
    entity_id: str | None = None


@dataclass(frozen=True)
class TurnSpec:
    entity_id: str
    turn_index: int


@dataclass(frozen=True)
class CommitDecision:
    action: BoundAction
    result: ActionResult


class Scheduler(Protocol):
    def select_turns(
        self,
        entities: Sequence[EntitySpec],
        tick_id: int,
        random_seed: int,
    ) -> Sequence[TurnSpec]: ...


class Controller(Protocol):
    async def next_action(
        self, context: TurnContext
    ) -> ActionIntent | FinishTurn: ...

    def dump_state(self) -> JsonValue: ...

    def load_state(self, state: JsonValue) -> None: ...


class World(Protocol):
    """The sole owner of domain semantics and domain state."""

    def snapshot(self) -> JsonValue: ...

    def restore(self, state: JsonValue) -> None: ...

    def observe(
        self,
        entity_id: str,
        snapshot: JsonValue,
        local_overlay: Sequence[BoundAction],
    ) -> JsonValue: ...

    def available_actions(
        self, entity_id: str, snapshot: JsonValue
    ) -> Sequence[ActionSpec]: ...

    def execute_read(
        self,
        action: BoundAction,
        snapshot: JsonValue,
        local_overlay: Sequence[BoundAction],
    ) -> ActionResult: ...

    def validate_write(
        self,
        action: BoundAction,
        snapshot: JsonValue,
        local_overlay: Sequence[BoundAction],
    ) -> ActionResult: ...

    def resolve_and_apply(
        self, snapshot: JsonValue, actions: Sequence[BoundAction]
    ) -> Sequence[CommitDecision]: ...


class StateStore(Protocol):
    def save_checkpoint(
        self,
        simulation_id: str,
        tick_id: int,
        world_state: JsonValue,
        controller_states: Mapping[str, JsonValue],
        runtime_state: Mapping[str, JsonValue],
    ) -> None: ...

    def load_latest_checkpoint(
        self, simulation_id: str
    ) -> Mapping[str, JsonValue] | None: ...


class EventSink(Protocol):
    def append(self, event: SimulationEvent) -> None: ...

    def close(self) -> None: ...

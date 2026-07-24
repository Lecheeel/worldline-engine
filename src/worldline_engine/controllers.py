"""Domain-neutral controller implementations."""

from __future__ import annotations

import inspect
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from .protocols import ActionIntent, Controller, FinishTurn, TurnContext

ControllerDecision = ActionIntent | FinishTurn
Rule = Callable[[TurnContext], ControllerDecision | Awaitable[ControllerDecision]]


class RuleController(Controller):
    """Delegates decisions to a deterministic application-supplied rule."""

    def __init__(self, rule: Rule) -> None:
        self._rule = rule

    async def next_action(self, context: TurnContext) -> ControllerDecision:
        decision = self._rule(context)
        if inspect.isawaitable(decision):
            return await decision
        return decision

    def dump_state(self) -> dict[str, Any]:
        return {}

    def load_state(self, state: Any) -> None:
        if state not in ({}, None):
            raise ValueError("RuleController does not have restorable state")


class ReplayController(Controller):
    """Returns recorded intents without calling an external model."""

    def __init__(self, actions_by_entity: Mapping[str, Sequence[ActionIntent]]) -> None:
        self._actions = {
            entity_id: tuple(actions)
            for entity_id, actions in actions_by_entity.items()
        }
        self._positions: dict[str, int] = defaultdict(int)

    async def next_action(self, context: TurnContext) -> ControllerDecision:
        position = self._positions[context.entity_id]
        actions = self._actions.get(context.entity_id, ())
        if position >= len(actions):
            return FinishTurn("replay_exhausted")
        self._positions[context.entity_id] = position + 1
        return actions[position]

    def dump_state(self) -> dict[str, int]:
        return dict(self._positions)

    def load_state(self, state: Any) -> None:
        if not isinstance(state, dict) or not all(
            isinstance(key, str) and isinstance(value, int)
            for key, value in state.items()
        ):
            raise ValueError("ReplayController state must be a string-to-int map")
        self._positions = defaultdict(int, state)

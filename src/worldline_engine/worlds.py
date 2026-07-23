"""Small domain worlds used to validate the engine protocol."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Sequence

from .protocols import (
    ActionKind,
    ActionResult,
    ActionSpec,
    ActionStatus,
    BoundAction,
    CommitDecision,
)


class CounterWorld:
    """A minimal world with a deterministic single-resource conflict."""

    _SPECS = (
        ActionSpec("read_value", ActionKind.READ),
        ActionSpec("add", ActionKind.WRITE, parameters_schema={"required": ["amount"]}),
        ActionSpec("claim", ActionKind.WRITE),
    )

    def __init__(self, value: int = 0) -> None:
        self._state: dict[str, Any] = {"value": value, "claimed_by": None}

    @property
    def state(self) -> dict[str, Any]:
        return deepcopy(self._state)

    def snapshot(self) -> dict[str, Any]:
        return self.state

    def restore(self, state: dict[str, Any]) -> None:
        if not isinstance(state.get("value"), int) or "claimed_by" not in state:
            raise ValueError("invalid CounterWorld state")
        self._state = deepcopy(state)

    def observe(
        self,
        entity_id: str,
        snapshot: dict[str, Any],
        local_overlay: Sequence[BoundAction],
    ) -> dict[str, Any]:
        del entity_id
        visible = deepcopy(snapshot)
        visible["pending_actions"] = [
            action.intent.action_type for action in local_overlay
        ]
        return visible

    def available_actions(
        self, entity_id: str, snapshot: dict[str, Any]
    ) -> Sequence[ActionSpec]:
        del entity_id, snapshot
        return self._SPECS

    def execute_read(
        self,
        action: BoundAction,
        snapshot: dict[str, Any],
        local_overlay: Sequence[BoundAction],
    ) -> ActionResult:
        if action.intent.action_type != "read_value":
            return ActionResult(action.action_id, ActionStatus.REJECTED, error_code="unknown_read")
        return ActionResult(
            action.action_id,
            ActionStatus.ACCEPTED,
            data=self.observe(action.entity_id, snapshot, local_overlay),
        )

    def validate_write(
        self,
        action: BoundAction,
        snapshot: dict[str, Any],
        local_overlay: Sequence[BoundAction],
    ) -> ActionResult:
        del snapshot, local_overlay
        action_type = action.intent.action_type
        if action_type == "add":
            amount = action.intent.parameters.get("amount")
            if not isinstance(amount, int):
                return ActionResult(action.action_id, ActionStatus.REJECTED, error_code="invalid_amount")
        elif action_type != "claim":
            return ActionResult(action.action_id, ActionStatus.REJECTED, error_code="unknown_write")
        return ActionResult(action.action_id, ActionStatus.ACCEPTED)

    def resolve_and_apply(
        self, snapshot: dict[str, Any], actions: Sequence[BoundAction]
    ) -> Sequence[CommitDecision]:
        next_state = deepcopy(snapshot)
        decisions: list[CommitDecision] = []
        for action in actions:
            if action.intent.action_type == "add":
                next_state["value"] += action.intent.parameters["amount"]
                result = ActionResult(action.action_id, ActionStatus.ACCEPTED)
            elif action.intent.action_type == "claim" and next_state["claimed_by"] is None:
                next_state["claimed_by"] = action.entity_id
                result = ActionResult(action.action_id, ActionStatus.ACCEPTED)
            elif action.intent.action_type == "claim":
                result = ActionResult(action.action_id, ActionStatus.SUPERSEDED, error_code="already_claimed")
            else:
                result = ActionResult(action.action_id, ActionStatus.FAILED, error_code="unvalidated_action")
            decisions.append(CommitDecision(action, result))
        self._state = next_state
        return tuple(decisions)

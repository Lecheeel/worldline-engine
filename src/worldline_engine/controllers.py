"""Replaceable controller implementations for tests, rules, and replay."""

from __future__ import annotations

import inspect
import json
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from .protocols import ActionIntent, Controller, FinishTurn, TurnContext
from .providers.base import CompletionRequest, ModelMessage, ModelProvider

ControllerDecision = ActionIntent | FinishTurn
Rule = Callable[[TurnContext], ControllerDecision | Awaitable[ControllerDecision]]


class RuleController(Controller):
    """Delegates each decision to a deterministic application-supplied rule."""

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


PromptBuilder = Callable[
    [TurnContext], Sequence[ModelMessage] | Awaitable[Sequence[ModelMessage]]
]


class LLMToolController(Controller):
    """Adapts one native model tool call at a time to an engine action intent.

    It intentionally has no provider-specific logic. A provider translates
    `ActionSpec` into a vendor schema and returns a normalized `ModelToolCall`.
    """

    def __init__(
        self,
        provider: ModelProvider,
        model: str,
        prompt_builder: PromptBuilder | None = None,
        temperature: float | None = 0.0,
        max_tokens: int | None = 512,
    ) -> None:
        if not model:
            raise ValueError("model must not be empty")
        self._provider = provider
        self._model = model
        self._prompt_builder = prompt_builder or self._default_prompt
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._request_count = 0
        self._usage: dict[str, int] = defaultdict(int)

    async def next_action(self, context: TurnContext) -> ControllerDecision:
        messages = self._prompt_builder(context)
        if inspect.isawaitable(messages):
            messages = await messages
        response = await self._provider.complete(
            CompletionRequest(
                model=self._model,
                messages=tuple(messages),
                tools=tuple(context.available_actions),
                temperature=self._temperature,
                max_tokens=self._max_tokens,
            )
        )
        self._request_count += 1
        for metric, value in response.usage.items():
            self._usage[metric] += value
        if not response.tool_calls:
            return FinishTurn("model_finished_without_tool_call")
        tool_call = response.tool_calls[0]
        return ActionIntent(
            action_type=tool_call.name,
            parameters=tool_call.arguments,
            client_ref=tool_call.call_id,
        )

    def dump_state(self) -> dict[str, Any]:
        return {"request_count": self._request_count, "usage": dict(self._usage)}

    def load_state(self, state: Any) -> None:
        if not isinstance(state, dict):
            raise ValueError("LLMToolController state must be a dictionary")
        request_count = state.get("request_count", 0)
        usage = state.get("usage", {})
        if not isinstance(request_count, int) or not isinstance(usage, dict):
            raise ValueError("LLMToolController state is invalid")
        if not all(isinstance(key, str) and isinstance(value, int) for key, value in usage.items()):
            raise ValueError("LLMToolController usage state is invalid")
        self._request_count = request_count
        self._usage = defaultdict(int, usage)

    @staticmethod
    def _default_prompt(context: TurnContext) -> Sequence[ModelMessage]:
        previous_result = None
        if context.previous_result is not None:
            previous_result = {
                "status": context.previous_result.status.value,
                "data": dict(context.previous_result.data),
                "error_code": context.previous_result.error_code,
                "error_message": context.previous_result.error_message,
            }
        return (
            ModelMessage(
                "system",
                "Choose at most one available world action. Use a function tool to act. "
                "If no action is appropriate, reply without a tool call.",
            ),
            ModelMessage(
                "user",
                json.dumps(
                    {
                        "observation": context.observation,
                        "previous_result": previous_result,
                        "remaining_actions": context.remaining_actions,
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            ),
        )

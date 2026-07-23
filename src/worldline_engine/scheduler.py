"""Deterministic turn selection policies."""

from __future__ import annotations

import hashlib
import random
from typing import Sequence

from .protocols import EntitySpec, Scheduler, TurnSpec


def _tick_seed(seed: int, tick_id: int) -> int:
    digest = hashlib.sha256(f"{seed}:{tick_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


class AllEntitiesScheduler(Scheduler):
    """Activates every enabled entity in stable entity-id order."""

    def select_turns(
        self,
        entities: Sequence[EntitySpec],
        tick_id: int,
        random_seed: int,
    ) -> Sequence[TurnSpec]:
        del tick_id, random_seed
        return tuple(
            TurnSpec(entity_id=entity.entity_id, turn_index=index)
            for index, entity in enumerate(
                sorted(
                    (entity for entity in entities if entity.enabled),
                    key=lambda entity: entity.entity_id,
                )
            )
        )


class RandomActivationScheduler(Scheduler):
    """Selects enabled entities using a reproducible tick-scoped RNG stream."""

    def __init__(self, activation_probability: float) -> None:
        if not 0.0 <= activation_probability <= 1.0:
            raise ValueError("activation_probability must be in [0, 1]")
        self.activation_probability = activation_probability

    def select_turns(
        self,
        entities: Sequence[EntitySpec],
        tick_id: int,
        random_seed: int,
    ) -> Sequence[TurnSpec]:
        rng = random.Random(_tick_seed(random_seed, tick_id))
        selected = [
            entity
            for entity in sorted(entities, key=lambda entity: entity.entity_id)
            if entity.enabled and rng.random() < self.activation_probability
        ]
        return tuple(
            TurnSpec(entity_id=entity.entity_id, turn_index=index)
            for index, entity in enumerate(selected)
        )

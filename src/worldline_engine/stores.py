"""Checkpoint stores. SQLite is local, durable, and the canonical MVP store."""

from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


class InMemoryStateStore:
    def __init__(self) -> None:
        self._checkpoints: dict[str, dict[str, Any]] = {}

    def save_checkpoint(
        self,
        simulation_id: str,
        tick_id: int,
        world_state: Any,
        controller_states: Mapping[str, Any],
        runtime_state: Mapping[str, Any],
    ) -> None:
        self._checkpoints[simulation_id] = deepcopy(
            {
                "tick_id": tick_id,
                "world_state": world_state,
                "controller_states": dict(controller_states),
                "runtime_state": dict(runtime_state),
            }
        )

    def load_latest_checkpoint(self, simulation_id: str) -> Mapping[str, Any] | None:
        checkpoint = self._checkpoints.get(simulation_id)
        return deepcopy(checkpoint) if checkpoint is not None else None


class SQLiteStateStore:
    """Stores one JSON-serializable checkpoint per simulation in SQLite."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoints (
                simulation_id TEXT NOT NULL,
                tick_id INTEGER NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (simulation_id, tick_id)
            )
            """
        )
        self._connection.commit()

    def save_checkpoint(
        self,
        simulation_id: str,
        tick_id: int,
        world_state: Any,
        controller_states: Mapping[str, Any],
        runtime_state: Mapping[str, Any],
    ) -> None:
        payload = json.dumps(
            {
                "tick_id": tick_id,
                "world_state": world_state,
                "controller_states": dict(controller_states),
                "runtime_state": dict(runtime_state),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        with self._connection:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO checkpoints(simulation_id, tick_id, payload_json)
                VALUES (?, ?, ?)
                """,
                (simulation_id, tick_id, payload),
            )

    def load_latest_checkpoint(self, simulation_id: str) -> Mapping[str, Any] | None:
        row = self._connection.execute(
            """
            SELECT payload_json FROM checkpoints
            WHERE simulation_id = ?
            ORDER BY tick_id DESC
            LIMIT 1
            """,
            (simulation_id,),
        ).fetchone()
        return None if row is None else json.loads(row[0])

    def close(self) -> None:
        self._connection.close()

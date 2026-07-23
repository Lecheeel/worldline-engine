"""Checkpoint stores. SQLite is local, durable, and the canonical MVP store."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class MemoryRecord:
    """Canonical, reconstructable memory. Embeddings are deliberately absent."""

    memory_id: str
    simulation_id: str
    person_id: str
    tick_id: int
    kind: str
    content: str
    importance: float = 0.0
    source_action_id: str | None = None


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


class SQLiteMemoryStore:
    """Canonical memory records stored alongside the experiment state.

    A sqlite-vec integration may index `memory_id` values from this table, but
    it must not be the only copy of a memory or its metadata.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_records (
                memory_id TEXT PRIMARY KEY,
                simulation_id TEXT NOT NULL,
                person_id TEXT NOT NULL,
                tick_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                importance REAL NOT NULL,
                source_action_id TEXT
            )
            """
        )
        self._connection.execute(
            """
            CREATE INDEX IF NOT EXISTS memory_records_lookup
            ON memory_records(simulation_id, person_id, tick_id)
            """
        )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_recalls (
                recall_id TEXT PRIMARY KEY,
                simulation_id TEXT NOT NULL,
                tick_id INTEGER NOT NULL,
                turn_id TEXT NOT NULL,
                person_id TEXT NOT NULL,
                query_text TEXT NOT NULL,
                memory_ids_json TEXT NOT NULL
            )
            """
        )
        self._connection.commit()

    def add(self, record: MemoryRecord) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO memory_records(
                    memory_id, simulation_id, person_id, tick_id, kind,
                    content, importance, source_action_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.memory_id,
                    record.simulation_id,
                    record.person_id,
                    record.tick_id,
                    record.kind,
                    record.content,
                    record.importance,
                    record.source_action_id,
                ),
            )

    def list_for_person(
        self, simulation_id: str, person_id: str, limit: int = 100
    ) -> list[MemoryRecord]:
        if limit < 1:
            raise ValueError("limit must be positive")
        rows = self._connection.execute(
            """
            SELECT memory_id, simulation_id, person_id, tick_id, kind,
                   content, importance, source_action_id
            FROM memory_records
            WHERE simulation_id = ? AND person_id = ?
            ORDER BY tick_id DESC, memory_id ASC
            LIMIT ?
            """,
            (simulation_id, person_id, limit),
        ).fetchall()
        return [MemoryRecord(*row) for row in rows]

    def get_by_ids(
        self,
        memory_ids: list[str],
        simulation_id: str,
        person_id: str,
    ) -> dict[str, MemoryRecord]:
        if not memory_ids:
            return {}
        placeholders = ",".join("?" for _ in memory_ids)
        rows = self._connection.execute(
            f"""
            SELECT memory_id, simulation_id, person_id, tick_id, kind,
                   content, importance, source_action_id
            FROM memory_records
            WHERE simulation_id = ? AND person_id = ?
              AND memory_id IN ({placeholders})
            """,
            (simulation_id, person_id, *memory_ids),
        ).fetchall()
        return {row[0]: MemoryRecord(*row) for row in rows}

    def record_recall(
        self,
        recall_id: str,
        simulation_id: str,
        tick_id: int,
        turn_id: str,
        person_id: str,
        query_text: str,
        memory_ids: list[str],
    ) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO memory_recalls(
                    recall_id, simulation_id, tick_id, turn_id, person_id,
                    query_text, memory_ids_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recall_id,
                    simulation_id,
                    tick_id,
                    turn_id,
                    person_id,
                    query_text,
                    json.dumps(memory_ids, separators=(",", ":")),
                ),
            )

    def list_recalls(self, simulation_id: str, person_id: str) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            """
            SELECT recall_id, tick_id, turn_id, query_text, memory_ids_json
            FROM memory_recalls
            WHERE simulation_id = ? AND person_id = ?
            ORDER BY tick_id ASC, recall_id ASC
            """,
            (simulation_id, person_id),
        ).fetchall()
        return [
            {
                "recall_id": row[0],
                "tick_id": row[1],
                "turn_id": row[2],
                "query": row[3],
                "memory_ids": json.loads(row[4]),
            }
            for row in rows
        ]

    def close(self) -> None:
        self._connection.close()

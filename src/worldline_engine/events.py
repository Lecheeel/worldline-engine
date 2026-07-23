"""Append-only event sinks. Events, unlike logs, are replayable facts."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from enum import Enum
from pathlib import Path

from .protocols import SimulationEvent


def _json_default(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


class MemoryEventSink:
    def __init__(self) -> None:
        self.events: list[SimulationEvent] = []

    def append(self, event: SimulationEvent) -> None:
        self.events.append(event)

    def close(self) -> None:
        return None


class JsonlEventSink:
    """Writes one immutable event record per JSONL line."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("a", encoding="utf-8")

    def append(self, event: SimulationEvent) -> None:
        self._file.write(json.dumps(asdict(event), default=_json_default) + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()


class SQLiteEventSink:
    """Persists replayable events in the experiment's SQLite database."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS simulation_events (
                event_id TEXT PRIMARY KEY,
                simulation_id TEXT NOT NULL,
                tick_id INTEGER NOT NULL,
                sequence INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                turn_id TEXT,
                action_id TEXT,
                entity_id TEXT,
                payload_json TEXT NOT NULL,
                UNIQUE (simulation_id, sequence)
            )
            """
        )
        self._connection.commit()

    def append(self, event: SimulationEvent) -> None:
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO simulation_events(
                    event_id, simulation_id, tick_id, sequence, event_type,
                    turn_id, action_id, entity_id, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.simulation_id,
                    event.tick_id,
                    event.sequence,
                    event.event_type,
                    event.turn_id,
                    event.action_id,
                    event.entity_id,
                    json.dumps(event.payload, default=_json_default, sort_keys=True),
                ),
            )

    def close(self) -> None:
        self._connection.close()

from __future__ import annotations

import asyncio
import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

from worldline_engine import (
    ActionIntent,
    AllEntitiesScheduler,
    EntitySpec,
    InMemoryStateStore,
    MemoryEventSink,
    MemoryRecord,
    ReplayController,
    RuleController,
    SQLiteStateStore,
    SQLiteEventSink,
    Simulation,
    SimulationConfig,
)
from worldline_engine.protocols import SimulationEvent
from worldline_engine.stores import SQLiteMemoryStore
from worldline_engine.vector import SQLiteVecMemoryIndex
from worldline_engine.worlds import CounterWorld


def make_simulation(
    *,
    config: SimulationConfig,
    controllers,
    world: CounterWorld | None = None,
    store=None,
    events=None,
) -> Simulation:
    return Simulation(
        config=config,
        entities=(
            EntitySpec("alice", "alice-controller"),
            EntitySpec("bob", "bob-controller"),
        ),
        controllers=controllers,
        scheduler=AllEntitiesScheduler(),
        world=world or CounterWorld(),
        state_store=store or InMemoryStateStore(),
        event_sink=events or MemoryEventSink(),
    )


class SimulationRuntimeTests(unittest.TestCase):
    def test_conflicts_are_deterministic_when_turn_concurrency_changes(self) -> None:
        def run_with(concurrency: int):
            sink = MemoryEventSink()
            world = CounterWorld()
            simulation = make_simulation(
                config=SimulationConfig(
                    simulation_id="deterministic",
                    max_concurrent_turns=concurrency,
                ),
                controllers={
                    "alice-controller": ReplayController({"alice": [ActionIntent("claim")]}),
                    "bob-controller": ReplayController({"bob": [ActionIntent("claim")]}),
                },
                world=world,
                events=sink,
            )
            asyncio.run(simulation.run())
            return world.state, [(event.event_type, event.payload) for event in sink.events]

        sequential_state, sequential_events = run_with(1)
        concurrent_state, concurrent_events = run_with(2)

        self.assertEqual({"value": 0, "claimed_by": "alice"}, sequential_state)
        self.assertEqual(sequential_state, concurrent_state)
        self.assertEqual(sequential_events, concurrent_events)

    def test_turn_reads_its_own_buffered_write_without_global_visibility(self) -> None:
        def rule(context):
            if context.previous_result is None:
                return ActionIntent("add", {"amount": 3})
            return ActionIntent("read_value")

        sink = MemoryEventSink()
        world = CounterWorld()
        simulation = Simulation(
            config=SimulationConfig("overlay", max_actions_per_turn=2),
            entities=(EntitySpec("alice", "controller"),),
            controllers={"controller": RuleController(rule)},
            scheduler=AllEntitiesScheduler(),
            world=world,
            state_store=InMemoryStateStore(),
            event_sink=sink,
        )

        asyncio.run(simulation.run())

        read_event = next(event for event in sink.events if event.event_type == "action_read")
        self.assertEqual(0, read_event.payload["result"]["data"]["value"])
        self.assertEqual(["add"], read_event.payload["result"]["data"]["pending_actions"])
        self.assertEqual(3, world.state["value"])

    def test_checkpoint_restore_matches_continuous_execution(self) -> None:
        actions = {"alice": [ActionIntent("add", {"amount": 2})], "bob": []}
        continuous_world = CounterWorld()
        continuous = make_simulation(
            config=SimulationConfig("continuous", max_ticks=2),
            controllers={
                "alice-controller": ReplayController(actions),
                "bob-controller": ReplayController(actions),
            },
            world=continuous_world,
        )
        asyncio.run(continuous.run())

        shared_store = InMemoryStateStore()
        first_world = CounterWorld()
        first_half = make_simulation(
            config=SimulationConfig("resumed", max_ticks=2),
            controllers={
                "alice-controller": ReplayController(actions),
                "bob-controller": ReplayController(actions),
            },
            world=first_world,
            store=shared_store,
        )
        asyncio.run(first_half.run(ticks=1))

        resumed_world = CounterWorld()
        resumed = make_simulation(
            config=SimulationConfig("resumed", max_ticks=2),
            controllers={
                "alice-controller": ReplayController(actions),
                "bob-controller": ReplayController(actions),
            },
            world=resumed_world,
            store=shared_store,
        )
        self.assertTrue(resumed.restore_latest_checkpoint())
        asyncio.run(resumed.run())

        self.assertEqual(continuous_world.state, resumed_world.state)

    def test_sqlite_checkpoint_is_persistent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "experiment.sqlite"
            store = SQLiteStateStore(path)
            store.save_checkpoint("run", 4, {"value": 2}, {"rule": {}}, {"next_tick": 5})
            store.close()

            reopened = SQLiteStateStore(path)
            checkpoint = reopened.load_latest_checkpoint("run")
            reopened.close()

        self.assertEqual(4, checkpoint["tick_id"])
        self.assertEqual({"value": 2}, checkpoint["world_state"])

    def test_sqlite_event_sink_and_memory_store_share_one_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "experiment.sqlite"
            events = SQLiteEventSink(path)
            memories = SQLiteMemoryStore(path)
            events.append(
                SimulationEvent(
                    event_id="run:event:1",
                    event_type="action_committed",
                    simulation_id="run",
                    tick_id=0,
                    sequence=1,
                    payload={"status": "accepted"},
                    entity_id="alice",
                )
            )
            memories.add(
                MemoryRecord(
                    memory_id="memory:1",
                    simulation_id="run",
                    person_id="alice",
                    tick_id=0,
                    kind="event",
                    content="Alice claimed the resource.",
                    importance=0.8,
                    source_action_id="run:0:0:0",
                )
            )
            events.close()
            memories.close()

            connection = sqlite3.connect(path)
            event_count = connection.execute("SELECT COUNT(*) FROM simulation_events").fetchone()[0]
            connection.close()

            reopened = SQLiteMemoryStore(path)
            records = reopened.list_for_person("run", "alice")
            reopened.close()

        self.assertEqual(1, event_count)
        self.assertEqual(["memory:1"], [record.memory_id for record in records])

    @unittest.skipUnless(importlib.util.find_spec("sqlite_vec"), "sqlite-vec extra is not installed")
    def test_sqlite_vec_indexes_canonical_memory_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "experiment.sqlite"
            memories = SQLiteMemoryStore(path)
            index = SQLiteVecMemoryIndex(path, dimensions=3)
            try:
                memories.add(
                    MemoryRecord("m1", "run", "alice", 0, "event", "first memory")
                )
                index.upsert("m1", [1.0, 0.0, 0.0])
                index.upsert("m2", [0.0, 1.0, 0.0])
                matches = index.search([0.9, 0.1, 0.0], limit=1)
            finally:
                index.close()
                memories.close()

        self.assertEqual(["m1"], [match.memory_id for match in matches])

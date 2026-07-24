from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from worldline_engine import (
    ActionIntent,
    AllEntitiesScheduler,
    EntitySpec,
    InMemoryStateStore,
    MemoryEventSink,
    ReplayController,
    RuleController,
    SQLiteStateStore,
    SQLiteEventSink,
    Simulation,
    SimulationConfig,
)
from worldline_engine.protocols import SimulationEvent
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

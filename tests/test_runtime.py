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

    def test_controller_failure_discards_prior_buffered_writes(self) -> None:
        calls = 0

        def failing_rule(_context):
            nonlocal calls
            calls += 1
            if calls == 1:
                return ActionIntent("add", {"amount": 5})
            raise RuntimeError("model unavailable")

        world = CounterWorld()
        sink = MemoryEventSink()
        simulation = Simulation(
            config=SimulationConfig("failure", max_actions_per_turn=2),
            entities=(EntitySpec("alice", "controller"),),
            controllers={"controller": RuleController(failing_rule)},
            scheduler=AllEntitiesScheduler(),
            world=world,
            state_store=InMemoryStateStore(),
            event_sink=sink,
        )
        asyncio.run(simulation.run())

        self.assertEqual({"value": 0, "claimed_by": None}, world.state)
        self.assertEqual("controller_error", next(event for event in sink.events if event.event_type == "controller_error").event_type)

    def test_turn_cost_budget_and_context_seed_are_deterministic(self) -> None:
        observed = []

        def rule(context):
            observed.append((context.remaining_cost, context.random_seed))
            return ActionIntent("add", {"amount": 1})

        config = SimulationConfig("budget", seed=77, max_actions_per_turn=2, max_cost_per_turn=1)
        world = CounterWorld()
        sink = MemoryEventSink()
        simulation = Simulation(
            config=config,
            entities=(EntitySpec("alice", "controller"),),
            controllers={"controller": RuleController(rule)},
            scheduler=AllEntitiesScheduler(),
            world=world,
            state_store=InMemoryStateStore(),
            event_sink=sink,
        )
        asyncio.run(simulation.run())

        self.assertEqual(1, world.state["value"])
        self.assertEqual([1, 0], [item[0] for item in observed])
        self.assertNotEqual(0, observed[0][1])
        self.assertEqual(observed[0][1], observed[1][1])
        self.assertEqual("cost_budget_exceeded", next(event for event in sink.events if event.event_type == "action_rejected").payload["result"]["error_code"])

    def test_turn_timeout_cancels_controller_without_writes(self) -> None:
        class SlowController:
            async def next_action(self, _context):
                await asyncio.sleep(0.05)
                return ActionIntent("add", {"amount": 1})

            def dump_state(self):
                return {}

            def load_state(self, _state):
                return None

        world = CounterWorld()
        sink = MemoryEventSink()
        simulation = Simulation(
            config=SimulationConfig("timeout", turn_timeout_seconds=0.001),
            entities=(EntitySpec("alice", "slow"),),
            controllers={"slow": SlowController()},
            scheduler=AllEntitiesScheduler(),
            world=world,
            state_store=InMemoryStateStore(),
            event_sink=sink,
        )
        asyncio.run(simulation.run())

        self.assertEqual({"value": 0, "claimed_by": None}, world.state)
        self.assertIn("turn_timeout", [event.event_type for event in sink.events])

    def test_commit_error_restores_world_snapshot(self) -> None:
        class ExplodingWorld(CounterWorld):
            def resolve_and_apply(self, snapshot, actions):
                self._state["value"] = 999
                raise RuntimeError("commit failed")

        world = ExplodingWorld()
        simulation = make_simulation(
            config=SimulationConfig("commit-error"),
            controllers={
                "alice-controller": ReplayController({"alice": [ActionIntent("add", {"amount": 1})]}),
                "bob-controller": ReplayController({"bob": []}),
            },
            world=world,
        )
        with self.assertRaises(RuntimeError):
            asyncio.run(simulation.run())
        self.assertEqual({"value": 0, "claimed_by": None}, world.state)

    def test_world_error_discards_turn_writes_and_isolated_as_event(self) -> None:
        class FailingValidationWorld(CounterWorld):
            calls = 0

            def validate_write(self, action, snapshot, local_overlay):
                self.calls += 1
                if self.calls == 2:
                    raise RuntimeError("validation backend failed")
                return super().validate_write(action, snapshot, local_overlay)

        world = FailingValidationWorld()
        sink = MemoryEventSink()
        simulation = Simulation(
            config=SimulationConfig("world-error", max_actions_per_turn=2),
            entities=(EntitySpec("alice", "controller"),),
            controllers={
                "controller": ReplayController(
                    {
                        "alice": [
                            ActionIntent("add", {"amount": 1}),
                            ActionIntent("add", {"amount": 2}),
                        ]
                    }
                )
            },
            scheduler=AllEntitiesScheduler(),
            world=world,
            state_store=InMemoryStateStore(),
            event_sink=sink,
        )
        asyncio.run(simulation.run())

        self.assertEqual(0, world.state["value"])
        world_error = next(event for event in sink.events if event.event_type == "world_error")
        self.assertEqual("validate_write", world_error.payload["stage"])

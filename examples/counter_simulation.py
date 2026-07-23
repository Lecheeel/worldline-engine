"""Run the protocol's minimal deterministic conflict example."""

from __future__ import annotations

import asyncio
from pathlib import Path

from worldline_engine import (
    ActionIntent,
    AllEntitiesScheduler,
    EntitySpec,
    ReplayController,
    SQLiteEventSink,
    SQLiteStateStore,
    Simulation,
    SimulationConfig,
)
from worldline_engine.worlds import CounterWorld


async def main() -> None:
    run_path = Path("runs/counter-example/experiment.sqlite")
    events = SQLiteEventSink(run_path)
    state_store = SQLiteStateStore(run_path)
    world = CounterWorld()
    simulation = Simulation(
        config=SimulationConfig("counter-example"),
        entities=(
            EntitySpec("alice", "alice"),
            EntitySpec("bob", "bob"),
        ),
        controllers={
            "alice": ReplayController({"alice": [ActionIntent("claim")]}),
            "bob": ReplayController({"bob": [ActionIntent("claim")]}),
        },
        scheduler=AllEntitiesScheduler(),
        world=world,
        state_store=state_store,
        event_sink=events,
    )
    try:
        await simulation.run()
        print(world.state)
    finally:
        events.close()
        state_store.close()


if __name__ == "__main__":
    asyncio.run(main())

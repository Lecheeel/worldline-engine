# Worldline Engine

Worldline Engine is a domain-neutral, deterministic and replayable discrete-time multi-agent simulation engine.

It owns execution semantics: tick and turn scheduling, immutable tick snapshots, turn-local write buffers, stable commit ordering, checkpoints, recovery, and append-only events. A `World` owns domain rules; a `Controller` proposes structured intents; the engine does not know whether an entity is a person, company, vehicle, or game character.

## Boundaries

The public contracts are `Simulation`, `EntitySpec`, `TurnContext`, `ActionIntent`, `ActionResult`, `World`, `Controller`, `Scheduler`, `StateStore`, and `EventSink`.

Worlds that need low-cost global state evolution may implement the optional
`advance_tick(tick_id)` lifecycle hook. The hook runs once after a successful
action commit, including ticks with no writes, and participates in snapshot
rollback if it fails.

The core package deliberately has no model SDK, embedding library, vector database, or social-domain module. Rule and replay controllers, memory/JSONL event sinks, and a standard-library SQLite checkpoint/event backend are included as generic infrastructure.

The social domain is developed independently in [Worldline Social](../worldline-social), which depends on this package and owns posts, relationships, recommendation, memory, providers, and social dynamics.

## Install and verify

Python 3.11 or newer is required.

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
python -m compileall -q src tests examples scripts
python -m pip wheel . --wheel-dir dist --no-deps
```

## Minimal usage

```python
from worldline_engine import Simulation, SimulationConfig

# Provide a Scheduler, Controller mapping, World, StateStore and EventSink.
simulation = Simulation(
    config=SimulationConfig("example"),
    entities=entities,
    controllers=controllers,
    scheduler=scheduler,
    world=world,
    state_store=state_store,
    event_sink=event_sink,
)
await simulation.run()
```

## Guarantees

- Every turn in a tick observes the same world snapshot.
- Uncommitted writes are visible only to their own turn.
- Buffered writes are submitted in stable order independent of concurrency.
- Turn action, controller-call, cost, repetition, failure, and timeout limits are explicit configuration.
- Controller or World failures discard the affected turn's buffered writes.
- A failed or malformed World commit restores the tick snapshot before propagating the error.
- Events are append-only facts and checkpoints contain world, controller, and runtime state.
- Replay can replace external controllers with recorded intents.

## License

Apache License 2.0. See [LICENSE](LICENSE).

# Worldline Engine

Worldline Engine 是与领域无关、确定性且可回放的多 Agent 离散时间仿真执行内核。它负责 tick 与 turn 调度、一致性快照、turn 局部写缓冲、稳定提交顺序、checkpoint、恢复和追加事件；`World` 负责领域规则，`Controller` 只提出结构化动作意图。

社会仿真实现位于独立公开仓库 [Worldline Social](https://github.com/Lecheeel/worldline-social)。Engine 不依赖 Social，也不包含帖子、人格、关系、推荐、LLM SDK、embedding 或向量数据库。

## 核心边界

稳定的公共契约包括 `Simulation`、`EntitySpec`、`TurnContext`、`ActionIntent`、`ActionResult`、`World`、`Controller`、`Scheduler`、`StateStore` 和 `EventSink`。

- 同一 tick 的所有 turn 从相同只读快照开始。
- 未提交的写入只对当前 turn 自己可见。
- 写入按稳定顺序提交，执行并发度不会改变提交结果。
- action、controller 调用、成本、重复动作、连续失败和 timeout 都有明确限制。
- Controller 或 World 失败会丢弃该 turn 已缓冲的写入。
- World 提交或 `advance_tick(tick_id)` 失败时，运行时恢复 tick 快照。
- checkpoint 保存 World、Controller 和运行时进度；事件是追加事实。

需要在每个成功 tick 后推进全局状态的领域 World 可以实现可选的 `advance_tick(tick_id)` hook。

## 安装与验证

要求 Python 3.11 或更高版本。

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
python -m compileall -q src tests examples scripts
python -m pip wheel . --wheel-dir dist --no-deps
```

## 最小使用示例

```python
from worldline_engine import Simulation, SimulationConfig

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

## 许可证

Apache License 2.0，详见 [LICENSE](LICENSE)。

---

## Overview

Worldline Engine is a domain-neutral, deterministic, replayable discrete-time multi-agent simulation execution core. It owns tick and turn scheduling, consistent snapshots, turn-local write buffers, stable commit order, checkpoints, recovery, and append-only events. `World` owns domain rules; `Controller` proposes structured intents.

The social domain lives in the separate public repository [Worldline Social](https://github.com/Lecheeel/worldline-social). Engine never depends on Social and contains no social semantics, model SDK, embedding library, or vector database.

## Guarantees

- All turns in a tick begin from one read-only snapshot.
- Pending writes are visible only within their originating turn.
- Stable commit order makes results independent of execution concurrency.
- Action, controller-call, cost, repetition, failure, and timeout limits are explicit.
- Controller and World failures discard buffered writes for the affected turn.
- Commit or tick-advance failures restore the tick snapshot.
- Checkpoints persist World, Controller, and runtime state; events are append-only facts.

Worlds may implement the optional `advance_tick(tick_id)` hook for deterministic global state evolution after a successful tick commit.

## Install and Verify

Python 3.11 or newer is required.

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
python -m compileall -q src tests examples scripts
python -m pip wheel . --wheel-dir dist --no-deps
```

## Minimal Usage

```python
from worldline_engine import Simulation, SimulationConfig

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

## License

Apache License 2.0. See [LICENSE](LICENSE).

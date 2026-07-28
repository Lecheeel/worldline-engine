# Worldline Engine

[![CI](https://github.com/Lecheeel/worldline-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/Lecheeel/worldline-engine/actions/workflows/ci.yml) [![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

> **让每一个“如果当时……”都能被运行、观察，并重新播放。**

Worldline Engine 是一个面向多 Agent 世界的确定性运行内核。它把一群拥有目标、规则和行动能力的实体，放进一个可以逐步推进的时间线里：每一轮发生什么、何时发生、如何提交、哪里失败，都有清晰而稳定的答案。

它不规定你要模拟什么。城市、市场、游戏世界、组织，或一群正在互相影响的人，都可以由上层项目定义自己的规则。Engine 只负责把这些规则可靠地推进下去，并留下足够完整的轨迹，让实验可以复现、比较和回放。

## 为什么是 Worldline

- **同样的起点，得到同样的世界**：确定性调度让实验结果可比较，而不是一次性运气。
- **时间真的向前走**：世界按 tick 推进，Agent 在各自的 turn 中行动，复杂过程因此变得可观察。
- **失败不会污染整个世界**：局部行动先暂存，只有通过规则检查才会提交。
- **随时暂停，之后继续**：checkpoint、恢复和追加事件让长实验不必从头开始。
- **领域保持自由**：引擎不绑定具体领域、模型供应商或数据库，领域规则由你的 World 决定。

## 快速开始

需要 Python 3.11 或更高版本：

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
```

Engine 本身不要求 LLM、embedding 或向量数据库。你可以先用规则或回放控制器跑通一个小世界，再按需要接入更复杂的 Agent。

想先看一个完整的最小闭环？从 [counter_simulation.py](examples/counter_simulation.py) 开始：两个实体在同一条时间线上行动，结果会被保存下来，并可以在之后继续检查或回放。

## 从一个问题开始

Worldline 适合把开放式的“如果……”变成可以反复比较的实验：如果行动顺序改变，结果还一样吗？如果中途暂停，世界能否从原处继续？如果把同一个规则放进另一个领域，它会呈现出什么样的秩序？

## 项目状态

这是一个持续演进中的开源项目，当前重点是稳定运行语义、可复现执行和清晰的领域边界。欢迎用它构建自己的实验世界，也欢迎通过 issue 和 pull request 分享想法。

## License

Apache License 2.0，详见 [LICENSE](LICENSE)。

---

## Overview

> **Run a world. Observe what happens. Replay the moment it changed.**

Worldline Engine is a deterministic execution core for multi-agent worlds. It places goal-driven entities inside a discrete timeline and gives every step a stable answer: what happened, when it happened, what was committed, and what failed.

The engine does not tell you what to simulate. A city, a market, a game, or an organization can define its own rules above the engine. Worldline Engine moves those rules forward reliably and preserves the trail needed to reproduce, compare, and replay an experiment.

## Why Worldline

- **Same starting point, same world**: deterministic scheduling makes runs comparable.
- **Time with structure**: ticks and turns make long-running interactions observable.
- **Isolated failure**: tentative actions are checked before they become world state.
- **Pause and resume**: checkpoints and event history make long experiments resumable.
- **Domain-neutral by design**: your World owns the meaning; the engine owns execution.

## Quick Start

Python 3.11 or newer is required:

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
```

## Start With a Question

Worldline turns open-ended “what if” questions into experiments you can compare: does changing action order change the outcome? Can a world continue from the exact moment it paused? What kind of order appears when the same execution rules meet a new domain?

No LLM, embedding, or vector database is required to get started. Begin with rules or replay, then add richer agents as your world needs them.

## Project Status

Worldline is evolving in the open, with current work focused on stable execution semantics, reproducible runs, and a clear boundary between the engine and domain worlds. Issues and pull requests are welcome.

## License

Apache License 2.0. See [LICENSE](LICENSE).

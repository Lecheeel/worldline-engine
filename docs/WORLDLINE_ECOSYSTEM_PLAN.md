# Worldline 项目拆分与实施规划

状态：实施中。`worldline-engine` 已完成核心收敛和第二阶段失败/预算语义，`worldline-social` 已建立独立公开仓库、最小 SocialWorld、PopulationManifest 和版本化 SocialState。

## 1. 项目关系

未来维护两个独立仓库，并保持单向依赖：

```text
worldline-engine
        ^
        |
worldline-social
```

- `worldline-engine` 是与领域无关的多 Agent 离散时间仿真执行内核。
- `worldline-social` 是基于引擎实现的全新社会仿真系统。
- 桌面上的 OASIS 项目只作为需求、实验和设计经验参考，不迁移其代码、API 或数据库 schema。

## 2. Worldline Engine 边界

引擎只负责：

- tick、turn 和调度；
- 一致性快照与 turn 局部写缓冲；
- ActionIntent、ActionResult 和通用动作协议；
- World 校验、冲突解决和确定性提交；
- Controller 生命周期、预算和失败隔离；
- checkpoint、恢复、事件和回放；
- 通用 `StateStore` 与 `EventSink` 协议。

核心协议包括 `Simulation`、`EntitySpec`、`TurnContext`、`ActionIntent`、`ActionResult`、`World`、`Controller`、`Scheduler`、`StateStore` 和 `EventSink`。

核心引擎不得依赖：

- 社会领域模型；
- 人格、情绪、信任、立场和关系语义；
- 帖子、评论、推荐、搜索和群聊；
- LLM SDK、embedding、向量数据库；
- OASIS 的 API、Camel Agent 或现有数据库 schema。

通用的内存存储、JSONL 事件和基于标准库 SQLite 的 checkpoint/event 实现可以保留在引擎中。记忆、embedding、向量索引和模型供应商适合作为扩展层，首阶段放在 `worldline-social`。

## 3. Worldline Social 边界

`worldline-social` 从零设计，不作为 OASIS 的兼容重构。建议分为：

```text
Population       人口清单、身份和初始化
SocialWorld      帖子、评论、关系、搜索、推荐和信息分发
SocialDynamics   人格、情绪、信任、立场和社会影响
Controllers      Rule、LLM、Replay、Prompt、记忆和 Provider
Experiments      配置、运行入口、分析和可视化
```

建议优先稳定三份领域契约：

1. `PopulationManifest`：外部人口如何导入；
2. `SocialAction`：动作名称、参数、读写类型、权限、预算和结果；
3. `SocialState`：帖子、关系、人格和动态状态如何保存、恢复和演进。

## 4. 调用方式

社会项目依赖已发布的 `worldline-engine`，实现引擎协议后组装运行：

```python
simulation = Simulation(
    config=config,
    entities=entities,
    controllers=controllers,
    scheduler=scheduler,
    world=SocialWorld(...),
    state_store=state_store,
    event_sink=event_sink,
)
await simulation.run()
```

引擎只处理结构化动作，不解释 `create_post`、`trust` 或 `personality` 的业务含义。`worldline-engine` 不得反向导入 `worldline-social`。

## 5. 迁移与实施顺序

1. 冻结当前引擎协议并发布第一个稳定开发版本。
2. 从引擎移出 `memory.py`、`vector.py`、`providers/` 及 DeepSeek 适配器。
3. 创建 `worldline-social`，先实现最小 `SocialWorld`。
4. 用 RuleController 跑通人物、帖子、评论、feed、tick、checkpoint、restore 和 replay。
5. 再加入关系、推荐、人口导入和社会动态模型。
6. 最后加入 LLM、记忆、embedding、向量召回和大规模执行。
7. 为 SocialWorld 增加引擎协议 conformance/integration tests。

第一条验收闭环：

```text
导入少量人物 -> 发帖/评论 -> tick 提交 -> checkpoint -> restore/replay
```

## 6. OASIS 的使用方式

OASIS 只提供参考：

- 动作目录和社会平台功能范围；
- 推荐系统和信息分发的实验思路；
- 数据 schema 和实验样例；
- 大规模执行中的性能经验。

不直接继承其 `SocialAgent`、`Platform`、Camel 模型耦合、数据库直读写、实时钟和并发动作语义。

## 7. 正式实施前需要确认的决策

以下事项会影响第一版设计，但目前不阻塞规划保存：

- `worldline-social` 的仓库位置、许可证和是否公开；
- `worldline-engine` 的首个正式版本号与 Python 支持范围；
- 引擎是否保留通用 SQLite checkpoint/event 实现；
- 第一版 SocialWorld 的最小动作集合；
- 人口清单的首版格式（JSON、YAML 或 Python API）；
- 是否优先支持单机恢复/replay，再考虑批量和分布式。

默认建议：两个公开独立仓库；引擎先保持 Python 3.11+；保留通用 SQLite 运行存储；SocialWorld 首版只做帖子、评论、feed 和点赞；先完成单机确定性和恢复语义。

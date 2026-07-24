# Worldline Engine Project Rules

本文件是 `worldline-engine` 的项目级协作规范。用户指令优先于本文件；
本文件优先于默认工程习惯。项目面向 GitHub 发布，默认分支固定为 `main`。

## 项目边界

- `runtime.py` 只管理执行语义，不依赖模型 SDK、向量数据库 SDK 或具体领域。
- `World` 是领域规则唯一所有者；`Controller` 只提出 `ActionIntent`。
- 模型供应商、Prompt、记忆和向量索引属于上层项目，不进入本仓库。
- SQLite 保存实验事实、状态、事件、原始记忆和召回审计；`sqlite-vec` 只是可重建索引。
- 不把 API key、完整凭据或私有请求对象写入事件、checkpoint、日志或测试文件。

## 本地命令

- 安装：`python -m pip install -e .`
- 测试：`python -m unittest discover -s tests -v`
- 静态检查：`python -m compileall -q src tests examples scripts`
- 格式化：当前没有配置格式化工具，不得声称已运行格式化。
- 构建：`python -m pip wheel . --wheel-dir dist --no-deps`

## 模块与测试

- 新增领域能力必须实现或扩展 `World`，不能把领域判断写进运行时。
- 新增领域或模型能力应放入使用本引擎的上层仓库。
- 影响 tick、快照、提交、回放、checkpoint 或召回语义时，必须运行完整测试集。
- 外部 API smoke test 使用临时环境变量，不能将密钥写入项目或输出。
- 生成的 `runs/`、SQLite、缓存、wheel 和日志不得提交。

## Git 约定

- 仓库默认分支为 `main`；首次初始化使用 `git init -b main`。
- 提交使用英文 Conventional Commits，例如：
  `feat(runtime): add deterministic turn budgets`。
- 提交前检查 `git diff --check`、`.gitignore` 和待提交文件。
- 不自动重写历史、不使用 destructive reset、不在未确认远端设置时推送。

## GitHub 发布

- 创建仓库前确认可见性、名称、描述、许可证和 Topics。
- Description 使用：`中文描述 | English description`。
- README 中文章节在上、英文章节在下，命令和能力说明保持一致。
- 首次推送必须明确使用 `main`，并设置上游：`git push -u origin main`。
- 发布前扫描密钥、私有配置、实验数据库、构建产物和 IDE 文件。

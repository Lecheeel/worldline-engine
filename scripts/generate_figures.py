"""Generate publication-style diagrams used by the README."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


plt.rcParams["font.family"] = "Noto Sans SC"
plt.rcParams["axes.unicode_minus"] = False


ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "docs" / "figures"


def box(ax, xy, width, height, title, detail, *, face="#f7f9fc", edge="#243447"):
    x, y = xy
    patch = FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0.012,rounding_size=0.02",
        linewidth=1.1, edgecolor=edge, facecolor=face,
    )
    ax.add_patch(patch)
    ax.text(x + width / 2, y + height * 0.64, title, ha="center", va="center",
            fontsize=10, fontweight="bold", color="#17202a")
    ax.text(x + width / 2, y + height * 0.30, detail, ha="center", va="center",
            fontsize=8.2, color="#34495e", linespacing=1.25)


def arrow(ax, start, end, *, color="#52606d", style="-|>"):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle=style, mutation_scale=12,
                                 linewidth=1.0, color=color, connectionstyle="arc3"))


def finish(ax, title, filename, *, xlim=(0, 10), ylim=(0, 6)):
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", pad=12)
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig = ax.figure
    fig.savefig(FIGURES / filename, format="svg", bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)


def architecture():
    fig, ax = plt.subplots(figsize=(11, 5.8), dpi=160)
    ax.add_patch(Rectangle((0.25, 0.35), 9.5, 5.05, facecolor="#fbfcfe",
                           edgecolor="#9aa5b1", linewidth=1.0, linestyle="--"))
    ax.text(0.5, 5.1, "WORLDLINE ENGINE EXECUTION CORE", fontsize=9,
            color="#52606d", fontweight="bold")

    box(ax, (0.7, 3.72), 2.1, 0.95, "Scheduler", "turn selection\nactivation policy", face="#e8f1fb")
    box(ax, (3.25, 3.72), 2.5, 0.95, "Simulation Runtime", "snapshot | budget | overlay\ndeterministic commit", face="#e8f1fb")
    box(ax, (6.2, 3.72), 2.15, 0.95, "Controller", "Rule / Replay / LLM\nActionIntent", face="#edf6f0")
    box(ax, (8.85, 3.72), 0.75, 0.95, "World", "validate", face="#fff4e5")
    arrow(ax, (2.8, 4.2), (3.2, 4.2))
    arrow(ax, (5.8, 4.2), (6.15, 4.2))
    arrow(ax, (8.4, 4.2), (8.8, 4.2))

    box(ax, (1.0, 1.45), 2.3, 1.0, "StateStore", "SQLite state + checkpoints\ncanonical experiment facts", face="#f4effa")
    box(ax, (3.85, 1.45), 2.3, 1.0, "EventSink", "JSONL / SQLite\nappend-only events", face="#f4effa")
    box(ax, (6.7, 1.45), 2.3, 1.0, "Extension Layer", "domain adapters\noptional integrations", face="#f4effa")
    arrow(ax, (9.2, 3.68), (8.0, 2.52), color="#7b8794")
    arrow(ax, (4.5, 3.68), (2.2, 2.52), color="#7b8794")
    arrow(ax, (4.6, 3.68), (5.0, 2.52), color="#7b8794")
    arrow(ax, (6.95, 3.68), (7.8, 2.52), color="#7b8794")
    ax.text(0.65, 0.72, "Solid arrows: execution flow    Dashed boundary: replaceable domain and provider extensions",
            fontsize=8.2, color="#52606d")
    finish(ax, "Figure 1. Layered execution architecture", "architecture.svg")


def world_structure():
    world_structure_language("zh")
    world_structure_language("en")


def world_structure_language(language: str):
    """Render a clean swimlane diagram in one language."""
    is_zh = language == "zh"
    labels = {
        "title": "Worldline Engine 世界结构" if is_zh else "Worldline Engine World Structure",
        "flow": "一个 Tick 的确定性执行流程" if is_zh else "Deterministic execution of one tick",
        "support": "状态与持久化支撑" if is_zh else "State and persistence support",
        "simulation": ("Simulation", "启动 / 恢复\n推进当前 tick") if is_zh else ("Simulation", "run / resume\nadvance tick"),
        "scheduler": ("Scheduler", "选择启用的 Agent") if is_zh else ("Scheduler", "select enabled agents"),
        "turn": ("Turn", "一个 Agent 的行动回合") if is_zh else ("Turn", "one agent action turn"),
        "controller": ("Controller", "读取观察\n提出 ActionIntent") if is_zh else ("Controller", "read observation\npropose ActionIntent"),
        "world": ("World", "读取 / 校验\n领域规则") if is_zh else ("World", "read / validate\ndomain rules"),
        "commit": ("Commit", "稳定顺序提交\n产生 ActionResult") if is_zh else ("Commit", "stable ordered commit\nproduce ActionResult"),
        "snapshot": ("Tick Snapshot", "所有 Turn 共享的\n只读世界快照") if is_zh else ("Tick Snapshot", "read-only world state\nshared by all turns"),
        "store": ("StateStore", "checkpoint\n恢复运行时状态") if is_zh else ("StateStore", "checkpoint\nrestore runtime state"),
        "events": ("EventSink", "追加事实\n审计与回放轨迹") if is_zh else ("EventSink", "append-only facts\naudit and replay trail"),
        "next": "进入下一个 Tick" if is_zh else "advance to next tick",
        "legend": "实线：执行流    虚线：状态与持久化" if is_zh else "Solid: execution flow    Dashed: state and persistence",
    }
    fig, ax = plt.subplots(figsize=(13, 5.7), dpi=180)
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 5.7)
    ax.axis("off")
    ax.set_facecolor("#ffffff")
    fig.patch.set_facecolor("#ffffff")

    ax.text(0.35, 5.35, labels["title"], fontsize=16, fontweight="bold", color="#17202a")
    ax.text(0.35, 5.02, labels["flow"], fontsize=10, color="#52606d")
    ax.add_patch(Rectangle((0.25, 2.7), 12.5, 2.0, facecolor="#f5f9fd", edgecolor="#b8c4cf", linewidth=1.0))
    ax.add_patch(Rectangle((0.25, 0.55), 12.5, 1.65, facecolor="#fbf8fd", edgecolor="#c9c0d6", linewidth=1.0))
    ax.text(0.5, 4.43, labels["flow"], fontsize=9, fontweight="bold", color="#34495e")
    ax.text(0.5, 1.94, labels["support"], fontsize=9, fontweight="bold", color="#5c4b6e")

    nodes = [
        (0.55, labels["simulation"], "#e4effa"),
        (2.55, labels["scheduler"], "#e4effa"),
        (4.55, labels["turn"], "#edf6f0"),
        (6.55, labels["controller"], "#edf6f0"),
        (8.55, labels["world"], "#fff4e5"),
        (10.55, labels["commit"], "#fff4e5"),
    ]
    for x, (title, detail), face in nodes:
        box(ax, (x, 3.25), 1.55, 0.82, title, detail, face=face)
    for x in (2.1, 4.1, 6.1, 8.1, 10.1):
        arrow(ax, (x, 3.66), (x + 0.38, 3.66))

    support_nodes = [
        (1.0, labels["snapshot"], "#ffffff"),
        (4.25, labels["store"], "#ffffff"),
        (7.5, labels["events"], "#ffffff"),
    ]
    for x, (title, detail), face in support_nodes:
        box(ax, (x, 0.92), 2.35, 0.72, title, detail, face=face)
    # Dashed support relationships avoid crossing the main flow.
    for start, end in [((1.32, 3.22), (2.0, 1.68)), ((9.33, 3.22), (5.35, 1.68)), ((10.95, 3.22), (8.6, 1.68))]:
        ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=10,
                                     linewidth=1.0, linestyle=(0, (4, 3)), color="#8b98a5"))
    ax.text(10.55, 1.12, labels["next"], fontsize=8.5, color="#52606d")
    ax.text(0.35, 0.18, labels["legend"], fontsize=8.5, color="#52606d")

    filename = "world-structure-zh.svg" if is_zh else "world-structure-en.svg"
    finish(ax, labels["title"], filename, xlim=(0, 13), ylim=(0, 5.7))


if __name__ == "__main__":
    architecture()
    world_structure()

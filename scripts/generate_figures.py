"""Generate publication-style diagrams used by the README."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


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
    """Show the lifecycle of one deterministic tick and its boundaries."""
    fig, ax = plt.subplots(figsize=(12, 7.0), dpi=160)
    ax.set_facecolor("#ffffff")

    # Outer execution boundary and the two phases inside each tick.
    ax.add_patch(FancyBboxPatch(
        (0.35, 0.35), 11.3, 6.15,
        boxstyle="round,pad=0.02,rounding_size=0.04",
        linewidth=1.1, edgecolor="#8b98a5", facecolor="#fbfcfe",
    ))
    ax.text(0.62, 6.18, "WORLDLINE ENGINE", fontsize=10, fontweight="bold", color="#52606d")
    ax.add_patch(FancyBboxPatch(
        (0.65, 3.2), 10.7, 2.55,
        boxstyle="round,pad=0.018,rounding_size=0.03",
        linewidth=1.0, edgecolor="#b8c4cf", facecolor="#eef5fb",
    ))
    ax.text(0.92, 5.48, "ONE TICK: read, act, validate, commit", fontsize=9,
            fontweight="bold", color="#34495e")
    ax.add_patch(FancyBboxPatch(
        (0.65, 0.72), 10.7, 2.05,
        boxstyle="round,pad=0.018,rounding_size=0.03",
        linewidth=1.0, edgecolor="#c9c0d6", facecolor="#f7f3fa",
    ))
    ax.text(0.92, 2.52, "PERSISTENCE AND REPLAY", fontsize=9,
            fontweight="bold", color="#5c4b6e")

    # Tick execution path.
    box(ax, (0.95, 4.2), 1.75, 0.9, "Simulation", "run / resume\ncurrent tick", face="#e4effa")
    box(ax, (3.0, 4.2), 1.75, 0.9, "Scheduler", "select enabled\nentities", face="#e4effa")
    box(ax, (5.05, 4.2), 1.75, 0.9, "Turn", "one Agent\ncontext + budget", face="#edf6f0")
    box(ax, (7.1, 4.2), 1.75, 0.9, "Controller", "observe\npropose intent", face="#edf6f0")
    box(ax, (9.15, 4.2), 1.75, 0.9, "World", "read / validate\napply domain rules", face="#fff4e5")
    arrow(ax, (2.75, 4.65), (2.95, 4.65))
    arrow(ax, (4.8, 4.65), (5.0, 4.65))
    arrow(ax, (6.85, 4.65), (7.05, 4.65))
    arrow(ax, (8.9, 4.65), (9.1, 4.65))

    # Turn internals and the stable commit loop.
    box(ax, (2.0, 3.42), 2.15, 0.62, "Agent / Entity", "TurnContext + observation", face="#f1f7f2")
    box(ax, (4.75, 3.42), 2.15, 0.62, "ActionIntent", "local write buffer", face="#f1f7f2")
    box(ax, (7.5, 3.42), 2.15, 0.62, "Commit", "stable action order\nActionResult", face="#fff4e5")
    arrow(ax, (5.9, 4.16), (3.2, 4.08), color="#7b8794")
    arrow(ax, (4.2, 3.73), (4.7, 3.73), color="#7b8794")
    arrow(ax, (6.95, 3.73), (7.45, 3.73), color="#7b8794")
    arrow(ax, (8.6, 4.16), (9.35, 4.16), color="#7b8794")

    # Persistence and replay surfaces.
    box(ax, (1.0, 1.18), 2.5, 0.82, "Tick Snapshot", "read-only world state\nshared by all turns", face="#ffffff")
    box(ax, (4.05, 1.18), 2.5, 0.82, "StateStore", "checkpoint\nrestore runtime state", face="#ffffff")
    box(ax, (7.1, 1.18), 2.5, 0.82, "EventSink", "append-only facts\nreplay / audit trail", face="#ffffff")
    box(ax, (10.0, 1.18), 1.05, 0.82, "World", "restore", face="#fff4e5")
    arrow(ax, (1.85, 4.16), (2.0, 2.08), color="#8b98a5", style="-|>")
    arrow(ax, (8.0, 3.38), (5.3, 2.08), color="#8b98a5", style="-|>")
    arrow(ax, (8.85, 3.38), (8.35, 2.08), color="#8b98a5", style="-|>")
    arrow(ax, (9.95, 3.38), (10.35, 2.08), color="#8b98a5", style="-|>")
    ax.text(1.0, 0.9, "Solid arrows: execution flow    Gray arrows: state, checkpoint, and event boundaries",
            fontsize=8.2, color="#52606d")
    finish(ax, "Figure 2. Deterministic world structure", "world-structure.svg", xlim=(0, 12), ylim=(0, 7))


if __name__ == "__main__":
    architecture()
    world_structure()

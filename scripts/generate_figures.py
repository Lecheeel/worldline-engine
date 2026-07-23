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
    box(ax, (6.7, 1.45), 2.3, 1.0, "Memory Layer", "embedding + recall\nSQLite + sqlite-vec", face="#f4effa")
    arrow(ax, (9.2, 3.68), (8.0, 2.52), color="#7b8794")
    arrow(ax, (4.5, 3.68), (2.2, 2.52), color="#7b8794")
    arrow(ax, (4.6, 3.68), (5.0, 2.52), color="#7b8794")
    arrow(ax, (6.95, 3.68), (7.8, 2.52), color="#7b8794")
    ax.text(0.65, 0.72, "Solid arrows: execution flow    Dashed boundary: replaceable domain and provider extensions",
            fontsize=8.2, color="#52606d")
    finish(ax, "Figure 1. Layered execution architecture", "architecture.svg")


def memory_pipeline():
    fig, ax = plt.subplots(figsize=(11, 4.9), dpi=160)
    ax.add_patch(Rectangle((0.3, 0.45), 9.4, 3.75, facecolor="#fbfcfe",
                           edgecolor="#9aa5b1", linewidth=1.0, linestyle="--"))
    ax.text(0.55, 3.92, "MEMORY RETRIEVAL AND REPLAY AUDIT PATH", fontsize=9,
            color="#52606d", fontweight="bold")
    box(ax, (0.65, 2.2), 1.55, 0.95, "Query", "person-scoped\ntext query", face="#e8f1fb")
    box(ax, (2.55, 2.2), 1.65, 0.95, "Embedding", "provider-specific\nvector", face="#e8f1fb")
    box(ax, (4.55, 2.2), 1.65, 0.95, "sqlite-vec", "nearest neighbors\nmemory_id only", face="#edf6f0")
    box(ax, (6.55, 2.2), 2.3, 0.95, "Canonical SQLite", "memory text + metadata\nrecall audit records", face="#f4effa")
    box(ax, (3.45, 0.75), 2.3, 0.95, "Context Builder", "ranked memories\nmodel-ready messages", face="#fff4e5")
    box(ax, (6.55, 0.75), 2.3, 0.95, "Controller", "LLM tool-call\ndecision", face="#fff4e5")
    arrow(ax, (2.25, 2.68), (2.5, 2.68))
    arrow(ax, (4.25, 2.68), (4.5, 2.68))
    arrow(ax, (6.25, 2.68), (6.5, 2.68))
    arrow(ax, (7.7, 2.18), (5.45, 1.78))
    arrow(ax, (5.8, 1.22), (6.45, 1.22))
    ax.annotate("audit: query + selected memory_id", xy=(5.95, 2.35), xytext=(5.8, 3.65),
                ha="center", fontsize=8, color="#7b8794",
                arrowprops={"arrowstyle": "-[", "linewidth": 0.8, "color": "#7b8794"})
    ax.text(0.65, 0.1, "Canonical text is the replay source; the vector index is rebuildable.",
            fontsize=8.2, color="#52606d")
    finish(ax, "Figure 2. Memory retrieval, context assembly, and auditability", "memory-pipeline.svg",
           ylim=(0, 4.7))


if __name__ == "__main__":
    architecture()
    memory_pipeline()

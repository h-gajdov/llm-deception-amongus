from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .ingest import iter_game_summaries


_IMPOSTOR_WIN = 1


@dataclass
class ExperimentStats:
    name: str
    path: Path
    num_games: int = 0
    impostor_wins: int = 0
    crewmate_wins: int = 0
    by_reason: Counter[str] = field(default_factory=Counter)


@dataclass
class DatasetStats:
    root: Path
    experiments: list[ExperimentStats] = field(default_factory=list)

    @property
    def total_games(self) -> int:
        return sum(e.num_games for e in self.experiments)

    @property
    def total_impostor_wins(self) -> int:
        return sum(e.impostor_wins for e in self.experiments)

    @property
    def total_crewmate_wins(self) -> int:
        return sum(e.crewmate_wins for e in self.experiments)

    def reason_totals(self) -> Counter[str]:
        merged: Counter[str] = Counter()
        for exp in self.experiments:
            merged.update(exp.by_reason)
        return merged


def find_summary_files(root: str | Path) -> list[Path]:
    root = Path(root)
    if (root / "summary.json").exists():
        return [root / "summary.json"]
    return sorted(root.rglob("summary.json"))


def compute_experiment_stats(summary_path: Path) -> ExperimentStats:
    stats = ExperimentStats(name=summary_path.parent.name, path=summary_path.parent)
    for _game_index, summary in iter_game_summaries(summary_path):
        stats.num_games += 1
        if summary.winner == _IMPOSTOR_WIN:
            stats.impostor_wins += 1
        else:
            stats.crewmate_wins += 1
        stats.by_reason[summary.winner_reason] += 1
    return stats


def compute_dataset_stats(root: str | Path) -> DatasetStats:
    root = Path(root)
    experiments = [compute_experiment_stats(p) for p in find_summary_files(root)]
    experiments.sort(key=lambda e: e.name)
    return DatasetStats(root=root, experiments=experiments)


def render_stats_text(stats: DatasetStats) -> str:
    lines = [f"Dataset 1 (game rollouts): {stats.root}", "─" * 60]
    if not stats.experiments:
        lines.append("No experiments found (looked for summary.json files).")
        return "\n".join(lines)

    lines.append(f"Experiments: {len(stats.experiments)}")
    lines.append(f"Total games: {stats.total_games}")
    lines.append("")
    lines.append("Per experiment:")
    width = max(len(e.name) for e in stats.experiments)
    for exp in stats.experiments:
        lines.append(
            f"  {exp.name:<{width}}  {exp.num_games:>5} games   "
            f"(impostors {exp.impostor_wins} / crewmates {exp.crewmate_wins})"
        )

    total = stats.total_games
    if total:
        imp, crew = stats.total_impostor_wins, stats.total_crewmate_wins
        lines.append("")
        lines.append("Win breakdown (all games):")
        lines.append(f"  Impostors: {imp:>5} ({100 * imp / total:5.1f}%)")
        lines.append(f"  Crewmates: {crew:>5} ({100 * crew / total:5.1f}%)")
        lines.append("By reason:")
        for reason, count in stats.reason_totals().most_common():
            lines.append(f"  {count:>5}  {reason}")
    return "\n".join(lines)


__all__ = [
    "DatasetStats",
    "ExperimentStats",
    "compute_dataset_stats",
    "compute_experiment_stats",
    "find_summary_files",
    "render_stats_text",
]

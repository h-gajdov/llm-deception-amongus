

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

DEFAULT = Path("expt-logs/qwen3_8b_selfplay_50_games/summary.json")


def main() -> None:
    pass
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    if not path.exists():
        sys.exit(f"No such file: {path}")

    games = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            games.append(next(iter(json.loads(line).values())))

    winners = Counter(g.get("winner_reason", "unknown") for g in games)
    impostors = Counter(
        sum(1 for k, v in g.items() if k.startswith("Player") and v["identity"] == "Impostor")
        for g in games
    )

    print(f"Dataset: {path}")
    print(f"Total games: {len(games)}")
    print("\nOutcomes:")
    for reason, n in winners.most_common():
        print(f"  {n:>4}  {reason}")
    print("\nImpostors per game:")
    for count, n in sorted(impostors.items()):
        print(f"  {count} impostors: {n} games")


if __name__ == "__main__":
    main()

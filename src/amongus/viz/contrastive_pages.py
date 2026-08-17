

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import Any

from ..logging import get_logger
from .contrastive_viz import build_pairs, load_contrastive_splits, summarize

logger = get_logger()

                                                                            
                                                                               
                                                                   
DEFAULT_PAIR_LIMIT = 600

                                                                              
                                             
SPLIT_ORDER = ("train", "test")

_HONEST = "honest"
_DISHONEST = "dishonest"
_SIDES = (_HONEST, _DISHONEST)


def collect_contrastive_page(
    dataset_dir: str | Path, *, pair_limit: int = DEFAULT_PAIR_LIMIT
) -> dict[str, Any] | None:
    pass
    root = Path(dataset_dir)
    if not root.exists():
        logger.info("No contrastive dataset at {}; the site's data page is omitted.", root)
        return None
    try:
        splits = load_contrastive_splits(root)
    except (FileNotFoundError, ImportError, OSError, ValueError) as exc:
        logger.warning("Skipping the contrastive page: {}", exc)
        return None

    rows = [{**row, "split": name} for name, rows in _ordered(splits) for row in rows]
    if not rows:
        logger.warning("Skipping the contrastive page: {} holds no rows.", root)
        return None

    pairs = _sorted_pairs(rows)
    personas, index = _personas(rows)
    shown = _thin(pairs, pair_limit)

    logger.info(
        "Contrastive page: {} example(s), {} pair(s) ({} embedded) from {}",
        len(rows),
        len(pairs),
        len(shown),
        root,
    )
    return {
        "path": str(root),
        "total": len(rows),
        "stats": summarize(rows),
        "splits": _splits(rows),
        "sources": _sources(rows, pairs),
        "personas": personas,
        "pairs_total": len(pairs),
        "pairs_shown": len(shown),
                                                                                     
                                                                             
        "complete_pairs": sum(1 for pair in pairs if _complete(pair)),
        "alternates": len(rows) - sum(1 for pair in pairs for side in _SIDES if pair[side]),
                                                                              
                                       
        "cross_split_pairs": sum(1 for pair in pairs if _straddles(pair)),
        "pairs": [_pair(pair, index) for pair in shown],
    }


def _ordered(splits: dict[str, list[dict[str, Any]]]) -> list[tuple[str, list[dict[str, Any]]]]:
    pass
    known = [(name, splits[name]) for name in SPLIT_ORDER if name in splits]
    extra = [(name, rows) for name, rows in splits.items() if name not in SPLIT_ORDER]
    return known + extra


def _complete(pair: dict[str, Any]) -> bool:
    pass
    return bool(pair[_HONEST]) and bool(pair[_DISHONEST])


def _straddles(pair: dict[str, Any]) -> bool:
    pass
    if not _complete(pair):
        return False
    return pair[_HONEST].get("split") != pair[_DISHONEST].get("split")


def _sorted_pairs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pass
    pairs = build_pairs(rows)
    return sorted(pairs, key=lambda pair: (str(pair["source"]), _index(str(pair["key"]))))


def _index(key: str) -> tuple[int, str]:
    pass
    tail = key.rsplit("-", 1)[-1]
    return (int(tail), "") if tail.isdigit() else (0, key)


def _thin(pairs: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    pass
    if limit <= 0 or len(pairs) <= limit:
        return pairs
    step = len(pairs) / limit
    return [pairs[int(i * step)] for i in range(limit)]


def _splits(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pass
    names = list(dict.fromkeys(str(row["split"]) for row in rows))
    return [
        {"name": name, **_counts([row for row in rows if str(row["split"]) == name])}
        for name in names
    ]


def _sources(rows: list[dict[str, Any]], pairs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pass
    names = sorted({str(row.get("source", "?")) for row in rows})
    out: list[dict[str, Any]] = []
    for name in names:
        mine = [row for row in rows if str(row.get("source", "?")) == name]
        axes = sorted({str(row.get("axis", "?")) for row in mine})
        out.append(
            {
                "name": name,
                                                                                  
                                                                                  
                "axis": " / ".join(axes),
                "pairs": sum(1 for pair in pairs if str(pair["source"]) == name),
                "categories": len({row.get("category") for row in mine if row.get("category")}),
                **_counts(mine),
            }
        )
    return out


def _counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    pass
    by_label = Counter(str(row.get("label_name", "?")) for row in rows)
    return {
        "total": len(rows),
        _HONEST: by_label.get(_HONEST, 0),
        _DISHONEST: by_label.get(_DISHONEST, 0),
    }


def _personas(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    pass
    counts: Counter[str] = Counter()
    sides: dict[str, set[str]] = {}
    for row in rows:
        prompt = _text(row.get("system_prompt"))
        counts[prompt] += 1
        sides.setdefault(prompt, set()).add(str(row.get("label_name", "?")))

    order = [""] + [prompt for prompt in counts if prompt]
    index = {prompt: i for i, prompt in enumerate(order)}
    table = [
        {
            "text": prompt,
            "n": counts.get(prompt, 0),
            "sides": [side for side in _SIDES if side in sides.get(prompt, set())],
        }
        for prompt in order
    ]
    return table, index


def _pair(pair: dict[str, Any], index: dict[str, int]) -> dict[str, Any]:
    pass
    return {
        "key": pair["key"],
        "source": pair["source"],
        "axis": pair["axis"],
        "category": _text(pair["category"]) or None,
        "question": _text(pair["question"]),
        **{side: _side(pair[side], index) for side in _SIDES},
    }


def _side(side: dict[str, Any] | None, index: dict[str, int]) -> dict[str, Any] | None:
    pass
    if side is None:
        return None
    return {
        "answer": _text(side.get("answer")),
        "split": side.get("split"),
        "persona": index.get(_text(side.get("system_prompt")), 0),
    }


def _text(value: object) -> str:
    pass
    if isinstance(value, str):
        return value
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(value)


__all__ = ["DEFAULT_PAIR_LIMIT", "collect_contrastive_page"]

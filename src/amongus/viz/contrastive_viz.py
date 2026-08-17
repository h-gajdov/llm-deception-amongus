

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from string import Template
from typing import Any

from ..logging import get_logger

logger = get_logger()

_HONEST_LABEL = 0

_SOURCE_HEX = {"tqa": "#4f8cff", "dqa": "#b57bff", "repeng": "#ffb347"}


def load_contrastive_splits(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    pass
    try:
        import pandas as pd
    except ImportError as exc:                                             
        msg = "pandas is required to read contrastive datasets."
        raise ImportError(msg) from exc

    p = Path(path)
    frames: dict[str, Any] = {}
    if p.is_file() and p.suffix == ".parquet":
        frames[p.stem] = pd.read_parquet(p)
    elif p.is_dir():
        parquets = sorted(p.glob("*.parquet"))
        frames = (
            {x.stem: pd.read_parquet(x) for x in parquets} if parquets else _frames_from_disk(p)
        )
    if not frames:
        msg = f"No parquet or saved dataset found at {p}"
        raise FileNotFoundError(msg)
    return {name: frame.to_dict("records") for name, frame in frames.items()}


def load_contrastive_rows(path: str | Path) -> list[dict[str, Any]]:
    pass
    return [row for rows in load_contrastive_splits(path).values() for row in rows]


def _frames_from_disk(directory: Path) -> dict[str, Any]:
    pass
    try:
        from datasets import load_from_disk
    except ImportError as exc:                                             
        msg = "The 'datasets' library is required to read a saved DatasetDict."
        raise ImportError(msg) from exc
    loaded: Any = load_from_disk(str(directory))
    if not hasattr(loaded, "items"):
        return {directory.name: loaded.to_pandas()}
    return {str(name): split.to_pandas() for name, split in loaded.items()}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pass
    return {
        "total": len(rows),
        "by_source": dict(Counter(r.get("source", "?") for r in rows)),
        "by_label": dict(Counter(r.get("label_name", "?") for r in rows)),
        "by_axis": dict(Counter(r.get("axis", "?") for r in rows)),
    }


def render_summary_text(stats: dict[str, Any], path: str | Path) -> str:
    pass
    lines = [
        f"Contrastive dataset: {path}",
        "─" * 56,
        f"Total examples: {stats['total']}",
        f"  by source: {stats['by_source']}",
        f"  by label:  {stats['by_label']}",
        f"  by axis:   {stats['by_axis']}",
    ]
    return "\n".join(lines)


def _pair_key(example_id: str) -> str:
    pass
    return example_id.rsplit("-", 1)[0]


def build_pairs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pass
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _pair_key(str(row.get("id", "")))
        group = groups.setdefault(
            key,
            {
                "key": key,
                "source": row.get("source", "?"),
                "axis": row.get("axis", "?"),
                "category": row.get("category"),
                "question": row.get("question") or "",
                "honest": None,
                "dishonest": None,
            },
        )
        if not group["question"] and row.get("question"):
            group["question"] = row["question"]
        side = "honest" if row.get("label") == _HONEST_LABEL else "dishonest"
        if group[side] is None:
            group[side] = {
                "system_prompt": row.get("system_prompt", "") or "",
                "answer": row.get("answer", "") or "",
                "split": row.get("split"),
            }
    return list(groups.values())


def build_contrastive_html(
    rows: list[dict[str, Any]],
    path: str | Path,
    *,
    limit: int = 400,
    seed: int = 0,
) -> str:
    pass
    stats = summarize(rows)
    pairs = build_pairs(rows)
    if limit and len(pairs) > limit:
        rng = random.Random(seed)
        pairs = rng.sample(pairs, limit)
    pairs.sort(key=lambda g: g["key"])

    data = {
        "path": str(path),
        "stats": stats,
        "sources": sorted(stats["by_source"]),
        "sourceHex": _SOURCE_HEX,
        "shown": len(pairs),
        "pairs": pairs,
    }
    return _PAGE.substitute(
        PATH=_escape(str(path)),
        TOTAL=stats["total"],
        SHOWN=len(pairs),
        DATA=json.dumps(data, ensure_ascii=False),
    )


def _escape(text: str) -> str:
    pass
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_PAGE = Template(
    """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Contrastive dataset — $PATH</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         background: #0f1220; color: #e6e8f0; }
  header { padding: 14px 20px; border-bottom: 1px solid #262a40; }
  header h1 { font-size: 17px; margin: 0 0 4px; }
  header .path { color: #8b93bd; font-size: 12px; word-break: break-all; }
  .tiles { display: flex; flex-wrap: wrap; gap: 10px; padding: 14px 20px 0; }
  .tile { background: #171a2e; border: 1px solid #2c3150; border-radius: 10px;
          padding: 8px 14px; font-size: 13px; }
  .tile b { font-size: 18px; display: block; }
  .controls { display: flex; flex-wrap: wrap; gap: 8px; padding: 14px 20px; align-items: center; }
  .controls button { background: #262a44; color: #e6e8f0; border: 1px solid #383e63;
                     border-radius: 999px; padding: 5px 14px; cursor: pointer; font-size: 13px; }
  .controls button.active { background: #394170; border-color: #5b64a0; }
  .controls input { flex: 1; min-width: 180px; background: #12142a; color: #e6e8f0;
                    border: 1px solid #2c3150; border-radius: 8px; padding: 7px 12px;
                    font-size: 14px; }
  main { padding: 4px 20px 40px; display: flex; flex-direction: column; gap: 12px; }
  .pair { border: 1px solid #262a40; border-radius: 12px; background: #14172a; overflow: hidden; }
  .pair .meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
                padding: 10px 14px; border-bottom: 1px solid #1e2338; font-size: 12px; }
  .badge { padding: 2px 9px; border-radius: 999px; font-weight: 700; color: #0c0e18; }
  .badge.axis { background: #2c3150; color: #b9c0e6; }
  .badge.cat { background: #23263e; color: #9aa4c8; }
  .q { padding: 10px 14px; color: #d7dcf5; font-size: 14px; }
  .q span { color: #7b83ad; }
  .sides { display: grid; grid-template-columns: 1fr 1fr; gap: 0; }
  @media (max-width: 760px) { .sides { grid-template-columns: 1fr; } }
  .side { padding: 12px 14px; font-size: 14px; }
  .side.honest { border-left: 4px solid #34d399; }
  .side.dishonest { border-left: 4px solid #ff6b6b; background: #1a1526; }
  .side .tag { font-size: 11px; font-weight: 700; letter-spacing: .05em;
               text-transform: uppercase; }
  .side.honest .tag { color: #34d399; }
  .side.dishonest .tag { color: #ff6b6b; }
  .persona { margin: 6px 0; font-size: 12px; color: #b9c0e6; font-style: italic;
             background: #20233c; border-radius: 8px; padding: 5px 9px; }
  .answer { margin-top: 6px; }
  .side.dishonest .answer { color: #ffc9c9; }
  .count { color: #8b93bd; font-size: 13px; padding: 0 20px; }
  .empty { color: #7b83ad; padding: 20px; }
</style>
</head>
<body>
<header>
  <h1>Contrastive dataset (honest vs. dishonest)</h1>
  <div class="path">$PATH — $TOTAL examples, showing $SHOWN pairs</div>
</header>
<div class="tiles" id="tiles"></div>
<div class="controls" id="controls"></div>
<div class="count" id="count"></div>
<main id="list"></main>
<script>
const DATA = $DATA;
const tiles = document.getElementById("tiles");
const controls = document.getElementById("controls");
const list = document.getElementById("list");
const count = document.getElementById("count");
let sourceFilter = "all";
let query = "";

function renderTiles() {
  const s = DATA.stats;
  const parts = [];
  parts.push('<div class="tile"><b>' + s.total + '</b>examples</div>');
  Object.keys(s.by_source).forEach(k =>
    parts.push('<div class="tile"><b>' + s.by_source[k] + '</b>' + k + '</div>'));
  Object.keys(s.by_label).forEach(k =>
    parts.push('<div class="tile"><b>' + s.by_label[k] + '</b>' + k + '</div>'));
  tiles.innerHTML = parts.join("");
}

function renderControls() {
  const btns = ["all"].concat(DATA.sources);
  controls.innerHTML = btns.map(s =>
    '<button data-src="' + s + '" class="' + (s === "all" ? "active" : "") + '">'
    + (s === "all" ? "All sources" : s) + '</button>').join("")
    + '<input id="search" type="text" placeholder="Search question / answer…">';
  controls.querySelectorAll("button").forEach(b => b.onclick = () => {
    sourceFilter = b.dataset.src;
    controls.querySelectorAll("button").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    render();
  });
  document.getElementById("search").oninput = e => {
    query = e.target.value.toLowerCase(); render();
  };
}

function esc(t) {
  const d = document.createElement("div");
  d.textContent = t == null ? "" : t;
  return d.innerHTML;
}

function sideHtml(side, kind) {
  if (!side) return '<div class="side ' + kind + '"><span class="tag">' + kind
    + '</span><div class="answer">(none)</div></div>';
  const persona = side.system_prompt
    ? '<div class="persona">' + esc(side.system_prompt) + '</div>' : '';
  return '<div class="side ' + kind + '"><span class="tag">' + kind + '</span>'
    + persona + '<div class="answer">' + esc(side.answer) + '</div></div>';
}

function pairHtml(p) {
  const hex = DATA.sourceHex[p.source] || "#888";
  const cat = p.category ? '<span class="badge cat">' + esc(p.category) + '</span>' : '';
  const q = p.question ? '<div class="q"><span>Q:</span> ' + esc(p.question) + '</div>' : '';
  return '<div class="pair"><div class="meta">'
    + '<span class="badge" style="background:' + hex + '">' + esc(p.source) + '</span>'
    + '<span class="badge axis">' + esc(p.axis) + '</span>' + cat + '</div>'
    + q + '<div class="sides">' + sideHtml(p.honest, "honest")
    + sideHtml(p.dishonest, "dishonest") + '</div></div>';
}

function matches(p) {
  if (sourceFilter !== "all" && p.source !== sourceFilter) return false;
  if (!query) return true;
  const hay = ((p.question || "") + " " + (p.honest ? p.honest.answer : "") + " "
    + (p.dishonest ? p.dishonest.answer : "")).toLowerCase();
  return hay.indexOf(query) >= 0;
}

function render() {
  const shown = DATA.pairs.filter(matches);
  count.textContent = shown.length + " pair(s)";
  list.innerHTML = shown.length
    ? shown.map(pairHtml).join("")
    : '<div class="empty">No pairs match the current filter.</div>';
}

renderTiles();
renderControls();
render();
</script>
</body>
</html>
"""
)


__all__ = [
    "build_contrastive_html",
    "build_pairs",
    "load_contrastive_rows",
    "load_contrastive_splits",
    "render_summary_text",
    "summarize",
]

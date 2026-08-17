

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..logging import get_logger

logger = get_logger()

METRICS_FILE = "metrics.json"
RESULTS_FILE = "results.json"


@dataclass(frozen=True)
class SuiteView:
    pass

    label: str
    sources: tuple[str, ...]


                                                                              
                                                                            
                                                                                
                                                                          
SUITE_VIEWS: tuple[SuiteView, ...] = (
    SuiteView("eval_pooling_20", ("eval_suite", "eval_suite_gpt2_last20")),
    SuiteView("eval_pooling_last", ("eval_suite_polling_last",)),
)

                                                                             
                                                                      
                                                                             
                                                                              
                                                              
SUITE_DATASETS: tuple[str, ...] = (
    "2025-02-01_llama_llama_100_games_v3",
    "2025-02-01_llama_phi_100_games_v3",
    "2025-02-01_phi_llama_100_games_v3",
    "2025-02-01_phi_phi_100_games_v3",
    "diverse_gemma4_100_games",
    "diverse_phi4_100_games",
    "diverse_qwen3_100_games",
    "mixed_gemma4_qwen3_100_games",
    "mixed_qwen3_gemma4_100_games",
)

                                                                                
                                                                           
_COMPARABILITY_KEYS = ("label_source", "text_mode", "apply_chat_template", "speak_only")

                                                                            
                                                                               
                                                                       
                                                                            
                                       
 
                                                                               
                                                                               
                                                                       
                                                                               
                                                                  
PALETTE_LIGHT = [
    "#2a78d6",        
    "#eb6834",          
    "#0d8a2f",         
    "#6a55d6",          
    "#d1568c",           
    "#1baf7a",        
    "#c99000",          
    "#cc2255",           
]
PALETTE_DARK = [
    "#6aa9f2",
    "#ff9257",
    "#4fc46a",
    "#a08bff",
    "#f58ab4",
    "#3ed3a3",
    "#f0c04a",
    "#ff5f7a",
]

                                                                               
METRIC_KEYS = ("accuracy", "f1", "auroc")

                                                                               
                                                                            
                                                    
_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}[_-]")
_GAMES_SUFFIX = re.compile(r"_\d+_games(_v\d+)?$")


def collect_probe_pages(probes_dir: str | Path) -> dict[str, Any] | None:
    pass
    root = Path(probes_dir)
    if not root.is_dir():
        logger.info("No probe directory at {}; the site's probe pages are omitted.", root)
        return None

    training: list[dict[str, Any]] = []
    runs: dict[str, dict[str, Any]] = {}
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if not child.is_dir():
            continue
        if (child / METRICS_FILE).exists():
            run = _read_training(child)
            if run is not None:
                training.append(run)
        if (child / RESULTS_FILE).exists():
            suite = _read_suite(child)
            if suite is not None:
                runs[child.name] = suite

                                                                                 
                                                                                
                                                                            
                                                                       
    viewed = {name for spec in SUITE_VIEWS for name in spec.sources}
    slots = _slots(training, {name: run for name, run in runs.items() if name in viewed})
    suites = [view for spec in SUITE_VIEWS if (view := _build_view(spec, runs, slots)) is not None]

    if not training and not suites:
        logger.warning(
            "No {} or {} under {}; probe pages omitted.", METRICS_FILE, RESULTS_FILE, root
        )
        return None

    logger.info(
        "Probe pages: {} training run(s), {} eval suite(s) from {}",
        len(training),
        len(suites),
        root,
    )
    return {
        "root": str(root),
        "slots": slots,
        "palette": {"light": PALETTE_LIGHT, "dark": PALETTE_DARK},
        "training": training,
        "suites": suites,
    }


                                                                               
               
                                                                               
def _read_training(folder: Path) -> dict[str, Any] | None:
    pass
    metrics = _load_json(folder / METRICS_FILE)
    if metrics is None:
        return None
    rows = [row for row in metrics.get("layer_metrics") or [] if row.get("layer") is not None]
    if not rows:
        logger.warning("Skipping {}: {} carries no layer metrics.", folder.name, METRICS_FILE)
        return None
    rows.sort(key=lambda row: int(row["layer"]))

    config = metrics.get("config") or {}
    model_cfg = config.get("model") or {}
    probe_cfg = config.get("probe") or {}
    layers = [int(row["layer"]) for row in rows]
    series = {key: [_number(row.get(key)) for row in rows] for key in METRIC_KEYS}

    best_layer = metrics.get("best_layer")
    selected = next((row for row in rows if row.get("layer") == best_layer), None)

    return {
        "name": folder.name,
        "model": metrics.get("model_name") or model_cfg.get("name") or folder.name,
        "device": metrics.get("device"),
        "pooling": metrics.get("pooling") or config.get("pooling"),
        "pooling_tokens": config.get("pooling_tokens"),
        "max_length": config.get("max_length"),
        "use_chat_template": config.get("use_chat_template"),
        "quantization": _quantization(model_cfg.get("quantization") or {}),
        "epochs": probe_cfg.get("epochs"),
        "lr": probe_cfg.get("lr"),
        "weight_decay": probe_cfg.get("weight_decay"),
        "standardize": probe_cfg.get("standardize"),
        "n_train": metrics.get("n_train"),
        "n_test": metrics.get("n_test"),
        "dataset_dir": config.get("dataset_dir"),
        "layers": layers,
        "series": series,
                                                                            
                                                                              
                                                                           
                                         
        "best_layer": best_layer,
        "best": {key: _number(selected.get(key)) for key in METRIC_KEYS} if selected else None,
        "peaks": {key: _peak(layers, series[key]) for key in METRIC_KEYS},
    }


def _peak(layers: list[int], values: list[float | None]) -> dict[str, Any] | None:
    pass
    pairs = [(v, layer) for layer, v in zip(layers, values, strict=True) if v is not None]
    if not pairs:
        return None
    value, layer = max(pairs, key=lambda pair: pair[0])
    return {"layer": layer, "value": value}


def _quantization(block: dict[str, Any]) -> str:
    pass
    if block.get("load_in_4bit"):
        return f"4-bit {block.get('bnb_4bit_quant_type', 'nf4')}"
    if block.get("load_in_8bit"):
        return "8-bit"
    return "none"


                                                                               
             
                                                                               
def _slots(training: list[dict[str, Any]], runs: dict[str, dict[str, Any]]) -> dict[str, int]:
    pass
    names: list[str] = [run["name"] for run in training]
    for suite in runs.values():
        names.extend(probe["name"] for probe in suite["probes"])
    return {name: i for i, name in enumerate(dict.fromkeys(names))}


def _build_view(
    spec: SuiteView, runs: dict[str, dict[str, Any]], slots: dict[str, int]
) -> dict[str, Any] | None:
    pass
    parts = [(name, runs[name]) for name in spec.sources if name in runs]
    missing = [name for name in spec.sources if name not in runs]
    if missing:
        logger.info("Suite view {}: no results.json for {}.", spec.label, ", ".join(missing))
    if not parts:
        return None

                                                                               
                                                                  
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    origin: dict[str, str] = {}
    for source, suite in parts:
        for row in suite["rows"]:
            key = (str(row["probe"]), str(row["dataset"]), str(row["variant"]))
            if key in merged:
                continue
            merged[key] = row
            origin.setdefault(str(row["probe"]), source)

    present = {key[1] for key in merged}
    datasets = [name for name in SUITE_DATASETS if name in present]
    dropped = sorted(present - set(datasets))
    if dropped:
        logger.info("Suite view {}: not charting {}.", spec.label, ", ".join(dropped))
    if not datasets:
        return None

    rows = [row for key, row in merged.items() if key[1] in datasets]
    probes = sorted({key[0] for key in merged}, key=lambda name: slots.get(name, len(slots)))
    base_settings = parts[0][1]["settings"]
    meta = {str(row["probe"]): row for row in rows}
    trained = {str(r["dataset"]): r for r in rows if r.get("variant") == "trained"}
    labels = _labels(datasets)

    return {
        "name": spec.label,
        "settings": base_settings,
        "sources": [
            {"name": source, "settings": suite["settings"], "skipped": suite["skipped"]}
            for source, suite in parts
        ],
        "skipped": [item for _, suite in parts for item in suite["skipped"]],
        "datasets": [
            {
                "name": name,
                "label": labels[name],
                "n": trained.get(name, {}).get("n"),
                "n_positive": trained.get(name, {}).get("n_positive"),
                "positive_rate": trained.get(name, {}).get("positive_rate"),
                "kind": trained.get(name, {}).get("dataset_kind"),
                "label_source": trained.get(name, {}).get("label_source"),
            }
            for name in datasets
        ],
        "probes": [
            {
                "name": name,
                "model": meta.get(name, {}).get("model_name"),
                "layer": meta.get(name, {}).get("layer"),
                "pooling_tokens": meta.get(name, {}).get("pooling_tokens"),
                "source": origin.get(name),
                                                                                
                                                                                
                                                                               
                "settings_diff": _settings_diff(base_settings, origin.get(name), parts),
            }
            for name in probes
        ],
        "rows": [_trim_row(row) for row in rows],
    }


def _settings_diff(
    base: dict[str, Any], source: str | None, parts: list[tuple[str, dict[str, Any]]]
) -> dict[str, Any]:
    pass
    settings = next((suite["settings"] for name, suite in parts if name == source), None)
    if settings is None:
        return {}
    return {
        key: settings.get(key)
        for key in _COMPARABILITY_KEYS
        if key in settings and settings.get(key) != base.get(key)
    }


def _read_suite(folder: Path) -> dict[str, Any] | None:
    pass
    report = _load_json(folder / RESULTS_FILE)
    if report is None:
        return None
    rows = report.get("rows") or []
    if not rows:
        logger.warning("Skipping suite {}: {} holds no rows.", folder.name, RESULTS_FILE)
        return None

                                                                              
                                     
    probes = _ordered(rows, "probe", report.get("probes"))
    meta = {str(r["probe"]): r for r in rows}
    return {
        "name": folder.name,
        "settings": report.get("settings") or {},
        "skipped": report.get("skipped") or [],
        "probes": [
            {
                "name": name,
                "model": meta.get(name, {}).get("model_name"),
                "layer": meta.get(name, {}).get("layer"),
                "pooling_tokens": meta.get(name, {}).get("pooling_tokens"),
            }
            for name in probes
        ],
        "rows": rows,
    }


def _trim_row(row: dict[str, Any]) -> dict[str, Any]:
    pass
    keys = (
        "dataset",
        "probe",
        "variant",
        "layer",
        "model_name",
        "n",
        "n_positive",
        "positive_rate",
        "accuracy",
        "f1",
        "precision",
        "recall",
        "auroc",
        "baseline_accuracy",
        "chance_auroc",
        "auroc_std",
        "accuracy_std",
        "seeds",
        "label_source",
        "dataset_kind",
        "pooling_tokens",
        "n_tokens",
    )
    return {key: row[key] for key in keys if key in row}


def _ordered(rows: list[dict[str, Any]], key: str, declared: object) -> list[str]:
    pass
    order = [str(name) for name in declared] if isinstance(declared, list) else []
    seen = set(order)
    for row in rows:
        value = str(row.get(key, ""))
        if value and value not in seen:
            seen.add(value)
            order.append(value)
    present = {str(row.get(key, "")) for row in rows}
    return [name for name in order if name in present]


def _labels(names: list[str]) -> dict[str, str]:
    pass
    short = {name: _GAMES_SUFFIX.sub("", _DATE_PREFIX.sub("", name)) or name for name in names}
    counts: dict[str, int] = {}
    for label in short.values():
        counts[label] = counts.get(label, 0) + 1
    return {
        name: (label if counts[label] == 1 else _DATE_PREFIX.sub("", name))
        for name, label in short.items()
    }


                                                                               
        
                                                                               
def _load_json(path: Path) -> dict[str, Any] | None:
    pass
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Skipping {}: {}", path, exc)
        return None
    if not isinstance(payload, dict):
        logger.warning("Skipping {}: expected a JSON object.", path)
        return None
    return payload


def _number(value: object) -> float | None:
    pass
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


__all__ = ["METRIC_KEYS", "PALETTE_DARK", "PALETTE_LIGHT", "collect_probe_pages"]

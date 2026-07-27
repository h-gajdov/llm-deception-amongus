

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from string import Template
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:                                  
    from collections.abc import Sequence

    from ..probes.eval import EvalReport

                                                          
_METRICS: list[tuple[str, str]] = [
    ("auroc", "AUROC"),
    ("accuracy", "Accuracy"),
    ("f1", "F1"),
    ("precision", "Precision"),
    ("recall", "Recall"),
]

                                                                    
_PALETTE = ["#4f8cff", "#ff6b6b", "#34d399", "#ffb347", "#b57bff", "#22d3ee", "#f472b6"]

                                  
_W, _H = 920, 480
_ML, _MR, _MT, _MB = 64, 24, 40, 140


def _escape(text: str) -> str:
    pass
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _metric_value(report: EvalReport, key: str) -> float | None:
    pass
    return getattr(report, key)


def _bars_svg(reports: Sequence[EvalReport], labels: Sequence[str]) -> str:
    pass
    plot_w = _W - _ML - _MR
    plot_h = _H - _MT - _MB
    base_y = _MT + plot_h                        
    n_models = max(len(reports), 1)

    def y_of(value: float) -> float:
        return _MT + (1.0 - value) * plot_h

    parts: list[str] = []

                                                                
    for tick in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = y_of(tick)
        parts.append(
            f'<line x1="{_ML}" y1="{y:.1f}" x2="{_ML + plot_w}" y2="{y:.1f}" '
            f'stroke="#2c3150" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{_ML - 8}" y="{y + 3:.1f}" text-anchor="end" '
            f'font-size="10" fill="#8b93bd">{tick:.2f}</text>'
        )

                                                                                
    y_ref = y_of(0.5)
    parts.append(
        f'<line x1="{_ML}" y1="{y_ref:.1f}" x2="{_ML + plot_w}" y2="{y_ref:.1f}" '
        f'stroke="#ff6b6b" stroke-width="1" stroke-dasharray="5 4" opacity="0.7"/>'
    )
    parts.append(
        f'<text x="{_ML + plot_w - 4}" y="{y_ref - 5:.1f}" text-anchor="end" '
        f'font-size="10" fill="#ff8a8a">0.5 chance</text>'
    )

                                                              
    group_w = plot_w / len(_METRICS)
    inner = group_w * 0.82
    bar_w = inner / n_models
    for g, (key, title) in enumerate(_METRICS):
        gx = _ML + g * group_w + (group_w - inner) / 2.0
        for i, report in enumerate(reports):
            value = _metric_value(report, key)
            colour = _PALETTE[i % len(_PALETTE)]
            x = gx + i * bar_w
            if value is None:
                                                                                
                parts.append(
                    f'<text x="{x + bar_w / 2:.1f}" y="{base_y - 4:.1f}" '
                    f'text-anchor="middle" font-size="9" fill="#7b83ad">n/a</text>'
                )
                continue
            h = value * plot_h
            y = base_y - h
            parts.append(
                f'<rect x="{x + 1:.1f}" y="{y:.1f}" width="{bar_w - 2:.1f}" '
                f'height="{h:.1f}" fill="{colour}" rx="2"><title>'
                f"{_escape(labels[i])} — {title}: {value:.3f}</title></rect>"
            )
            if n_models <= 4:
                parts.append(
                    f'<text x="{x + bar_w / 2:.1f}" y="{y - 3:.1f}" '
                    f'text-anchor="middle" font-size="9" fill="#c8cdea">{value:.2f}</text>'
                )
                                      
        parts.append(
            f'<text x="{gx + inner / 2:.1f}" y="{base_y + 18:.1f}" text-anchor="middle" '
            f'font-size="12" fill="#d7dcf5">{title}</text>'
        )

                                  
    legend_y = base_y + 44
    lx = _ML
    for i, label in enumerate(labels):
        colour = _PALETTE[i % len(_PALETTE)]
        parts.append(
            f'<rect x="{lx}" y="{legend_y - 10}" width="12" height="12" '
            f'fill="{colour}" rx="2"/>'
        )
        parts.append(
            f'<text x="{lx + 18}" y="{legend_y}" font-size="12" fill="#e6e8f0">'
            f"{_escape(label)}</text>"
        )
        lx += 26 + len(label) * 7                                         

    return (
        f'<svg viewBox="0 0 {_W} {_H}" width="100%" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="Probe evaluation metrics by model">{"".join(parts)}</svg>'
    )


def _table_html(reports: Sequence[EvalReport], labels: Sequence[str]) -> str:
    pass
    head = (
        "<tr><th>Model</th><th>Layer</th><th>n</th><th>Impostor rate</th>"
        "<th>AUROC</th><th>Accuracy</th><th>Majority</th>"
        "<th>F1</th><th>Precision</th><th>Recall</th></tr>"
    )
    rows: list[str] = []
    for i, report in enumerate(reports):
        colour = _PALETTE[i % len(_PALETTE)]
        auroc = "n/a" if report.auroc is None else f"{report.auroc:.3f}"
        swatch = f'<span class="sw" style="background:{colour}"></span>'
        rows.append(
            "<tr>"
            f"<td>{swatch}{_escape(labels[i])}</td>"
            f"<td>{report.layer}</td>"
            f"<td>{report.n}</td>"
            f"<td>{report.impostor_rate:.3f}</td>"
            f"<td>{auroc}</td>"
            f"<td>{report.accuracy:.3f}</td>"
            f"<td>{report.baseline_accuracy:.3f}</td>"
            f"<td>{report.f1:.3f}</td>"
            f"<td>{report.precision:.3f}</td>"
            f"<td>{report.recall:.3f}</td>"
            "</tr>"
        )
    return f"<table><thead>{head}</thead><tbody>{''.join(rows)}</tbody></table>"


@dataclass
class _Meta:
    pass

    dataset_dir: str
    split: str
    text_mode: str
    speak_only: bool


def _subtitle(reports: Sequence[EvalReport], meta: _Meta) -> str:
    pass
    return (
        f"{meta.dataset_dir} — split={meta.split}, text_mode={meta.text_mode}, "
        f"speak_only={str(meta.speak_only).lower()} — {len(reports)} model(s)"
    )


def render_comparison_png(
    reports: Sequence[EvalReport],
    labels: Sequence[str],
    meta: dict[str, Any],
    output_path: str | Path,
    *,
    dpi: int = 150,
) -> Path:
    pass
    try:
        import matplotlib

        matplotlib.use("Agg")                                               
        import matplotlib.pyplot as plt
    except ImportError as exc:                                                    
        msg = "matplotlib is required for --format png (install the 'ml' extra)."
        raise ImportError(msg) from exc

    m = _Meta(
        dataset_dir=str(meta.get("dataset_dir", "")),
        split=str(meta.get("split", "all")),
        text_mode=str(meta.get("text_mode", "response")),
        speak_only=bool(meta.get("speak_only", False)),
    )
    n_models = max(len(reports), 1)
    bar_w = 0.8 / n_models
    positions = range(len(_METRICS))

    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    for i, report in enumerate(reports):
        colour = _PALETTE[i % len(_PALETTE)]
        offset = (i - (n_models - 1) / 2.0) * bar_w
        xs = [p + offset for p in positions]
        raw = [_metric_value(report, key) for key, _ in _METRICS]
        values = [v or 0.0 for v in raw]
        bars = ax.bar(xs, values, bar_w, label=labels[i], color=colour)
                                                                                
                                                            
        ax.bar_label(
            bars,
            labels=["" if v is None else f"{v:.2f}" for v in raw],
            padding=2,
            fontsize=7,
            color="#444",
        )
        for x, v in zip(xs, raw, strict=True):
            if v is None:                                           
                ax.text(x, 0.01, "n/a", ha="center", va="bottom", fontsize=7, color="#888")

    ax.axhline(0.5, ls="--", lw=1, color="#d9534f", alpha=0.7)
    ax.text(
        len(_METRICS) - 0.5, 0.505, "0.5 chance", ha="right", va="bottom",
        fontsize=8, color="#d9534f",
    )
    ax.set_xticks(list(positions))
    ax.set_xticklabels([title for _, title in _METRICS])
    ax.set_ylim(0.0, 1.05)
    ax.set_ylabel("score")
    ax.grid(axis="y", ls=":", alpha=0.4)
    ax.set_axisbelow(True)
    ax.legend(loc="upper right", fontsize=9, framealpha=0.9)
    fig.suptitle("Deception probe evaluation — model comparison", fontsize=13, x=0.02, ha="left")
    ax.set_title(_subtitle(reports, m), fontsize=8, color="#666", loc="left")
    fig.tight_layout()

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out


def render_comparison_html(
    reports: Sequence[EvalReport],
    labels: Sequence[str],
    meta: dict[str, Any],
) -> str:
    pass
    m = _Meta(
        dataset_dir=str(meta.get("dataset_dir", "")),
        split=str(meta.get("split", "all")),
        text_mode=str(meta.get("text_mode", "response")),
        speak_only=bool(meta.get("speak_only", False)),
    )
    subtitle = (
        f"{_escape(m.dataset_dir)} — split={m.split}, text_mode={m.text_mode}, "
        f"speak_only={str(m.speak_only).lower()} — {len(reports)} model(s)"
    )
    return _PAGE.substitute(
        SUBTITLE=subtitle,
        CHART=_bars_svg(reports, labels),
        TABLE=_table_html(reports, labels),
    )


_PAGE = Template(
    """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Probe evaluation — model comparison</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         background: #0f1220; color: #e6e8f0; }
  header { padding: 16px 22px; border-bottom: 1px solid #262a40; }
  header h1 { font-size: 18px; margin: 0 0 4px; }
  header .sub { color: #8b93bd; font-size: 12px; word-break: break-all; }
  main { padding: 18px 22px 44px; }
  .card { background: #14172a; border: 1px solid #262a40; border-radius: 12px;
          padding: 16px; margin-bottom: 18px; }
  h2 { font-size: 14px; margin: 0 0 10px; color: #b9c0e6; font-weight: 600; }
  table { border-collapse: collapse; width: 100%; font-size: 13px; }
  th, td { padding: 7px 10px; text-align: right; border-bottom: 1px solid #262a40; }
  th:first-child, td:first-child { text-align: left; }
  th { color: #8b93bd; font-weight: 600; }
  .sw { display: inline-block; width: 11px; height: 11px; border-radius: 3px;
        margin-right: 7px; vertical-align: middle; }
  .note { color: #7b83ad; font-size: 12px; margin-top: 10px; }
</style>
</head>
<body>
<header>
  <h1>Deception probe evaluation — model comparison</h1>
  <div class="sub">$SUBTITLE</div>
</header>
<main>
  <div class="card">
    <h2>Metrics by model</h2>
    $CHART
    <div class="note">Bars are on a 0-1 scale. The dashed red line marks 0.5
      (chance for AUROC). Hover a bar for its exact value.</div>
  </div>
  <div class="card">
    <h2>All metrics &amp; counts</h2>
    $TABLE
    <div class="note">"Majority" is the accuracy of always predicting the
      majority class - the floor to beat. AUROC's floor is 0.5.</div>
  </div>
</main>
</body>
</html>
"""
)


__all__ = ["render_comparison_html", "render_comparison_png"]

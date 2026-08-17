from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..data.schema_v2 import TURNS_FILE
from ..logging import get_logger
from .batch import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_OUTPUT_TOKENS,
    TERMINAL_STATUSES,
    build_batch_request,
    describe_batch_errors,
    get_client,
    iter_batch_result_lines,
    poll_batch,
    request_counts_dict,
    resolve_model,
    retrieve_batch,
    submit_and_maybe_wait,
    write_batch_input,
)
from .context import DatasetContext, build_turn_context
from .live import call_live
from .prompts import SYSTEM_PROMPT, build_user_message
from .schema import ANNOTATION_SCHEMA_VERSION, PROMPT_VERSION, RESPONSE_FORMAT, TurnAnnotationResult

logger = get_logger()


LIVE_CHECKPOINT_INTERVAL = 10

OUT_DIRNAME = "gpt4omini"
CLAIMS_FILE = "claims.jsonl"
SUMMARY_FILE = "annotation-summary.json"
FAILURES_FILE = "annotation-failures.jsonl"
BATCH_INPUT_FILE = "batch-input.jsonl"
ANNOTATION_METADATA_FILE = "annotation-metadata.json"


MAX_ATTEMPTS = 3


@dataclass
class AnnotationRunResult:
    dataset_dir: Path
    out_dir: Path
    status: str
    batch_id: str | None
    total_turns: int
    annotated_turns: int
    pending_turns: int
    message: str


def run_annotation(
    dataset_dir: str | Path,
    *,
    model: str | None = None,
    overwrite: bool = False,
    wait: bool = False,
    poll_interval_s: float = 20.0,
    poll_timeout_s: float | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    live: bool = False,
) -> AnnotationRunResult:
    dataset_dir = Path(dataset_dir)
    turns_path = dataset_dir / TURNS_FILE
    if not turns_path.exists():
        msg = f"{TURNS_FILE} not found under {dataset_dir}"
        raise FileNotFoundError(msg)
    out_dir = dataset_dir / OUT_DIRNAME

    original_turns = _read_raw_jsonl(turns_path)
    turn_ids = [str(t["turn_id"]) for t in original_turns]
    total = len(turn_ids)

    existing_annotations = _read_existing_annotations(out_dir)
    metadata = _read_metadata(out_dir)
    attempts: dict[str, int] = dict((metadata or {}).get("attempts", {}))
    failures = _read_failures(out_dir)

    annotated_ids = {tid for tid in turn_ids if existing_annotations.get(tid) is not None}
    exhausted_ids = {
        tid for tid in turn_ids if tid not in annotated_ids and attempts.get(tid, 0) >= MAX_ATTEMPTS
    }
    resolved_ids = annotated_ids | exhausted_ids
    is_complete = total > 0 and len(resolved_ids) == total

    if is_complete and not overwrite:
        return AnnotationRunResult(
            dataset_dir=dataset_dir,
            out_dir=out_dir,
            status="already_complete",
            batch_id=None,
            total_turns=total,
            annotated_turns=len(annotated_ids),
            pending_turns=0,
            message=(
                f"{out_dir} is already fully annotated ({len(annotated_ids)}/{total} succeeded, "
                f"{len(exhausted_ids)} permanently failed). Pass overwrite=True to redo it."
            ),
        )

    if overwrite:
        existing_annotations = {}
        metadata = None
        attempts = {}
        failures = {}
        annotated_ids = set()
        exhausted_ids = set()
        resolved_ids = set()

    out_dir.mkdir(parents=True, exist_ok=True)
    resolved_model = resolve_model(model)
    if metadata is None:
        metadata = _new_metadata(dataset_dir, resolved_model)

    pending_ids = [tid for tid in turn_ids if tid not in resolved_ids]

    if not pending_ids:
        metadata["batch_status"] = "completed"
        metadata["batch_id"] = None
        metadata["attempts"] = attempts
        _finalize(out_dir, original_turns, existing_annotations, failures, metadata)
        return AnnotationRunResult(
            dataset_dir=dataset_dir,
            out_dir=out_dir,
            status="completed",
            batch_id=None,
            total_turns=total,
            annotated_turns=len(annotated_ids),
            pending_turns=0,
            message=(
                f"Annotation complete: {len(annotated_ids)}/{total} turns annotated"
                + (
                    f", {len(exhausted_ids)} permanently failed after {MAX_ATTEMPTS} attempts."
                    if exhausted_ids
                    else "."
                )
            ),
        )

    client = get_client()
    status: str

    if live:
        ctx = DatasetContext(dataset_dir)
        chunk_ids = pending_ids[:batch_size]
        _run_live(
            client,
            resolved_model,
            chunk_ids,
            ctx,
            existing_annotations,
            attempts,
            failures,
            metadata,
            out_dir,
            original_turns,
        )
        annotated_now = sum(1 for tid in turn_ids if existing_annotations.get(tid) is not None)
        still_exhausted = {
            tid
            for tid in turn_ids
            if existing_annotations.get(tid) is None and attempts.get(tid, 0) >= MAX_ATTEMPTS
        }
        if annotated_now + len(still_exhausted) == total:
            metadata["batch_status"] = "completed"
            status = "completed"
        else:
            status = "live_progress"
        metadata["attempts"] = attempts
        _finalize(out_dir, original_turns, existing_annotations, failures, metadata)
        return AnnotationRunResult(
            dataset_dir=dataset_dir,
            out_dir=out_dir,
            status=status,
            batch_id=None,
            total_turns=total,
            annotated_turns=annotated_now,
            pending_turns=max(total - annotated_now - len(still_exhausted), 0),
            message=_status_message(status, metadata, annotated_now, total),
        )

    batch_id = metadata.get("batch_id")

    if batch_id:
        chunk_ids = metadata.get("batch_row_ids") or pending_ids
        batch = retrieve_batch(client, batch_id)
        if wait and batch.status not in TERMINAL_STATUSES:
            batch = poll_batch(
                client, batch_id, poll_interval_s=poll_interval_s, timeout_s=poll_timeout_s
            )
        status = _handle_batch_status(
            batch, client, chunk_ids, existing_annotations, attempts, failures, metadata
        )
    else:
        chunk_ids = pending_ids[:batch_size]
        ctx = DatasetContext(dataset_dir)
        turn_by_id = {t.turn_id: t for t in ctx.turns}
        requests = []
        for tid in chunk_ids:
            turn = turn_by_id.get(tid)
            if turn is None:
                logger.warning("Turn {} is in turns.jsonl but missing from DatasetContext.", tid)
                continue
            turn_context = build_turn_context(turn, ctx)
            user_message = build_user_message(turn_context)
            custom_id = f"{turn.game_id}:{turn.turn_id}"
            requests.append(
                build_batch_request(
                    custom_id, SYSTEM_PROMPT, user_message, resolved_model, RESPONSE_FORMAT
                )
            )
        input_path = out_dir / BATCH_INPUT_FILE
        write_batch_input(input_path, requests)

        def _checkpoint(batch: Any, requests: list[dict[str, object]] = requests) -> None:
            is_new_batch = metadata.get("batch_id") != batch.id
            metadata["batch_id"] = batch.id
            metadata["batch_status"] = batch.status
            metadata["batch_row_ids"] = chunk_ids
            if is_new_batch:
                metadata.setdefault("batch_history", []).append(
                    {
                        "batch_id": batch.id,
                        "submitted_at": datetime.now(timezone.utc).isoformat(),
                        "num_requests": len(requests),
                    }
                )
            metadata["attempts"] = attempts
            _finalize(out_dir, original_turns, existing_annotations, failures, metadata)

        metadata["requested_model"] = resolved_model
        batch = submit_and_maybe_wait(
            client,
            input_path,
            wait=wait,
            poll_interval_s=poll_interval_s,
            poll_timeout_s=poll_timeout_s,
            checkpoint=_checkpoint,
        )

        _checkpoint(batch)
        if wait:
            status = _handle_batch_status(
                batch, client, chunk_ids, existing_annotations, attempts, failures, metadata
            )
        else:
            status = "submitted"

    metadata["attempts"] = attempts
    _finalize(out_dir, original_turns, existing_annotations, failures, metadata)

    annotated_now = sum(1 for tid in turn_ids if existing_annotations.get(tid) is not None)
    still_exhausted = {
        tid
        for tid in turn_ids
        if existing_annotations.get(tid) is None and attempts.get(tid, 0) >= MAX_ATTEMPTS
    }
    pending_now = total - annotated_now - len(still_exhausted)
    return AnnotationRunResult(
        dataset_dir=dataset_dir,
        out_dir=out_dir,
        status=status,
        batch_id=metadata.get("batch_id"),
        total_turns=total,
        annotated_turns=annotated_now,
        pending_turns=max(pending_now, 0),
        message=_status_message(status, metadata, annotated_now, total),
    )


def _handle_batch_status(
    batch: Any,
    client: Any,
    pending_ids: list[str],
    existing_annotations: dict[str, dict[str, Any] | None],
    attempts: dict[str, int],
    failures: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
) -> str:
    metadata["batch_status"] = batch.status
    metadata["batch_request_counts"] = request_counts_dict(batch)
    if batch.status == "completed":
        _merge_batch(client, batch, existing_annotations, attempts, failures, metadata)
        metadata["batch_id"] = None
        return "merged"
    if batch.status in TERMINAL_STATUSES:
        error_detail = describe_batch_errors(batch)
        for tid in pending_ids:
            attempts[tid] = attempts.get(tid, 0) + 1
            failures[tid] = {
                "game_id": tid.split("#", 1)[0],
                "turn_id": tid,
                "custom_id": f"{tid.split('#', 1)[0]}:{tid}",
                "error_type": f"batch_{batch.status}",
                "error": error_detail,
                "attempt": attempts[tid],
            }
        metadata["batch_id"] = None
        return f"batch_{batch.status}"
    return "polling"


def _run_live(
    client: Any,
    resolved_model: str,
    chunk_ids: list[str],
    ctx: DatasetContext,
    existing_annotations: dict[str, dict[str, Any] | None],
    attempts: dict[str, int],
    failures: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
    out_dir: Path,
    original_turns: list[dict[str, Any]],
) -> None:
    turn_by_id = {t.turn_id: t for t in ctx.turns}
    usage_totals: Counter[str] = Counter()
    models_seen: Counter[str] = Counter()
    total = len(chunk_ids)

    def _sync_and_persist() -> None:
        if models_seen:
            metadata["actual_model"] = models_seen.most_common(1)[0][0]
        if usage_totals:
            cumulative = dict(metadata.get("token_usage") or {})
            for key, value in usage_totals.items():
                cumulative[key] = cumulative.get(key, 0) + value
            metadata["token_usage"] = cumulative
            usage_totals.clear()
        metadata["attempts"] = attempts
        _finalize(out_dir, original_turns, existing_annotations, failures, metadata)

    try:
        for i, tid in enumerate(chunk_ids, start=1):
            turn = turn_by_id.get(tid)
            if turn is None:
                logger.warning("Turn {} is in turns.jsonl but missing from DatasetContext.", tid)
                continue
            turn_context = build_turn_context(turn, ctx)
            user_message = build_user_message(turn_context)
            parsed, error_type, error_message, meta = call_live(
                client,
                model=resolved_model,
                system_prompt=SYSTEM_PROMPT,
                user_message=user_message,
                response_format=RESPONSE_FORMAT,
                max_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            )
            if parsed is not None:
                try:
                    validated = TurnAnnotationResult.model_validate(parsed)
                except ValidationError as exc:
                    error_type, error_message = "validation_error", str(exc)[:2000]
                else:
                    existing_annotations[tid] = validated.model_dump(mode="json")
                    failures.pop(tid, None)
                    if meta and meta.get("model"):
                        models_seen[meta["model"]] += 1
                    usage = (meta or {}).get("usage") or {}
                    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                        usage_totals[key] += int(usage.get(key, 0) or 0)
                    error_type = None
            if error_type is not None:
                attempts[tid] = attempts.get(tid, 0) + 1
                failures[tid] = {
                    "game_id": turn.game_id,
                    "turn_id": tid,
                    "custom_id": f"{turn.game_id}:{tid}",
                    "error_type": error_type,
                    "error": error_message or "unknown error",
                    "attempt": attempts[tid],
                }
            if i % LIVE_CHECKPOINT_INTERVAL == 0:
                _sync_and_persist()
                logger.info("Live progress: {}/{} turns processed this run.", i, total)
    finally:
        _sync_and_persist()


def _merge_batch(
    client: Any,
    batch: Any,
    existing_annotations: dict[str, dict[str, Any] | None],
    attempts: dict[str, int],
    failures: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
) -> None:
    usage_totals: Counter[str] = Counter()
    models_seen: Counter[str] = Counter()
    for line in iter_batch_result_lines(client, batch):
        custom_id, annotation, error_type, error_msg, meta = _parse_result_line(line)
        if ":" not in custom_id:
            logger.warning("Batch result line has an unparseable custom_id: {!r}", custom_id)
            continue
        game_id, turn_id = custom_id.split(":", 1)
        if annotation is not None:
            existing_annotations[turn_id] = annotation
            failures.pop(turn_id, None)
            if meta and meta.get("model"):
                models_seen[meta["model"]] += 1
            usage = (meta or {}).get("usage") or {}
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                usage_totals[key] += int(usage.get(key, 0) or 0)
        else:
            attempts[turn_id] = attempts.get(turn_id, 0) + 1
            failures[turn_id] = {
                "game_id": game_id,
                "turn_id": turn_id,
                "custom_id": custom_id,
                "error_type": error_type,
                "error": error_msg,
                "attempt": attempts[turn_id],
            }
    if models_seen:
        metadata["actual_model"] = models_seen.most_common(1)[0][0]
    if usage_totals:
        cumulative = dict(metadata.get("token_usage") or {})
        for key, value in usage_totals.items():
            cumulative[key] = cumulative.get(key, 0) + value
        metadata["token_usage"] = cumulative


def _parse_result_line(
    line: dict[str, Any],
) -> tuple[str, dict[str, Any] | None, str | None, str | None, dict[str, Any] | None]:
    custom_id = str(line.get("custom_id", ""))
    error = line.get("error")
    if error:
        return custom_id, None, "api_error", str(error)[:2000], None
    response = line.get("response")
    if not response:
        return custom_id, None, "missing_response", "No response and no error in result line.", None
    status_code = response.get("status_code")
    body = response.get("body") or {}
    if status_code is not None and status_code != 200:
        return custom_id, None, "api_error", f"HTTP {status_code}: {json.dumps(body)[:500]}", None
    meta = {"model": body.get("model"), "usage": body.get("usage")}
    choices = body.get("choices") or []
    if not choices:
        return custom_id, None, "parse_error", "No choices in response body.", meta
    content = choices[0].get("message", {}).get("content", "")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        return custom_id, None, "parse_error", f"Invalid JSON in model content: {exc}", meta
    try:
        validated = TurnAnnotationResult.model_validate(parsed)
    except ValidationError as exc:
        return custom_id, None, "validation_error", str(exc)[:2000], meta
    return custom_id, validated.model_dump(mode="json"), None, None, meta


def _finalize(
    out_dir: Path,
    original_turns: list[dict[str, Any]],
    existing_annotations: dict[str, dict[str, Any] | None],
    failures: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
) -> None:
    records: list[dict[str, Any]] = []
    claims_rows: list[dict[str, Any]] = []
    truth_dist: Counter[str] = Counter()
    deception_dist: Counter[str] = Counter()
    scores: list[float] = []
    review_count = 0
    spoken_count = 0
    annotated_count = 0

    for raw in original_turns:
        turn_id = str(raw.get("turn_id"))
        game_id = raw.get("game_id")
        annotation = existing_annotations.get(turn_id)
        records.append({**raw, "gpt_annotation": annotation})

        model_output = raw.get("model_output") or {}
        if isinstance(model_output, dict) and model_output.get("speech"):
            spoken_count += 1

        if annotation is None:
            continue
        annotated_count += 1
        truth_dist[str(annotation.get("truth_status"))] += 1
        deception_dist[str(annotation.get("deception_status"))] += 1
        scores.append(float(annotation.get("deception_score", 0.0)))
        if annotation.get("requires_manual_review"):
            review_count += 1
        for claim in annotation.get("claims", []) or []:
            claims_rows.append({"game_id": game_id, "turn_id": turn_id, **claim})

    total = len(original_turns)
    _write_jsonl(out_dir / TURNS_FILE, records)
    _write_jsonl(out_dir / CLAIMS_FILE, claims_rows)
    _write_jsonl(
        out_dir / FAILURES_FILE,
        sorted(failures.values(), key=lambda f: (str(f.get("game_id")), str(f.get("turn_id")))),
    )
    summary = {
        "total_turns": total,
        "annotated_turns": annotated_count,
        "spoken_turns": spoken_count,
        "non_spoken_turns": total - spoken_count,
        "extracted_claim_count": len(claims_rows),
        "truth_label_distribution": dict(truth_dist),
        "deception_label_distribution": dict(deception_dist),
        "average_deception_score": (sum(scores) / len(scores)) if scores else 0.0,
        "manual_review_count": review_count,
        "failures": len(failures),
        "missing_responses": total - annotated_count,
    }
    (out_dir / SUMMARY_FILE).write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    metadata["annotation_schema_version"] = ANNOTATION_SCHEMA_VERSION
    metadata["prompt_version"] = PROMPT_VERSION
    metadata["annotation_timestamp"] = datetime.now(timezone.utc).isoformat()
    (out_dir / ANNOTATION_METADATA_FILE).write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _status_message(status: str, metadata: dict[str, Any], annotated: int, total: int) -> str:
    batch_id = metadata.get("batch_id")
    if status == "submitted":
        history = metadata.get("batch_history") or [{}]
        n = history[-1].get("num_requests", "?")
        return (
            f"Submitted batch {batch_id} ({n} turns; {annotated}/{total} already annotated). "
            "Re-run later to fetch results; any turns beyond this batch's --batch-size cap will "
            "be submitted in the next chunk once this one resolves."
        )
    if status == "polling":
        counts = metadata.get("batch_request_counts")
        progress = (
            f" ({counts['completed']}/{counts['total']} completed, {counts['failed']} failed)"
            if counts
            else ""
        )
        return (
            f"Batch {batch_id} is still {metadata.get('batch_status')}{progress}. "
            "Re-run later (no --wait needed just to check), or pass --wait to block."
        )
    if status == "merged":
        return f"Merged batch results: {annotated}/{total} turns now annotated."
    if status == "live_progress":
        return f"Live run: {annotated}/{total} annotated so far. Re-run to process the next chunk."
    if status.startswith("batch_"):
        return (
            f"Batch ended with status '{metadata.get('batch_status')}'; recorded failures for the "
            f"pending turns. Re-run to submit a retry batch ({annotated}/{total} annotated so far)."
        )
    return f"{annotated}/{total} turns annotated."


def _read_raw_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _read_existing_annotations(out_dir: Path) -> dict[str, dict[str, Any] | None]:
    rows = _read_raw_jsonl(out_dir / TURNS_FILE)
    return {str(row["turn_id"]): row.get("gpt_annotation") for row in rows if "turn_id" in row}


def _read_failures(out_dir: Path) -> dict[str, dict[str, Any]]:
    rows = _read_raw_jsonl(out_dir / FAILURES_FILE)
    return {str(row["turn_id"]): row for row in rows if "turn_id" in row}


def _read_metadata(out_dir: Path) -> dict[str, Any] | None:
    path = out_dir / ANNOTATION_METADATA_FILE
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _new_metadata(dataset_dir: Path, model: str) -> dict[str, Any]:
    return {
        "annotation_schema_version": ANNOTATION_SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "requested_model": model,
        "actual_model": None,
        "annotation_timestamp": None,
        "batch_id": None,
        "batch_status": "not_submitted",
        "batch_row_ids": None,
        "batch_request_counts": None,
        "token_usage": None,
        "source_dataset_path": str(dataset_dir.resolve()),
        "attempts": {},
        "batch_history": [],
    }


__all__ = [
    "ANNOTATION_METADATA_FILE",
    "BATCH_INPUT_FILE",
    "CLAIMS_FILE",
    "FAILURES_FILE",
    "MAX_ATTEMPTS",
    "OUT_DIRNAME",
    "SUMMARY_FILE",
    "AnnotationRunResult",
    "run_annotation",
]

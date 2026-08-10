

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..logging import get_logger
from .batch import (
    DEFAULT_BATCH_SIZE,
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
from .holistic_prompts import HOLISTIC_SYSTEM_PROMPT, build_holistic_user_message
from .holistic_schema import (
    HOLISTIC_MAX_OUTPUT_TOKENS,
    HOLISTIC_PROMPT_VERSION,
    HOLISTIC_RESPONSE_FORMAT,
    HOLISTIC_SCHEMA_VERSION,
    HolisticRatingResult,
)
from .legacy_context import build_row_context, find_legacy_log, load_legacy_rows, row_id
from .live import call_live

logger = get_logger()

                                                                   
                                                                        
                                                                        
                                                                          
LIVE_CHECKPOINT_INTERVAL = 10

OUT_DIRNAME = "gpt4omini_holistic"
RATINGS_FILE = "turns.jsonl"
SUMMARY_FILE = "annotation-summary.json"
FAILURES_FILE = "annotation-failures.jsonl"
BATCH_INPUT_FILE = "batch-input.jsonl"
ANNOTATION_METADATA_FILE = "annotation-metadata.json"

                                                                             
                                                        
MAX_ATTEMPTS = 3

SCORE_KEYS: tuple[str, ...] = ("awareness", "lying", "deception", "planning")


@dataclass
class HolisticRunResult:
    pass

    dataset_dir: Path
    out_dir: Path
    status: str
    batch_id: str | None
    total_rows: int
    rated_rows: int
    pending_rows: int
    message: str


def run_holistic_annotation(
    dataset_dir: str | Path,
    *,
    model: str | None = None,
    overwrite: bool = False,
    wait: bool = False,
    poll_interval_s: float = 20.0,
    poll_timeout_s: float | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    live: bool = False,
) -> HolisticRunResult:
    pass
    dataset_dir = Path(dataset_dir)
    log_path = find_legacy_log(dataset_dir)
    out_dir = dataset_dir / OUT_DIRNAME

    original_rows = load_legacy_rows(log_path)
    row_ids = [row_id(raw, i) for i, raw in enumerate(original_rows)]
    total = len(row_ids)

    existing_ratings = _read_existing_ratings(out_dir)
    metadata = _read_metadata(out_dir)
    attempts: dict[str, int] = dict((metadata or {}).get("attempts", {}))
    failures = _read_failures(out_dir)

    rated_ids = {rid for rid in row_ids if existing_ratings.get(rid) is not None}
    exhausted_ids = {
        rid for rid in row_ids if rid not in rated_ids and attempts.get(rid, 0) >= MAX_ATTEMPTS
    }
    resolved_ids = rated_ids | exhausted_ids
    is_complete = total > 0 and len(resolved_ids) == total

    if is_complete and not overwrite:
        return HolisticRunResult(
            dataset_dir=dataset_dir,
            out_dir=out_dir,
            status="already_complete",
            batch_id=None,
            total_rows=total,
            rated_rows=len(rated_ids),
            pending_rows=0,
            message=(
                f"{out_dir} is already fully rated ({len(rated_ids)}/{total} succeeded, "
                f"{len(exhausted_ids)} permanently failed). Pass overwrite=True to redo it."
            ),
        )

    if overwrite:
        existing_ratings = {}
        metadata = None
        attempts = {}
        failures = {}
        rated_ids = set()
        exhausted_ids = set()
        resolved_ids = set()

    out_dir.mkdir(parents=True, exist_ok=True)
    resolved_model = resolve_model(model)
    if metadata is None:
        metadata = _new_metadata(dataset_dir, log_path, resolved_model)

    pending_ids = [rid for rid in row_ids if rid not in resolved_ids]

    if not pending_ids:
        metadata["batch_status"] = "completed"
        metadata["batch_id"] = None
        metadata["attempts"] = attempts
        _finalize(out_dir, original_rows, existing_ratings, failures, metadata)
        return HolisticRunResult(
            dataset_dir=dataset_dir,
            out_dir=out_dir,
            status="completed",
            batch_id=None,
            total_rows=total,
            rated_rows=len(rated_ids),
            pending_rows=0,
            message=(
                f"Rating complete: {len(rated_ids)}/{total} rows rated"
                + (
                    f", {len(exhausted_ids)} permanently failed after {MAX_ATTEMPTS} attempts."
                    if exhausted_ids
                    else "."
                )
            ),
        )

    client = get_client()
    row_by_id = dict(zip(row_ids, original_rows, strict=True))
    status: str

    if live:
        chunk_ids = pending_ids[:batch_size]
        _run_live(
            client,
            resolved_model,
            chunk_ids,
            row_by_id,
            existing_ratings,
            attempts,
            failures,
            metadata,
            out_dir,
            original_rows,
        )
        rated_now = sum(1 for rid in row_ids if existing_ratings.get(rid) is not None)
        still_exhausted = {
            rid
            for rid in row_ids
            if existing_ratings.get(rid) is None and attempts.get(rid, 0) >= MAX_ATTEMPTS
        }
        if rated_now + len(still_exhausted) == total:
            metadata["batch_status"] = "completed"
            status = "completed"
        else:
            status = "live_progress"
        metadata["attempts"] = attempts
        _finalize(out_dir, original_rows, existing_ratings, failures, metadata)
        return HolisticRunResult(
            dataset_dir=dataset_dir,
            out_dir=out_dir,
            status=status,
            batch_id=None,
            total_rows=total,
            rated_rows=rated_now,
            pending_rows=max(total - rated_now - len(still_exhausted), 0),
            message=_status_message(status, metadata, rated_now, total),
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
            batch, client, chunk_ids, existing_ratings, attempts, failures, metadata
        )
    else:
        chunk_ids = pending_ids[:batch_size]
        requests = []
        for rid in chunk_ids:
            raw = row_by_id.get(rid)
            if raw is None:
                logger.warning("Row {} missing from the source log on rebuild.", rid)
                continue
            row_context = build_row_context(raw)
            user_message = build_holistic_user_message(row_context)
            custom_id = f"{raw.get('game_index')}:{rid}"
            requests.append(
                build_batch_request(
                    custom_id,
                    HOLISTIC_SYSTEM_PROMPT,
                    user_message,
                    resolved_model,
                    HOLISTIC_RESPONSE_FORMAT,
                    max_tokens=HOLISTIC_MAX_OUTPUT_TOKENS,
                )
            )
        input_path = out_dir / BATCH_INPUT_FILE
        write_batch_input(input_path, requests)

        def _checkpoint(batch: Any, requests: list[dict[str, object]] = requests) -> None:
            pass
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
            _finalize(out_dir, original_rows, existing_ratings, failures, metadata)

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
                batch, client, chunk_ids, existing_ratings, attempts, failures, metadata
            )
        else:
            status = "submitted"

    metadata["attempts"] = attempts
    _finalize(out_dir, original_rows, existing_ratings, failures, metadata)

    rated_now = sum(1 for rid in row_ids if existing_ratings.get(rid) is not None)
    still_exhausted = {
        rid
        for rid in row_ids
        if existing_ratings.get(rid) is None and attempts.get(rid, 0) >= MAX_ATTEMPTS
    }
    pending_now = total - rated_now - len(still_exhausted)
    return HolisticRunResult(
        dataset_dir=dataset_dir,
        out_dir=out_dir,
        status=status,
        batch_id=metadata.get("batch_id"),
        total_rows=total,
        rated_rows=rated_now,
        pending_rows=max(pending_now, 0),
        message=_status_message(status, metadata, rated_now, total),
    )


def _handle_batch_status(
    batch: Any,
    client: Any,
    pending_ids: list[str],
    existing_ratings: dict[str, dict[str, Any] | None],
    attempts: dict[str, int],
    failures: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
) -> str:
    pass
    metadata["batch_status"] = batch.status
    metadata["batch_request_counts"] = request_counts_dict(batch)
    if batch.status == "completed":
        _merge_batch(client, batch, existing_ratings, attempts, failures, metadata)
        metadata["batch_id"] = None
        return "merged"
    if batch.status in TERMINAL_STATUSES:                                
        error_detail = describe_batch_errors(batch)
        for rid in pending_ids:
            attempts[rid] = attempts.get(rid, 0) + 1
            game_id = rid.split("#", 1)[0]
            failures[rid] = {
                "game_id": game_id,
                "turn_id": rid,
                "custom_id": f"{game_id}:{rid}",
                "error_type": f"batch_{batch.status}",
                "error": error_detail,
                "attempt": attempts[rid],
            }
        metadata["batch_id"] = None
        return f"batch_{batch.status}"
    return "polling"


def _run_live(
    client: Any,
    resolved_model: str,
    chunk_ids: list[str],
    row_by_id: dict[str, dict[str, Any]],
    existing_ratings: dict[str, dict[str, Any] | None],
    attempts: dict[str, int],
    failures: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
    out_dir: Path,
    original_rows: list[dict[str, Any]],
) -> None:
    pass
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
        _finalize(out_dir, original_rows, existing_ratings, failures, metadata)

    try:
        for i, rid in enumerate(chunk_ids, start=1):
            raw = row_by_id.get(rid)
            if raw is None:
                logger.warning("Row {} missing from the source log on rebuild.", rid)
                continue
            game_id = str(raw.get("game_index"))
            row_context = build_row_context(raw)
            user_message = build_holistic_user_message(row_context)
            parsed, error_type, error_message, meta = call_live(
                client,
                model=resolved_model,
                system_prompt=HOLISTIC_SYSTEM_PROMPT,
                user_message=user_message,
                response_format=HOLISTIC_RESPONSE_FORMAT,
                max_tokens=HOLISTIC_MAX_OUTPUT_TOKENS,
            )
            if parsed is not None:
                try:
                    validated = HolisticRatingResult.model_validate(parsed)
                except ValidationError as exc:
                    error_type, error_message = "validation_error", str(exc)[:2000]
                else:
                    existing_ratings[rid] = validated.model_dump(mode="json")
                    failures.pop(rid, None)
                    if meta and meta.get("model"):
                        models_seen[meta["model"]] += 1
                    usage = (meta or {}).get("usage") or {}
                    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                        usage_totals[key] += int(usage.get(key, 0) or 0)
                    error_type = None                                             
            if error_type is not None:
                attempts[rid] = attempts.get(rid, 0) + 1
                failures[rid] = {
                    "game_id": game_id,
                    "turn_id": rid,
                    "custom_id": f"{game_id}:{rid}",
                    "error_type": error_type,
                    "error": error_message or "unknown error",
                    "attempt": attempts[rid],
                }
            if i % LIVE_CHECKPOINT_INTERVAL == 0:
                _sync_and_persist()
                logger.info("Live progress: {}/{} rows processed this run.", i, total)
    finally:
        _sync_and_persist()


def _merge_batch(
    client: Any,
    batch: Any,
    existing_ratings: dict[str, dict[str, Any] | None],
    attempts: dict[str, int],
    failures: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
) -> None:
    pass
    usage_totals: Counter[str] = Counter()
    models_seen: Counter[str] = Counter()
    for line in iter_batch_result_lines(client, batch):
        custom_id, rating, error_type, error_msg, meta = _parse_result_line(line)
        if ":" not in custom_id:
            logger.warning("Batch result line has an unparseable custom_id: {!r}", custom_id)
            continue
        game_id, rid = custom_id.split(":", 1)
        if rating is not None:
            existing_ratings[rid] = rating
            failures.pop(rid, None)
            if meta and meta.get("model"):
                models_seen[meta["model"]] += 1
            usage = (meta or {}).get("usage") or {}
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                usage_totals[key] += int(usage.get(key, 0) or 0)
        else:
            attempts[rid] = attempts.get(rid, 0) + 1
            failures[rid] = {
                "game_id": game_id,
                "turn_id": rid,
                "custom_id": custom_id,
                "error_type": error_type,
                "error": error_msg,
                "attempt": attempts[rid],
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
    pass
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
        validated = HolisticRatingResult.model_validate(parsed)
    except ValidationError as exc:
        return custom_id, None, "validation_error", str(exc)[:2000], meta
    return custom_id, validated.model_dump(mode="json"), None, None, meta


def _finalize(
    out_dir: Path,
    original_rows: list[dict[str, Any]],
    existing_ratings: dict[str, dict[str, Any] | None],
    failures: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
) -> None:
    pass
    records: list[dict[str, Any]] = []
    score_totals: dict[str, int] = dict.fromkeys(SCORE_KEYS, 0)
    score_dists: dict[str, Counter[int]] = {key: Counter() for key in SCORE_KEYS}
    role_totals: dict[str, dict[str, int]] = {}
    role_counts: Counter[str] = Counter()
    rated_count = 0

    for i, raw in enumerate(original_rows):
        rid = row_id(raw, i)
        rating = existing_ratings.get(rid)
        records.append({**raw, "turn_id": rid, "holistic_rating": rating})
        if rating is None:
            continue
        rated_count += 1
        role = str((raw.get("player") or {}).get("identity", "unknown"))
        role_counts[role] += 1
        role_bucket = role_totals.setdefault(role, dict.fromkeys(SCORE_KEYS, 0))
        for key in SCORE_KEYS:
            value = int(rating.get(key, 0))
            score_totals[key] += value
            score_dists[key][value] += 1
            role_bucket[key] += value

    total = len(original_rows)
    _write_jsonl(out_dir / RATINGS_FILE, records)
    _write_jsonl(
        out_dir / FAILURES_FILE,
        sorted(failures.values(), key=lambda f: (str(f.get("game_id")), str(f.get("turn_id")))),
    )
    summary = {
        "total_rows": total,
        "rated_rows": rated_count,
        "average_scores": {
            key: (score_totals[key] / rated_count if rated_count else 0.0) for key in SCORE_KEYS
        },
        "score_distributions": {
            key: {str(v): c for v, c in sorted(score_dists[key].items())} for key in SCORE_KEYS
        },
        "average_scores_by_role": {
            role: {key: (role_totals[role][key] / role_counts[role]) for key in SCORE_KEYS}
            for role in role_totals
        },
        "failures": len(failures),
        "missing_responses": total - rated_count,
    }
    (out_dir / SUMMARY_FILE).write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    metadata["annotation_schema_version"] = HOLISTIC_SCHEMA_VERSION
    metadata["prompt_version"] = HOLISTIC_PROMPT_VERSION
    metadata["annotation_timestamp"] = datetime.now(timezone.utc).isoformat()
    (out_dir / ANNOTATION_METADATA_FILE).write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _status_message(status: str, metadata: dict[str, Any], rated: int, total: int) -> str:
    pass
    batch_id = metadata.get("batch_id")
    if status == "submitted":
        history = metadata.get("batch_history") or [{}]
        n = history[-1].get("num_requests", "?")
        return (
            f"Submitted batch {batch_id} ({n} rows; {rated}/{total} already rated). "
            "Re-run later to fetch results; any rows beyond this batch's --batch-size cap will "
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
        return f"Merged batch results: {rated}/{total} rows now rated."
    if status == "live_progress":
        return f"Live run: {rated}/{total} rated so far. Re-run to process the next chunk."
    if status.startswith("batch_"):
        return (
            f"Batch ended with status '{metadata.get('batch_status')}'; recorded failures for the "
            f"pending rows. Re-run to submit a retry batch ({rated}/{total} rated so far)."
        )
    return f"{rated}/{total} rows rated."


                                                                               
                  
                                                                               


def _read_raw_jsonl(path: Path) -> list[dict[str, Any]]:
    pass
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            rows.append(json.loads(stripped))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    pass
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def _read_existing_ratings(out_dir: Path) -> dict[str, dict[str, Any] | None]:
    pass
    rows = _read_raw_jsonl(out_dir / RATINGS_FILE)
    return {str(row["turn_id"]): row.get("holistic_rating") for row in rows if "turn_id" in row}


def _read_failures(out_dir: Path) -> dict[str, dict[str, Any]]:
    pass
    rows = _read_raw_jsonl(out_dir / FAILURES_FILE)
    return {str(row["turn_id"]): row for row in rows if "turn_id" in row}


def _read_metadata(out_dir: Path) -> dict[str, Any] | None:
    pass
    path = out_dir / ANNOTATION_METADATA_FILE
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _new_metadata(dataset_dir: Path, log_path: Path, model: str) -> dict[str, Any]:
    pass
    return {
        "annotation_schema_version": HOLISTIC_SCHEMA_VERSION,
        "prompt_version": HOLISTIC_PROMPT_VERSION,
        "requested_model": model,
        "actual_model": None,
        "annotation_timestamp": None,
        "batch_id": None,
        "batch_status": "not_submitted",
        "batch_row_ids": None,
        "batch_request_counts": None,
        "token_usage": None,
        "source_dataset_path": str(dataset_dir.resolve()),
        "source_log_file": log_path.name,
        "attempts": {},
        "batch_history": [],
    }


__all__ = [
    "ANNOTATION_METADATA_FILE",
    "BATCH_INPUT_FILE",
    "FAILURES_FILE",
    "MAX_ATTEMPTS",
    "OUT_DIRNAME",
    "RATINGS_FILE",
    "SUMMARY_FILE",
    "HolisticRunResult",
    "run_holistic_annotation",
]

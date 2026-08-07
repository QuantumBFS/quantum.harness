"""Exact-fallback depth-9..12 scan of the 488 depth-8 survivors."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import exterior_depth8_exact_fallback as depth8
from . import weights
from .exterior_candidates import (
    candidate_card,
    candidate_id,
    exact_atoms_from_card,
    float_atoms_from_card,
)
from .exterior_thin_scan import mixed_words


SCHEMA_VERSION = "exterior-depth12-exact-fallback-v1"
RUN_ID = "exterior-depth12-exact-fallback-v1"
DEPTHS = (9, 10, 11, 12)
WORDS = mixed_words(2, depths=DEPTHS)
WORKERS = 76
PARENT_STATUS = depth8.SURVIVOR_STATUS
SURVIVOR_STATUS = "survivor-depth12-exact-fallback"
TERMINAL_STATUSES = {
    SURVIVOR_STATUS,
    "rejected-negative-stable",
    "rejected-negative-exact-fallback",
    "rejected-complex-stable",
    "operational-error",
}


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return value


def _write_json_atomic(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _stage2_plan(
    stage2_run_dir: str | Path,
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    plan = _load_json(Path(stage2_run_dir) / "plan-summary.json")
    entries = plan.get("candidates")
    if (
        not isinstance(plan.get("run_id"), str)
        or not isinstance(plan.get("source_commit"), str)
        or not isinstance(plan.get("plan_hash"), str)
        or not isinstance(plan.get("protocol_hash"), str)
        or not isinstance(entries, list)
        or not all(isinstance(entry, dict) for entry in entries)
    ):
        raise RuntimeError("invalid Stage-2 plan summary")
    by_id: dict[str, dict[str, object]] = {}
    for entry in entries:
        identity = entry.get("candidate_id")
        if not isinstance(identity, str) or identity in by_id:
            raise RuntimeError("invalid or duplicate Stage-2 candidate")
        by_id[identity] = entry
    return plan, by_id


def _stage2_provenance(plan: Mapping[str, object]) -> dict[str, object]:
    return {
        "stage2_run_id": plan["run_id"],
        "stage2_source_commit": plan["source_commit"],
        "stage2_plan_hash": plan["plan_hash"],
        "stage2_protocol_hash": plan["protocol_hash"],
    }


def _validate_depth8_lineage(
    stage2_plan: Mapping[str, object],
    depth8_plan: Mapping[str, object],
) -> None:
    expected = {
        "parent_run_id": stage2_plan["run_id"],
        "parent_source_commit": stage2_plan["source_commit"],
        "parent_plan_hash": stage2_plan["plan_hash"],
        "parent_protocol_hash": stage2_plan["protocol_hash"],
    }
    if any(depth8_plan.get(key) != value for key, value in expected.items()):
        raise RuntimeError("depth-8 run does not bind the supplied Stage-2 plan")


def _validate_card_entry(
    depth8_entry: Mapping[str, object],
    stage2_entry: Mapping[str, object],
) -> None:
    identity = stage2_entry.get("candidate_id")
    keys = ("candidate_id", "card_sha256", "template", "seed", "dimension")
    if any(depth8_entry.get(key) != stage2_entry.get(key) for key in keys):
        raise RuntimeError(f"depth-8/Stage-2 candidate mismatch: {identity}")
    card = candidate_card(
        template=str(stage2_entry["template"]),
        seed=stage2_entry["seed"],  # type: ignore[arg-type]
    )
    if (
        candidate_id(card) != identity
        or stage2_entry.get("card_sha256") != identity
        or card["dimension"] != stage2_entry.get("dimension")
    ):
        raise RuntimeError(f"Stage-2 candidate does not reconstruct: {identity}")


def _depth8_manifest(
    depth8_root: Path,
    entry: Mapping[str, object],
    *,
    depth8_plan_hash: str,
) -> tuple[dict[str, object], Path]:
    identity = str(entry["candidate_id"])
    path = depth8_root / "candidates" / identity / "manifest.json"
    manifest = _load_json(path)
    if (
        manifest.get("schema_version") != depth8.SCHEMA_VERSION
        or manifest.get("run_id") != depth8.RUN_ID
        or manifest.get("continuation_plan_hash") != depth8_plan_hash
        or manifest.get("candidate_id") != identity
        or manifest.get("card_sha256") != identity
        or manifest.get("status") not in depth8.TERMINAL_STATUSES
    ):
        raise RuntimeError(f"invalid depth-8 terminal manifest: {identity}")
    if manifest["status"] == PARENT_STATUS and (
        manifest.get("depths") != list(depth8.DEPTHS)
        or manifest.get("planned_words") != 472
        or manifest.get("tested_words") != 472
        or manifest.get("first_failure") is not None
    ):
        raise RuntimeError(f"incomplete depth-8 survivor evidence: {identity}")
    return manifest, path


def plan_continuation(
    stage2_run_dir: str | Path,
    depth8_run_dir: str | Path,
    run_dir: str | Path,
    *,
    expected_count: int | None = 488,
) -> dict[str, object]:
    """Freeze exactly the completed depth-8 survivors for deeper scanning."""

    stage2, stage2_entries = _stage2_plan(stage2_run_dir)
    depth8_root = Path(depth8_run_dir)
    parent_plan = _load_json(depth8_root / "continuation-plan.json")
    parent_entries = depth8._validate_plan(parent_plan)
    _validate_depth8_lineage(stage2, parent_plan)

    selected: list[dict[str, object]] = []
    for parent_entry in parent_entries:
        identity = str(parent_entry["candidate_id"])
        stage2_entry = stage2_entries.get(identity)
        if stage2_entry is None:
            raise RuntimeError(f"depth-8 candidate absent from Stage-2: {identity}")
        _validate_card_entry(parent_entry, stage2_entry)
        manifest, path = _depth8_manifest(
            depth8_root,
            parent_entry,
            depth8_plan_hash=str(parent_plan["continuation_plan_hash"]),
        )
        if manifest["status"] != PARENT_STATUS:
            continue
        selected.append(
            {
                "candidate_id": identity,
                "card_sha256": identity,
                "template": stage2_entry["template"],
                "seed": stage2_entry["seed"],
                "dimension": stage2_entry["dimension"],
                "stage2_shard": stage2_entry.get("shard"),
                "depth8_manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    selected.sort(key=lambda entry: str(entry["candidate_id"]))
    if expected_count is not None and len(selected) != expected_count:
        raise RuntimeError(
            f"expected {expected_count} depth-8 survivors, found {len(selected)}"
        )

    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": RUN_ID,
        **_stage2_provenance(stage2),
        "depth8_run_id": parent_plan["run_id"],
        "depth8_plan_hash": parent_plan["continuation_plan_hash"],
        "depths": list(DEPTHS),
        "word_count_per_candidate": len(WORDS),
        "workers": WORKERS,
        "candidate_count": len(selected),
        "candidates": selected,
    }
    payload["continuation_plan_hash"] = _sha256(payload)
    _write_json_atomic(Path(run_dir) / "continuation-plan.json", payload)
    return {
        "run_id": RUN_ID,
        "candidate_count": len(selected),
        "word_count_per_candidate": len(WORDS),
        "continuation_plan_hash": payload["continuation_plan_hash"],
    }


def _validate_plan(plan: Mapping[str, object]) -> list[dict[str, object]]:
    stored = plan.get("continuation_plan_hash")
    payload = dict(plan)
    payload.pop("continuation_plan_hash", None)
    entries = plan.get("candidates")
    if (
        plan.get("schema_version") != SCHEMA_VERSION
        or plan.get("run_id") != RUN_ID
        or plan.get("depths") != list(DEPTHS)
        or plan.get("word_count_per_candidate") != len(WORDS)
        or plan.get("workers") != WORKERS
        or not isinstance(stored, str)
        or _sha256(payload) != stored
        or not isinstance(entries, list)
        or not all(isinstance(entry, dict) for entry in entries)
        or plan.get("candidate_count") != len(entries)
    ):
        raise RuntimeError("depth-12 continuation plan is invalid")
    return entries


def _validate_inputs(
    stage2_run_dir: str | Path,
    depth8_run_dir: str | Path,
    plan: Mapping[str, object],
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]]]:
    stage2, stage2_entries = _stage2_plan(stage2_run_dir)
    if any(
        plan.get(key) != value
        for key, value in _stage2_provenance(stage2).items()
    ):
        raise RuntimeError("Stage-2 input changed after depth-12 planning")
    depth8_plan = _load_json(Path(depth8_run_dir) / "continuation-plan.json")
    depth8_entries_list = depth8._validate_plan(depth8_plan)
    _validate_depth8_lineage(stage2, depth8_plan)
    if (
        depth8_plan.get("run_id") != plan.get("depth8_run_id")
        or depth8_plan.get("continuation_plan_hash") != plan.get("depth8_plan_hash")
    ):
        raise RuntimeError("depth-8 input changed after depth-12 planning")
    depth8_entries = {
        str(entry["candidate_id"]): entry for entry in depth8_entries_list
    }
    return stage2_entries, depth8_entries


def _run_candidate(
    stage2_entry: Mapping[str, object],
    *,
    plan: Mapping[str, object],
    worker_index: int,
) -> dict[str, object]:
    card = candidate_card(
        template=str(stage2_entry["template"]),
        seed=stage2_entry["seed"],  # type: ignore[arg-type]
    )
    identity = candidate_id(card)
    if (
        identity != stage2_entry["candidate_id"]
        or identity != stage2_entry["card_sha256"]
    ):
        raise RuntimeError("Stage-2 candidate identity mismatch")
    exact_atoms = exact_atoms_from_card(card)
    float_atoms = float_atoms_from_card(card)
    counts: Counter[str] = Counter()
    fallback_records: list[dict[str, object]] = []
    first_failure: dict[str, object] | None = None
    status = SURVIVOR_STATUS
    for word in WORDS:
        product = np.eye(int(stage2_entry["dimension"]))
        for index in word:
            product = product @ float_atoms[index]
        result = weights.classify_product(product)
        counts[result.classification] += 1
        if result.classification in {"positive", "zero"}:
            continue
        record = depth8._result_record(result, word)
        if result.classification == "negative":
            status = "rejected-negative-stable"
            first_failure = record
            break
        if result.classification == "complex":
            status = "rejected-complex-stable"
            first_failure = record
            break
        if result.classification != "uncertain":
            raise RuntimeError(f"unsupported classifier result {result.classification}")
        classification, evidence = depth8._adjudicate_word(
            [exact_atoms[index] for index in word]
        )
        fallback_records.append({"word_indices": list(word), **evidence})
        if classification == "negative":
            status = "rejected-negative-exact-fallback"
            first_failure = {**record, "exact_fallback": evidence}
            break
        if classification != "nonnegative":
            raise RuntimeError(f"unsupported exact fallback result {classification}")
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": RUN_ID,
        "continuation_plan_hash": plan["continuation_plan_hash"],
        "stage2_run_id": plan["stage2_run_id"],
        "stage2_plan_hash": plan["stage2_plan_hash"],
        "stage2_protocol_hash": plan["stage2_protocol_hash"],
        "depth8_run_id": plan["depth8_run_id"],
        "depth8_plan_hash": plan["depth8_plan_hash"],
        "parent_status": PARENT_STATUS,
        "candidate_id": identity,
        "card_sha256": identity,
        "template": stage2_entry["template"],
        "seed": stage2_entry["seed"],
        "dimension": stage2_entry["dimension"],
        "worker_index": worker_index,
        "workers": WORKERS,
        "depths": list(DEPTHS),
        "planned_words": len(WORDS),
        "tested_words": sum(counts.values()),
        "normal_classification_counts": dict(sorted(counts.items())),
        "exact_fallback_count": len(fallback_records),
        "exact_fallback_records": fallback_records,
        "status": status,
        "first_failure": first_failure,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def _terminal_is_valid(
    manifest: Mapping[str, object],
    *,
    entry: Mapping[str, object],
    plan: Mapping[str, object],
    worker_index: int | None = None,
) -> bool:
    status = manifest.get("status")
    if (
        manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("run_id") != RUN_ID
        or manifest.get("continuation_plan_hash") != plan["continuation_plan_hash"]
        or manifest.get("candidate_id") != entry["candidate_id"]
        or manifest.get("workers") != WORKERS
        or status not in TERMINAL_STATUSES
        or (worker_index is not None and manifest.get("worker_index") != worker_index)
    ):
        return False
    if status == "operational-error":
        return isinstance(manifest.get("error"), str)
    tested = manifest.get("tested_words")
    if (
        manifest.get("card_sha256") != entry["candidate_id"]
        or manifest.get("depths") != list(DEPTHS)
        or manifest.get("planned_words") != len(WORDS)
        or not isinstance(tested, int)
        or isinstance(tested, bool)
        or not 1 <= tested <= len(WORDS)
    ):
        return False
    failure = manifest.get("first_failure")
    if status == SURVIVOR_STATUS:
        return tested == len(WORDS) and failure is None
    if not isinstance(failure, Mapping):
        return False
    if status == "rejected-negative-stable":
        return failure.get("classification") == "negative"
    if status == "rejected-complex-stable":
        return failure.get("classification") == "complex"
    exact = failure.get("exact_fallback")
    return (
        failure.get("classification") == "uncertain"
        and isinstance(exact, Mapping)
        and isinstance(exact.get("exact_determinant"), Mapping)
        and exact["exact_determinant"].get("sign") == -1
    )


def run_worker(
    stage2_run_dir: str | Path,
    depth8_run_dir: str | Path,
    run_dir: str | Path,
    *,
    worker_index: int,
    workers: int = WORKERS,
    progress: bool = False,
) -> dict[str, int]:
    """Run one of exactly 76 deterministic hash workers with atomic resume."""

    if (
        workers != WORKERS
        or not isinstance(worker_index, int)
        or isinstance(worker_index, bool)
        or not 0 <= worker_index < WORKERS
    ):
        raise ValueError(f"require 0 <= worker_index < {WORKERS} and workers={WORKERS}")
    root = Path(run_dir)
    plan = _load_json(root / "continuation-plan.json")
    entries = _validate_plan(plan)
    stage2_entries, depth8_entries = _validate_inputs(
        stage2_run_dir, depth8_run_dir, plan
    )
    completed = reused = operational_errors = 0
    for entry in entries:
        identity = str(entry["candidate_id"])
        if int(identity[:16], 16) % WORKERS != worker_index:
            continue
        path = root / "candidates" / identity / "manifest.json"
        if path.is_file():
            manifest = _load_json(path)
            if not _terminal_is_valid(
                manifest,
                entry=entry,
                plan=plan,
                worker_index=worker_index,
            ):
                raise RuntimeError(f"stale depth-12 manifest for {identity}")
            reused += 1
            operational_errors += manifest["status"] == "operational-error"
            continue
        stage2_entry = stage2_entries.get(identity)
        parent_entry = depth8_entries.get(identity)
        if stage2_entry is None or parent_entry is None:
            raise RuntimeError(f"candidate missing from frozen inputs: {identity}")
        _validate_card_entry(parent_entry, stage2_entry)
        parent_manifest, parent_path = _depth8_manifest(
            Path(depth8_run_dir),
            parent_entry,
            depth8_plan_hash=str(plan["depth8_plan_hash"]),
        )
        if (
            parent_manifest["status"] != PARENT_STATUS
            or hashlib.sha256(parent_path.read_bytes()).hexdigest()
            != entry["depth8_manifest_sha256"]
        ):
            raise RuntimeError(f"depth-8 survivor evidence changed: {identity}")
        try:
            manifest = _run_candidate(
                stage2_entry,
                plan=plan,
                worker_index=worker_index,
            )
        except Exception as exc:
            manifest = {
                "schema_version": SCHEMA_VERSION,
                "run_id": RUN_ID,
                "continuation_plan_hash": plan["continuation_plan_hash"],
                "candidate_id": identity,
                "worker_index": worker_index,
                "workers": WORKERS,
                "status": "operational-error",
                "error": f"{type(exc).__name__}: {exc}",
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        _write_json_atomic(path, manifest)
        completed += 1
        operational_errors += manifest["status"] == "operational-error"
        if progress:
            print(
                f"worker {worker_index}/{WORKERS}: {identity} {manifest['status']}",
                flush=True,
            )
    return {
        "completed": completed,
        "reused": reused,
        "operational_errors": operational_errors,
    }


def collect_run(
    run_dir: str | Path,
    *,
    markdown: str | Path | None = None,
) -> dict[str, object]:
    """Collect compact completion and scientific counts."""

    root = Path(run_dir)
    plan = _load_json(root / "continuation-plan.json")
    entries = _validate_plan(plan)
    counts: Counter[str] = Counter()
    tested_words = exact_fallbacks = missing = stale = 0
    survivors: list[str] = []
    for entry in entries:
        identity = str(entry["candidate_id"])
        path = root / "candidates" / identity / "manifest.json"
        if not path.is_file():
            missing += 1
            continue
        manifest = _load_json(path)
        if not _terminal_is_valid(manifest, entry=entry, plan=plan):
            stale += 1
            continue
        status = str(manifest["status"])
        counts[status] += 1
        tested_words += int(manifest.get("tested_words", 0))
        exact_fallbacks += int(manifest.get("exact_fallback_count", 0))
        if status == SURVIVOR_STATUS:
            survivors.append(identity)
    result: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": RUN_ID,
        "continuation_plan_hash": plan["continuation_plan_hash"],
        "depth8_plan_hash": plan["depth8_plan_hash"],
        "planned": len(entries),
        "terminal": sum(counts.values()),
        "missing": missing,
        "stale": stale,
        "status_counts": dict(sorted(counts.items())),
        "tested_words": tested_words,
        "exact_fallbacks": exact_fallbacks,
        "survivors": survivors,
    }
    _write_json_atomic(root / "collect.json", result)
    if markdown is not None:
        lines = [
            f"# Depth-12 exact-fallback continuation — {RUN_ID}",
            "",
            f"- planned / terminal / missing / stale: {len(entries)} / "
            f"{sum(counts.values())} / {missing} / {stale}",
            f"- tested words: {tested_words}; exact fallbacks: {exact_fallbacks}",
            "",
            "| status | count |",
            "|---|---:|",
        ]
        lines.extend(
            f"| {status} | {count} |" for status, count in sorted(counts.items())
        )
        path = Path(markdown)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("--stage2-run-dir", required=True)
    plan.add_argument("--depth8-run-dir", required=True)
    plan.add_argument("--run-dir", required=True)
    plan.add_argument("--expected-count", type=int, default=488)
    run = commands.add_parser("run")
    run.add_argument("--stage2-run-dir", required=True)
    run.add_argument("--depth8-run-dir", required=True)
    run.add_argument("--run-dir", required=True)
    run.add_argument("--worker-index", required=True, type=int)
    run.add_argument("--workers", type=int, default=WORKERS)
    collect = commands.add_parser("collect")
    collect.add_argument("--run-dir", required=True)
    collect.add_argument("--markdown")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "plan":
        result = plan_continuation(
            args.stage2_run_dir,
            args.depth8_run_dir,
            args.run_dir,
            expected_count=args.expected_count,
        )
    elif args.command == "run":
        result = run_worker(
            args.stage2_run_dir,
            args.depth8_run_dir,
            args.run_dir,
            worker_index=args.worker_index,
            workers=args.workers,
            progress=True,
        )
    else:
        result = collect_run(args.run_dir, markdown=args.markdown)
    print(_canonical_json(result), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["collect_run", "main", "plan_continuation", "run_worker"]

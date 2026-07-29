"""Complete depths 9..12 for Stage-3 high-precision nonnegative cards."""

from __future__ import annotations

import argparse
import hashlib
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import exterior_deep_high_precision_replay as stage3hp
from . import exterior_deep_survivor as stage3
from . import exterior_depth12_exact_fallback as common
from . import exterior_depth8_exact_fallback as exact_fallback
from . import weights
from .exterior_candidates import (
    candidate_card,
    candidate_id,
    exact_atoms_from_card,
    float_atoms_from_card,
)


SCHEMA_VERSION = "exterior-depth12-hp-continuation-v1"
RUN_ID = "exterior-depth12-hp-continuation-v1"
DEPTHS = common.DEPTHS
WORDS = common.WORDS
WORKERS = common.WORKERS
SURVIVOR_STATUS = "survivor-depth12-hp-continuation"
TERMINAL_STATUSES = {
    SURVIVOR_STATUS,
    "rejected-negative-stable",
    "rejected-negative-exact-fallback",
    "rejected-complex-stable",
    "operational-error",
}


def _stage2_inputs(
    stage2_run_dir: str | Path,
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    plan, entries = stage3._load_stage2_survivors(stage2_run_dir)
    if not isinstance(plan.get("plan_hash"), str):
        raise RuntimeError("Stage-2 plan hash is missing")
    return plan, {str(entry["candidate_id"]): entry for entry in entries}


def _validate_lineage(
    stage2_plan: Mapping[str, object],
    hp_plan: Mapping[str, object],
) -> None:
    expected = {
        "stage2_run_id": stage2_plan["run_id"],
        "stage2_source_commit": stage2_plan["source_commit"],
        "stage2_plan_hash": stage2_plan["plan_hash"],
        "stage2_protocol_hash": stage2_plan["protocol_hash"],
        "stage3_run_id": stage3.RUN_ID,
        "stage3_protocol_hash": stage3._protocol_hash(stage2_plan, stage3.RUN_ID),
    }
    if any(hp_plan.get(key) != value for key, value in expected.items()):
        raise RuntimeError("Stage-3 high-precision run has different lineage")


def _validate_stage3_manifest(
    manifest: Mapping[str, object],
    *,
    entry: Mapping[str, object],
    stage2_plan: Mapping[str, object],
    protocol_hash: str,
) -> tuple[dict[str, object], list[int]]:
    if not stage3._terminal_manifest_is_valid(
        manifest,
        entry=entry,
        plan=stage2_plan,
        run_id=stage3.RUN_ID,
        protocol_hash=protocol_hash,
    ):
        raise RuntimeError(f"invalid Stage-3 terminal: {entry['candidate_id']}")
    return stage3hp._validate_failure(manifest, str(entry["candidate_id"]))


def _validate_hp_manifest(
    manifest: Mapping[str, object],
    *,
    hp_entry: Mapping[str, object],
    replay_plan_hash: str,
) -> None:
    exact = manifest.get("exact_determinant")
    if (
        manifest.get("schema_version") != stage3hp.SCHEMA_VERSION
        or manifest.get("run_id") != stage3hp.RUN_ID
        or manifest.get("replay_plan_hash") != replay_plan_hash
        or manifest.get("candidate_id") != hp_entry["candidate_id"]
        or manifest.get("card_sha256") != hp_entry["candidate_id"]
        or manifest.get("word_indices") != hp_entry["word_indices"]
        or manifest.get("first_failure_sha256")
        != hp_entry["first_failure_sha256"]
        or manifest.get("status") != "confirmed-nonnegative"
        or not isinstance(exact, Mapping)
        or exact.get("sign") not in (0, 1)
    ):
        raise RuntimeError(
            f"incomplete Stage-3 high-precision proof: {hp_entry['candidate_id']}"
        )


def _valid_word(word: object) -> bool:
    return (
        isinstance(word, list)
        and len(word) in DEPTHS
        and all(
            isinstance(index, int)
            and not isinstance(index, bool)
            and index in (0, 1)
            for index in word
        )
        and 0 in word
        and 1 in word
    )


def plan_continuation(
    stage2_run_dir: str | Path,
    stage3_run_dir: str | Path,
    stage3hp_run_dir: str | Path,
    run_dir: str | Path,
    *,
    expected_count: int | None = 307,
) -> dict[str, object]:
    """Freeze confirmed Stage-3 nonnegative records for full-tranche scanning."""

    stage2_plan, stage2_entries = _stage2_inputs(stage2_run_dir)
    hp_root = Path(stage3hp_run_dir)
    hp_plan = common._load_json(hp_root / "replay-plan.json")
    hp_entries = stage3hp._validate_plan(hp_plan)
    _validate_lineage(stage2_plan, hp_plan)
    protocol_hash = str(hp_plan["stage3_protocol_hash"])
    stage3_root = Path(stage3_run_dir)

    selected: list[dict[str, object]] = []
    for hp_entry in hp_entries:
        identity = str(hp_entry["candidate_id"])
        stage2_entry = stage2_entries.get(identity)
        if stage2_entry is None:
            raise RuntimeError(f"HP candidate absent from Stage-2: {identity}")
        stage3_path = stage3_root / "candidates" / identity / "manifest.json"
        stage3_manifest = common._load_json(stage3_path)
        failure, word = _validate_stage3_manifest(
            stage3_manifest,
            entry=stage2_entry,
            stage2_plan=stage2_plan,
            protocol_hash=protocol_hash,
        )
        if (
            not _valid_word(word)
            or word != hp_entry.get("word_indices")
            or stage3hp._sha256(failure) != hp_entry.get("first_failure_sha256")
            or hashlib.sha256(stage3_path.read_bytes()).hexdigest()
            != hp_entry.get("stage3_manifest_sha256")
        ):
            raise RuntimeError(f"Stage-3 stopping-word binding mismatch: {identity}")
        hp_path = hp_root / "candidates" / identity / "manifest.json"
        hp_manifest = common._load_json(hp_path)
        _validate_hp_manifest(
            hp_manifest,
            hp_entry=hp_entry,
            replay_plan_hash=str(hp_plan["replay_plan_hash"]),
        )
        card = candidate_card(
            template=str(stage2_entry["template"]),
            seed=stage2_entry["seed"],  # type: ignore[arg-type]
        )
        if (
            candidate_id(card) != identity
            or stage2_entry.get("card_sha256") != identity
        ):
            raise RuntimeError(f"Stage-2 candidate does not reconstruct: {identity}")
        selected.append(
            {
                "candidate_id": identity,
                "card_sha256": identity,
                "template": stage2_entry["template"],
                "seed": stage2_entry["seed"],
                "dimension": stage2_entry["dimension"],
                "stage2_shard": stage2_entry.get("shard"),
                "confirmed_word_indices": word,
                "first_failure_sha256": hp_entry["first_failure_sha256"],
                "stage3_manifest_sha256": hp_entry["stage3_manifest_sha256"],
                "stage3hp_manifest_sha256": hashlib.sha256(
                    hp_path.read_bytes()
                ).hexdigest(),
            }
        )
    selected.sort(key=lambda entry: str(entry["candidate_id"]))
    if expected_count is not None and len(selected) != expected_count:
        raise RuntimeError(
            f"expected {expected_count} confirmed-nonnegative records, "
            f"found {len(selected)}"
        )

    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": RUN_ID,
        "stage2_run_id": stage2_plan["run_id"],
        "stage2_source_commit": stage2_plan["source_commit"],
        "stage2_plan_hash": stage2_plan["plan_hash"],
        "stage2_protocol_hash": stage2_plan["protocol_hash"],
        "stage3_run_id": stage3.RUN_ID,
        "stage3_protocol_hash": protocol_hash,
        "stage3hp_run_id": hp_plan["run_id"],
        "stage3hp_plan_hash": hp_plan["replay_plan_hash"],
        "depths": list(DEPTHS),
        "word_count_per_candidate": len(WORDS),
        "workers": WORKERS,
        "candidate_count": len(selected),
        "candidates": selected,
    }
    payload["continuation_plan_hash"] = common._sha256(payload)
    common._write_json_atomic(Path(run_dir) / "continuation-plan.json", payload)
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
        or plan.get("stage3_run_id") != stage3.RUN_ID
        or plan.get("stage3hp_run_id") != stage3hp.RUN_ID
        or plan.get("depths") != list(DEPTHS)
        or plan.get("word_count_per_candidate") != len(WORDS)
        or plan.get("workers") != WORKERS
        or not isinstance(stored, str)
        or common._sha256(payload) != stored
        or not isinstance(entries, list)
        or not all(isinstance(entry, dict) for entry in entries)
        or plan.get("candidate_count") != len(entries)
    ):
        raise RuntimeError("Stage-3 HP continuation plan is invalid")
    return entries


def _validate_inputs(
    stage2_run_dir: str | Path,
    stage3hp_run_dir: str | Path,
    plan: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, dict[str, object]], dict[str, object]]:
    stage2_plan, stage2_entries = _stage2_inputs(stage2_run_dir)
    expected = {
        "stage2_run_id": stage2_plan["run_id"],
        "stage2_source_commit": stage2_plan["source_commit"],
        "stage2_plan_hash": stage2_plan["plan_hash"],
        "stage2_protocol_hash": stage2_plan["protocol_hash"],
        "stage3_run_id": stage3.RUN_ID,
        "stage3_protocol_hash": stage3._protocol_hash(stage2_plan, stage3.RUN_ID),
    }
    if any(plan.get(key) != value for key, value in expected.items()):
        raise RuntimeError("Stage-2/Stage-3 input changed after planning")
    hp_plan = common._load_json(Path(stage3hp_run_dir) / "replay-plan.json")
    stage3hp._validate_plan(hp_plan)
    _validate_lineage(stage2_plan, hp_plan)
    if (
        hp_plan.get("run_id") != plan.get("stage3hp_run_id")
        or hp_plan.get("replay_plan_hash") != plan.get("stage3hp_plan_hash")
    ):
        raise RuntimeError("Stage-3 HP input changed after planning")
    return stage2_plan, stage2_entries, hp_plan


def _run_candidate(
    entry: Mapping[str, object],
    stage2_entry: Mapping[str, object],
    hp_manifest: Mapping[str, object],
    *,
    plan: Mapping[str, object],
    worker_index: int,
) -> dict[str, object]:
    card = candidate_card(
        template=str(stage2_entry["template"]),
        seed=stage2_entry["seed"],  # type: ignore[arg-type]
    )
    identity = candidate_id(card)
    if identity != entry["candidate_id"] or identity != stage2_entry["card_sha256"]:
        raise RuntimeError("candidate identity mismatch")
    exact_atoms = exact_atoms_from_card(card)
    float_atoms = float_atoms_from_card(card)
    counts: Counter[str] = Counter()
    fallbacks: list[dict[str, object]] = []
    reused_evidence: dict[str, object] | None = None
    tested = 0
    status = SURVIVOR_STATUS
    first_failure: dict[str, object] | None = None
    for word in WORDS:
        tested += 1
        if list(word) == entry["confirmed_word_indices"]:
            reused_evidence = {
                "source": "reused-stage3-high-precision-proof",
                "word_indices": list(word),
                "stage3hp_manifest_sha256": entry["stage3hp_manifest_sha256"],
                "ladder": hp_manifest.get("ladder", []),
                "exact_determinant": hp_manifest["exact_determinant"],
            }
            continue
        product = np.eye(int(stage2_entry["dimension"]))
        for index in word:
            product = product @ float_atoms[index]
        result = weights.classify_product(product)
        counts[result.classification] += 1
        if result.classification in {"positive", "zero"}:
            continue
        record = exact_fallback._result_record(result, word)
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
        classification, evidence = exact_fallback._adjudicate_word(
            [exact_atoms[index] for index in word]
        )
        fallbacks.append({"word_indices": list(word), **evidence})
        if classification == "negative":
            status = "rejected-negative-exact-fallback"
            first_failure = {**record, "exact_fallback": evidence}
            break
        if classification != "nonnegative":
            raise RuntimeError(f"unsupported exact fallback result {classification}")
    if status == SURVIVOR_STATUS and reused_evidence is None:
        raise RuntimeError("confirmed Stage-3 stopping word was not traversed")
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": RUN_ID,
        "continuation_plan_hash": plan["continuation_plan_hash"],
        "stage2_run_id": plan["stage2_run_id"],
        "stage2_plan_hash": plan["stage2_plan_hash"],
        "stage2_protocol_hash": plan["stage2_protocol_hash"],
        "stage3_run_id": plan["stage3_run_id"],
        "stage3_protocol_hash": plan["stage3_protocol_hash"],
        "stage3hp_run_id": plan["stage3hp_run_id"],
        "stage3hp_plan_hash": plan["stage3hp_plan_hash"],
        "candidate_id": identity,
        "card_sha256": identity,
        "template": stage2_entry["template"],
        "seed": stage2_entry["seed"],
        "dimension": stage2_entry["dimension"],
        "worker_index": worker_index,
        "workers": WORKERS,
        "depths": list(DEPTHS),
        "planned_words": len(WORDS),
        "tested_words": tested,
        "normal_classification_counts": dict(sorted(counts.items())),
        "reused_hp_count": int(reused_evidence is not None),
        "reused_hp_evidence": reused_evidence,
        "exact_fallback_count": len(fallbacks),
        "exact_fallback_records": fallbacks,
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
        return (
            tested == len(WORDS)
            and failure is None
            and manifest.get("reused_hp_count") == 1
        )
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
    stage3_run_dir: str | Path,
    stage3hp_run_dir: str | Path,
    run_dir: str | Path,
    *,
    worker_index: int,
    workers: int = WORKERS,
    progress: bool = False,
) -> dict[str, int]:
    """Run one of exactly 76 deterministic workers with atomic resume."""

    if (
        workers != WORKERS
        or not isinstance(worker_index, int)
        or isinstance(worker_index, bool)
        or not 0 <= worker_index < WORKERS
    ):
        raise ValueError(f"require 0 <= worker_index < {WORKERS} and workers={WORKERS}")
    root = Path(run_dir)
    plan = common._load_json(root / "continuation-plan.json")
    entries = _validate_plan(plan)
    stage2_plan, stage2_entries, hp_plan = _validate_inputs(
        stage2_run_dir, stage3hp_run_dir, plan
    )
    stage3_root = Path(stage3_run_dir)
    hp_root = Path(stage3hp_run_dir)
    completed = reused = operational_errors = 0
    for entry in entries:
        identity = str(entry["candidate_id"])
        if int(identity[:16], 16) % WORKERS != worker_index:
            continue
        output = root / "candidates" / identity / "manifest.json"
        if output.is_file():
            manifest = common._load_json(output)
            if not _terminal_is_valid(
                manifest,
                entry=entry,
                plan=plan,
                worker_index=worker_index,
            ):
                raise RuntimeError(f"stale Stage-3 HP continuation: {identity}")
            reused += 1
            operational_errors += manifest["status"] == "operational-error"
            continue
        stage2_entry = stage2_entries.get(identity)
        if stage2_entry is None:
            raise RuntimeError(f"candidate absent from current Stage-2: {identity}")
        stage3_path = stage3_root / "candidates" / identity / "manifest.json"
        stage3_manifest = common._load_json(stage3_path)
        failure, word = _validate_stage3_manifest(
            stage3_manifest,
            entry=stage2_entry,
            stage2_plan=stage2_plan,
            protocol_hash=str(plan["stage3_protocol_hash"]),
        )
        if (
            word != entry["confirmed_word_indices"]
            or stage3hp._sha256(failure) != entry["first_failure_sha256"]
            or hashlib.sha256(stage3_path.read_bytes()).hexdigest()
            != entry["stage3_manifest_sha256"]
        ):
            raise RuntimeError(f"Stage-3 evidence changed: {identity}")
        hp_path = hp_root / "candidates" / identity / "manifest.json"
        hp_manifest = common._load_json(hp_path)
        hp_entry = {
            "candidate_id": identity,
            "word_indices": entry["confirmed_word_indices"],
            "first_failure_sha256": entry["first_failure_sha256"],
        }
        _validate_hp_manifest(
            hp_manifest,
            hp_entry=hp_entry,
            replay_plan_hash=str(hp_plan["replay_plan_hash"]),
        )
        if (
            hashlib.sha256(hp_path.read_bytes()).hexdigest()
            != entry["stage3hp_manifest_sha256"]
        ):
            raise RuntimeError(f"Stage-3 HP proof changed: {identity}")
        try:
            manifest = _run_candidate(
                entry,
                stage2_entry,
                hp_manifest,
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
        common._write_json_atomic(output, manifest)
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
    plan = common._load_json(root / "continuation-plan.json")
    entries = _validate_plan(plan)
    counts: Counter[str] = Counter()
    tested = fallbacks = reused_hp = missing = stale = 0
    survivors: list[str] = []
    for entry in entries:
        identity = str(entry["candidate_id"])
        path = root / "candidates" / identity / "manifest.json"
        if not path.is_file():
            missing += 1
            continue
        manifest = common._load_json(path)
        if not _terminal_is_valid(manifest, entry=entry, plan=plan):
            stale += 1
            continue
        status = str(manifest["status"])
        counts[status] += 1
        tested += int(manifest.get("tested_words", 0))
        fallbacks += int(manifest.get("exact_fallback_count", 0))
        reused_hp += int(manifest.get("reused_hp_count", 0))
        if status == SURVIVOR_STATUS:
            survivors.append(identity)
    result: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": RUN_ID,
        "continuation_plan_hash": plan["continuation_plan_hash"],
        "stage3hp_plan_hash": plan["stage3hp_plan_hash"],
        "planned": len(entries),
        "terminal": sum(counts.values()),
        "missing": missing,
        "stale": stale,
        "status_counts": dict(sorted(counts.items())),
        "tested_words": tested,
        "reused_hp_proofs": reused_hp,
        "exact_fallbacks": fallbacks,
        "survivors": survivors,
    }
    common._write_json_atomic(root / "collect.json", result)
    if markdown is not None:
        lines = [
            f"# Stage-3 HP continuation — {RUN_ID}",
            "",
            f"- planned / terminal / missing / stale: {len(entries)} / "
            f"{sum(counts.values())} / {missing} / {stale}",
            f"- tested words: {tested}; reused HP proofs: {reused_hp}; "
            f"new exact fallbacks: {fallbacks}",
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
    plan.add_argument("--stage3-run-dir", required=True)
    plan.add_argument("--stage3hp-run-dir", required=True)
    plan.add_argument("--run-dir", required=True)
    plan.add_argument("--expected-count", type=int, default=307)
    run = commands.add_parser("run")
    run.add_argument("--stage2-run-dir", required=True)
    run.add_argument("--stage3-run-dir", required=True)
    run.add_argument("--stage3hp-run-dir", required=True)
    run.add_argument("--run-dir", required=True)
    run.add_argument("--worker-index", type=int, required=True)
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
            args.stage3_run_dir,
            args.stage3hp_run_dir,
            args.run_dir,
            expected_count=args.expected_count,
        )
    elif args.command == "run":
        result = run_worker(
            args.stage2_run_dir,
            args.stage3_run_dir,
            args.stage3hp_run_dir,
            args.run_dir,
            worker_index=args.worker_index,
            workers=args.workers,
            progress=True,
        )
    else:
        result = collect_run(args.run_dir, markdown=args.markdown)
    print(common._canonical_json(result), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["collect_run", "main", "plan_continuation", "run_worker"]

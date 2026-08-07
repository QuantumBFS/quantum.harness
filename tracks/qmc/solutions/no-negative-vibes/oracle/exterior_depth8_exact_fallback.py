"""Depth-5..8 continuation of high-precision-confirmed exterior candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path

import mpmath as mp
import numpy as np
import sympy as sp

from . import weights
from .exterior_candidates import (
    candidate_card,
    candidate_id,
    exact_atoms_from_card,
    float_atoms_from_card,
)
from .exterior_high_precision_replay import (
    _exact_determinant,
    _one_precision,
    _parent_provenance,
    _validate_parent_manifest,
    _validate_replay_plan,
)
from .exterior_thin_scan import mixed_words


SCHEMA_VERSION = "exterior-depth8-exact-fallback-v1"
RUN_ID = "exterior-depth8-exact-fallback-v1"
DEPTHS = (5, 6, 7, 8)
SURVIVOR_STATUS = "survivor-depth8-exact-fallback"
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


def _hp_manifest(
    hp_root: Path,
    identity: str,
    *,
    replay_plan_hash: str,
) -> dict[str, object]:
    manifest = _load_json(hp_root / "candidates" / identity / "manifest.json")
    if (
        manifest.get("candidate_id") != identity
        or manifest.get("replay_plan_hash") != replay_plan_hash
        or manifest.get("status")
        not in {"confirmed-negative", "confirmed-nonnegative"}
    ):
        raise RuntimeError(f"invalid completed high-precision result for {identity}")
    return manifest


def _validate_nonnegative_hp(
    manifest: Mapping[str, object],
    *,
    hp_entry: Mapping[str, object],
) -> None:
    exact = manifest.get("exact_determinant")
    if (
        manifest.get("status") != "confirmed-nonnegative"
        or manifest.get("word_indices") != hp_entry.get("word_indices")
        or manifest.get("first_failure_sha256")
        != hp_entry.get("first_failure_sha256")
        or not isinstance(exact, Mapping)
        or exact.get("sign") not in (0, 1)
    ):
        raise RuntimeError("high-precision nonnegative evidence is incomplete")


def plan_continuation(
    parent_run_dir: str | Path,
    hp_run_dir: str | Path,
    run_dir: str | Path,
    *,
    expected_count: int | None = 511,
) -> dict[str, object]:
    """Select only completed high-precision-confirmed nonnegative cards."""

    parent_root = Path(parent_run_dir)
    hp_root = Path(hp_run_dir)
    parent_plan = _load_json(parent_root / "plan-summary.json")
    provenance = _parent_provenance(parent_plan)
    parent_entries_raw = parent_plan.get("candidates")
    if not isinstance(parent_entries_raw, list):
        raise RuntimeError("parent candidates are missing")
    parent_entries = {
        entry["candidate_id"]: entry
        for entry in parent_entries_raw
        if isinstance(entry, dict) and isinstance(entry.get("candidate_id"), str)
    }
    hp_plan = _load_json(hp_root / "replay-plan.json")
    hp_entries = _validate_replay_plan(hp_plan)
    if any(
        hp_plan.get(key) != value
        for key, value in provenance.items()
    ):
        raise RuntimeError("high-precision replay does not bind this parent run")

    selected: list[dict[str, object]] = []
    for hp_entry in hp_entries:
        identity = str(hp_entry["candidate_id"])
        if identity not in parent_entries:
            raise RuntimeError(f"high-precision candidate absent from parent: {identity}")
        hp_manifest = _hp_manifest(
            hp_root, identity, replay_plan_hash=str(hp_plan["replay_plan_hash"]),
        )
        if hp_manifest["status"] == "confirmed-negative":
            continue
        _validate_nonnegative_hp(hp_manifest, hp_entry=hp_entry)
        parent_entry = parent_entries[identity]
        parent_manifest = _load_json(
            parent_root / "candidates" / identity / "manifest.json"
        )
        _validate_parent_manifest(
            parent_manifest, entry=parent_entry, provenance=provenance,
        )
        selected.append(
            {
                "candidate_id": identity,
                "card_sha256": parent_entry["card_sha256"],
                "template": parent_entry["template"],
                "seed": parent_entry["seed"],
                "dimension": parent_entry["dimension"],
                "shard": parent_entry["shard"],
                "confirmed_word_indices": hp_entry["word_indices"],
                "first_failure_sha256": hp_entry["first_failure_sha256"],
                "hp_manifest_sha256": hashlib.sha256(
                    (
                        hp_root
                        / "candidates"
                        / identity
                        / "manifest.json"
                    ).read_bytes()
                ).hexdigest(),
            }
        )
    selected.sort(key=lambda entry: str(entry["candidate_id"]))
    if expected_count is not None and len(selected) != expected_count:
        raise RuntimeError(
            f"expected {expected_count} confirmed nonnegative cards, found {len(selected)}"
        )
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": RUN_ID,
        **provenance,
        "hp_replay_plan_hash": hp_plan["replay_plan_hash"],
        "depths": list(DEPTHS),
        "word_count_per_candidate": len(mixed_words(2, depths=DEPTHS)),
        "candidate_count": len(selected),
        "candidates": selected,
    }
    payload["continuation_plan_hash"] = _sha256(payload)
    _write_json_atomic(Path(run_dir) / "continuation-plan.json", payload)
    return {
        "run_id": RUN_ID,
        "candidate_count": len(selected),
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
        or plan.get("word_count_per_candidate") != 472
        or not isinstance(stored, str)
        or _sha256(payload) != stored
        or not isinstance(entries, list)
        or not all(isinstance(entry, dict) for entry in entries)
        or plan.get("candidate_count") != len(entries)
    ):
        raise RuntimeError("continuation plan is invalid")
    return entries


def _result_record(result: weights.WeightResult, word: Sequence[int]) -> dict[str, object]:
    return {
        "classification": result.classification,
        "word_indices": list(word),
        "depth": len(word),
        "phase_real": float(result.phase.real),
        "phase_imag": float(result.phase.imag),
        "log_abs_weight": (
            result.log_abs if math.isfinite(result.log_abs) else str(result.log_abs)
        ),
        "sigma_min_I_plus_D": (
            result.sigma_min
            if math.isfinite(result.sigma_min)
            else str(result.sigma_min)
        ),
        "condition_number_I_plus_D": (
            result.condition_number
            if math.isfinite(result.condition_number)
            else str(result.condition_number)
        ),
    }


def _adjudicate_word(
    factors: Sequence[sp.MatrixBase],
) -> tuple[str, dict[str, object]]:
    ladder: list[dict[str, object]] = []
    values: list[tuple[mp.mpf, mp.mpf]] = []
    for dps in (80, 120, 180):
        record, real, imag = _one_precision(factors, dps=dps)
        ladder.append(record)
        values.append((real, imag))
    with mp.workdps(220):
        same_sign = len({record["sign"] for record in ladder}) == 1
        scale = max(mp.mpf(1), abs(values[-1][0]))
        agreement = abs(values[-1][0] - values[-2][0]) <= mp.power(10, -60) * scale
        near_zero = abs(values[-1][0]) <= mp.power(10, -60)
    if near_zero or not same_sign or not agreement:
        record, real, imag = _one_precision(factors, dps=260)
        ladder.append(record)
        values.append((real, imag))
    exact = _exact_determinant(factors)
    exact_sign = 1 if exact > 0 else -1 if exact < 0 else 0
    final_sign = ladder[-1]["sign"]
    if final_sign == "complex":
        raise RuntimeError("material imaginary part in rational direct-factor replay")
    if exact_sign < 0 and final_sign != "negative":
        raise RuntimeError("high-precision replay disagrees with exact negative sign")
    if exact_sign > 0 and final_sign != "positive":
        raise RuntimeError("high-precision replay disagrees with exact positive sign")
    evidence = {
        "source": "fresh-high-precision-exact-fallback",
        "ladder": ladder,
        "exact_determinant": {
            "numerator": str(exact.p),
            "denominator": str(exact.q),
            "sign": exact_sign,
        },
    }
    return ("negative" if exact_sign < 0 else "nonnegative"), evidence


def _run_candidate(
    entry: Mapping[str, object],
    *,
    plan: Mapping[str, object],
    hp_manifest: Mapping[str, object],
    worker_index: int,
    workers: int,
) -> dict[str, object]:
    card = candidate_card(
        template=str(entry["template"]), seed=entry["seed"],  # type: ignore[arg-type]
    )
    identity = candidate_id(card)
    if identity != entry["candidate_id"] or identity != entry["card_sha256"]:
        raise RuntimeError("candidate identity mismatch")
    exact_atoms = exact_atoms_from_card(card)
    float_atoms = float_atoms_from_card(card)
    words = mixed_words(len(float_atoms), depths=DEPTHS)
    counts: Counter[str] = Counter()
    fallback_records: list[dict[str, object]] = []
    first_failure: dict[str, object] | None = None
    status = SURVIVOR_STATUS
    for word in words:
        product = np.eye(int(entry["dimension"]))
        for index in word:
            product = product @ float_atoms[index]
        result = weights.classify_product(product)
        counts[result.classification] += 1
        if result.classification in {"positive", "zero"}:
            continue
        record = _result_record(result, word)
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
        if list(word) == entry["confirmed_word_indices"]:
            _validate_nonnegative_hp(
                hp_manifest,
                hp_entry={
                    "word_indices": entry["confirmed_word_indices"],
                    "first_failure_sha256": entry["first_failure_sha256"],
                },
            )
            evidence = {
                "source": "reused-completed-hp-replay",
                "hp_manifest_sha256": entry["hp_manifest_sha256"],
                "exact_determinant": hp_manifest["exact_determinant"],
                "ladder": hp_manifest.get("ladder", []),
            }
            classification = "nonnegative"
        else:
            factors = [exact_atoms[index] for index in word]
            classification, evidence = _adjudicate_word(factors)
        fallback_records.append({"word_indices": list(word), **evidence})
        if classification == "negative":
            status = "rejected-negative-exact-fallback"
            first_failure = {
                **record,
                "exact_fallback": evidence,
            }
            break
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": RUN_ID,
        "continuation_plan_hash": plan["continuation_plan_hash"],
        "parent_run_id": plan["parent_run_id"],
        "parent_source_commit": plan["parent_source_commit"],
        "parent_plan_hash": plan["parent_plan_hash"],
        "parent_protocol_hash": plan["parent_protocol_hash"],
        "hp_replay_plan_hash": plan["hp_replay_plan_hash"],
        "candidate_id": identity,
        "card_sha256": identity,
        "template": entry["template"],
        "seed": entry["seed"],
        "dimension": entry["dimension"],
        "shard": entry["shard"],
        "worker_index": worker_index,
        "workers": workers,
        "depths": list(DEPTHS),
        "planned_words": len(words),
        "tested_words": sum(counts.values()),
        "normal_classification_counts": dict(sorted(counts.items())),
        "exact_fallback_count": len(fallback_records),
        "exact_fallback_records": fallback_records,
        "status": status,
        "first_failure": first_failure,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def run_worker(
    parent_run_dir: str | Path,
    hp_run_dir: str | Path,
    run_dir: str | Path,
    *,
    worker_index: int,
    workers: int = 76,
) -> dict[str, int]:
    """Run one deterministic hash worker with atomic per-card resume."""

    if workers <= 0 or not 0 <= worker_index < workers:
        raise ValueError("worker_index must be in range(workers)")
    root = Path(run_dir)
    plan = _load_json(root / "continuation-plan.json")
    entries = _validate_plan(plan)
    parent_plan = _load_json(Path(parent_run_dir) / "plan-summary.json")
    if any(plan.get(key) != value for key, value in _parent_provenance(parent_plan).items()):
        raise RuntimeError("parent run does not match continuation plan")
    hp_root = Path(hp_run_dir)
    hp_plan = _load_json(hp_root / "replay-plan.json")
    _validate_replay_plan(hp_plan)
    if hp_plan.get("replay_plan_hash") != plan["hp_replay_plan_hash"]:
        raise RuntimeError("high-precision run does not match continuation plan")
    completed = reused = operational_errors = 0
    for entry in entries:
        identity = str(entry["candidate_id"])
        if int(identity[:16], 16) % workers != worker_index:
            continue
        path = root / "candidates" / identity / "manifest.json"
        if path.is_file():
            manifest = _load_json(path)
            if (
                manifest.get("candidate_id") != identity
                or manifest.get("continuation_plan_hash")
                != plan["continuation_plan_hash"]
                or manifest.get("worker_index") != worker_index
                or manifest.get("workers") != workers
                or manifest.get("status") not in TERMINAL_STATUSES
            ):
                raise RuntimeError(f"stale continuation manifest for {identity}")
            reused += 1
            operational_errors += manifest["status"] == "operational-error"
            continue
        hp_manifest_path = hp_root / "candidates" / identity / "manifest.json"
        hp_manifest = _hp_manifest(
            hp_root, identity, replay_plan_hash=str(plan["hp_replay_plan_hash"]),
        )
        if hashlib.sha256(hp_manifest_path.read_bytes()).hexdigest() != entry[
            "hp_manifest_sha256"
        ]:
            raise RuntimeError(f"high-precision manifest changed for {identity}")
        try:
            manifest = _run_candidate(
                entry,
                plan=plan,
                hp_manifest=hp_manifest,
                worker_index=worker_index,
                workers=workers,
            )
        except Exception as exc:
            manifest = {
                "schema_version": SCHEMA_VERSION,
                "run_id": RUN_ID,
                "continuation_plan_hash": plan["continuation_plan_hash"],
                "candidate_id": identity,
                "worker_index": worker_index,
                "workers": workers,
                "status": "operational-error",
                "error": f"{type(exc).__name__}: {exc}",
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        _write_json_atomic(path, manifest)
        completed += 1
        operational_errors += manifest["status"] == "operational-error"
    return {
        "completed": completed,
        "reused": reused,
        "operational_errors": operational_errors,
    }


def collect_run(
    run_dir: str | Path, *, markdown: str | Path | None = None,
) -> dict[str, object]:
    """Collect compact scientific and completion counts."""

    root = Path(run_dir)
    plan = _load_json(root / "continuation-plan.json")
    entries = _validate_plan(plan)
    counts: Counter[str] = Counter()
    tested_words = exact_fallbacks = 0
    missing: list[str] = []
    stale: list[str] = []
    for entry in entries:
        identity = str(entry["candidate_id"])
        path = root / "candidates" / identity / "manifest.json"
        if not path.is_file():
            missing.append(identity)
            continue
        manifest = _load_json(path)
        status = manifest.get("status")
        if (
            manifest.get("candidate_id") != identity
            or manifest.get("continuation_plan_hash")
            != plan["continuation_plan_hash"]
            or status not in TERMINAL_STATUSES
        ):
            stale.append(identity)
            continue
        counts[str(status)] += 1
        tested_words += int(manifest.get("tested_words", 0))
        exact_fallbacks += int(manifest.get("exact_fallback_count", 0))
    result: dict[str, object] = {
        "run_id": RUN_ID,
        "continuation_plan_hash": plan["continuation_plan_hash"],
        "hp_replay_plan_hash": plan["hp_replay_plan_hash"],
        "planned": len(entries),
        "terminal": sum(counts.values()),
        "missing": len(missing),
        "stale": len(stale),
        "status_counts": dict(sorted(counts.items())),
        "tested_words": tested_words,
        "exact_fallbacks": exact_fallbacks,
        "missing_candidate_ids": missing,
        "stale_candidate_ids": stale,
    }
    _write_json_atomic(root / "collect.json", result)
    if markdown is not None:
        lines = [
            f"# Depth-8 exact-fallback continuation — {RUN_ID}",
            "",
            f"- continuation plan: `{plan['continuation_plan_hash']}`",
            f"- selected confirmed-nonnegative cards: {len(entries)}",
            f"- terminal / missing / stale: {sum(counts.values())} / "
            f"{len(missing)} / {len(stale)}",
            f"- tested words: {tested_words}; exact fallbacks: {exact_fallbacks}",
            "",
            "| status | count |",
            "|---|---:|",
        ]
        lines.extend(f"| {status} | {count} |" for status, count in sorted(counts.items()))
        path = Path(markdown)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--parent-run-dir", required=True)
    plan.add_argument("--hp-run-dir", required=True)
    plan.add_argument("--run-dir", required=True)
    plan.add_argument("--expected-count", type=int, default=511)
    run = subparsers.add_parser("run")
    run.add_argument("--parent-run-dir", required=True)
    run.add_argument("--hp-run-dir", required=True)
    run.add_argument("--run-dir", required=True)
    run.add_argument("--worker-index", required=True, type=int)
    run.add_argument("--workers", type=int, default=76)
    collect = subparsers.add_parser("collect")
    collect.add_argument("--run-dir", required=True)
    collect.add_argument("--markdown")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "plan":
        result = plan_continuation(
            args.parent_run_dir,
            args.hp_run_dir,
            args.run_dir,
            expected_count=args.expected_count,
        )
    elif args.command == "run":
        result = run_worker(
            args.parent_run_dir,
            args.hp_run_dir,
            args.run_dir,
            worker_index=args.worker_index,
            workers=args.workers,
        )
    else:
        result = collect_run(args.run_dir, markdown=args.markdown)
    print(_canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["collect_run", "main", "plan_continuation", "run_worker"]

"""High-precision replay of Stage-2 exterior-scan uncertain candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path

import mpmath as mp
import sympy as sp

from .exterior_candidates import candidate_card, candidate_id, exact_atoms_from_card
from .high_precision import replay_weight


SCHEMA_VERSION = "exterior-high-precision-replay-v1"
RUN_ID = "exterior-survivor-pressure-v1-high-precision-v1"
TERMINAL_STATUSES = {
    "confirmed-negative",
    "confirmed-nonnegative",
    "unresolved-high-precision",
}
DEFAULT_DPS = (80, 120, 180)


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


def _write_json_atomic(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path} must contain a JSON object")
    return value


def _parent_provenance(plan: Mapping[str, object]) -> dict[str, object]:
    required = ("run_id", "source_commit", "plan_hash", "protocol_hash")
    if any(not isinstance(plan.get(key), str) or not plan[key] for key in required):
        raise RuntimeError("parent plan has incomplete provenance")
    return {
        "parent_run_id": plan["run_id"],
        "parent_source_commit": plan["source_commit"],
        "parent_plan_hash": plan["plan_hash"],
        "parent_protocol_hash": plan["protocol_hash"],
    }


def _validate_parent_manifest(
    manifest: Mapping[str, object],
    *,
    entry: Mapping[str, object],
    provenance: Mapping[str, object],
) -> tuple[dict[str, object], list[int]]:
    identity = entry["candidate_id"]
    if (
        manifest.get("status") != "uncertain-high-precision"
        or manifest.get("candidate_id") != identity
        or manifest.get("card_sha256") != identity
        or manifest.get("run_id") != provenance["parent_run_id"]
        or manifest.get("source_commit") != provenance["parent_source_commit"]
        or manifest.get("protocol_hash") != provenance["parent_protocol_hash"]
        or manifest.get("template") != entry["template"]
        or manifest.get("seed") != entry["seed"]
    ):
        raise RuntimeError(f"invalid uncertain parent manifest for {identity}")
    failure = manifest.get("first_failure")
    if not isinstance(failure, dict):
        raise RuntimeError(f"missing first_failure for {identity}")
    word = failure.get("word_indices")
    if (
        failure.get("classification") != "uncertain"
        or failure.get("exact_card_sha256") != identity
        or not isinstance(word, list)
        or not word
        or failure.get("depth") != len(word)
        or any(
            not isinstance(index, int) or isinstance(index, bool) or index not in (0, 1)
            for index in word
        )
    ):
        raise RuntimeError(f"invalid uncertain first_failure for {identity}")
    return failure, word


def plan_replay(
    parent_run_dir: str | Path,
    run_dir: str | Path,
    *,
    expected_count: int | None = 514,
) -> dict[str, object]:
    """Select and hash-bind the Stage-2 uncertain queue."""

    parent_root = Path(parent_run_dir)
    parent_plan = _load_json(parent_root / "plan-summary.json")
    provenance = _parent_provenance(parent_plan)
    candidates = parent_plan.get("candidates")
    if not isinstance(candidates, list):
        raise RuntimeError("parent plan candidates are missing")
    selected: list[dict[str, object]] = []
    for raw_entry in candidates:
        if not isinstance(raw_entry, dict):
            raise RuntimeError("parent candidate entry is invalid")
        identity = raw_entry.get("candidate_id")
        if not isinstance(identity, str):
            raise RuntimeError("parent candidate identity is invalid")
        path = parent_root / "candidates" / identity / "manifest.json"
        if not path.is_file():
            raise RuntimeError(f"parent run is incomplete: {identity}")
        manifest = _load_json(path)
        if manifest.get("status") != "uncertain-high-precision":
            continue
        failure, word = _validate_parent_manifest(
            manifest, entry=raw_entry, provenance=provenance,
        )
        selected.append(
            {
                "candidate_id": identity,
                "card_sha256": raw_entry.get("card_sha256"),
                "template": raw_entry.get("template"),
                "seed": raw_entry.get("seed"),
                "dimension": raw_entry.get("dimension"),
                "parent_shard": raw_entry.get("shard"),
                "word_indices": word,
                "first_failure_sha256": _sha256(failure),
            }
        )
    selected.sort(key=lambda entry: str(entry["candidate_id"]))
    if expected_count is not None and len(selected) != expected_count:
        raise RuntimeError(
            f"expected {expected_count} uncertain candidates, found {len(selected)}"
        )
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": RUN_ID,
        **provenance,
        "dps_ladder": list(DEFAULT_DPS),
        "candidate_count": len(selected),
        "candidates": selected,
    }
    payload["replay_plan_hash"] = _sha256(payload)
    _write_json_atomic(Path(run_dir) / "replay-plan.json", payload)
    return {
        "run_id": RUN_ID,
        "candidate_count": len(selected),
        "replay_plan_hash": payload["replay_plan_hash"],
    }


def _validate_replay_plan(plan: Mapping[str, object]) -> list[dict[str, object]]:
    stored_hash = plan.get("replay_plan_hash")
    payload = dict(plan)
    payload.pop("replay_plan_hash", None)
    if (
        plan.get("schema_version") != SCHEMA_VERSION
        or plan.get("run_id") != RUN_ID
        or not isinstance(stored_hash, str)
        or _sha256(payload) != stored_hash
        or plan.get("dps_ladder") != list(DEFAULT_DPS)
    ):
        raise RuntimeError("replay plan hash or protocol mismatch")
    entries = plan.get("candidates")
    if not isinstance(entries, list) or not all(isinstance(x, dict) for x in entries):
        raise RuntimeError("replay plan candidates are invalid")
    if plan.get("candidate_count") != len(entries):
        raise RuntimeError("replay plan candidate count mismatch")
    return entries


def _decimal_matrix(matrix: sp.MatrixBase, *, dps: int) -> list[list[str]]:
    with mp.workdps(dps + 40):
        result: list[list[str]] = []
        for row in range(matrix.rows):
            values: list[str] = []
            for column in range(matrix.cols):
                value = sp.Rational(matrix[row, column])
                decimal = mp.mpf(int(value.p)) / mp.mpf(int(value.q))
                values.append(mp.nstr(decimal, n=dps + 30))
            result.append(values)
        return result


def _one_precision(
    factors: Sequence[sp.MatrixBase], *, dps: int,
) -> tuple[dict[str, object], mp.mpf, mp.mpf]:
    weight = replay_weight(
        {"factors": [_decimal_matrix(factor, dps=dps) for factor in factors]},
        dps=dps,
    )
    with mp.workdps(dps + 20):
        real = mp.mpf(mp.re(weight))
        imag = mp.mpf(mp.im(weight))
        sign = "positive" if real > 0 else "negative" if real < 0 else "zero"
        if abs(imag) > mp.power(10, -(dps // 2)):
            sign = "complex"
        record = {
            "dps": dps,
            "adapter_guard_digits": 40,
            "weight_real": mp.nstr(real, n=dps),
            "weight_imag": mp.nstr(imag, n=dps),
            "abs_weight": mp.nstr(abs(weight), n=dps),
            "sign": sign,
        }
        return record, real, imag


def _exact_determinant(factors: Sequence[sp.MatrixBase]) -> sp.Rational:
    product = sp.eye(factors[0].rows)
    for factor in factors:
        product = product * factor
    return sp.Rational(sp.det(sp.eye(product.rows) + product))


def _replay_candidate(
    parent_manifest: Mapping[str, object],
    *,
    entry: Mapping[str, object],
    plan: Mapping[str, object],
    worker_index: int,
    workers: int,
) -> dict[str, object]:
    started = datetime.now(timezone.utc)
    failure, word = _validate_parent_manifest(
        parent_manifest, entry=entry, provenance=plan,
    )
    card = candidate_card(template=str(entry["template"]), seed=entry["seed"])  # type: ignore[arg-type]
    identity = candidate_id(card)
    if (
        identity != entry["candidate_id"]
        or identity != entry["card_sha256"]
        or _sha256(failure) != entry["first_failure_sha256"]
    ):
        raise RuntimeError("candidate or first-failure identity mismatch")
    atoms = exact_atoms_from_card(card)
    factors = [atoms[index] for index in word]
    ladder: list[dict[str, object]] = []
    values: list[tuple[mp.mpf, mp.mpf]] = []
    for dps in DEFAULT_DPS:
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
    final_sign = ladder[-1]["sign"]
    exact_sign = 1 if exact > 0 else -1 if exact < 0 else 0
    if final_sign == "complex":
        status = "unresolved-high-precision"
        reason = "material imaginary component"
    elif exact_sign < 0 and final_sign == "negative":
        status = "confirmed-negative"
        reason = "high-precision replay agrees with exact rational determinant"
    elif exact_sign > 0 and final_sign == "positive":
        status = "confirmed-nonnegative"
        reason = "high-precision replay agrees with exact rational determinant"
    elif exact_sign == 0 and (
        final_sign == "zero"
        or abs(values[-1][0]) <= mp.power(10, -(int(ladder[-1]["dps"]) // 2))
    ):
        status = "confirmed-nonnegative"
        reason = "exact rational determinant is zero"
    else:
        status = "unresolved-high-precision"
        reason = "numerical replay disagrees with exact rational determinant"
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": RUN_ID,
        "replay_plan_hash": plan["replay_plan_hash"],
        "parent_run_id": plan["parent_run_id"],
        "parent_source_commit": plan["parent_source_commit"],
        "parent_plan_hash": plan["parent_plan_hash"],
        "parent_protocol_hash": plan["parent_protocol_hash"],
        "candidate_id": identity,
        "card_sha256": identity,
        "template": entry["template"],
        "seed": entry["seed"],
        "dimension": entry["dimension"],
        "parent_shard": entry["parent_shard"],
        "worker_index": worker_index,
        "workers": workers,
        "word_indices": word,
        "first_failure_sha256": entry["first_failure_sha256"],
        "ladder": ladder,
        "exact_determinant": {
            "numerator": str(exact.p),
            "denominator": str(exact.q),
            "sign": exact_sign,
        },
        "status": status,
        "reason": reason,
        "python_version": platform.python_version(),
        "mpmath_version": mp.__version__,
        "created_at_utc": started.isoformat(),
    }


def run_worker(
    parent_run_dir: str | Path,
    run_dir: str | Path,
    *,
    worker_index: int,
    workers: int,
) -> dict[str, int]:
    """Replay one deterministic hash partition, atomically and resumably."""

    if workers <= 0 or not 0 <= worker_index < workers:
        raise ValueError("worker_index must be in range(workers)")
    root = Path(run_dir)
    plan = _load_json(root / "replay-plan.json")
    entries = _validate_replay_plan(plan)
    parent_root = Path(parent_run_dir)
    parent_plan = _load_json(parent_root / "plan-summary.json")
    if _parent_provenance(parent_plan) != {
        key: plan[key]
        for key in (
            "parent_run_id",
            "parent_source_commit",
            "parent_plan_hash",
            "parent_protocol_hash",
        )
    }:
        raise RuntimeError("parent run does not match replay plan")
    completed = reused = unresolved = 0
    for entry in entries:
        identity = str(entry["candidate_id"])
        if int(identity[:16], 16) % workers != worker_index:
            continue
        output = root / "candidates" / identity / "manifest.json"
        if output.is_file():
            manifest = _load_json(output)
            if (
                manifest.get("candidate_id") != identity
                or manifest.get("replay_plan_hash") != plan["replay_plan_hash"]
                or manifest.get("status") not in TERMINAL_STATUSES
                or manifest.get("worker_index") != worker_index
                or manifest.get("workers") != workers
            ):
                raise RuntimeError(f"stale replay manifest for {identity}")
            reused += 1
            unresolved += manifest["status"] == "unresolved-high-precision"
            continue
        parent_manifest = _load_json(
            parent_root / "candidates" / identity / "manifest.json"
        )
        try:
            manifest = _replay_candidate(
                parent_manifest,
                entry=entry,
                plan=plan,
                worker_index=worker_index,
                workers=workers,
            )
        except Exception as exc:
            manifest = {
                "schema_version": SCHEMA_VERSION,
                "run_id": RUN_ID,
                "replay_plan_hash": plan["replay_plan_hash"],
                "candidate_id": identity,
                "worker_index": worker_index,
                "workers": workers,
                "status": "unresolved-high-precision",
                "reason": f"{type(exc).__name__}: {exc}",
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        _write_json_atomic(output, manifest)
        completed += 1
        unresolved += manifest["status"] == "unresolved-high-precision"
    return {"completed": completed, "reused": reused, "unresolved": unresolved}


def collect_replay(
    run_dir: str | Path, *, markdown: str | Path | None = None,
) -> dict[str, object]:
    """Collect a compact terminal-status summary."""

    root = Path(run_dir)
    plan = _load_json(root / "replay-plan.json")
    entries = _validate_replay_plan(plan)
    counts: Counter[str] = Counter()
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
            or manifest.get("replay_plan_hash") != plan["replay_plan_hash"]
            or status not in TERMINAL_STATUSES
        ):
            stale.append(identity)
            continue
        counts[str(status)] += 1
    result: dict[str, object] = {
        "run_id": RUN_ID,
        "replay_plan_hash": plan["replay_plan_hash"],
        "parent_run_id": plan["parent_run_id"],
        "parent_source_commit": plan["parent_source_commit"],
        "parent_plan_hash": plan["parent_plan_hash"],
        "parent_protocol_hash": plan["parent_protocol_hash"],
        "planned": len(entries),
        "terminal": sum(counts.values()),
        "missing": len(missing),
        "stale": len(stale),
        "status_counts": dict(sorted(counts.items())),
        "missing_candidate_ids": missing,
        "stale_candidate_ids": stale,
    }
    _write_json_atomic(root / "collect.json", result)
    if markdown is not None:
        lines = [
            f"# Stage-2 high-precision replay — {RUN_ID}",
            "",
            f"- replay plan: `{plan['replay_plan_hash']}`",
            f"- parent run: `{plan['parent_run_id']}`",
            f"- planned / terminal / missing / stale: "
            f"{len(entries)} / {sum(counts.values())} / {len(missing)} / {len(stale)}",
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
    plan.add_argument("--run-dir", required=True)
    plan.add_argument("--expected-count", type=int, default=514)
    run = subparsers.add_parser("run")
    run.add_argument("--parent-run-dir", required=True)
    run.add_argument("--run-dir", required=True)
    run.add_argument("--worker-index", type=int, required=True)
    run.add_argument("--workers", type=int, required=True)
    collect = subparsers.add_parser("collect")
    collect.add_argument("--run-dir", required=True)
    collect.add_argument("--markdown")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "plan":
        result = plan_replay(
            args.parent_run_dir,
            args.run_dir,
            expected_count=args.expected_count,
        )
    elif args.command == "run":
        result = run_worker(
            args.parent_run_dir,
            args.run_dir,
            worker_index=args.worker_index,
            workers=args.workers,
        )
    else:
        result = collect_replay(args.run_dir, markdown=args.markdown)
    print(_canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["collect_replay", "main", "plan_replay", "run_worker"]

"""High-precision replay of Stage-4 depth-13..16 uncertain first failures."""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path

import mpmath as mp

from . import exterior_deep_high_precision_replay as hp
from . import exterior_depth16_survivor as stage4
from .exterior_candidates import candidate_card, candidate_id, exact_atoms_from_card


SCHEMA_VERSION = "exterior-depth16-high-precision-replay-v1"
RUN_ID = "exterior-survivor-depth16-high-precision-v1"
DEFAULT_DPS = hp.DEFAULT_DPS
TERMINAL_STATUSES = hp.TERMINAL_STATUSES
_adjudicate = hp._adjudicate


def _validate_failure(
    manifest: Mapping[str, object], identity: str,
) -> tuple[dict[str, object], list[int]]:
    failure = manifest.get("first_failure")
    if not isinstance(failure, dict):
        raise RuntimeError(f"missing Stage-4 first failure for {identity}")
    word = failure.get("word_indices")
    if (
        manifest.get("status") != "uncertain-high-precision"
        or failure.get("classification") != "uncertain"
        or failure.get("exact_card_sha256") != identity
        or not isinstance(word, list)
        or failure.get("depth") != len(word)
        or len(word) not in stage4.DEPTHS
        or any(
            not isinstance(index, int) or isinstance(index, bool) or index not in (0, 1)
            for index in word
        )
    ):
        raise RuntimeError(f"invalid Stage-4 uncertain failure for {identity}")
    return failure, word


def plan_replay(
    stage2_run_dir: str | Path,
    stage3_run_dir: str | Path,
    stage4_run_dir: str | Path,
    run_dir: str | Path,
    *,
    expected_count: int | None = 179,
) -> dict[str, object]:
    """Freeze exactly the completed Stage-4 uncertain first failures."""

    stage2_plan, entries, stage3_protocol_hash = stage4.load_stage3_survivors(
        stage2_run_dir, stage3_run_dir
    )
    if not isinstance(stage2_plan.get("plan_hash"), str):
        raise RuntimeError("Stage-2 plan hash is missing")
    stage4_protocol_hash = stage4._protocol_hash(
        stage2_plan, stage3_protocol_hash, stage4.RUN_ID
    )
    stage4_root = Path(stage4_run_dir)
    selected: list[dict[str, object]] = []
    for entry in entries:
        identity = str(entry["candidate_id"])
        path = stage4_root / "candidates" / identity / "manifest.json"
        if not path.is_file():
            raise RuntimeError(f"completed Stage-4 manifest missing: {identity}")
        manifest = hp._load_json(path)
        if not stage4._manifest_is_valid(
            manifest,
            entry=entry,
            plan=stage2_plan,
            stage3_protocol=stage3_protocol_hash,
            run_id=stage4.RUN_ID,
            protocol_hash=stage4_protocol_hash,
        ):
            raise RuntimeError(f"invalid Stage-4 terminal manifest: {identity}")
        if manifest["status"] != "uncertain-high-precision":
            continue
        failure, word = _validate_failure(manifest, identity)
        selected.append(
            {
                "candidate_id": identity,
                "card_sha256": entry["card_sha256"],
                "template": entry["template"],
                "seed": entry["seed"],
                "dimension": entry["dimension"],
                "stage2_shard": entry["shard"],
                "word_indices": word,
                "first_failure_sha256": hp._sha256(failure),
                "stage4_manifest_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    selected.sort(key=lambda entry: str(entry["candidate_id"]))
    if expected_count is not None and len(selected) != expected_count:
        raise RuntimeError(
            f"expected {expected_count} Stage-4 uncertainties, found {len(selected)}"
        )
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "run_id": RUN_ID,
        "stage2_run_id": stage2_plan["run_id"],
        "stage2_source_commit": stage2_plan["source_commit"],
        "stage2_plan_hash": stage2_plan["plan_hash"],
        "stage2_protocol_hash": stage2_plan["protocol_hash"],
        "stage3_run_id": stage4.stage3.RUN_ID,
        "stage3_protocol_hash": stage3_protocol_hash,
        "stage4_run_id": stage4.RUN_ID,
        "stage4_protocol_hash": stage4_protocol_hash,
        "stage4_depths": list(stage4.DEPTHS),
        "dps_ladder": list(DEFAULT_DPS),
        "candidate_count": len(selected),
        "candidates": selected,
    }
    payload["replay_plan_hash"] = hp._sha256(payload)
    hp._write_json_atomic(Path(run_dir) / "replay-plan.json", payload)
    return {
        "run_id": RUN_ID,
        "candidate_count": len(selected),
        "replay_plan_hash": payload["replay_plan_hash"],
    }


def _validate_plan(plan: Mapping[str, object]) -> list[dict[str, object]]:
    stored = plan.get("replay_plan_hash")
    payload = dict(plan)
    payload.pop("replay_plan_hash", None)
    entries = plan.get("candidates")
    if (
        plan.get("schema_version") != SCHEMA_VERSION
        or plan.get("run_id") != RUN_ID
        or plan.get("stage3_run_id") != stage4.stage3.RUN_ID
        or plan.get("stage4_run_id") != stage4.RUN_ID
        or plan.get("stage4_depths") != list(stage4.DEPTHS)
        or plan.get("dps_ladder") != list(DEFAULT_DPS)
        or not isinstance(stored, str)
        or hp._sha256(payload) != stored
        or not isinstance(entries, list)
        or not all(isinstance(entry, dict) for entry in entries)
        or plan.get("candidate_count") != len(entries)
    ):
        raise RuntimeError("Stage-4 replay plan is invalid")
    return entries


def _validate_inputs(
    stage2_run_dir: str | Path,
    stage3_run_dir: str | Path,
    plan: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    stage2_plan, entries, stage3_protocol_hash = stage4.load_stage3_survivors(
        stage2_run_dir, stage3_run_dir
    )
    stage4_protocol_hash = stage4._protocol_hash(
        stage2_plan, stage3_protocol_hash, stage4.RUN_ID
    )
    if (
        stage2_plan.get("run_id") != plan["stage2_run_id"]
        or stage2_plan.get("source_commit") != plan["stage2_source_commit"]
        or stage2_plan.get("plan_hash") != plan["stage2_plan_hash"]
        or stage2_plan.get("protocol_hash") != plan["stage2_protocol_hash"]
        or stage3_protocol_hash != plan["stage3_protocol_hash"]
        or stage4_protocol_hash != plan["stage4_protocol_hash"]
    ):
        raise RuntimeError("Stage-2/Stage-3/Stage-4 provenance does not match replay plan")
    return {str(entry["candidate_id"]): entry for entry in entries}


def _replay_one(
    entry: Mapping[str, object],
    stage4_manifest: Mapping[str, object],
    *,
    plan: Mapping[str, object],
    worker_index: int,
    workers: int,
) -> dict[str, object]:
    identity = str(entry["candidate_id"])
    failure, word = _validate_failure(stage4_manifest, identity)
    if (
        hp._sha256(failure) != entry["first_failure_sha256"]
        or stage4_manifest.get("protocol_hash") != plan["stage4_protocol_hash"]
    ):
        raise RuntimeError("Stage-4 first-failure binding mismatch")
    card = candidate_card(
        template=str(entry["template"]), seed=entry["seed"],  # type: ignore[arg-type]
    )
    if candidate_id(card) != identity or identity != entry["card_sha256"]:
        raise RuntimeError("exact candidate reconstruction mismatch")
    atoms = exact_atoms_from_card(card)
    factors = [atoms[index] for index in word]
    status, ladder, exact, reason = _adjudicate(factors)
    exact_sign = 1 if exact > 0 else -1 if exact < 0 else 0
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": RUN_ID,
        "replay_plan_hash": plan["replay_plan_hash"],
        "stage2_run_id": plan["stage2_run_id"],
        "stage2_source_commit": plan["stage2_source_commit"],
        "stage2_plan_hash": plan["stage2_plan_hash"],
        "stage2_protocol_hash": plan["stage2_protocol_hash"],
        "stage3_run_id": plan["stage3_run_id"],
        "stage3_protocol_hash": plan["stage3_protocol_hash"],
        "stage4_run_id": plan["stage4_run_id"],
        "stage4_protocol_hash": plan["stage4_protocol_hash"],
        "candidate_id": identity,
        "card_sha256": identity,
        "template": entry["template"],
        "seed": entry["seed"],
        "dimension": entry["dimension"],
        "stage2_shard": entry["stage2_shard"],
        "worker_index": worker_index,
        "workers": workers,
        "word_indices": word,
        "first_failure_sha256": entry["first_failure_sha256"],
        "stage4_manifest_sha256": entry["stage4_manifest_sha256"],
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
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def run_worker(
    stage2_run_dir: str | Path,
    stage3_run_dir: str | Path,
    stage4_run_dir: str | Path,
    run_dir: str | Path,
    *,
    worker_index: int,
    workers: int = 76,
) -> dict[str, int]:
    """Replay one deterministic hash partition with atomic resume."""

    if workers <= 0 or not 0 <= worker_index < workers:
        raise ValueError("worker_index must be in range(workers)")
    root = Path(run_dir)
    plan = hp._load_json(root / "replay-plan.json")
    entries = _validate_plan(plan)
    stage2_entries = _validate_inputs(stage2_run_dir, stage3_run_dir, plan)
    stage4_root = Path(stage4_run_dir)
    completed = reused = unresolved = 0
    for entry in entries:
        identity = str(entry["candidate_id"])
        if int(identity[:16], 16) % workers != worker_index:
            continue
        if identity not in stage2_entries:
            raise RuntimeError(f"candidate missing from current Stage-4 inputs: {identity}")
        output = root / "candidates" / identity / "manifest.json"
        if output.is_file():
            manifest = hp._load_json(output)
            if (
                manifest.get("candidate_id") != identity
                or manifest.get("replay_plan_hash") != plan["replay_plan_hash"]
                or manifest.get("worker_index") != worker_index
                or manifest.get("workers") != workers
                or manifest.get("status") not in TERMINAL_STATUSES
            ):
                raise RuntimeError(f"stale depth-16 replay manifest for {identity}")
            reused += 1
            unresolved += manifest["status"] == "unresolved-high-precision"
            continue
        stage4_path = stage4_root / "candidates" / identity / "manifest.json"
        if hashlib.sha256(stage4_path.read_bytes()).hexdigest() != entry[
            "stage4_manifest_sha256"
        ]:
            raise RuntimeError(f"Stage-4 manifest changed for {identity}")
        stage4_manifest = hp._load_json(stage4_path)
        try:
            manifest = _replay_one(
                entry,
                stage4_manifest,
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
        hp._write_json_atomic(output, manifest)
        completed += 1
        unresolved += manifest["status"] == "unresolved-high-precision"
    return {"completed": completed, "reused": reused, "unresolved": unresolved}


def collect_replay(
    run_dir: str | Path, *, markdown: str | Path | None = None,
) -> dict[str, object]:
    """Collect compact completion and exact-sign counts."""

    root = Path(run_dir)
    plan = hp._load_json(root / "replay-plan.json")
    entries = _validate_plan(plan)
    counts: Counter[str] = Counter()
    missing: list[str] = []
    stale: list[str] = []
    for entry in entries:
        identity = str(entry["candidate_id"])
        path = root / "candidates" / identity / "manifest.json"
        if not path.is_file():
            missing.append(identity)
            continue
        manifest = hp._load_json(path)
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
        "stage2_run_id": plan["stage2_run_id"],
        "stage2_source_commit": plan["stage2_source_commit"],
        "stage2_plan_hash": plan["stage2_plan_hash"],
        "stage2_protocol_hash": plan["stage2_protocol_hash"],
        "stage3_run_id": plan["stage3_run_id"],
        "stage3_protocol_hash": plan["stage3_protocol_hash"],
        "stage4_run_id": plan["stage4_run_id"],
        "stage4_protocol_hash": plan["stage4_protocol_hash"],
        "planned": len(entries),
        "terminal": sum(counts.values()),
        "missing": len(missing),
        "stale": len(stale),
        "status_counts": dict(sorted(counts.items())),
        "missing_candidate_ids": missing,
        "stale_candidate_ids": stale,
    }
    hp._write_json_atomic(root / "collect.json", result)
    if markdown is not None:
        lines = [
            f"# Stage-4 high-precision replay — {RUN_ID}",
            "",
            f"- replay plan: `{plan['replay_plan_hash']}`",
            f"- Stage-4 protocol: `{plan['stage4_protocol_hash']}`",
            f"- planned / terminal / missing / stale: "
            f"{len(entries)} / {sum(counts.values())} / "
            f"{len(missing)} / {len(stale)}",
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
    plan.add_argument("--stage2-run-dir", required=True)
    plan.add_argument("--stage3-run-dir", required=True)
    plan.add_argument("--stage4-run-dir", required=True)
    plan.add_argument("--run-dir", required=True)
    plan.add_argument("--expected-count", type=int, default=179)
    run = subparsers.add_parser("run")
    run.add_argument("--stage2-run-dir", required=True)
    run.add_argument("--stage3-run-dir", required=True)
    run.add_argument("--stage4-run-dir", required=True)
    run.add_argument("--run-dir", required=True)
    run.add_argument("--worker-index", type=int, required=True)
    run.add_argument("--workers", type=int, default=76)
    collect = subparsers.add_parser("collect")
    collect.add_argument("--run-dir", required=True)
    collect.add_argument("--markdown")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "plan":
        result = plan_replay(
            args.stage2_run_dir,
            args.stage3_run_dir,
            args.stage4_run_dir,
            args.run_dir,
            expected_count=args.expected_count,
        )
    elif args.command == "run":
        result = run_worker(
            args.stage2_run_dir,
            args.stage3_run_dir,
            args.stage4_run_dir,
            args.run_dir,
            worker_index=args.worker_index,
            workers=args.workers,
        )
    else:
        result = collect_replay(args.run_dir, markdown=args.markdown)
    print(hp._canonical_json(result), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["collect_replay", "main", "plan_replay", "run_worker"]

"""Thin, resumable depth-2..4 scan of exact exterior candidate alphabets."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from . import weights
from .exterior_candidates import (
    TEMPLATES,
    candidate_card,
    candidate_id,
    float_atoms_from_card,
)


SCHEMA_VERSION = "exterior-thin-first-v1"
ORACLE_VERSION = "determinant-weight-v1"
WORD_ORDER = "right-append-lexicographic-mixed"
DEFAULT_DEPTHS = (2, 3, 4)
TERMINAL_STATUSES = {
    "rejected-negative",
    "rejected-complex",
    "uncertain-high-precision",
    "survivor-shallow-zero-failure",
}


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _json_number(value: float) -> float | str:
    if math.isfinite(value):
        return value
    if math.isnan(value):
        return "NaN"
    return "Infinity" if value > 0 else "-Infinity"


def mixed_words(
    atom_count: int,
    *,
    depths: tuple[int, ...] = DEFAULT_DEPTHS,
) -> tuple[tuple[int, ...], ...]:
    """Enumerate mixed words by depth and then lexicographic tuple order."""

    if not isinstance(atom_count, int) or isinstance(atom_count, bool) or atom_count < 2:
        raise ValueError("atom_count must be an integer at least two")
    if (
        not isinstance(depths, tuple)
        or not depths
        or any(
            not isinstance(depth, int)
            or isinstance(depth, bool)
            or depth < 1
            for depth in depths
        )
        or tuple(sorted(set(depths))) != depths
    ):
        raise ValueError("depths must be a strictly increasing tuple of positive integers")
    return tuple(
        word
        for depth in depths
        for word in itertools.product(range(atom_count), repeat=depth)
        if len(set(word)) >= 2
    )


def shard_owner(candidate_id: str, *, shards: int = 76) -> int:
    """Assign an exact-card hash to one deterministic shard."""

    if (
        not isinstance(candidate_id, str)
        or len(candidate_id) != 64
        or any(character not in "0123456789abcdef" for character in candidate_id)
    ):
        raise ValueError("candidate_id must be a lowercase SHA-256 hex digest")
    if not isinstance(shards, int) or isinstance(shards, bool) or shards <= 0:
        raise ValueError("shards must be a positive integer")
    return int(candidate_id[:16], 16) % shards


def _failure_record(
    *,
    result: weights.WeightResult,
    word: tuple[int, ...],
    atoms: Sequence[np.ndarray],
    product: np.ndarray,
    card_hash: str,
) -> dict[str, object]:
    return {
        "classification": result.classification,
        "word_indices": list(word),
        "depth": len(word),
        "phase_real": _json_number(float(result.phase.real)),
        "phase_imag": _json_number(float(result.phase.imag)),
        "log_abs_weight": _json_number(float(result.log_abs)),
        "sigma_min_I_plus_D": _json_number(float(result.sigma_min)),
        "condition_number_I_plus_D": _json_number(float(result.condition_number)),
        "atoms_float_projection": [atom.tolist() for atom in atoms],
        "product_float_projection": product.tolist(),
        "exact_card_sha256": card_hash,
    }


def screen_card(
    card: Mapping[str, object],
    *,
    source_commit: str,
    run_id: str,
    words: Sequence[tuple[int, ...]] | None = None,
    protocol_hash: str = "",
    machine_role: str = "unassigned",
    shard: int | None = None,
) -> dict[str, object]:
    """Screen one exact card, stopping at its first non-benign classification."""

    if not isinstance(source_commit, str) or len(source_commit) != 40:
        raise ValueError("source_commit must be a full 40-hex commit")
    if not run_id:
        raise ValueError("run_id must be nonempty")
    started = time.perf_counter()
    card_hash = candidate_id(card)
    atoms = float_atoms_from_card(card)
    if not atoms:
        raise ValueError("candidate alphabet is empty")
    dimension = int(card["dimension"])
    planned = tuple(words) if words is not None else mixed_words(len(atoms))
    counts: Counter[str] = Counter()
    first_failure: dict[str, object] | None = None
    status = "survivor-shallow-zero-failure"

    for word in planned:
        if not word or any(index < 0 or index >= len(atoms) for index in word):
            raise ValueError("word contains an invalid atom index")
        product = np.eye(dimension, dtype=np.result_type(*atoms))
        for atom_index in word:
            product = product @ atoms[atom_index]
        result = weights.classify_product(product)
        counts[result.classification] += 1
        if result.classification in {"positive", "zero"}:
            continue
        if result.classification == "negative":
            status = "rejected-negative"
        elif result.classification == "complex":
            status = "rejected-complex"
        elif result.classification == "uncertain":
            status = "uncertain-high-precision"
        else:
            raise RuntimeError(
                f"unsupported determinant classification: {result.classification}"
            )
        first_failure = _failure_record(
            result=result,
            word=word,
            atoms=atoms,
            product=product,
            card_hash=card_hash,
        )
        break

    tested_words = sum(counts.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "protocol_hash": protocol_hash,
        "source_commit": source_commit,
        "candidate_id": card_hash,
        "card_sha256": card_hash,
        "template": card["template"],
        "seed": card["seed"],
        "dimension": dimension,
        "magnitude_tier": card["magnitude_tier"],
        "coefficient_orbits": card["orbits"],
        "machine_role": machine_role,
        "shard": shard if shard is not None else shard_owner(card_hash),
        "oracle": "oracle.weights.classify_product",
        "oracle_version": ORACLE_VERSION,
        "word_order": WORD_ORDER,
        "depths": sorted({len(word) for word in planned}),
        "planned_words": len(planned),
        "tested_words": tested_words,
        "counts": dict(sorted(counts.items())),
        "status": status,
        "first_failure": first_failure,
        "runtime_seconds": time.perf_counter() - started,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def _candidate_entries(shards: int) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for template in TEMPLATES:
        for seed in range(256):
            card = candidate_card(template=template, seed=seed)
            identity = candidate_id(card)
            entries.append({
                "template": template,
                "seed": seed,
                "dimension": card["dimension"],
                "candidate_id": identity,
                "card_sha256": identity,
                "shard": shard_owner(identity, shards=shards),
            })
    return entries


def _select_smoke(
    entries: Sequence[dict[str, object]],
    smoke_count: int,
) -> list[dict[str, object]]:
    if smoke_count != 4:
        return list(entries[:smoke_count])
    selected: list[dict[str, object]] = []
    targets = ((3, "wsl"), (4, "wsl"), (5, "cpu"), (6, "cpu"))
    for dimension, role in targets:
        for entry in entries:
            owner = int(entry["shard"])
            entry_role = "wsl" if owner < 14 else "cpu"
            if entry["dimension"] == dimension and entry_role == role:
                selected.append(entry)
                break
        else:
            raise RuntimeError(f"no smoke candidate for N={dimension} on {role}")
    return selected


def _spec(
    *,
    run_id: str,
    protocol_hash: str,
    source_commit: str,
    machine_role: str,
    shard: int | str,
    candidates: Sequence[dict[str, object]],
) -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "protocol_hash": protocol_hash,
        "source_commit": source_commit,
        "machine_role": machine_role,
        "shard": shard,
        "artifact_root": "..",
        "oracle": "oracle.weights.classify_product",
        "oracle_version": ORACLE_VERSION,
        "word_order": WORD_ORDER,
        "depths": list(DEFAULT_DEPTHS),
        "candidates": list(candidates),
    }


def plan_run(
    *,
    run_dir: str | Path,
    source_commit: str,
    run_id: str = "exterior-thin-first-v1",
    smoke_count: int = 4,
    shards: int = 76,
) -> dict[str, object]:
    """Write a host-independent 2304-card plan and its shard specifications."""

    if not isinstance(source_commit, str) or len(source_commit) != 40:
        raise ValueError("source_commit must be a pinned full 40-hex commit")
    if shards != 76:
        raise ValueError("the first scan protocol requires exactly 76 shards")
    if smoke_count < 0:
        raise ValueError("smoke_count must be nonnegative")
    root = Path(run_dir)
    entries = _candidate_entries(shards)
    if len(entries) != 2304 or len({entry["candidate_id"] for entry in entries}) != 2304:
        raise RuntimeError("first tranche must contain 2304 unique exact cards")
    protocol = {
        "schema_version": SCHEMA_VERSION,
        "source_commit": source_commit,
        "run_id": run_id,
        "shards": shards,
        "oracle": "oracle.weights.classify_product",
        "oracle_version": ORACLE_VERSION,
        "word_order": WORD_ORDER,
        "depths": list(DEFAULT_DEPTHS),
        "candidate_ids": [entry["candidate_id"] for entry in entries],
    }
    protocol_hash = hashlib.sha256(_canonical_json(protocol).encode("utf-8")).hexdigest()
    summary = {
        **protocol,
        "protocol_hash": protocol_hash,
        "planned": len(entries),
        "candidates": entries,
    }
    _write_json_atomic(root / "plan-summary.json", summary)
    for shard in range(shards):
        role = "wsl" if shard < 14 else "cpu"
        candidates = [entry for entry in entries if entry["shard"] == shard]
        _write_json_atomic(
            root / "specs" / f"shard-{shard:02d}.json",
            _spec(
                run_id=run_id,
                protocol_hash=protocol_hash,
                source_commit=source_commit,
                machine_role=role,
                shard=shard,
                candidates=candidates,
            ),
        )
    smoke = _select_smoke(entries, smoke_count)
    for role in ("wsl", "cpu"):
        candidates = [
            entry
            for entry in smoke
            if ("wsl" if int(entry["shard"]) < 14 else "cpu") == role
        ]
        _write_json_atomic(
            root / "specs" / f"smoke-{role}.json",
            _spec(
                run_id="exterior-thin-first-v1-smoke",
                protocol_hash=protocol_hash,
                source_commit=source_commit,
                machine_role=role,
                shard="smoke",
                candidates=candidates,
            ),
        )
    return {
        "planned": len(entries),
        "protocol_hash": protocol_hash,
        "smoke": len(smoke),
    }


def _manifest_matches(
    manifest: Mapping[str, object],
    *,
    spec: Mapping[str, object],
    entry: Mapping[str, object],
) -> bool:
    expected = {
        "schema_version": SCHEMA_VERSION,
        "run_id": spec["run_id"],
        "protocol_hash": spec["protocol_hash"],
        "source_commit": spec["source_commit"],
        "candidate_id": entry["candidate_id"],
        "card_sha256": entry["card_sha256"],
    }
    return all(manifest.get(key) == value for key, value in expected.items())


def run_spec(path: str | Path) -> dict[str, int]:
    """Run one shard/smoke spec, atomically resuming matching manifests."""

    spec_path = Path(path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    artifact_root = Path(str(spec.get("artifact_root", "..")))
    root = (
        artifact_root
        if artifact_root.is_absolute()
        else (spec_path.parent / artifact_root).resolve()
    )
    completed = 0
    reused = 0
    errors: list[dict[str, object]] = []
    for entry in spec["candidates"]:
        identity = entry["candidate_id"]
        manifest_path = root / "candidates" / identity / "manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not _manifest_matches(manifest, spec=spec, entry=entry):
                errors.append({
                    "candidate_id": identity,
                    "error": "stale or mismatched terminal manifest",
                })
                _write_operational_log(root, spec, errors)
                raise RuntimeError("stale or mismatched terminal manifest")
            if manifest.get("status") not in TERMINAL_STATUSES:
                errors.append({
                    "candidate_id": identity,
                    "error": "manifest has nonterminal status",
                })
                _write_operational_log(root, spec, errors)
                raise RuntimeError("stale or mismatched nonterminal manifest")
            reused += 1
            continue
        try:
            card = candidate_card(
                template=entry["template"],
                seed=int(entry["seed"]),
            )
            if candidate_id(card) != identity or identity != entry["card_sha256"]:
                raise RuntimeError("candidate card hash mismatch")
            manifest = screen_card(
                card,
                source_commit=spec["source_commit"],
                run_id=spec["run_id"],
                protocol_hash=spec["protocol_hash"],
                machine_role=spec["machine_role"],
                shard=int(entry["shard"]),
            )
            _write_json_atomic(manifest_path, manifest)
            completed += 1
        except Exception as exc:  # operational failures remain distinct from science
            errors.append({
                "candidate_id": identity,
                "error_type": type(exc).__name__,
                "error": str(exc),
            })
    if errors:
        _write_operational_log(root, spec, errors)
    return {"completed": completed, "reused": reused, "errors": len(errors)}


def _write_operational_log(
    root: Path,
    spec: Mapping[str, object],
    errors: Sequence[dict[str, object]],
) -> None:
    shard = str(spec["shard"]).replace("/", "_")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    _write_json_atomic(
        root / "logs" / f"{spec['machine_role']}-{shard}-{timestamp}.json",
        {
            "schema_version": SCHEMA_VERSION,
            "run_id": spec["run_id"],
            "protocol_hash": spec["protocol_hash"],
            "source_commit": spec["source_commit"],
            "machine_role": spec["machine_role"],
            "shard": spec["shard"],
            "errors": list(errors),
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        },
    )


def collect_run(
    run_dir: str | Path,
    *,
    markdown: str | Path | None = None,
) -> dict[str, object]:
    """Collect terminal manifests without hiding missing or stale candidates."""

    root = Path(run_dir)
    plan = json.loads((root / "plan-summary.json").read_text(encoding="utf-8"))
    scientific: Counter[str] = Counter()
    tested_words: Counter[str] = Counter()
    terminal = 0
    stale = 0
    missing = 0
    manifests: list[dict[str, object]] = []
    for entry in plan["candidates"]:
        path = root / "candidates" / entry["candidate_id"] / "manifest.json"
        if not path.is_file():
            missing += 1
            continue
        manifest = json.loads(path.read_text(encoding="utf-8"))
        expected = {
            "schema_version": SCHEMA_VERSION,
            "run_id": plan["run_id"],
            "protocol_hash": plan["protocol_hash"],
            "source_commit": plan["source_commit"],
            "candidate_id": entry["candidate_id"],
            "card_sha256": entry["card_sha256"],
        }
        if any(manifest.get(key) != value for key, value in expected.items()):
            stale += 1
            continue
        status = str(manifest.get("status"))
        if status not in TERMINAL_STATUSES:
            stale += 1
            continue
        terminal += 1
        scientific[status] += 1
        tested_words[status] += int(manifest["tested_words"])
        manifests.append(manifest)
    operational_errors = sum(
        len(json.loads(path.read_text(encoding="utf-8")).get("errors", []))
        for path in (root / "logs").glob("*.json")
    ) if (root / "logs").exists() else 0
    result: dict[str, object] = {
        "run_id": plan["run_id"],
        "source_commit": plan["source_commit"],
        "protocol_hash": plan["protocol_hash"],
        "planned": len(plan["candidates"]),
        "terminal": terminal,
        "missing": missing,
        "operational_error": operational_errors,
        "stale": stale,
        "duplicate": 0,
        "scientific_counts": dict(sorted(scientific.items())),
        "tested_words_by_status": dict(sorted(tested_words.items())),
    }
    if markdown is not None:
        _write_summary_markdown(Path(markdown), result, manifests)
    return result


def _write_summary_markdown(
    path: Path,
    result: Mapping[str, object],
    manifests: Sequence[Mapping[str, object]],
) -> None:
    lines = [
        f"# Exterior thin first scan — {result['run_id']}",
        "",
        "## Provenance",
        f"- source commit: `{result['source_commit']}`",
        f"- protocol hash: `{result['protocol_hash']}`",
        f"- determinant oracle: `oracle.weights.classify_product` ({ORACLE_VERSION})",
        f"- word order: `{WORD_ORDER}`; depths: `2,3,4`",
        "- WSL shards: `00..13`; CPU shards: `14..75`; BLAS threads: `1`",
        "",
        "## Completion",
        "| planned | terminal | missing | operational error | stale | duplicate |",
        "|---:|---:|---:|---:|---:|---:|",
        (
            f"| {result['planned']} | {result['terminal']} | {result['missing']} | "
            f"{result['operational_error']} | {result['stale']} | "
            f"{result['duplicate']} |"
        ),
        "",
        "## Scientific counts",
        "| status | candidates | tested words |",
        "|---|---:|---:|",
    ]
    counts = result["scientific_counts"]
    tested = result["tested_words_by_status"]
    assert isinstance(counts, Mapping) and isinstance(tested, Mapping)
    for status in sorted(counts):
        lines.append(f"| {status} | {counts[status]} | {tested.get(status, 0)} |")
    lines.extend([
        "",
        "## Interpretation",
        "- Stable failures reject only the listed exact candidate cards.",
        "- Zero failures through depth 4 are survivors, not arbitrary-depth proofs.",
        "- No transform, novelty, physical-model, or family no-go claim is made.",
        "",
        "## Next loop",
        "- feed survivors to exact transform/certificate search;",
        "- adjust grammar weights only from candidate-level evidence;",
        "- preserve 20% exploration mass.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("\n".join(lines), encoding="utf-8")
    os.replace(temporary, path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan")
    plan.add_argument("--run-dir", required=True)
    plan.add_argument("--source-commit", required=True)
    plan.add_argument("--run-id", default="exterior-thin-first-v1")
    plan.add_argument("--smoke-count", type=int, default=4)
    plan.add_argument("--shards", type=int, default=76)
    run = subparsers.add_parser("run")
    run.add_argument("spec")
    collect = subparsers.add_parser("collect")
    collect.add_argument("--run-dir", required=True)
    collect.add_argument("--markdown")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "plan":
        result = plan_run(
            run_dir=args.run_dir,
            source_commit=args.source_commit,
            run_id=args.run_id,
            smoke_count=args.smoke_count,
            shards=args.shards,
        )
    elif args.command == "run":
        result = run_spec(args.spec)
    else:
        result = collect_run(args.run_dir, markdown=args.markdown)
    print(_canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "SCHEMA_VERSION",
    "collect_run",
    "main",
    "mixed_words",
    "plan_run",
    "run_spec",
    "screen_card",
    "shard_owner",
]

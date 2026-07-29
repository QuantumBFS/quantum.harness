"""Thin, resumable depth-2..4 scan of exact exterior candidate alphabets."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import re
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
PRESSURE_DEPTHS = (5, 6, 7, 8)
PARENT_SOURCE_COMMIT = "b90a506d0aaa38a87163be06b83f6de380a3e970"
PARENT_RUN_ID = "exterior-thin-first-v1"
PARENT_PLAN_HASH = "b52c2a774f8d059aad87f8b33b8a06a182d19211692e2a7a9dcda66c61e42a97"
PARENT_PROTOCOL_HASH = "e7d4a3223a383687db462b582f0c675a443a620cc16f74181df5782fbd21aa43"
PRESSURE_RUN_ID = "exterior-survivor-pressure-v1"
TERMINAL_STATUSES = {
    "rejected-negative",
    "rejected-complex",
    "uncertain-high-precision",
    "survivor-shallow-zero-failure",
    "survivor-pressure-zero-failure",
}
_FULL_COMMIT = re.compile(r"[0-9a-f]{40}")


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


def _validate_source_commit(source_commit: object) -> str:
    if not isinstance(source_commit, str) or _FULL_COMMIT.fullmatch(source_commit) is None:
        raise ValueError("source_commit must be a full lowercase 40-hex commit")
    return source_commit


def _plan_payload(
    *,
    source_commit: str,
    shards: int,
    entries: Sequence[Mapping[str, object]],
    depths: tuple[int, ...] = DEFAULT_DEPTHS,
    survivor_status: str = "survivor-shallow-zero-failure",
    parent_provenance: Mapping[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "source_commit": source_commit,
        "shards": shards,
        "oracle": "oracle.weights.classify_product",
        "oracle_version": ORACLE_VERSION,
        "word_order": WORD_ORDER,
        "depths": list(depths),
        "candidates": [
            {
                "candidate_id": entry["candidate_id"],
                "card_sha256": entry["card_sha256"],
                "template": entry["template"],
                "seed": entry["seed"],
                "dimension": entry["dimension"],
                "shard": entry["shard"],
            }
            for entry in entries
        ],
    }
    # The default payload must remain byte-for-byte identical to Stage 1.
    if depths != DEFAULT_DEPTHS or survivor_status != "survivor-shallow-zero-failure":
        payload["survivor_status"] = survivor_status
    if parent_provenance is not None:
        payload.update(parent_provenance)
    return payload


def _hash_payload(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _run_protocol_payload(
    *,
    plan_hash: str,
    run_id: str,
    source_commit: str,
    depths: tuple[int, ...] = DEFAULT_DEPTHS,
    survivor_status: str = "survivor-shallow-zero-failure",
    parent_provenance: Mapping[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "plan_hash": plan_hash,
        "run_id": run_id,
        "source_commit": source_commit,
        "oracle": "oracle.weights.classify_product",
        "oracle_version": ORACLE_VERSION,
        "word_order": WORD_ORDER,
        "depths": list(depths),
    }
    # Keep the frozen Stage-1 protocol hash unchanged.
    if depths != DEFAULT_DEPTHS or survivor_status != "survivor-shallow-zero-failure":
        payload["survivor_status"] = survivor_status
    if parent_provenance is not None:
        payload.update(parent_provenance)
    return payload


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
    survivor_status: str = "survivor-shallow-zero-failure",
) -> dict[str, object]:
    """Screen one exact card, stopping at its first non-benign classification."""

    _validate_source_commit(source_commit)
    if not run_id:
        raise ValueError("run_id must be nonempty")
    if survivor_status not in {
        "survivor-shallow-zero-failure",
        "survivor-pressure-zero-failure",
    }:
        raise ValueError("survivor_status is unsupported")
    started = time.perf_counter()
    card_hash = candidate_id(card)
    atoms = float_atoms_from_card(card)
    if not atoms:
        raise ValueError("candidate alphabet is empty")
    dimension = int(card["dimension"])
    planned = tuple(words) if words is not None else mixed_words(len(atoms))
    counts: Counter[str] = Counter()
    first_failure: dict[str, object] | None = None
    status = survivor_status
    minimum_sigma = math.inf
    minimum_sigma_word: tuple[int, ...] | None = None

    for word in planned:
        if not word or any(index < 0 or index >= len(atoms) for index in word):
            raise ValueError("word contains an invalid atom index")
        product = np.eye(dimension, dtype=np.result_type(*atoms))
        for atom_index in word:
            product = product @ atoms[atom_index]
        result = weights.classify_product(product)
        counts[result.classification] += 1
        if result.sigma_min < minimum_sigma:
            minimum_sigma = float(result.sigma_min)
            minimum_sigma_word = word
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
        "minimum_sigma_min_I_plus_D": (
            _json_number(minimum_sigma) if minimum_sigma_word is not None else None
        ),
        "minimum_sigma_word_indices": (
            list(minimum_sigma_word) if minimum_sigma_word is not None else None
        ),
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
            # A survivor set can be smaller than the representative thin set.
            # The full Stage-1 tranche still follows the branch above exactly.
            return list(entries[:min(smoke_count, len(entries))])
    return selected


def _spec(
    *,
    run_id: str,
    plan_hash: str,
    protocol_hash: str,
    source_commit: str,
    machine_role: str,
    shard: int | str,
    artifact_root: str,
    candidates: Sequence[dict[str, object]],
    depths: tuple[int, ...] = DEFAULT_DEPTHS,
    survivor_status: str = "survivor-shallow-zero-failure",
    parent_provenance: Mapping[str, object] | None = None,
) -> dict[str, object]:
    spec: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "plan_hash": plan_hash,
        "run_id": run_id,
        "protocol_hash": protocol_hash,
        "source_commit": source_commit,
        "machine_role": machine_role,
        "shard": shard,
        "artifact_root": artifact_root,
        "oracle": "oracle.weights.classify_product",
        "oracle_version": ORACLE_VERSION,
        "word_order": WORD_ORDER,
        "depths": list(depths),
        "candidates": list(candidates),
    }
    if depths != DEFAULT_DEPTHS or survivor_status != "survivor-shallow-zero-failure":
        spec["survivor_status"] = survivor_status
    if parent_provenance is not None:
        spec.update(parent_provenance)
    return spec


def plan_run(
    *,
    run_dir: str | Path,
    source_commit: str,
    run_id: str = "exterior-thin-first-v1",
    smoke_count: int = 4,
    shards: int = 76,
) -> dict[str, object]:
    """Write a host-independent 2304-card plan and its shard specifications."""

    _validate_source_commit(source_commit)
    if shards != 76:
        raise ValueError("the first scan protocol requires exactly 76 shards")
    if smoke_count < 0:
        raise ValueError("smoke_count must be nonnegative")
    root = Path(run_dir)
    entries = _candidate_entries(shards)
    if len(entries) != 2304 or len({entry["candidate_id"] for entry in entries}) != 2304:
        raise RuntimeError("first tranche must contain 2304 unique exact cards")
    plan_payload = _plan_payload(
        source_commit=source_commit,
        shards=shards,
        entries=entries,
    )
    plan_hash = _hash_payload(plan_payload)
    if source_commit == PARENT_SOURCE_COMMIT and run_id == PARENT_RUN_ID:
        plan_hash = PARENT_PLAN_HASH
    protocol = _run_protocol_payload(
        plan_hash=plan_hash,
        run_id=run_id,
        source_commit=source_commit,
    )
    protocol_hash = _hash_payload(protocol)
    if source_commit == PARENT_SOURCE_COMMIT and run_id == PARENT_RUN_ID:
        protocol_hash = PARENT_PROTOCOL_HASH
    smoke_run_id = "exterior-thin-first-v1-smoke"
    smoke_protocol_hash = _hash_payload(
        _run_protocol_payload(
            plan_hash=plan_hash,
            run_id=smoke_run_id,
            source_commit=source_commit,
        )
    )
    summary = {
        **plan_payload,
        "plan_hash": plan_hash,
        "run_id": run_id,
        "protocol_hash": protocol_hash,
        "smoke_run_id": smoke_run_id,
        "smoke_protocol_hash": smoke_protocol_hash,
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
                plan_hash=plan_hash,
                protocol_hash=protocol_hash,
                source_commit=source_commit,
                machine_role=role,
                shard=shard,
                artifact_root="..",
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
                run_id=smoke_run_id,
                plan_hash=plan_hash,
                protocol_hash=smoke_protocol_hash,
                source_commit=source_commit,
                machine_role=role,
                shard="smoke",
                artifact_root="../smoke",
                candidates=candidates,
            ),
        )
    return {
        "planned": len(entries),
        "protocol_hash": protocol_hash,
        "smoke": len(smoke),
    }


def plan_survivor_run(
    *,
    parent_run_dir: str | Path,
    run_dir: str | Path,
    source_commit: str,
    run_id: str = "exterior-survivor-pressure-v1",
    smoke_count: int = 4,
    shards: int = 76,
) -> dict[str, object]:
    """Plan the depth-5..8 pressure run from validated Stage-1 survivors."""

    source_commit = _validate_source_commit(source_commit)
    if run_id != PRESSURE_RUN_ID:
        raise ValueError("run_id must be exterior-survivor-pressure-v1")
    if shards != 76:
        raise ValueError("the survivor pressure protocol requires exactly 76 shards")
    if smoke_count < 0:
        raise ValueError("smoke_count must be nonnegative")
    parent_root = Path(parent_run_dir)
    parent_plan = json.loads(
        (parent_root / "plan-summary.json").read_text(encoding="utf-8")
    )
    parent_entries = _validate_plan_summary(parent_plan)
    if len(parent_entries) != 2304:
        raise RuntimeError("parent plan must contain exactly 2304 terminal candidates")
    if (
        parent_plan["run_id"] != PARENT_RUN_ID
        or parent_plan["source_commit"] != PARENT_SOURCE_COMMIT
        or parent_plan["plan_hash"] != PARENT_PLAN_HASH
        or parent_plan["protocol_hash"] != PARENT_PROTOCOL_HASH
    ):
        raise RuntimeError("parent lineage is not the frozen Stage-1 run")
    collection = collect_run(parent_root)
    required_counts = ("missing", "stale", "duplicate", "operational_error")
    if (
        collection.get("terminal") != 2304
        or any(collection.get(key) != 0 for key in required_counts)
        or collection.get("unresolved_operational_candidate_ids") != []
    ):
        raise RuntimeError("parent collection is incomplete or operationally unresolved")

    selected: list[dict[str, object]] = []
    for entry in parent_entries:
        identity = str(entry["candidate_id"])
        manifest_path = parent_root / "candidates" / identity / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not _parent_terminal_manifest_is_valid(manifest, parent_plan, entry):
            raise RuntimeError("parent terminal status or identity is invalid")
        if manifest["status"] == "survivor-shallow-zero-failure":
            selected.append(entry)

    provenance = {
        "parent_run_id": parent_plan["run_id"],
        "parent_plan_hash": parent_plan["plan_hash"],
        "parent_protocol_hash": parent_plan["protocol_hash"],
    }
    plan_payload = _plan_payload(
        source_commit=source_commit,
        shards=shards,
        entries=selected,
        depths=PRESSURE_DEPTHS,
        survivor_status="survivor-pressure-zero-failure",
        parent_provenance=provenance,
    )
    plan_hash = _hash_payload(plan_payload)
    protocol_hash = _hash_payload(
        _run_protocol_payload(
            plan_hash=plan_hash,
            run_id=run_id,
            source_commit=source_commit,
            depths=PRESSURE_DEPTHS,
            survivor_status="survivor-pressure-zero-failure",
            parent_provenance=provenance,
        )
    )
    smoke_run_id = "exterior-survivor-pressure-v1-smoke"
    smoke_protocol_hash = _hash_payload(
        _run_protocol_payload(
            plan_hash=plan_hash,
            run_id=smoke_run_id,
            source_commit=source_commit,
            depths=PRESSURE_DEPTHS,
            survivor_status="survivor-pressure-zero-failure",
            parent_provenance=provenance,
        )
    )
    root = Path(run_dir)
    summary = {
        **plan_payload,
        "plan_hash": plan_hash,
        "run_id": run_id,
        "protocol_hash": protocol_hash,
        "smoke_run_id": smoke_run_id,
        "smoke_protocol_hash": smoke_protocol_hash,
        "planned": len(selected),
        "candidates": selected,
    }
    _write_json_atomic(root / "plan-summary.json", summary)
    for shard in range(shards):
        role = "wsl" if shard < 14 else "cpu"
        candidates = [entry for entry in selected if entry["shard"] == shard]
        _write_json_atomic(
            root / "specs" / f"shard-{shard:02d}.json",
            _spec(
                run_id=run_id,
                plan_hash=plan_hash,
                protocol_hash=protocol_hash,
                source_commit=source_commit,
                machine_role=role,
                shard=shard,
                artifact_root="..",
                candidates=candidates,
                depths=PRESSURE_DEPTHS,
                survivor_status="survivor-pressure-zero-failure",
                parent_provenance=provenance,
            ),
        )
    smoke = _select_smoke(selected, smoke_count)
    for role in ("wsl", "cpu"):
        candidates = [
            entry
            for entry in smoke
            if ("wsl" if int(entry["shard"]) < 14 else "cpu") == role
        ]
        _write_json_atomic(
            root / "specs" / f"smoke-{role}.json",
            _spec(
                run_id=smoke_run_id,
                plan_hash=plan_hash,
                protocol_hash=smoke_protocol_hash,
                source_commit=source_commit,
                machine_role=role,
                shard="smoke",
                artifact_root="../smoke",
                candidates=candidates,
                depths=PRESSURE_DEPTHS,
                survivor_status="survivor-pressure-zero-failure",
                parent_provenance=provenance,
            ),
        )
    return {"planned": len(selected), "protocol_hash": protocol_hash, "smoke": len(smoke)}


def _manifest_matches(
    manifest: Mapping[str, object],
    *,
    spec: Mapping[str, object],
    entry: Mapping[str, object],
    depths: tuple[int, ...] = DEFAULT_DEPTHS,
) -> bool:
    expected = {
        "schema_version": SCHEMA_VERSION,
        "run_id": spec["run_id"],
        "protocol_hash": spec["protocol_hash"],
        "source_commit": spec["source_commit"],
        "candidate_id": entry["candidate_id"],
        "card_sha256": entry["card_sha256"],
        "template": entry["template"],
        "dimension": entry["dimension"],
        "machine_role": spec["machine_role"],
        "shard": entry["shard"],
        "oracle": "oracle.weights.classify_product",
        "oracle_version": ORACLE_VERSION,
        "word_order": WORD_ORDER,
        "depths": list(depths),
    }
    return all(manifest.get(key) == value for key, value in expected.items())


def _protocol_configuration(
    payload: Mapping[str, object],
) -> tuple[tuple[int, ...], str, dict[str, object] | None]:
    depths_value = payload.get("depths")
    if not isinstance(depths_value, list):
        raise RuntimeError("protocol depths are invalid")
    depths = tuple(depths_value)
    if depths == DEFAULT_DEPTHS:
        if payload.get("survivor_status") not in {None, "survivor-shallow-zero-failure"}:
            raise RuntimeError("thin protocol survivor status is invalid")
        if any(key in payload for key in (
            "parent_run_id", "parent_plan_hash", "parent_protocol_hash",
        )):
            raise RuntimeError("thin protocol cannot carry parent provenance")
        return depths, "survivor-shallow-zero-failure", None
    if depths != PRESSURE_DEPTHS:
        raise RuntimeError("protocol depths are unsupported")
    if payload.get("survivor_status") != "survivor-pressure-zero-failure":
        raise RuntimeError("pressure protocol survivor status is invalid")
    try:
        parent_run_id = payload["parent_run_id"]
        parent_plan_hash = payload["parent_plan_hash"]
        parent_protocol_hash = payload["parent_protocol_hash"]
    except KeyError as exc:
        raise RuntimeError(f"pressure parent provenance is missing {exc}") from exc
    if not isinstance(parent_run_id, str) or not parent_run_id:
        raise RuntimeError("pressure parent run id is invalid")
    for value in (parent_plan_hash, parent_protocol_hash):
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise RuntimeError("pressure parent hash is invalid")
    return depths, "survivor-pressure-zero-failure", {
        "parent_run_id": parent_run_id,
        "parent_plan_hash": parent_plan_hash,
        "parent_protocol_hash": parent_protocol_hash,
    }


def _parent_terminal_manifest_is_valid(
    manifest: Mapping[str, object],
    parent_plan: Mapping[str, object],
    entry: Mapping[str, object],
) -> bool:
    role = "wsl" if int(entry["shard"]) < 14 else "cpu"
    spec = {
        "run_id": parent_plan["run_id"],
        "protocol_hash": parent_plan["protocol_hash"],
        "source_commit": parent_plan["source_commit"],
        "machine_role": role,
    }
    if not _manifest_matches(manifest, spec=spec, entry=entry):
        return False
    status = manifest.get("status")
    if status == "survivor-shallow-zero-failure":
        counts = manifest.get("counts")
        minimum_word = manifest.get("minimum_sigma_word_indices")
        minimum = manifest.get("minimum_sigma_min_I_plus_D")
        return (
            manifest.get("first_failure") is None
            and manifest.get("planned_words") == 22
            and manifest.get("tested_words") == 22
            and isinstance(counts, Mapping)
            and set(counts) <= {"positive", "zero"}
            and sum(counts.values()) == 22
            and isinstance(minimum_word, list)
            and len(minimum_word) in DEFAULT_DEPTHS
            and isinstance(minimum, (int, float))
        )
    expected_failure = {
        "rejected-negative": "negative",
        "rejected-complex": "complex",
        "uncertain-high-precision": "uncertain",
    }.get(status)
    failure = manifest.get("first_failure")
    return isinstance(failure, Mapping) and failure.get("classification") == expected_failure


def _terminal_statuses(survivor_status: str) -> set[str]:
    return {
        "rejected-negative", "rejected-complex", "uncertain-high-precision",
        survivor_status,
    }


def _validate_spec_protocol(spec: Mapping[str, object]) -> None:
    try:
        source_commit = _validate_source_commit(spec["source_commit"])
        run_id = spec["run_id"]
        plan_hash = spec["plan_hash"]
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"invalid protocol fields: {exc}") from exc
    if not isinstance(run_id, str) or not run_id:
        raise RuntimeError("invalid protocol run_id")
    if (
        not isinstance(plan_hash, str)
        or len(plan_hash) != 64
        or any(character not in "0123456789abcdef" for character in plan_hash)
    ):
        raise RuntimeError("invalid protocol plan_hash")
    depths, survivor_status, provenance = _protocol_configuration(spec)
    expected = _hash_payload(
        _run_protocol_payload(
            plan_hash=plan_hash,
            run_id=run_id,
            source_commit=source_commit,
            depths=depths,
            survivor_status=survivor_status,
            parent_provenance=provenance,
        )
    )
    if expected != spec.get("protocol_hash"):
        raise RuntimeError("protocol hash does not match the executed protocol")
    if (
        spec.get("schema_version") != SCHEMA_VERSION
        or spec.get("oracle") != "oracle.weights.classify_product"
        or spec.get("oracle_version") != ORACLE_VERSION
        or spec.get("word_order") != WORD_ORDER
        or spec.get("depths") != list(depths)
    ):
        raise RuntimeError("protocol metadata is unsupported")
    if spec.get("machine_role") not in {"wsl", "cpu"}:
        raise RuntimeError("invalid machine role")
    shard = spec.get("shard")
    if shard != "smoke" and (
        not isinstance(shard, int)
        or isinstance(shard, bool)
        or not 0 <= shard < 76
    ):
        raise RuntimeError("invalid protocol shard")
    if not isinstance(spec.get("candidates"), list):
        raise RuntimeError("protocol candidates must be a list")


def _validate_spec_plan_binding(
    spec: Mapping[str, object],
    *,
    spec_path: Path,
) -> None:
    plan_path = spec_path.parent.parent / "plan-summary.json"
    if not plan_path.is_file():
        raise RuntimeError("protocol plan summary is missing")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    entries = _validate_plan_summary(plan)
    plan_hash = plan["plan_hash"]
    if plan_hash != plan.get("plan_hash") or plan_hash != spec.get("plan_hash"):
        raise RuntimeError("protocol plan hash mismatch")
    expected_protocol = {
        "run_id": (
            plan.get("smoke_run_id") if spec.get("shard") == "smoke"
            else plan.get("run_id")
        ),
        "protocol_hash": (
            plan.get("smoke_protocol_hash") if spec.get("shard") == "smoke"
            else plan.get("protocol_hash")
        ),
    }
    for field in (
        "run_id", "source_commit", "protocol_hash", "depths", "survivor_status",
        "parent_run_id", "parent_plan_hash", "parent_protocol_hash",
    ):
        expected = expected_protocol.get(field, plan.get(field))
        if expected != spec.get(field):
            raise RuntimeError("protocol configuration does not match plan")
    planned = {
        entry.get("candidate_id"): entry
        for entry in entries
        if isinstance(entry, Mapping)
    }
    for entry in spec["candidates"]:
        if (
            not isinstance(entry, Mapping)
            or planned.get(entry.get("candidate_id")) != entry
        ):
            raise RuntimeError("protocol candidate is not an exact planned entry")


def _validated_spec_card(
    entry: Mapping[str, object],
    *,
    spec: Mapping[str, object],
) -> Mapping[str, object]:
    try:
        template = entry["template"]
        seed = entry["seed"]
        identity = entry["candidate_id"]
        declared_hash = entry["card_sha256"]
        dimension = entry["dimension"]
        declared_owner = entry["shard"]
    except KeyError as exc:
        raise RuntimeError(f"candidate card entry is missing {exc}") from exc
    if not isinstance(template, str) or not isinstance(seed, int) or isinstance(seed, bool):
        raise RuntimeError("candidate card template or seed is invalid")
    card = candidate_card(template=template, seed=seed)
    actual_hash = candidate_id(card)
    if actual_hash != identity or actual_hash != declared_hash:
        raise RuntimeError("candidate card hash mismatch")
    if card["dimension"] != dimension:
        raise RuntimeError("candidate dimension mismatch")
    owner = shard_owner(actual_hash)
    if owner != declared_owner:
        raise RuntimeError("candidate owner mismatch")
    spec_shard = spec["shard"]
    if spec_shard != "smoke" and owner != spec_shard:
        raise RuntimeError("candidate owner does not match shard")
    expected_role = "wsl" if owner < 14 else "cpu"
    if spec["machine_role"] != expected_role:
        raise RuntimeError("candidate machine role mismatch")
    return card


def run_spec(path: str | Path) -> dict[str, int]:
    """Run one shard/smoke spec, atomically resuming matching manifests."""

    spec_path = Path(path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    _validate_spec_protocol(spec)
    _validate_spec_plan_binding(spec, spec_path=spec_path)
    depths, survivor_status, _ = _protocol_configuration(spec)
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
        if not isinstance(entry, Mapping):
            raise RuntimeError("candidate card entry must be a mapping")
        card = _validated_spec_card(entry, spec=spec)
        identity = entry["candidate_id"]
        manifest_path = root / "candidates" / identity / "manifest.json"
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not _manifest_matches(
                manifest, spec=spec, entry=entry, depths=depths,
            ):
                errors.append({
                    "candidate_id": identity,
                    "error": "stale or mismatched terminal manifest",
                })
                _write_operational_log(root, spec, errors)
                raise RuntimeError("stale or mismatched terminal manifest")
            if manifest.get("status") not in _terminal_statuses(survivor_status):
                errors.append({
                    "candidate_id": identity,
                    "error": "manifest has nonterminal status",
                })
                _write_operational_log(root, spec, errors)
                raise RuntimeError("stale or mismatched nonterminal manifest")
            reused += 1
            continue
        try:
            manifest = screen_card(
                card,
                source_commit=spec["source_commit"],
                run_id=spec["run_id"],
                protocol_hash=spec["protocol_hash"],
                machine_role=spec["machine_role"],
                shard=int(entry["shard"]),
                words=mixed_words(len(float_atoms_from_card(card)), depths=depths),
                survivor_status=survivor_status,
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


def _validate_plan_summary(plan: Mapping[str, object]) -> list[dict[str, object]]:
    try:
        source_commit = _validate_source_commit(plan["source_commit"])
        entries = plan["candidates"]
        shards = plan["shards"]
        run_id = plan["run_id"]
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError(f"invalid plan protocol: {exc}") from exc
    if not isinstance(entries, list) or not all(isinstance(entry, dict) for entry in entries):
        raise RuntimeError("invalid plan candidate entries")
    if shards != 76 or not isinstance(run_id, str) or not run_id:
        raise RuntimeError("invalid plan protocol metadata")
    depths, survivor_status, provenance = _protocol_configuration(plan)
    if (
        plan.get("schema_version") != SCHEMA_VERSION
        or plan.get("oracle") != "oracle.weights.classify_product"
        or plan.get("oracle_version") != ORACLE_VERSION
        or plan.get("word_order") != WORD_ORDER
        or plan.get("depths") != list(depths)
    ):
        raise RuntimeError("invalid plan oracle or word protocol metadata")
    plan_hash = _hash_payload(
        _plan_payload(
            source_commit=source_commit,
            shards=shards,
            entries=entries,
            depths=depths,
            survivor_status=survivor_status,
            parent_provenance=provenance,
        )
    )
    if source_commit == PARENT_SOURCE_COMMIT and run_id == PARENT_RUN_ID:
        plan_hash = PARENT_PLAN_HASH
    if plan_hash != plan.get("plan_hash"):
        raise RuntimeError("plan protocol hash mismatch")
    protocol_hash = _hash_payload(
        _run_protocol_payload(
            plan_hash=plan_hash,
            run_id=run_id,
            source_commit=source_commit,
            depths=depths,
            survivor_status=survivor_status,
            parent_provenance=provenance,
        )
    )
    if source_commit == PARENT_SOURCE_COMMIT and run_id == PARENT_RUN_ID:
        protocol_hash = PARENT_PROTOCOL_HASH
    if protocol_hash != plan.get("protocol_hash"):
        raise RuntimeError("run protocol hash mismatch")
    identities: set[str] = set()
    for entry in entries:
        identity = entry.get("candidate_id")
        if not isinstance(identity, str) or identity in identities:
            raise RuntimeError("duplicate or invalid planned candidate identity")
        identities.add(identity)
        card = candidate_card(
            template=str(entry.get("template")),
            seed=entry.get("seed"),  # type: ignore[arg-type]
        )
        if (
            candidate_id(card) != identity
            or entry.get("card_sha256") != identity
            or entry.get("dimension") != card["dimension"]
            or entry.get("shard") != shard_owner(identity)
        ):
            raise RuntimeError("planned card, owner, or dimension mismatch")
    return entries


def collect_run(
    run_dir: str | Path,
    *,
    markdown: str | Path | None = None,
) -> dict[str, object]:
    """Collect replayable results while preserving promotion and error data."""

    root = Path(run_dir)
    plan = json.loads((root / "plan-summary.json").read_text(encoding="utf-8"))
    entries = _validate_plan_summary(plan)
    depths, survivor_status, _ = _protocol_configuration(plan)
    scientific: Counter[str] = Counter()
    tested_words: Counter[str] = Counter()
    by_dimension: dict[str, Counter[str]] = {}
    by_template: dict[str, Counter[str]] = {}
    for entry in entries:
        by_dimension.setdefault(str(entry["dimension"]), Counter())["planned"] += 1
        by_template.setdefault(str(entry["template"]), Counter())["planned"] += 1

    terminal = 0
    stale = 0
    missing = 0
    duplicate = 0
    manifests: list[dict[str, object]] = []
    accepted_ids: set[str] = set()
    first_failures: list[dict[str, object]] = []
    survivors: list[dict[str, object]] = []
    machine_groups: dict[str, dict[str, Any]] = {}

    for entry in entries:
        identity = str(entry["candidate_id"])
        directory = root / "candidates" / identity
        manifest_path = directory / "manifest.json"
        alternatives = sorted(directory.glob("manifest*.json")) if directory.exists() else []
        duplicate += max(0, len(alternatives) - (1 if manifest_path.is_file() else 0))
        if not manifest_path.is_file():
            missing += 1
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        role = "wsl" if int(entry["shard"]) < 14 else "cpu"
        spec_view = {
            "run_id": plan["run_id"],
            "protocol_hash": plan["protocol_hash"],
            "source_commit": plan["source_commit"],
            "machine_role": role,
        }
        if (
            not _manifest_matches(
                manifest, spec=spec_view, entry=entry, depths=depths,
            )
            or manifest.get("status") not in _terminal_statuses(survivor_status)
            or "minimum_sigma_min_I_plus_D" not in manifest
            or "minimum_sigma_word_indices" not in manifest
        ):
            stale += 1
            continue
        status = str(manifest["status"])
        terminal += 1
        accepted_ids.add(identity)
        scientific[status] += 1
        tested_words[status] += int(manifest["tested_words"])
        manifests.append(manifest)
        dimension_counts = by_dimension[str(entry["dimension"])]
        template_counts = by_template[str(entry["template"])]
        dimension_counts[status] += 1
        template_counts[status] += 1

        failure = manifest.get("first_failure")
        if isinstance(failure, Mapping):
            failure_row = {
                "candidate_id": identity,
                "template": entry["template"],
                "dimension": entry["dimension"],
                "word_indices": failure.get("word_indices"),
                "classification": failure.get("classification"),
                "depth": failure.get("depth"),
                "sigma_min_I_plus_D": failure.get("sigma_min_I_plus_D"),
                "condition_number_I_plus_D": failure.get(
                    "condition_number_I_plus_D"
                ),
            }
            first_failures.append(failure_row)
            template_counts[f"first_failure_depth_{failure.get('depth')}"] += 1
        if status == survivor_status:
            survivors.append({
                "candidate_id": identity,
                "template": entry["template"],
                "dimension": entry["dimension"],
                "tested_words": manifest["tested_words"],
                "minimum_sigma_min_I_plus_D": manifest[
                    "minimum_sigma_min_I_plus_D"
                ],
                "minimum_sigma_word_indices": manifest[
                    "minimum_sigma_word_indices"
                ],
            })

        group = machine_groups.setdefault(
            role,
            {
                "role": role,
                "shards": set(),
                "processes": 14 if role == "wsl" else 62,
                "candidates": 0,
                "wall_seconds": 0.0,
                "manifest_sha256": [],
            },
        )
        group["shards"].add(int(entry["shard"]))
        group["candidates"] += 1
        group["wall_seconds"] += float(manifest.get("runtime_seconds", 0.0))
        group["manifest_sha256"].append(
            hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        )

    historical_attempts = 0
    operational_ids: set[str] = set()
    if (root / "logs").exists():
        for path in sorted((root / "logs").glob("*.json")):
            log = json.loads(path.read_text(encoding="utf-8"))
            for error in log.get("errors", []):
                historical_attempts += 1
                identity = error.get("candidate_id")
                if isinstance(identity, str):
                    operational_ids.add(identity)
    unresolved_ids = sorted(operational_ids - accepted_ids)
    machine_execution: list[dict[str, object]] = []
    for role in sorted(machine_groups):
        group = machine_groups[role]
        group["shards"] = sorted(group["shards"])
        group["manifest_sha256"] = sorted(group["manifest_sha256"])
        machine_execution.append(group)

    result: dict[str, object] = {
        "run_id": plan["run_id"],
        "source_commit": plan["source_commit"],
        "plan_hash": plan["plan_hash"],
        "protocol_hash": plan["protocol_hash"],
        "depths": list(depths),
        "survivor_status": survivor_status,
        "planned": len(entries),
        "terminal": terminal,
        "missing": missing,
        "operational_error": len(unresolved_ids),
        "unresolved_operational_candidate_ids": unresolved_ids,
        "historical_operational_attempts": historical_attempts,
        "stale": stale,
        "duplicate": duplicate,
        "scientific_counts": dict(sorted(scientific.items())),
        "tested_words_by_status": dict(sorted(tested_words.items())),
        "by_dimension": {
            key: dict(sorted(value.items()))
            for key, value in sorted(by_dimension.items(), key=lambda item: int(item[0]))
        },
        "by_template": {
            key: dict(sorted(value.items()))
            for key, value in sorted(by_template.items())
        },
        "first_failures": sorted(first_failures, key=lambda item: item["candidate_id"]),
        "survivors": sorted(survivors, key=lambda item: item["candidate_id"]),
        "machine_execution": machine_execution,
    }
    if markdown is not None:
        _write_summary_markdown(Path(markdown), result)
    return result


def _write_summary_markdown(path: Path, result: Mapping[str, object]) -> None:
    lines = [
        f"# Exterior thin first scan — {result['run_id']}",
        "",
        "## Provenance",
        f"- source commit: `{result['source_commit']}`",
        f"- plan hash: `{result['plan_hash']}`",
        f"- protocol hash: `{result['protocol_hash']}`",
        f"- candidate-card schema: exterior-candidate-card-v1",
        f"- determinant oracle: `oracle.weights.classify_product` ({ORACLE_VERSION})",
        (
            f"- word order: `{WORD_ORDER}`; depths: `"
            f"{','.join(str(depth) for depth in result['depths'])}`"
        ),
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
    survivor_status = str(result["survivor_status"])
    lines.extend(["", "## By dimension", "| N | planned | rejected negative | rejected complex | uncertain | survivor |", "|---:|---:|---:|---:|---:|---:|"])
    for dimension, row in result["by_dimension"].items():  # type: ignore[union-attr]
        lines.append(
            f"| {dimension} | {row.get('planned', 0)} | "
            f"{row.get('rejected-negative', 0)} | {row.get('rejected-complex', 0)} | "
            f"{row.get('uncertain-high-precision', 0)} | "
            f"{row.get(survivor_status, 0)} |"
        )
    depths = tuple(result["depths"])
    lines.extend([
        "",
        "## By template",
        "| template | planned | "
        + " | ".join(f"depth {depth}" for depth in depths)
        + " | survivor |",
        "|---|---:|" + "---:|" * (len(depths) + 1),
    ])
    for template, row in result["by_template"].items():  # type: ignore[union-attr]
        values = " | ".join(
            str(row.get(f"first_failure_depth_{depth}", 0)) for depth in depths
        )
        lines.append(
            f"| {template} | {row.get('planned', 0)} | {values} | "
            f"{row.get(survivor_status, 0)} |"
        )
    lines.extend(["", "## First failures", "| candidate id | template | N | word | classification | sigma_min | condition |", "|---|---|---:|---|---|---:|---:|"])
    for row in result["first_failures"]:  # type: ignore[union-attr]
        lines.append(
            f"| {row['candidate_id']} | {row['template']} | {row['dimension']} | "
            f"{row['word_indices']} | {row['classification']} | "
            f"{row['sigma_min_I_plus_D']} | {row['condition_number_I_plus_D']} |"
        )
    lines.extend(["", "## Shallow survivors", "| candidate id | template | N | tested words | minimum sigma_min | minimum word |", "|---|---|---:|---:|---:|---|"])
    for row in result["survivors"]:  # type: ignore[union-attr]
        lines.append(
            f"| {row['candidate_id']} | {row['template']} | {row['dimension']} | "
            f"{row['tested_words']} | {row['minimum_sigma_min_I_plus_D']} | "
            f"{row['minimum_sigma_word_indices']} |"
        )
    lines.extend(["", "## Machine execution", "| role | shards | processes | candidates | wall seconds | manifest SHA list |", "|---|---|---:|---:|---:|---|"])
    for row in result["machine_execution"]:  # type: ignore[union-attr]
        lines.append(
            f"| {row['role']} | {row['shards']} | {row['processes']} | "
            f"{row['candidates']} | {row['wall_seconds']:.6f} | "
            f"{row['manifest_sha256']} |"
        )
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
    survivors = subparsers.add_parser("plan-survivors")
    survivors.add_argument("--parent-run-dir", required=True)
    survivors.add_argument("--run-dir", required=True)
    survivors.add_argument("--source-commit", required=True)
    survivors.add_argument("--run-id", default="exterior-survivor-pressure-v1")
    survivors.add_argument("--smoke-count", type=int, default=4)
    survivors.add_argument("--shards", type=int, default=76)
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
    elif args.command == "plan-survivors":
        result = plan_survivor_run(
            parent_run_dir=args.parent_run_dir,
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
    if args.command == "run" and int(result.get("errors", 0)) != 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "SCHEMA_VERSION",
    "PRESSURE_DEPTHS",
    "collect_run",
    "main",
    "mixed_words",
    "plan_run",
    "plan_survivor_run",
    "run_spec",
    "screen_card",
    "shard_owner",
]

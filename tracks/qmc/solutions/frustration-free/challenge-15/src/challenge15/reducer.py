"""Deterministic fail-closed reduction of production evaluation shards."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import math
import os
from pathlib import Path
import resource
import socket
from typing import Any, Mapping, Sequence

from .artifacts import publish_production_envelope
from .production_policy import production_policy
from .production_schema import (
    JSONValue,
    canonical_json,
    envelope_for,
    payload_sha256,
    validate_envelope,
)


EXPECTED_SEEDS = (0, 1, 2, 3, 4)


@dataclass(frozen=True, slots=True)
class Reduction:
    canonical_payload: Mapping[str, JSONValue]
    execution_receipt: Mapping[str, JSONValue]
    expected_ranks_sha256: str


@dataclass(frozen=True, slots=True)
class PublishedReduction:
    payload_path: Path
    receipt_path: Path
    payload_sha256: str
    receipt_sha256: str
    expected_ranks_sha256: str


def aggregate_coordinate_seed_uncertainty(
    shards_by_seed: Mapping[int, Mapping[str, Any]],
) -> dict[str, JSONValue]:
    """Recompute unbiased paired-seed covariance from exactly five shards."""

    if set(shards_by_seed) != set(EXPECTED_SEEDS):
        raise ValueError("coordinate aggregate requires exact five paired seeds")
    e0: list[float] = []
    e2: list[float] = []
    within_seed_inputs: list[dict[str, JSONValue]] = []
    for seed in EXPECTED_SEEDS:
        shard = shards_by_seed[seed]
        if int(shard.get("seed", -1)) != seed:
            raise ValueError("coordinate aggregate seed identity mismatch")
        paired = shard.get("paired_gap_diagnostics")
        if not isinstance(paired, Mapping) or paired.get("uncertainty_status") != "pending":
            raise ValueError("per-seed coordinate uncertainty must remain pending")
        diagnostics = shard.get("sector_diagnostics")
        if not isinstance(diagnostics, Mapping) or set(diagnostics) != {"L0", "L2"}:
            raise ValueError("coordinate aggregate sector diagnostics are invalid")
        lower = float(diagnostics["L0"]["estimate"])
        upper = float(diagnostics["L2"]["estimate"])
        standard_error0 = float(diagnostics["L0"]["standard_error"])
        standard_error2 = float(diagnostics["L2"]["standard_error"])
        variance0 = standard_error0**2
        variance2 = standard_error2**2
        covariance = 0.0
        variance_gap = variance0 + variance2
        if not all(
            math.isfinite(value)
            for value in (
                lower,
                upper,
                standard_error0,
                standard_error2,
                variance0,
                variance2,
                variance_gap,
            )
        ) or standard_error0 < 0 or standard_error2 < 0:
            raise ValueError("coordinate uncertainty input is nonfinite")
        e0.append(lower)
        e2.append(upper)
        within_seed_inputs.append(
            {
                "seed": seed,
                "e0": lower,
                "e2": upper,
                "variance_mc_e0": variance0,
                "variance_mc_e2": variance2,
                "monte_carlo_covariance_e0_e2": covariance,
                "variance_mc_gap": variance_gap,
            }
        )
    count = len(EXPECTED_SEEDS)
    mean0 = sum(e0) / count
    mean2 = sum(e2) / count
    s00 = sum((value - mean0) ** 2 for value in e0) / (count - 1)
    s22 = sum((value - mean2) ** 2 for value in e2) / (count - 1)
    s02 = sum(
        (lower - mean0) * (upper - mean2)
        for lower, upper in zip(e0, e2, strict=True)
    ) / (count - 1)
    gap_mean_variance = max(0.0, (s00 + s22 - 2.0 * s02) / count)
    return {
        "paired_seed_ids": list(EXPECTED_SEEDS),
        "e0_seed_estimates": e0,
        "e2_seed_estimates": e2,
        "within_seed_inputs": within_seed_inputs,
        "optimizer_variance_e0": s00,
        "optimizer_variance_e2": s22,
        "optimizer_covariance_e0_e2": s02,
        "paired_seed_count": count,
        "variance_seed_mean_gap": gap_mean_variance,
        "uncertainty_status": "accepted",
    }


def expected_ranks_sha256(expected_ranks: Sequence[int]) -> str:
    """Hash the canonical ordered expected-rank list."""

    ranks = _validate_expected_ranks(
        expected_ranks, allow_nonroot_singleton=True
    )
    return hashlib.sha256(canonical_json(list(ranks))).hexdigest()


def build_identity_map(
    *,
    stage: str,
    expected_ranks: Sequence[int],
    input_sha256_by_identity: Mapping[tuple[int, int], str],
    input_path_by_identity: Mapping[tuple[int, int], str] | None = None,
    array_concurrency: int,
    policy_sha256: str,
    source_manifest_sha256: str,
    runtime_attestations: Mapping[str, Mapping[str, str]],
    base_configuration_sha256: str,
    particles: int,
) -> dict[str, JSONValue]:
    """Build an ordered identity map and derive its task count."""

    ranks = _validate_expected_ranks(expected_ranks, allow_nonroot_singleton=True)
    if not isinstance(stage, str) or not stage:
        raise ValueError("identity-map stage must be nonempty")
    if stage in {"training", "coordinate", "exact"} and len(ranks) != 1:
        raise ValueError(
            "scientific Slurm maps require exactly five new-rank identities"
        )
    if (
        not isinstance(array_concurrency, int)
        or isinstance(array_concurrency, bool)
        or array_concurrency < 1
    ):
        raise ValueError("array concurrency must be positive")
    expected = {(rank, seed) for rank in ranks for seed in EXPECTED_SEEDS}
    if set(input_sha256_by_identity) != expected:
        raise ValueError("identity-map inputs do not match the rank/seed cross-product")
    if input_path_by_identity is None or set(input_path_by_identity) != expected:
        raise ValueError("identity-map canonical input paths do not match identities")
    tasks: list[dict[str, JSONValue]] = []
    for index, (rank, seed) in enumerate(sorted(expected)):
        digest = input_sha256_by_identity[(rank, seed)]
        _require_sha(digest, "identity-map input")
        input_path = Path(input_path_by_identity[(rank, seed)])
        if not input_path.is_absolute():
            raise ValueError("identity-map input path must be absolute")
        tasks.append(
            {
                "array_index": index,
                "rank": rank,
                "seed": seed,
                "input_sha256": digest,
                "input_path_identity": str(input_path),
                "output_relative_path": f"rank={rank}/seed={seed}.json",
            }
        )
    payload: dict[str, JSONValue] = {
        "policy_sha256": policy_sha256,
        "source_manifest_sha256": source_manifest_sha256,
        "runtime_attestations": {
            role: dict(controllers)
            for role, controllers in runtime_attestations.items()
        },
        "base_configuration_sha256": base_configuration_sha256,
        "particles": particles,
        "stage": stage,
        "expected_ranks": list(ranks),
        "expected_ranks_sha256": expected_ranks_sha256(ranks),
        "expected_seeds": list(EXPECTED_SEEDS),
        "task_count": len(tasks),
        "tasks": tasks,
        "array_concurrency": min(array_concurrency, len(tasks)),
    }
    envelope_for("challenge15.identity-map.v1", payload)
    return payload


def slurm_array_spec(identity_map: Mapping[str, Any]) -> str:
    """Derive the Slurm array range from a validated identity-map payload."""

    envelope_for("challenge15.identity-map.v1", identity_map)
    count = int(identity_map["task_count"])
    concurrency = int(identity_map["array_concurrency"])
    if count < 1 or concurrency < 1:
        raise ValueError("identity map cannot define an empty Slurm array")
    return f"0-{count - 1}%{concurrency}"


def reduce_size(
    expected_ranks: tuple[int, ...],
    identity_map: Path,
    oracle: Path,
    generation_roots: Sequence[Path],
    exact_shards: Sequence[Path],
    coordinate_shards: Sequence[Path],
    prerequisite_terminal_selection: Path | None,
) -> Reduction:
    """Classify one size from explicit immutable inputs."""

    started = _now()
    ranks = _validate_expected_ranks(expected_ranks)
    rank_digest = expected_ranks_sha256(ranks)
    identity = validate_envelope(Path(identity_map), "challenge15.identity-map.v1")
    oracle_payload = validate_envelope(
        Path(oracle), "challenge15.production-oracle.v1"
    )
    common = _common(oracle_payload)
    _require_common(identity, common, "identity map")
    if (
        identity["stage"] != "reduction"
        or identity["expected_ranks"] != list(ranks)
        or identity["expected_ranks_sha256"] != rank_digest
        or identity["expected_seeds"] != list(EXPECTED_SEEDS)
    ):
        raise ValueError("identity map does not match the requested reduction")
    if oracle_payload["sphere_spec"]["particles"] != common["particles"]:
        raise ValueError("oracle particle identity is inconsistent")

    generations = _load_generations(generation_roots, ranks, common)
    _validate_identity_map(identity, generations, ranks)
    oracle_digest = payload_sha256(oracle_payload)
    exact = _load_shards(
        exact_shards,
        "challenge15.exact-evaluation-shard.v1",
        ranks,
        generations,
        common,
        oracle_digest=oracle_digest,
    )
    coordinate = _load_shards(
        coordinate_shards,
        "challenge15.coordinate-evaluation-shard.v1",
        ranks,
        generations,
        common,
    )
    prerequisite = _validate_prerequisite(
        prerequisite_terminal_selection, common
    )

    expected = {(rank, seed) for rank in ranks for seed in EXPECTED_SEEDS}
    missing = [
        {"kind": kind, "rank": rank, "seed": seed}
        for kind, found in (("exact", exact), ("coordinate", coordinate))
        for rank, seed in sorted(expected - set(found))
    ]
    failed: list[dict[str, JSONValue]] = []
    final_seed_results: dict[int, bool] = {}
    transitions: list[dict[str, JSONValue]] = []
    aggregate_uncertainty_by_rank: dict[int, Mapping[str, JSONValue]] = {}
    for rank in ranks:
        rank_shards = {
            seed: coordinate[(rank, seed)]
            for seed in EXPECTED_SEEDS
            if (rank, seed) in coordinate
        }
        if len(rank_shards) == len(EXPECTED_SEEDS):
            try:
                aggregate_uncertainty_by_rank[rank] = (
                    aggregate_coordinate_seed_uncertainty(rank_shards)
                )
            except ValueError as exc:
                failed.append(
                    {
                        "kind": "coordinate-aggregate",
                        "rank": rank,
                        "seed": 0,
                        "reason": str(exc),
                    }
                )
    for identity_key in sorted(expected & set(exact) & set(coordinate)):
        rank, seed = identity_key
        training_passed = _training_equivalence_gate(
            generations[identity_key], failed, rank, seed
        )
        exact_passed = _exact_gate(
            exact[identity_key], oracle_payload, failed, rank, seed
        )
        coordinate_passed = _coordinate_gate(
            coordinate[identity_key], failed, rank, seed
        )
        if rank == ranks[-1]:
            final_seed_results[seed] = (
                training_passed and exact_passed and coordinate_passed
            )

    for previous_rank, current_rank in zip(ranks, ranks[1:], strict=False):
        transition_passed = True
        per_seed: list[dict[str, JSONValue]] = []
        for seed in EXPECTED_SEEDS:
            previous_key = (previous_rank, seed)
            current_key = (current_rank, seed)
            if not {
                previous_key,
                current_key,
            } <= set(exact) or not {
                previous_key,
                current_key,
            } <= set(coordinate):
                transition_passed = False
                continue
            passed, detail = _transition_gate(
                exact[previous_key],
                exact[current_key],
                coordinate[previous_key],
                coordinate[current_key],
            )
            transition_passed &= passed
            per_seed.append({"seed": seed, **detail})
            if not passed:
                failed.append(
                    {
                        "kind": "rank-transition",
                        "rank": current_rank,
                        "seed": seed,
                        "reason": str(detail["reason"]),
                    }
                )
        paired_passed, paired_detail = _paired_transition_gate(
            previous_rank,
            current_rank,
            coordinate,
        )
        transition_passed &= paired_passed
        if not paired_passed:
            failed.append(
                {
                    "kind": "rank-transition",
                    "rank": current_rank,
                    "seed": 0,
                    "reason": str(paired_detail["reason"]),
                }
            )
        transitions.append(
            {
                "previous_rank": previous_rank,
                "new_rank": current_rank,
                "paired_seeds": list(EXPECTED_SEEDS),
                "per_seed": per_seed,
                **paired_detail,
                "passed": transition_passed,
            }
        )
    policy = production_policy()
    required_final = int(policy["seed_policy"]["minimum_accepted_final_rank_seeds"])
    required_transitions = int(policy["rank_policy"]["required_rank_doublings"])
    passing_seeds = sorted(
        seed for seed, passed in final_seed_results.items() if passed
    )
    oracle_passed = all(oracle_payload["gate_metrics"].values())
    if not oracle_passed:
        failed.append(
            {
                "kind": "oracle",
                "rank": ranks[-1],
                "seed": 0,
                "reason": "oracle-gate-failed",
            }
        )
    seed_gate_passed = len(passing_seeds) >= required_final
    rank_gate_passed = (
        len(transitions) >= required_transitions
        and all(
            bool(transition["passed"])
            for transition in transitions[-required_transitions:]
        )
    )
    if not seed_gate_passed:
        failed.append(
            {
                "kind": "aggregate",
                "rank": ranks[-1],
                "seed": 0,
                "reason": "insufficient-final-seeds",
            }
        )
    if not rank_gate_passed:
        failed.append(
            {
                "kind": "aggregate",
                "rank": ranks[-1],
                "seed": 0,
                "reason": "insufficient-passing-doublings",
            }
        )
    accepted = (
        not missing
        and not failed
        and oracle_passed
        and prerequisite["accepted"] == (common["particles"] != 6)
        and seed_gate_passed
        and rank_gate_passed
    )
    primitive = _aggregate_metrics(
        [
            exact[(ranks[-1], seed)]["primitive_metrics"]
            for seed in EXPECTED_SEEDS
            if (ranks[-1], seed) in exact
        ],
        oracle_payload,
    )
    canonical: dict[str, JSONValue] = {
        **common,
        "expected_ranks": list(ranks),
        "expected_seeds": list(EXPECTED_SEEDS),
        "oracle_sha256": oracle_digest,
        "generation_sha256_by_identity": _identity_hash_map(generations),
        "exact_sha256_by_identity": _identity_hash_map(exact),
        "coordinate_sha256_by_identity": _identity_hash_map(coordinate),
        "coordinate_uncertainty_by_rank": [
            {"rank": rank, **dict(aggregate_uncertainty_by_rank[rank])}
            for rank in ranks
            if rank in aggregate_uncertainty_by_rank
        ],
        "prerequisite": prerequisite,
        "primitive_metrics": primitive,
        "rank_transitions": transitions,
        "seed_gate": {
            "passing_seeds": passing_seeds,
            "required_count": required_final,
            "passed": seed_gate_passed,
        },
        "missing_identities": missing,
        "failed_gates": sorted(
            failed,
            key=lambda item: (
                str(item["kind"]),
                int(item["rank"]),
                int(item["seed"]),
                str(item["reason"]),
            ),
        ),
        "production_accepted": accepted,
        "claim": {
            "statement": (
                policy["claim_policy"]["accepted_claim"]
                if accepted
                else policy["claim_policy"]["pending_claim"]
            ),
            "basis": (
                "all immutable production gates passed"
                if accepted
                else "one or more immutable production gates remain pending"
            ),
        },
    }
    envelope_for("challenge15.size-result.v1", canonical)
    finished = _now()
    receipt: dict[str, JSONValue] = {
        **common,
        "canonical_payload_sha256": payload_sha256(canonical),
        "started_at_utc": started,
        "finished_at_utc": finished,
        "hostname": socket.gethostname(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "devices": [os.environ.get("JAX_PLATFORMS", "cpu")],
        "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "stage_elapsed_seconds": max(
            0.0,
            (
                datetime.fromisoformat(finished.replace("Z", "+00:00"))
                - datetime.fromisoformat(started.replace("Z", "+00:00"))
            ).total_seconds(),
        ),
        "cache_counters": {
            "hits": 0,
            "misses": (
                2
                + len(generations)
                + len(exact)
                + len(coordinate)
                + (1 if prerequisite_terminal_selection is not None else 0)
            ),
        },
    }
    envelope_for("challenge15.reduction-receipt.v1", receipt)
    return Reduction(canonical, receipt, rank_digest)


def publish_reduction(
    result: Reduction,
    output_dir: Path,
    receipt_dir: Path,
) -> PublishedReduction:
    """Publish canonical result and execution receipt into separate namespaces."""

    canonical = dict(result.canonical_payload)
    receipt = dict(result.execution_receipt)
    payload_digest = payload_sha256(canonical)
    receipt_digest = payload_sha256(receipt)
    if receipt.get("canonical_payload_sha256") != payload_digest:
        raise ValueError("reduction receipt does not bind its canonical payload")
    if result.expected_ranks_sha256 != expected_ranks_sha256(
        tuple(canonical["expected_ranks"])
    ):
        raise ValueError("reduction expected-rank identity mismatch")
    validate_size_result_semantics(canonical)
    envelope_for("challenge15.size-result.v1", canonical)
    envelope_for("challenge15.reduction-receipt.v1", receipt)

    payload_parent = Path(output_dir) / result.expected_ranks_sha256
    receipt_parent = Path(receipt_dir)
    payload_parent.mkdir(parents=True, exist_ok=True)
    receipt_parent.mkdir(parents=True, exist_ok=True)
    payload_path = payload_parent / f"{payload_digest}.json"
    receipt_path = receipt_parent / f"{receipt_digest}.json"
    publish_production_envelope(
        payload_path,
        "challenge15.size-result.v1",
        canonical,
    )
    publish_production_envelope(
        receipt_path,
        "challenge15.reduction-receipt.v1",
        receipt,
        context={
            "approved_roots": (Path(output_dir), Path(receipt_dir)),
            "canonical_payload_path": payload_path,
            "hostname": receipt["hostname"],
            "slurm_job_id": receipt["slurm_job_id"],
            "devices": receipt["devices"],
            "cache_counters": receipt["cache_counters"],
        },
    )
    return PublishedReduction(
        payload_path=payload_path,
        receipt_path=receipt_path,
        payload_sha256=payload_digest,
        receipt_sha256=receipt_digest,
        expected_ranks_sha256=result.expected_ranks_sha256,
    )


def validate_size_result_semantics(payload: Mapping[str, Any]) -> None:
    """Recompute the semantic acceptance state of a size-result payload."""

    ranks = _validate_expected_ranks(tuple(payload["expected_ranks"]))
    if payload["expected_seeds"] != list(EXPECTED_SEEDS):
        raise ValueError("size-result semantic seed set mismatch")
    expected_keys = {
        f"rank={rank},seed={seed}"
        for rank in ranks
        for seed in EXPECTED_SEEDS
    }
    generation_keys = set(payload["generation_sha256_by_identity"])
    exact_keys = set(payload["exact_sha256_by_identity"])
    coordinate_keys = set(payload["coordinate_sha256_by_identity"])
    for label, identities in (
        ("generation", payload["generation_sha256_by_identity"]),
        ("exact", payload["exact_sha256_by_identity"]),
        ("coordinate", payload["coordinate_sha256_by_identity"]),
    ):
        for digest in identities.values():
            _require_sha(digest, f"size-result semantic {label}")
    if generation_keys != expected_keys:
        raise ValueError("size-result semantic generation coverage mismatch")
    if not exact_keys <= expected_keys or not coordinate_keys <= expected_keys:
        raise ValueError("size-result semantic evaluation identity mismatch")
    expected_missing = [
        {"kind": kind, "rank": rank, "seed": seed}
        for kind, keys in (("exact", exact_keys), ("coordinate", coordinate_keys))
        for rank in ranks
        for seed in EXPECTED_SEEDS
        if f"rank={rank},seed={seed}" not in keys
    ]
    if payload["missing_identities"] != expected_missing:
        raise ValueError("size-result semantic missing identity mismatch")
    uncertainty = payload["coordinate_uncertainty_by_rank"]
    expected_uncertainty_ranks = [
        rank
        for rank in ranks
        if all(f"rank={rank},seed={seed}" in coordinate_keys for seed in EXPECTED_SEEDS)
    ]
    if [item["rank"] for item in uncertainty] != expected_uncertainty_ranks:
        raise ValueError("size-result coordinate uncertainty coverage mismatch")
    for item in uncertainty:
        if (
            item["paired_seed_ids"] != list(EXPECTED_SEEDS)
            or item["paired_seed_count"] != len(EXPECTED_SEEDS)
            or item["uncertainty_status"] != "accepted"
        ):
            raise ValueError("size-result coordinate uncertainty is not aggregate-only")
        inputs = item["within_seed_inputs"]
        if [entry["seed"] for entry in inputs] != list(EXPECTED_SEEDS):
            raise ValueError("size-result coordinate uncertainty seed order mismatch")
        e0 = [float(entry["e0"]) for entry in inputs]
        e2 = [float(entry["e2"]) for entry in inputs]
        if item["e0_seed_estimates"] != e0 or item["e2_seed_estimates"] != e2:
            raise ValueError("size-result coordinate uncertainty estimates mismatch")
        for entry in inputs:
            if entry["monte_carlo_covariance_e0_e2"] != 0 or not math.isclose(
                entry["variance_mc_gap"],
                entry["variance_mc_e0"] + entry["variance_mc_e2"],
                rel_tol=0.0,
                abs_tol=1e-15,
            ):
                raise ValueError("size-result coordinate MC covariance mismatch")
        count = len(EXPECTED_SEEDS)
        mean0 = sum(e0) / count
        mean2 = sum(e2) / count
        s00 = sum((value - mean0) ** 2 for value in e0) / (count - 1)
        s22 = sum((value - mean2) ** 2 for value in e2) / (count - 1)
        s02 = sum(
            (lower - mean0) * (upper - mean2)
            for lower, upper in zip(e0, e2, strict=True)
        ) / (count - 1)
        expected_gap_variance = max(0.0, (s00 + s22 - 2.0 * s02) / count)
        for actual, expected in (
            (item["optimizer_variance_e0"], s00),
            (item["optimizer_variance_e2"], s22),
            (item["optimizer_covariance_e0_e2"], s02),
            (item["variance_seed_mean_gap"], expected_gap_variance),
        ):
            if not math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-15):
                raise ValueError("size-result unbiased coordinate covariance mismatch")

    transitions = payload["rank_transitions"]
    rank_pairs = list(zip(ranks, ranks[1:], strict=False))
    if len(transitions) != len(rank_pairs) or any(
        transition.get("previous_rank") != previous
        or transition.get("new_rank") != current
        for transition, (previous, current) in zip(
            transitions, rank_pairs, strict=True
        )
    ):
        raise ValueError("size-result semantic rank transition mismatch")
    policy = production_policy()
    required_transitions = int(policy["rank_policy"]["required_rank_doublings"])
    final_transitions_passed = (
        len(transitions) >= required_transitions
        and all(
            transition.get("passed") is True
            for transition in transitions[-required_transitions:]
        )
    )
    seed_gate = payload["seed_gate"]
    passing_seeds = seed_gate["passing_seeds"]
    required_seeds = int(
        policy["seed_policy"]["minimum_accepted_final_rank_seeds"]
    )
    if (
        passing_seeds != sorted(set(passing_seeds))
        or not set(passing_seeds) <= set(EXPECTED_SEEDS)
        or seed_gate["required_count"] != required_seeds
        or seed_gate["passed"] != (len(passing_seeds) >= required_seeds)
    ):
        raise ValueError("size-result semantic seed gate mismatch")
    prerequisite = payload["prerequisite"]
    prerequisite_passed = (
        prerequisite
        == {
            "particles": None,
            "terminal_selection_sha256": None,
            "accepted": False,
        }
        if payload["particles"] == 6
        else prerequisite["particles"] == payload["particles"] - 1
        and prerequisite["terminal_selection_sha256"] is not None
        and prerequisite["accepted"] is True
    )
    per_state_passed = all(
        value is True
        for inputs in payload["primitive_metrics"][
            "per_state_gate_inputs_by_sector"
        ].values()
        for value in inputs.values()
    )
    accepted = (
        not expected_missing
        and not payload["failed_gates"]
        and seed_gate["passed"] is True
        and final_transitions_passed
        and prerequisite_passed
        and per_state_passed
    )
    if payload["production_accepted"] is not accepted:
        raise ValueError("size-result semantic acceptance mismatch")
    expected_statement = (
        policy["claim_policy"]["accepted_claim"]
        if accepted
        else policy["claim_policy"]["pending_claim"]
    )
    if payload["claim"]["statement"] != expected_statement:
        raise ValueError("size-result semantic claim mismatch")


def _validate_expected_ranks(
    expected_ranks: Sequence[int],
    *,
    allow_nonroot_singleton: bool = False,
) -> tuple[int, ...]:
    ranks = tuple(expected_ranks)
    if not ranks or any(
        not isinstance(rank, int) or isinstance(rank, bool) or rank < 1
        for rank in ranks
    ):
        raise ValueError("expected ranks must be positive integers")
    if len(set(ranks)) != len(ranks):
        raise ValueError("expected ranks contain duplicates")
    if allow_nonroot_singleton and len(ranks) == 1:
        return ranks
    if ranks[0] != 1 or any(
        current != 2 * previous
        for previous, current in zip(ranks, ranks[1:], strict=False)
    ):
        raise ValueError("expected ranks must be ordered consecutive doublings from 1")
    return ranks


def _common(payload: Mapping[str, Any]) -> dict[str, JSONValue]:
    return {
        field: payload[field]
        for field in (
            "policy_sha256",
            "source_manifest_sha256",
            "runtime_attestations",
            "base_configuration_sha256",
            "particles",
        )
    }


def _require_common(
    payload: Mapping[str, Any],
    common: Mapping[str, JSONValue],
    label: str,
) -> None:
    for field, expected in common.items():
        if payload.get(field) != expected:
            raise ValueError(f"{label} has stale {field}")


def _load_generations(
    roots: Sequence[Path],
    ranks: tuple[int, ...],
    common: Mapping[str, JSONValue],
) -> dict[tuple[int, int], Mapping[str, Any]]:
    if len({Path(root).absolute() for root in roots}) != len(roots):
        raise ValueError("generation roots contain duplicates")
    found: dict[tuple[int, int], Mapping[str, Any]] = {}
    roots_by_seed: dict[int, Path] = {}
    for root in roots:
        directory = Path(root) / "generations"
        if not directory.is_dir():
            raise ValueError("generation root has no generations namespace")
        local: list[tuple[str, Mapping[str, Any]]] = []
        for child in sorted(directory.iterdir()):
            if not child.is_dir() or len(tuple(child.iterdir())) != 1:
                raise ValueError("generation namespace contains a malformed object")
            manifest = child / "manifest.json"
            payload = validate_envelope(
                manifest, "challenge15.training-generation.v1"
            )
            digest = payload_sha256(payload)
            if child.name != digest:
                raise ValueError("generation content-addressed identity mismatch")
            _require_common(payload, common, "generation")
            rank, seed = int(payload["rank"]), int(payload["seed"])
            if rank not in ranks or seed not in EXPECTED_SEEDS:
                raise ValueError("generation has an unexpected identity")
            if (rank, seed) in found:
                raise ValueError("generation identity is duplicated or forked")
            found[(rank, seed)] = payload
            local.append((digest, payload))
        seeds = {int(payload["seed"]) for _, payload in local}
        if len(seeds) != 1:
            raise ValueError("one generation root must contain exactly one seed")
        seed = seeds.pop()
        if seed in roots_by_seed:
            raise ValueError("generation roots duplicate a seed")
        roots_by_seed[seed] = Path(root)
        previous_digest: str | None = None
        previous_payload: Mapping[str, Any] | None = None
        by_rank = {int(payload["rank"]): (digest, payload) for digest, payload in local}
        _validate_declared_extensions(Path(root), seed, ranks, by_rank, common)
        for rank in ranks:
            if rank not in by_rank:
                raise ValueError("generation chain omits an expected rank")
            digest, payload = by_rank[rank]
            if payload["parent_generation_sha256"] != previous_digest:
                raise ValueError("generation chain has a wrong parent")
            if previous_payload is not None and (
                payload["parent_parameter_sha256"]
                != previous_payload["parameter_sha256"]
                or payload["parent_optimizer_state_sha256"]
                != previous_payload["optimizer_state_sha256"]
            ):
                raise ValueError("generation parent state is inconsistent")
            previous_digest, previous_payload = digest, payload
    if set(roots_by_seed) != set(EXPECTED_SEEDS):
        raise ValueError("generation roots do not cover exactly five seeds")
    return found


def _validate_declared_extensions(
    root: Path,
    seed: int,
    ranks: tuple[int, ...],
    generations: Mapping[int, tuple[str, Mapping[str, Any]]],
    common: Mapping[str, JSONValue],
) -> None:
    """Validate the complete declared extension namespace."""

    directory = root / "extensions"
    if not directory.is_dir():
        raise ValueError("generation extension namespace is malformed")
    by_rank: dict[int, tuple[str, Mapping[str, Any]]] = {}
    for path in sorted(directory.iterdir()):
        if not path.is_file() or path.suffix != ".json":
            raise ValueError("generation extension namespace contains malformed input")
        payload = validate_envelope(path, "challenge15.rank-extension.v1")
        digest = payload_sha256(payload)
        if path.name != f"{digest}.json":
            raise ValueError("rank extension filename is not content-addressed")
        _require_common(payload, common, "rank extension")
        if payload["seed"] != seed or payload["new_rank"] not in ranks:
            raise ValueError("rank extension has an unexpected identity")
        rank = int(payload["new_rank"])
        if rank in by_rank:
            raise ValueError("rank extension identity is duplicated")
        by_rank[rank] = (digest, payload)
    if set(by_rank) != set(ranks):
        raise ValueError("rank extensions do not cover every expected rank")
    previous_generation: tuple[str, Mapping[str, Any]] | None = None
    for rank in ranks:
        digest, extension = by_rank[rank]
        generation_digest, generation = generations[rank]
        if generation["extension_sha256"] != digest:
            raise ValueError("generation does not bind its declared extension")
        expected_previous = None if previous_generation is None else rank // 2
        if extension["previous_rank"] != expected_previous:
            raise ValueError("rank extension chain has a gap")
        if previous_generation is None:
            expected_parent = (None, None, None)
        else:
            expected_parent = (
                previous_generation[0],
                previous_generation[1]["parameter_sha256"],
                previous_generation[1]["optimizer_state_sha256"],
            )
        actual_parent = (
            extension["parent_generation_sha256"],
            extension["parent_parameter_sha256"],
            extension["parent_optimizer_state_sha256"],
        )
        if actual_parent != expected_parent:
            raise ValueError("rank extension parent lineage is inconsistent")
        previous_generation = (generation_digest, generation)


def _validate_identity_map(
    identity: Mapping[str, Any],
    generations: Mapping[tuple[int, int], Mapping[str, Any]],
    ranks: tuple[int, ...],
) -> None:
    expected = {(rank, seed) for rank in ranks for seed in EXPECTED_SEEDS}
    tasks = identity["tasks"]
    if identity["task_count"] != len(expected) or len(tasks) != len(expected):
        raise ValueError("identity map has the wrong task count")
    actual: dict[tuple[int, int], str] = {}
    for index, task in enumerate(tasks):
        if task["array_index"] != index:
            raise ValueError("identity map array indices are not canonical")
        key = (int(task["rank"]), int(task["seed"]))
        if key in actual:
            raise ValueError("identity map contains a duplicate identity")
        actual[key] = str(task["input_sha256"])
    if set(actual) != expected:
        raise ValueError("identity map does not cover the exact cross-product")
    for key, digest in actual.items():
        if digest != payload_sha256(generations[key]):
            raise ValueError("identity map generation hash is stale")


def _load_shards(
    paths: Sequence[Path],
    schema: str,
    ranks: tuple[int, ...],
    generations: Mapping[tuple[int, int], Mapping[str, Any]],
    common: Mapping[str, JSONValue],
    *,
    oracle_digest: str | None = None,
) -> dict[tuple[int, int], Mapping[str, Any]]:
    if len({Path(path).absolute() for path in paths}) != len(paths):
        raise ValueError("shard paths contain duplicates")
    found: dict[tuple[int, int], Mapping[str, Any]] = {}
    for path in paths:
        payload = validate_envelope(Path(path), schema)
        _require_common(payload, common, "evaluation shard")
        key = (int(payload["rank"]), int(payload["seed"]))
        if key[0] not in ranks or key[1] not in EXPECTED_SEEDS:
            raise ValueError("evaluation shard has an unexpected identity")
        if key in found:
            raise ValueError("evaluation identity is duplicated")
        generation = generations.get(key)
        if generation is None:
            raise ValueError("evaluation shard has no declared generation")
        if (
            payload["generation_sha256"] != payload_sha256(generation)
            or payload["parameter_sha256"] != generation["parameter_sha256"]
        ):
            raise ValueError("evaluation shard has stale generation lineage")
        if oracle_digest is not None and payload["oracle_sha256"] != oracle_digest:
            raise ValueError("exact shard has a stale oracle")
        found[key] = payload
    return found


def _validate_prerequisite(
    path: Path | None,
    common: Mapping[str, JSONValue],
) -> dict[str, JSONValue]:
    particles = int(common["particles"])
    if particles == 6:
        if path is not None:
            raise ValueError("N=6 cannot consume a prerequisite")
        return {
            "particles": None,
            "terminal_selection_sha256": None,
            "accepted": False,
        }
    if path is None:
        raise ValueError("non-root size requires an accepted terminal selection")
    payload = validate_envelope(Path(path), "challenge15.terminal-selection.v1")
    if payload["particles"] != particles - 1 or not payload["production_accepted"]:
        raise ValueError("prerequisite terminal selection is not accepted predecessor")
    for field in (
        "policy_sha256",
        "source_manifest_sha256",
    ):
        if payload[field] != common[field]:
            raise ValueError(f"prerequisite has stale {field}")
    terminal_path = Path(path).absolute()
    terminal_digest = payload_sha256(payload)
    if (
        terminal_path.name != f"{terminal_digest}.json"
        or terminal_path.parent.name
        != f"base={payload['base_configuration_sha256']}"
        or terminal_path.parent.parent.name != f"N={payload['particles']}"
        or terminal_path.parent.parent.parent.name != "terminal-selections"
    ):
        raise ValueError("prerequisite terminal selection is not content-addressed")
    _validate_prerequisite_chain(terminal_path, payload)
    return {
        "particles": particles - 1,
        "terminal_selection_sha256": payload_sha256(payload),
        "accepted": True,
    }


def _validate_prerequisite_chain(
    terminal_path: Path,
    terminal: Mapping[str, Any],
) -> None:
    trusted_root = terminal_path.parent.parent.parent.parent
    finalization_path = (
        trusted_root
        / "finalizations"
        / f"N={terminal['particles']}"
        / f"base={terminal['base_configuration_sha256']}"
        / f"expected={terminal['selected_expected_ranks_sha256']}"
        / f"{terminal['selected_finalization_sha256']}.json"
    )
    finalization = validate_envelope(
        finalization_path, "challenge15.reduction-finalization.v1"
    )
    finalization_digest = payload_sha256(finalization)
    if (
        finalization_digest != terminal["selected_finalization_sha256"]
        or finalization_path.name != f"{finalization_digest}.json"
        or finalization["production_accepted"] is not True
    ):
        raise ValueError("prerequisite finalization identity mismatch")
    for field in (
        "policy_sha256",
        "source_manifest_sha256",
        "runtime_attestations",
        "base_configuration_sha256",
        "particles",
    ):
        if finalization[field] != terminal[field]:
            raise ValueError(f"prerequisite finalization has stale {field}")
    if (
        finalization["expected_ranks_sha256"]
        != terminal["selected_expected_ranks_sha256"]
        or finalization["selected_reduction_sha256"]
        != terminal["selected_reduction_sha256"]
        or expected_ranks_sha256(tuple(finalization["expected_ranks"]))
        != finalization["expected_ranks_sha256"]
    ):
        raise ValueError("prerequisite finalization lineage mismatch")

    reduction_path = Path(str(finalization["selected_reduction_path"]))
    reductions_root = trusted_root / "reductions"
    if (
        not reduction_path.is_absolute()
        or reduction_path.parent.parent != reductions_root
        or reduction_path.parent.name != finalization["expected_ranks_sha256"]
        or reduction_path.name
        != f"{finalization['selected_reduction_sha256']}.json"
    ):
        raise ValueError("prerequisite reduction path is outside the trusted root")
    reduction = validate_envelope(
        reduction_path, "challenge15.size-result.v1"
    )
    validate_size_result_semantics(reduction)
    reduction_digest = payload_sha256(reduction)
    if (
        reduction_digest != terminal["selected_reduction_sha256"]
        or reduction["production_accepted"] is not True
        or reduction["expected_ranks"] != finalization["expected_ranks"]
        or expected_ranks_sha256(tuple(reduction["expected_ranks"]))
        != terminal["selected_expected_ranks_sha256"]
    ):
        raise ValueError("prerequisite reduction lineage mismatch")
    for field in (
        "policy_sha256",
        "source_manifest_sha256",
        "runtime_attestations",
        "base_configuration_sha256",
        "particles",
    ):
        if reduction[field] != finalization[field]:
            raise ValueError(f"prerequisite reduction has stale {field}")


def _exact_gate(
    shard: Mapping[str, Any],
    oracle: Mapping[str, Any],
    failed: list[dict[str, JSONValue]],
    rank: int,
    seed: int,
) -> bool:
    metrics = shard["primitive_metrics"]
    policy = production_policy()["exact_acceptance"]["nqs"]
    gap_reference = (
        oracle["sector_summaries"]["L2"]["lowest_energy_ec"]
        - oracle["sector_summaries"]["L0"]["lowest_energy_ec"]
    )
    checks: list[tuple[str, float, float, str]] = []
    energy_threshold = min(
        float(policy["exact_sum_energy_error_max_ec"]),
        float(policy["exact_sum_energy_error_max_gap_fraction"])
        * abs(gap_reference),
    )
    for sector in ("L0", "L2"):
        statistic = metrics["energy_by_sector"][sector]
        reference = oracle["sector_summaries"][sector]["lowest_energy_ec"]
        checks.append(
            (
                f"energy-{sector}",
                abs(statistic["estimate"] - reference)
                + 2 * statistic["standard_error"],
                energy_threshold,
                "maximum",
            )
        )
        overlap = metrics["overlap_by_sector"][sector]["estimate"]
        checks.append(
            (
                f"overlap-{sector}",
                overlap,
                float(policy["exact_overlap_min"]),
                "minimum",
            )
        )
        checks.append(
            (
                f"symmetry-{sector}",
                metrics["symmetry_residual_by_sector"][sector],
                float(
                    production_policy()["exact_acceptance"]["hamiltonian"][
                        "eigenpair_residual_max"
                    ]
                ),
                "maximum",
            )
        )
        for component, value in metrics["quadrature_change_by_sector"][
            sector
        ].items():
            checks.append(
                (
                    f"quadrature-{sector}-{component}",
                    value,
                    float(
                        policy[
                            "quadrature_normalized_amplitude_energy_symmetry_change_max"
                        ]
                    ),
                    "maximum",
                )
            )
    gap = metrics["gap"]
    checks.append(
        (
            "gap",
            abs(gap["estimate"] - gap_reference) + 2 * gap["standard_error"],
            float(policy["gap_ed_relative_error_max"]) * abs(gap_reference),
            "maximum",
        )
    )
    passed = True
    for name, value, threshold, direction in checks:
        state = _threshold_state(value, threshold, direction)
        if state != "pass":
            passed = False
            failed.append(
                {
                    "kind": "exact",
                    "rank": rank,
                    "seed": seed,
                    "reason": (
                        "ambiguous-threshold" if state == "ambiguous" else name
                    ),
                }
            )
    if policy["per_state_gates_required"]:
        for sector, inputs in metrics[
            "per_state_gate_inputs_by_sector"
        ].items():
            for name, value in inputs.items():
                if value is not True:
                    passed = False
                    failed.append(
                        {
                            "kind": "exact",
                            "rank": rank,
                            "seed": seed,
                            "reason": f"per-state-{sector}-{name.replace('_', '-')}",
                        }
                    )
    equivalence = shard["metric_equivalence"]
    equivalence_state = _threshold_state(
        equivalence["maximum_difference"],
        equivalence["absolute_tolerance"],
        "maximum",
    )
    if not equivalence["passed"] or equivalence_state != "pass":
        passed = False
        failed.append(
            {
                "kind": "exact",
                "rank": rank,
                "seed": seed,
                "reason": (
                    "metric-equivalence-ambiguous"
                    if equivalence_state == "ambiguous"
                    else "metric-equivalence"
                ),
            }
        )
    span = metrics["projected_span"]
    for sector in ("L0", "L2"):
        if (
            span["completeness_claim_by_sector"][sector]
            and span["numerical_rank_by_sector"][sector]
            != span["dim_m_l_by_sector"][sector]
        ):
            passed = False
            failed.append(
                {
                    "kind": "exact",
                    "rank": rank,
                    "seed": seed,
                    "reason": "projected-span",
                }
            )
    return passed


def _training_equivalence_gate(
    generation: Mapping[str, Any],
    failed: list[dict[str, JSONValue]],
    rank: int,
    seed: int,
) -> bool:
    equivalence = generation["training_metrics"]["metric_equivalence"]
    if equivalence["classification"] in {"not-required", "passed"}:
        return True
    failed.append(
        {
            "kind": "training",
            "rank": rank,
            "seed": seed,
            "reason": "metric-equivalence-pending",
        }
    )
    return False


def _coordinate_gate(
    shard: Mapping[str, Any],
    failed: list[dict[str, JSONValue]],
    rank: int,
    seed: int,
) -> bool:
    diagnostics = shard["sector_diagnostics"]
    paired = shard["paired_gap_diagnostics"]
    policy = production_policy()["vmc_diagnostics"]
    reasons: list[str] = []
    if (
        shard["execution_validation"]["metric_equivalence"]["classification"]
        != "passed"
    ):
        reasons.append("metric-equivalence-pending")
    if (
        shard["sampler_configuration"]["chains"]
        < policy["minimum_chains_per_sector"]
    ):
        reasons.append("minimum-chains")
    if (
        shard["sampler_configuration"]["draws"]
        < policy["minimum_retained_values_per_sector"]
    ):
        reasons.append("minimum-retained-values")
    for name, diagnostic in (
        ("L0", diagnostics["L0"]),
        ("L2", diagnostics["L2"]),
        ("paired-gap", paired),
    ):
        if not diagnostic["autocorrelation_converged"]:
            reasons.append(f"{name}-autocorrelation")
        if (
            _threshold_state(
                diagnostic["effective_sample_size"],
                float(policy["minimum_effective_sample_size"]),
                "minimum",
            )
            != "pass"
        ):
            reasons.append(f"{name}-effective-sample-size")
        if (
            _threshold_state(
                diagnostic["split_rhat"],
                float(policy["maximum_split_rhat"]),
                "maximum",
            )
            != "pass"
        ):
            reasons.append(f"{name}-split-rhat")
    for name, diagnostic in (
        ("L0", diagnostics["L0"]),
        ("L2", diagnostics["L2"]),
    ):
        for acceptance, minimum, maximum in (
            (
                "local_acceptance",
                policy["evaluation_local_acceptance_rate_min"],
                policy["evaluation_local_acceptance_rate_max"],
            ),
            (
                "total_acceptance",
                policy["evaluation_total_acceptance_rate_min"],
                policy["evaluation_total_acceptance_rate_max"],
            ),
        ):
            value = diagnostic[acceptance]
            if (
                _threshold_state(value, float(minimum), "minimum") != "pass"
                or _threshold_state(value, float(maximum), "maximum") != "pass"
            ):
                reasons.append(f"{name}-{acceptance.replace('_', '-')}")
    if paired["uncertainty_status"] != "pending":
        reasons.append("per-seed-uncertainty-not-pending")
    inputs = paired["within_seed_inputs"]
    if (
        len(inputs) != 1
        or inputs[0]["seed"] != seed
        or not math.isclose(
            inputs[0]["variance_mc_gap"],
            inputs[0]["variance_mc_e0"]
            + inputs[0]["variance_mc_e2"]
            - 2.0 * inputs[0]["monte_carlo_covariance_e0_e2"],
            rel_tol=0.0,
            abs_tol=1e-15,
        )
    ):
        reasons.append("within-seed-mc-uncertainty")
    for reason in reasons:
        failed.append(
            {
                "kind": "coordinate",
                "rank": rank,
                "seed": seed,
                "reason": reason,
            }
        )
    return not reasons


def _transition_gate(
    previous_exact: Mapping[str, Any],
    current_exact: Mapping[str, Any],
    previous_coordinate: Mapping[str, Any],
    current_coordinate: Mapping[str, Any],
) -> tuple[bool, dict[str, JSONValue]]:
    energy_values = []
    for sector in ("L0", "L2"):
        before = previous_coordinate["sector_diagnostics"][sector]
        after = current_coordinate["sector_diagnostics"][sector]
        energy_values.append(
            abs(after["estimate"] - before["estimate"])
            + 2
            * math.sqrt(
                before["standard_error"] ** 2 + after["standard_error"] ** 2
            )
        )
    before_gap = previous_coordinate["paired_gap_diagnostics"]
    after_gap = current_coordinate["paired_gap_diagnostics"]
    gap_value = (
        abs(after_gap["estimate"] - before_gap["estimate"])
        + 2
        * math.sqrt(
            before_gap["standard_error"] ** 2
            + after_gap["standard_error"] ** 2
        )
    ) / abs(after_gap["estimate"])
    overlap_value = max(
        abs(
            current_exact["primitive_metrics"]["overlap_by_sector"][sector][
                "estimate"
            ]
            - previous_exact["primitive_metrics"]["overlap_by_sector"][sector][
                "estimate"
            ]
        )
        for sector in ("L0", "L2")
    )
    policy = production_policy()["rank_policy"]
    states = [
        _threshold_state(
            max(energy_values),
            float(policy["energy_change_plus_2sigma_max_ec"]),
            "maximum",
        ),
        _threshold_state(
            overlap_value,
            float(policy["overlap_change_max"]),
            "maximum",
        ),
    ]
    passed = all(state == "pass" for state in states)
    reason = (
        "passed"
        if passed
        else "ambiguous-threshold"
        if "ambiguous" in states
        else "convergence"
    )
    return passed, {
        "energy_change_plus_2sigma_max_ec": max(energy_values),
        "gap_change_plus_2sigma_relative": gap_value,
        "overlap_change_max": overlap_value,
        "passed": passed,
        "reason": reason,
    }


def _paired_transition_gate(
    previous_rank: int,
    current_rank: int,
    coordinate: Mapping[tuple[int, int], Mapping[str, Any]],
) -> tuple[bool, dict[str, JSONValue]]:
    keys = {
        (rank, seed)
        for rank in (previous_rank, current_rank)
        for seed in EXPECTED_SEEDS
    }
    if not keys <= set(coordinate):
        return False, {
            "paired_gap_mean_change": 0.0,
            "paired_gap_standard_error": 0.0,
            "paired_gap_change_plus_2sigma_relative": 0.0,
            "paired_gap_passed": False,
            "reason": "missing-paired-seeds",
        }
    changes = [
        coordinate[(current_rank, seed)]["paired_gap_diagnostics"]["estimate"]
        - coordinate[(previous_rank, seed)]["paired_gap_diagnostics"]["estimate"]
        for seed in EXPECTED_SEEDS
    ]
    count = len(changes)
    mean_change = sum(changes) / count
    sample_variance = sum(
        (change - mean_change) ** 2 for change in changes
    ) / (count - 1)
    standard_error = math.sqrt(sample_variance / count)
    current_mean = sum(
        coordinate[(current_rank, seed)]["paired_gap_diagnostics"]["estimate"]
        for seed in EXPECTED_SEEDS
    ) / count
    relative = (
        0.0
        if current_mean == 0.0
        else (abs(mean_change) + 2 * standard_error) / abs(current_mean)
    )
    threshold = float(
        production_policy()["rank_policy"]["gap_change_plus_2sigma_relative_max"]
    )
    state = (
        "fail"
        if current_mean == 0.0
        else _threshold_state(relative, threshold, "maximum")
    )
    passed = state == "pass"
    return passed, {
        "paired_gap_mean_change": mean_change,
        "paired_gap_standard_error": standard_error,
        "paired_gap_change_plus_2sigma_relative": relative,
        "paired_gap_passed": passed,
        "reason": (
            "passed"
            if passed
            else "ambiguous-threshold"
            if state == "ambiguous"
            else "paired-gap-convergence"
        ),
    }


def _threshold_state(value: float, threshold: float, direction: str) -> str:
    tolerance = max(math.ulp(float(threshold)) * 4, abs(threshold) * 1e-14)
    if abs(value - threshold) <= tolerance:
        return "ambiguous"
    if direction == "maximum":
        return "pass" if value < threshold else "fail"
    return "pass" if value > threshold else "fail"


def _aggregate_metrics(
    metrics: Sequence[Mapping[str, Any]],
    oracle: Mapping[str, Any],
) -> dict[str, JSONValue]:
    if not metrics:
        gap = (
            oracle["sector_summaries"]["L2"]["lowest_energy_ec"]
            - oracle["sector_summaries"]["L0"]["lowest_energy_ec"]
        )
        return {
            "energy_by_sector": {
                "L0": _empty_statistic(
                    oracle["sector_summaries"]["L0"]["lowest_energy_ec"]
                ),
                "L2": _empty_statistic(
                    oracle["sector_summaries"]["L2"]["lowest_energy_ec"]
                ),
            },
            "gap": {
                **_empty_statistic(gap),
                "monte_carlo_covariance_e0_e2": 0.0,
                "optimizer_induced_covariance_e0_e2": 0.0,
            },
            "overlap_by_sector": {
                "L0": _empty_statistic(0.0),
                "L2": _empty_statistic(0.0),
            },
            "symmetry_residual_by_sector": {"L0": 0.0, "L2": 0.0},
            "per_state_gate_inputs_by_sector": {
                sector: {
                    "finite": False,
                    "normalized_amplitude_nonzero": False,
                }
                for sector in ("L0", "L2")
            },
            "quadrature_change_by_sector": {
                sector: {
                    component: 0.0
                    for component in ("normalized_amplitude", "energy", "symmetry")
                }
                for sector in ("L0", "L2")
            },
            "projected_span": {
                "singular_values_by_sector": {"L0": [0.0], "L2": [0.0]},
                "numerical_rank_by_sector": {"L0": 0, "L2": 0},
                "dim_m_l_by_sector": {"L0": 0, "L2": 0},
                "completeness_claim_by_sector": {"L0": False, "L2": False},
            },
        }
    primitive_fields = (
        "energy_by_sector",
        "gap",
        "overlap_by_sector",
        "symmetry_residual_by_sector",
        "per_state_gate_inputs_by_sector",
        "quadrature_change_by_sector",
        "projected_span",
    )
    result = {key: metrics[0][key] for key in primitive_fields}
    for group in ("energy_by_sector", "overlap_by_sector"):
        result[group] = {}
        for sector in ("L0", "L2"):
            result[group][sector] = _mean_statistic(
                [item[group][sector] for item in metrics]
            )
    result["gap"] = {
        **_mean_statistic([item["gap"] for item in metrics]),
        "monte_carlo_covariance_e0_e2": sum(
            item["gap"]["monte_carlo_covariance_e0_e2"] for item in metrics
        )
        / len(metrics),
        "optimizer_induced_covariance_e0_e2": sum(
            item["gap"]["optimizer_induced_covariance_e0_e2"]
            for item in metrics
        )
        / len(metrics),
    }
    result["symmetry_residual_by_sector"] = {
        sector: max(
            item["symmetry_residual_by_sector"][sector] for item in metrics
        )
        for sector in ("L0", "L2")
    }
    result["per_state_gate_inputs_by_sector"] = {
        sector: {
            name: all(
                item["per_state_gate_inputs_by_sector"][sector][name]
                for item in metrics
            )
            for name in ("finite", "normalized_amplitude_nonzero")
        }
        for sector in ("L0", "L2")
    }
    result["quadrature_change_by_sector"] = {
        sector: {
            component: max(
                item["quadrature_change_by_sector"][sector][component]
                for item in metrics
            )
            for component in ("normalized_amplitude", "energy", "symmetry")
        }
        for sector in ("L0", "L2")
    }
    return result


def _mean_statistic(statistics: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    count = len(statistics)
    estimate = sum(item["estimate"] for item in statistics) / count
    error = math.sqrt(
        sum(item["standard_error"] ** 2 for item in statistics)
    ) / count
    return {
        "estimate": estimate,
        "standard_error": error,
        "ci_low": estimate - 2 * error,
        "ci_high": estimate + 2 * error,
    }


def _empty_statistic(estimate: float) -> dict[str, float]:
    return {
        "estimate": estimate,
        "standard_error": 0.0,
        "ci_low": estimate,
        "ci_high": estimate,
    }


def _identity_hash_map(
    values: Mapping[tuple[int, int], Mapping[str, Any]],
) -> dict[str, str]:
    return {
        f"rank={rank},seed={seed}": payload_sha256(payload)
        for (rank, seed), payload in sorted(values.items())
    }


def _require_sha(value: Any, label: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be a lowercase SHA256")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

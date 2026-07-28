from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

import numpy as np

from .audit import verify_manifest
from .contracts import CandidateAdapter, DiagnosticProvider, StateHandle
from .gates import (
    FINAL_GATE_NAMES,
    apply_ed_reveal,
    evaluate_pre_reveal,
)
from .protocol import ProtocolConfig
from .resources import RuntimeMeter
from .statistics import blocking_estimate, combine_independent


SCHEMA_VERSION = "challenge-15-scalable-v1.0"
L2_M_VALUES = (-2, -1, 0, 1, 2)
L2_M_KEYS = frozenset(str(m) for m in L2_M_VALUES)
BLINDNESS_RECORD = {"human_blind": False, "oracle_isolated": True}
RUN_RECORD_KEYS = frozenset(
    {
        "schema_version",
        "protocol_sha256",
        "system",
        "candidate",
        "training_seed",
        "blindness",
        "construction",
        "statistics",
        "diagnostics",
        "resources",
        "gates",
        "audit",
        "ed_comparison",
    }
)


def _state_statistics(
    state: StateHandle,
    *,
    state_index: int,
    training_seed: int,
    chains: int,
    samples_per_chain: int,
    burn_in_steps: int,
    block_size: int,
) -> dict[str, dict[str, float]]:
    energy_rows: list[np.ndarray] = []
    l2_rows: list[np.ndarray] = []
    for chain in range(chains):
        seed = training_seed + 1000 * state_index + chain
        batch = state.sample(samples_per_chain, seed)
        if (
            batch.n_samples != samples_per_chain
            or batch.seed != seed
            or len(batch.configs) != samples_per_chain
        ):
            raise ValueError("sample batch does not match the frozen schedule")
        if batch.burn_in_steps != burn_in_steps:
            raise ValueError("sample batch does not use the frozen burn-in")

        logpsi = np.asarray(state.logpsi(batch.configs))
        if logpsi.shape != (samples_per_chain,) or not np.all(
            np.isfinite(logpsi)
        ):
            raise ValueError("logpsi must be a finite vector of sampled values")

        energy = np.asarray(state.local_energy(batch.configs))
        l2 = np.asarray(state.local_l2(batch.configs))
        if energy.shape != (samples_per_chain,):
            raise ValueError("local_energy must return one value per sample")
        if l2.shape != (samples_per_chain,):
            raise ValueError("local_l2 must return one value per sample")
        energy_rows.append(energy)
        l2_rows.append(l2)

    return {
        "energy": blocking_estimate(
            np.stack(energy_rows), block_size=block_size
        ).to_dict(),
        "l2": blocking_estimate(
            np.stack(l2_rows), block_size=block_size
        ).to_dict(),
    }


def collect_evidence(
    *,
    candidate: CandidateAdapter,
    diagnostics: DiagnosticProvider,
    protocol: ProtocolConfig,
    training_seed: int,
) -> dict[str, Any]:
    tower = dict(candidate.generate_multiplet())
    if not all(type(m) is int for m in tower) or set(tower) != set(L2_M_VALUES):
        raise ValueError("candidate must provide the exact integer M=-2..2 multiplet")

    ground_state = candidate.ground_state()
    if (
        type(ground_state.l) is not int
        or type(ground_state.m) is not int
        or ground_state.l != 0
        or ground_state.m != 0
    ):
        raise ValueError("ground state must have exact integer l=0, m=0 metadata")
    for m in L2_M_VALUES:
        state = tower[m]
        if (
            type(state.l) is not int
            or type(state.m) is not int
            or state.l != 2
            or state.m != m
        ):
            raise ValueError(
                "each L=2 state must have exact integer l=2 and mapping-key m"
            )

    states = [ground_state, *(tower[m] for m in L2_M_VALUES)]
    labels = [state.label for state in states]
    if (
        not all(type(label) is str and bool(label) for label in labels)
        or len(set(labels)) != len(labels)
    ):
        raise ValueError("state labels must be nonempty and unique")

    sampling = protocol.sampling
    state_records = [
        _state_statistics(
            state,
            state_index=state_index,
            training_seed=training_seed,
            chains=int(sampling["chains"]),
            samples_per_chain=int(sampling["samples_per_chain"]),
            burn_in_steps=int(sampling["burn_in_steps"]),
            block_size=int(sampling["block_size"]),
        )
        for state_index, state in enumerate(states)
    ]
    ground = state_records[0]
    excited = state_records[1:]
    combined_mean = sum(state["energy"]["mean"] for state in excited) / len(
        excited
    )
    combined_error = math.sqrt(
        sum(state["energy"]["standard_error"] ** 2 for state in excited)
    ) / len(excited)
    gap_mean, gap_error = combine_independent(
        combined_mean,
        combined_error,
        ground["energy"]["mean"],
        ground["energy"]["standard_error"],
    )

    metrics = asdict(candidate.resource_metrics())
    metrics["effective_sample_size"] = min(
        state["energy"]["effective_sample_size"] for state in state_records
    )
    symmetry = protocol.symmetry
    diagnostic_record = dict(
        diagnostics.evaluate(
            candidate,
            seed=int(symmetry["seed"]),
            swap_probes=int(symmetry["swap_probes"]),
            rotation_probes=int(symmetry["rotation_probes"]),
        )
    )

    return {
        "construction": asdict(candidate.construction_certificate()),
        "statistics": {
            "ground": ground,
            "l2_by_m": {
                str(m): state_records[index + 1]
                for index, m in enumerate(L2_M_VALUES)
            },
            "combined_l2": {
                "mean": combined_mean,
                "standard_error": combined_error,
            },
            "gap": {"mean": gap_mean, "standard_error": gap_error},
        },
        "diagnostics": diagnostic_record,
        "resources": metrics,
    }


def evaluate_candidate(
    *,
    candidate: CandidateAdapter,
    diagnostics: DiagnosticProvider,
    protocol: ProtocolConfig,
    manifest_path: Path,
    project_root: Path,
    oracle_path: Path,
    training_seed: int,
    oracle_loader: Callable[[str], Mapping[str, Any]] = json.loads,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    if progress is not None:
        progress("audit: verifying frozen training manifest")
    audit = verify_manifest(
        manifest_path,
        project_root=project_root,
        protocol=protocol,
        expected_training_seed=training_seed,
    )
    if not audit.valid:
        raise ValueError(f"manifest audit failed: {'; '.join(audit.issues)}")

    with RuntimeMeter() as meter:
        evidence = collect_evidence(
            candidate=candidate,
            diagnostics=diagnostics,
            protocol=protocol,
            training_seed=training_seed,
        )

    resources = evidence["resources"]
    resources["wall_seconds"] = max(
        float(resources["wall_seconds"]), meter.wall_seconds
    )
    resources["peak_rss_bytes"] = max(
        int(resources["peak_rss_bytes"]), meter.peak_rss_bytes
    )
    resources["checkpoint_bytes"] = max(
        int(resources["checkpoint_bytes"]), audit.artifact_bytes
    )
    resources["ess_per_second"] = (
        float(resources["effective_sample_size"]) / resources["wall_seconds"]
    )

    pre_reveal = evaluate_pre_reveal(evidence, protocol, audit)
    if progress is not None:
        progress("reveal: loading ED oracle after audit")
    oracle_text = Path(oracle_path).read_text(encoding="utf-8")
    revealed = apply_ed_reveal(
        pre_reveal,
        oracle_loader(oracle_text),
        protocol,
    )
    revealed.update(
        schema_version=SCHEMA_VERSION,
        protocol_sha256=protocol.sha256,
        system=dict(protocol.physics),
        candidate={"name": candidate.name, "family": candidate.family},
        training_seed=training_seed,
        blindness=dict(BLINDNESS_RECORD),
    )
    validate_run_record(revealed)
    return revealed


def validate_run_record(record: Mapping[str, Any]) -> None:
    if set(record) != RUN_RECORD_KEYS or record.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("run record schema mismatch")

    gates = record.get("gates")
    if not isinstance(gates, Mapping) or set(gates) != set(FINAL_GATE_NAMES):
        raise ValueError("run record gate set mismatch")
    if any(type(gates[name]) is not bool for name in FINAL_GATE_NAMES):
        raise ValueError("run record gate values must be booleans")
    base_gate_names = tuple(
        name for name in FINAL_GATE_NAMES if name != "scalable_v1_pass"
    )
    expected_final = all(gates[name] is True for name in base_gate_names)
    if gates["scalable_v1_pass"] is not expected_final:
        raise ValueError("run record scalable_v1_pass semantics mismatch")

    statistics = record.get("statistics")
    if not isinstance(statistics, Mapping):
        raise ValueError("run record M set mismatch")
    l2_by_m = statistics.get("l2_by_m")
    if not isinstance(l2_by_m, Mapping) or set(l2_by_m) != L2_M_KEYS:
        raise ValueError("run record M set mismatch")

    if record.get("blindness") != BLINDNESS_RECORD:
        raise ValueError("run record blindness mismatch")


def write_json_report(result: Mapping[str, Any], output: Path) -> Path:
    validate_run_record(result)
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        dir=output_path.parent,
        prefix=f".{output_path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        descriptor = -1
        os.replace(temporary_path, output_path)
    except BaseException:
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError:
                pass
        temporary_path.unlink(missing_ok=True)
        raise
    return output_path

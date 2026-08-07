"""B0 certification for the traditional 13-operator VMCRG baseline."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
import json
from pathlib import Path
import resource
from statistics import NormalDist
import time
from typing import Any

import numpy as np

from .artifacts import (
    atomic_write_json,
    atomic_write_npz,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
)
from .fast import FastMultiOperatorBiasedMetropolis
from .ising import IsingLattice
from .issue28_protocol import (
    Issue28Protocol,
    canonical_operator_basis_record,
    create_gauge_reference,
    operator_basis_sha256,
)
from .multi_optimizer import MultiOperatorOptimizer, MultiOptimizationRecord
from .operators import EVEN_SHAPES, OperatorBasis
from .paper_observables import (
    integrated_autocorrelation_time,
    normalized_connected_autocorrelation,
)


_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_B0_CONFIG = _ROOT / "config" / "issue28_b0_v1.json"


@dataclass(frozen=True)
class TraditionalCertificationPreset:
    name: str
    length: int
    coupling: float
    block_size: int
    steps: int
    sweeps_per_step: int
    walkers: int
    learning_rate: float
    optimizer_seed: int
    validation_thermalization: int
    validation_measurements: int
    validation_runs: int
    validation_seed: int
    autocorrelation_thermalization: int
    autocorrelation_measurements: int
    autocorrelation_spacing: int
    autocorrelation_max_lag: int
    autocorrelation_chains: int
    autocorrelation_seed: int
    local_delta_trials: int
    local_delta_seed: int
    gauge_configurations: int


def traditional_handoff_from_values(
    bias: np.ndarray,
    values: np.ndarray,
) -> np.ndarray:
    coefficients = np.asarray(bias, dtype=np.float64)
    operator_values = np.asarray(values, dtype=np.float64)
    if coefficients.ndim != 1:
        raise ValueError("bias must be one-dimensional")
    if operator_values.shape[-1] != coefficients.size:
        raise ValueError("operator values and bias have incompatible shapes")
    return -(operator_values @ coefficients)


def traditional_handoff_energy(
    bias: np.ndarray,
    spins: np.ndarray,
    basis: OperatorBasis,
) -> np.ndarray:
    configurations = np.asarray(spins, dtype=np.int8)
    if configurations.ndim == 2:
        configurations = configurations[None, ...]
    if configurations.ndim != 3:
        raise ValueError("spins must contain one or more square configurations")
    values = np.stack([basis.values(configuration) for configuration in configurations])
    return traditional_handoff_from_values(bias, values)


def _load_config(path: Path, preset: str) -> tuple[TraditionalCertificationPreset, dict[str, Any]]:
    value = json.loads(path.read_text(encoding="ascii"))
    if value.get("protocol") != "issue28_b0_traditional_certification_v1":
        raise ValueError("unexpected B0 protocol")
    if preset not in value["presets"]:
        raise ValueError(f"unknown B0 preset: {preset}")
    item = value["presets"][preset]
    run = TraditionalCertificationPreset(
        name=preset,
        length=int(item["length"]),
        coupling=float(item["coupling"]),
        block_size=int(item["block_size"]),
        steps=int(item["steps"]),
        sweeps_per_step=int(item["sweeps_per_step"]),
        walkers=int(item["walkers"]),
        learning_rate=float(item["learning_rate"]),
        optimizer_seed=int(item["optimizer_seed"]),
        validation_thermalization=int(item["validation_thermalization"]),
        validation_measurements=int(item["validation_measurements"]),
        validation_runs=int(item["validation_runs"]),
        validation_seed=int(item["validation_seed"]),
        autocorrelation_thermalization=int(item["autocorrelation_thermalization"]),
        autocorrelation_measurements=int(item["autocorrelation_measurements"]),
        autocorrelation_spacing=int(item["autocorrelation_spacing"]),
        autocorrelation_max_lag=int(item["autocorrelation_max_lag"]),
        autocorrelation_chains=int(item["autocorrelation_chains"]),
        autocorrelation_seed=int(item["autocorrelation_seed"]),
        local_delta_trials=int(item["local_delta_trials"]),
        local_delta_seed=int(item["local_delta_seed"]),
        gauge_configurations=int(item["gauge_configurations"]),
    )
    if run.length != 45 or run.coupling != 0.436 or run.block_size != 3:
        raise ValueError("B0 must use the frozen 45x45, K=0.436, b=3 setup")
    positive = (
        run.steps,
        run.sweeps_per_step,
        run.walkers,
        run.learning_rate,
        run.validation_measurements,
        run.validation_runs,
        run.autocorrelation_measurements,
        run.autocorrelation_spacing,
        run.autocorrelation_chains,
        run.local_delta_trials,
        run.gauge_configurations,
    )
    if any(number <= 0 for number in positive):
        raise ValueError("B0 run budgets must be positive")
    if run.walkers < 2 or run.validation_runs < 2 or run.autocorrelation_chains < 2:
        raise ValueError("B0 requires at least two independent walkers/chains")
    if run.autocorrelation_max_lag >= run.autocorrelation_measurements:
        raise ValueError("B0 autocorrelation max lag must be shorter than the series")
    anchor = dict(value["principal_coupling_anchor"])
    expected_anchor_hash = str(anchor.pop("anchor_record_sha256", ""))
    actual_anchor_hash = sha256_bytes(canonical_json_bytes(anchor))
    if expected_anchor_hash != actual_anchor_hash:
        raise ValueError(
            "principal coupling anchor hash mismatch: "
            f"expected {expected_anchor_hash}, got {actual_anchor_hash}"
        )
    return run, value


def _trajectory_arrays(records: list[MultiOptimizationRecord]) -> dict[str, np.ndarray]:
    return {
        "instantaneous_bias": np.stack([record.instantaneous_bias for record in records]),
        "running_bias": np.stack([record.running_bias for record in records]),
        "mean_operators": np.stack([record.mean_operators for record in records]),
        "covariance": np.stack([record.covariance for record in records]),
        "gradients": np.stack([record.gradient for record in records]),
        "updates": np.stack([record.update for record in records]),
        "gradient_norm": np.asarray([record.gradient_norm for record in records]),
        "covariance_condition_number": np.asarray(
            [record.covariance_condition_number for record in records]
        ),
        "acceptance_rates": np.stack([record.acceptance_rates for record in records]),
        "elapsed_seconds": np.asarray([record.elapsed_seconds for record in records]),
    }


def _convergence_report(
    records: list[MultiOptimizationRecord],
    block_sites: int,
    gates: dict[str, Any],
) -> dict[str, Any]:
    window = min(len(records), max(2, len(records) // 5))
    late = np.stack([record.mean_operators for record in records[-window:]]) / block_sites
    mean = late.mean(axis=0)
    standard_error = (
        late.std(axis=0, ddof=1) / np.sqrt(window)
        if window > 1
        else np.zeros(late.shape[1], dtype=np.float64)
    )
    z = np.divide(mean, standard_error, out=np.zeros_like(mean), where=standard_error > 0)
    zero_se_nonzero = (standard_error == 0) & (mean != 0)
    z[zero_se_nonzero] = np.sign(mean[zero_se_nonzero]) * np.finfo(np.float64).max
    running = np.stack([record.running_bias for record in records])
    start_index = max(0, int(np.floor(0.9 * len(records))) - 1)
    drift = float(np.max(np.abs(running[-1] - running[start_index])))
    maximum_condition = float(
        max(record.covariance_condition_number for record in records[-window:])
    )
    maximum_abs_z = float(np.max(np.abs(z)))
    passed = bool(
        maximum_abs_z <= float(gates["maximum_late_abs_z"])
        and drift <= float(gates["maximum_bias_drift"])
        and maximum_condition <= float(gates["maximum_covariance_condition"])
    )
    return {
        "late_window_steps": window,
        "late_mean_operators_per_block_site": mean.tolist(),
        "late_standard_errors_per_block_site": standard_error.tolist(),
        "late_z_scores": z.tolist(),
        "maximum_absolute_late_z": maximum_abs_z,
        "maximum_bias_drift_last_ten_percent": drift,
        "maximum_covariance_condition_number": maximum_condition,
        "final_gradient_norm": records[-1].gradient_norm,
        "gates": {
            "maximum_late_abs_z": float(gates["maximum_late_abs_z"]),
            "maximum_bias_drift": float(gates["maximum_bias_drift"]),
            "maximum_covariance_condition": float(
                gates["maximum_covariance_condition"]
            ),
        },
        "status": "PASS" if passed else "FAIL",
    }


def _local_delta_report(
    basis: OperatorBasis,
    bias: np.ndarray,
    trials: int,
    seed: int,
    atol: float,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    maximum_operator_error = 0.0
    maximum_energy_error = 0.0
    for _ in range(trials):
        spins = rng.choice(np.asarray([-1, 1], dtype=np.int8), size=(basis.length, basis.length))
        x = int(rng.integers(basis.length))
        y = int(rng.integers(basis.length))
        before = basis.values(spins)
        incremental = basis.delta_for_flip(spins, x, y)
        trial = spins.copy()
        trial[x, y] *= -1
        direct = basis.values(trial) - before
        maximum_operator_error = max(
            maximum_operator_error,
            float(np.max(np.abs(incremental - direct))),
        )
        maximum_energy_error = max(
            maximum_energy_error,
            abs(float(incremental @ bias) - float(direct @ bias)),
        )
    maximum = max(maximum_operator_error, maximum_energy_error)
    return {
        "trials": trials,
        "seed": seed,
        "maximum_operator_delta_error": maximum_operator_error,
        "maximum_energy_delta_error": maximum_energy_error,
        "maximum_absolute_error": maximum,
        "absolute_tolerance": atol,
        "status": "PASS" if maximum <= atol else "FAIL",
    }


def _frozen_validation(
    run: TraditionalCertificationPreset,
    couplings: np.ndarray,
    bias: np.ndarray,
    micro_basis: OperatorBasis,
    block_basis: OperatorBasis,
    family_alpha: float,
) -> dict[str, Any]:
    sequences = np.random.SeedSequence(run.validation_seed).spawn(run.validation_runs)

    def one_chain(sequence: np.random.SeedSequence) -> tuple[np.ndarray, float]:
        rng = np.random.default_rng(sequence)
        sampler = FastMultiOperatorBiasedMetropolis(
            IsingLattice.random(run.length, rng),
            couplings,
            bias,
            rng,
            EVEN_SHAPES,
            block_size=run.block_size,
            micro_basis=micro_basis,
            block_basis=block_basis,
        )
        if run.validation_thermalization:
            sampler.run_sweeps(run.validation_thermalization)
        attempted_before = sampler.attempted
        accepted_before = sampler.accepted
        _, block_sum, _, _ = sampler.measure_moments(run.validation_measurements, 1)
        sampler.assert_cache_consistent()
        return (
            block_sum / run.validation_measurements,
            (sampler.accepted - accepted_before) / (sampler.attempted - attempted_before),
        )

    with ThreadPoolExecutor(max_workers=run.validation_runs) as executor:
        results = list(executor.map(one_chain, sequences))
    block_sites = (run.length // run.block_size) ** 2
    chain_means = np.stack([item[0] for item in results]) / block_sites
    mean = chain_means.mean(axis=0)
    standard_error = chain_means.std(axis=0, ddof=1) / np.sqrt(run.validation_runs)
    z = np.divide(mean, standard_error, out=np.zeros_like(mean), where=standard_error > 0)
    zero_se_nonzero = (standard_error == 0) & (mean != 0)
    z[zero_se_nonzero] = np.sign(mean[zero_se_nonzero]) * np.finfo(np.float64).max
    critical = NormalDist().inv_cdf(1.0 - family_alpha / (2.0 * len(EVEN_SHAPES)))
    maximum_abs_z = float(np.max(np.abs(z)))
    return {
        "thermalization_sweeps": run.validation_thermalization,
        "measurement_sweeps_per_chain": run.validation_measurements,
        "independent_chains": run.validation_runs,
        "seed": run.validation_seed,
        "mean_operators_per_block_site": mean.tolist(),
        "chain_means_per_block_site": chain_means.tolist(),
        "chain_level_standard_errors": standard_error.tolist(),
        "z_scores_against_uniform_target": z.tolist(),
        "maximum_absolute_z": maximum_abs_z,
        "family_alpha": family_alpha,
        "bonferroni_critical_absolute_z": critical,
        "acceptance_rates": [float(item[1]) for item in results],
        "status": "PASS" if maximum_abs_z <= critical else "FAIL",
    }


def _principal_coupling_report(
    couplings: np.ndarray,
    anchor: dict[str, Any],
) -> dict[str, Any]:
    indices = np.asarray(anchor["indices"], dtype=np.int64)
    expected = np.asarray(anchor["values"], dtype=np.float64)
    tolerances = np.asarray(anchor["absolute_tolerances"], dtype=np.float64)
    observed = couplings[indices]
    errors = np.abs(observed - expected)
    passed = bool(np.all(errors <= tolerances))
    return {
        "indices": indices.tolist(),
        "operator_names": [EVEN_SHAPES[int(index)].name for index in indices],
        "observed": observed.tolist(),
        "verified_harness_anchor": expected.tolist(),
        "absolute_errors": errors.tolist(),
        "absolute_tolerances": tolerances.tolist(),
        "anchor_source": str(anchor["source"]),
        "evidence_path": str(anchor["evidence_path"]),
        "evidence_sha256": str(anchor["evidence_sha256"]),
        "anchor_record_sha256": str(anchor["anchor_record_sha256"]),
        "status": "PASS" if passed else "FAIL",
    }


def _tau(series: np.ndarray, maximum_lag: int) -> float | None:
    if float(np.var(series)) == 0.0:
        return None
    acf = normalized_connected_autocorrelation(series, maximum_lag)
    value = float(integrated_autocorrelation_time(acf))
    return value if np.isfinite(value) and value > 0.0 else None


def _autocorrelation_report(
    run: TraditionalCertificationPreset,
    couplings: np.ndarray,
    bias: np.ndarray,
    micro_basis: OperatorBasis,
    block_basis: OperatorBasis,
    ratio_threshold: float,
) -> dict[str, Any]:
    sequences = np.random.SeedSequence(run.autocorrelation_seed).spawn(
        3 * run.autocorrelation_chains
    )

    def one_chain(index: int) -> tuple[float | None, float | None, float, float]:
        initial = IsingLattice.random(
            run.length,
            np.random.default_rng(sequences[3 * index]),
        ).spins
        taus: list[float | None] = []
        acceptance: list[float] = []
        for arm_bias, sequence in (
            (bias, sequences[3 * index + 1]),
            (np.zeros_like(bias), sequences[3 * index + 2]),
        ):
            sampler = FastMultiOperatorBiasedMetropolis(
                IsingLattice(initial.copy()),
                couplings,
                arm_bias,
                np.random.default_rng(sequence),
                EVEN_SHAPES,
                block_size=run.block_size,
                micro_basis=micro_basis,
                block_basis=block_basis,
            )
            if run.autocorrelation_thermalization:
                sampler.run_sweeps(run.autocorrelation_thermalization)
            attempted_before = sampler.attempted
            accepted_before = sampler.accepted
            values = sampler.nearest_neighbor_product_series(
                run.autocorrelation_measurements,
                run.autocorrelation_spacing,
            )
            taus.append(_tau(values, run.autocorrelation_max_lag))
            acceptance.append(
                (sampler.accepted - accepted_before)
                / (sampler.attempted - attempted_before)
            )
            sampler.assert_cache_consistent()
        return taus[0], taus[1], acceptance[0], acceptance[1]

    with ThreadPoolExecutor(max_workers=run.autocorrelation_chains) as executor:
        results = list(executor.map(one_chain, range(run.autocorrelation_chains)))
    usable = [item for item in results if item[0] is not None and item[1] is not None]
    ratios = np.asarray([item[0] / item[1] for item in usable], dtype=np.float64)
    if ratios.size >= 2:
        mean = float(ratios.mean())
        standard_error = float(ratios.std(ddof=1) / np.sqrt(ratios.size))
        upper = mean + 2.0 * standard_error
    elif ratios.size == 1:
        mean = float(ratios[0])
        standard_error = None
        upper = None
    else:
        mean = None
        standard_error = None
        upper = None
    passed = upper is not None and upper < ratio_threshold
    return {
        "observable": "normalized_S0_micro_times_S0_block",
        "thermalization_sweeps": run.autocorrelation_thermalization,
        "measurements_per_chain": run.autocorrelation_measurements,
        "spacing_sweeps": run.autocorrelation_spacing,
        "maximum_lag": run.autocorrelation_max_lag,
        "independent_paired_chains": run.autocorrelation_chains,
        "usable_paired_chains": len(usable),
        "seed": run.autocorrelation_seed,
        "biased_tau_by_chain": [item[0] for item in results],
        "unbiased_tau_by_chain": [item[1] for item in results],
        "paired_tau_ratio_mean": mean,
        "paired_tau_ratio_standard_error": standard_error,
        "paired_tau_ratio_upper_2se": upper,
        "ratio_threshold": ratio_threshold,
        "biased_acceptance_rates": [float(item[2]) for item in results],
        "unbiased_acceptance_rates": [float(item[3]) for item in results],
        "status": "PASS" if passed else "FAIL",
    }


def certify_traditional_baseline(
    protocol: Issue28Protocol,
    output: str | Path,
    *,
    preset: str = "formal",
    config_path: str | Path = _DEFAULT_B0_CONFIG,
) -> dict[str, Any]:
    """Run B0 and write a complete, hash-linked certification directory."""
    expected_basis_hash = operator_basis_sha256(protocol.physical.length // protocol.physical.block_size)
    if protocol.operator_basis_sha256 != expected_basis_hash:
        raise ValueError(
            "operator basis hash mismatch: "
            f"expected {expected_basis_hash}, got {protocol.operator_basis_sha256}"
        )
    root = Path(output)
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"refusing to overwrite nonempty B0 output: {root}")

    b0_config_path = Path(config_path)
    run, config = _load_config(b0_config_path, preset)
    b0_config_sha256 = sha256_file(b0_config_path)
    if (
        run.length != protocol.physical.length
        or run.coupling != protocol.physical.coupling
        or run.block_size != protocol.physical.block_size
    ):
        raise ValueError("B0 preset does not match the Issue #28 physical protocol")

    root.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    basis_record = canonical_operator_basis_record(run.length // run.block_size)
    basis_record["sha256"] = sha256_bytes(canonical_json_bytes(basis_record))
    atomic_write_json(root / "basis.json", basis_record)

    couplings = np.zeros(len(EVEN_SHAPES), dtype=np.float64)
    couplings[0] = run.coupling
    optimizer = MultiOperatorOptimizer(
        length=run.length,
        couplings=couplings,
        shapes=EVEN_SHAPES,
        walkers=run.walkers,
        seed=run.optimizer_seed,
        block_size=run.block_size,
        compiled=True,
        parallel_walkers=True,
    )
    progress_every = max(1, run.steps // 20)

    def progress(record: MultiOptimizationRecord) -> None:
        if record.step == 0 or (record.step + 1) % progress_every == 0:
            print(
                "B0传统基线 "
                f"步数={record.step + 1}/{run.steps} "
                f"梯度范数={record.gradient_norm:.6g} "
                f"主耦合={-record.running_bias[0]:.6g}",
                flush=True,
            )

    records = optimizer.run(
        steps=run.steps,
        sweeps_per_step=run.sweeps_per_step,
        learning_rate=run.learning_rate,
        callback=progress,
    )
    for sampler in optimizer.samplers:
        sampler.assert_cache_consistent()
    atomic_write_npz(root / "trajectory.npz", _trajectory_arrays(records))

    final_bias = records[-1].running_bias.copy()
    final_couplings = -final_bias
    micro_basis = optimizer.samplers[0].micro_basis
    block_basis = optimizer.samplers[0].block_basis
    gates = dict(config["gates"])
    convergence = _convergence_report(records, block_basis.length**2, gates)
    atomic_write_json(root / "convergence.json", convergence)

    local_delta = _local_delta_report(
        block_basis,
        final_bias,
        run.local_delta_trials,
        run.local_delta_seed,
        float(protocol.gates["local_delta_atol"]),
    )
    atomic_write_json(root / "local_energy_delta.json", local_delta)
    validation = _frozen_validation(
        run,
        couplings,
        final_bias,
        micro_basis,
        block_basis,
        float(gates["validation_family_alpha"]),
    )
    atomic_write_json(root / "frozen_validation.json", validation)
    principal = _principal_coupling_report(final_couplings, config["principal_coupling_anchor"])
    if preset != "formal":
        principal["status"] = "NOT_EVALUATED_SMOKE"
    atomic_write_json(root / "principal_couplings.json", principal)

    gauge_protocol = replace(
        protocol,
        gauge=replace(protocol.gauge, configurations=run.gauge_configurations),
    )
    gauge_record = create_gauge_reference(gauge_protocol, root / "gauge_reference")
    with np.load(root / "gauge_reference" / "gauge_reference.npz", allow_pickle=False) as archive:
        gauge_spins = np.asarray(archive["spins"], dtype=np.int8)
    gauge_basis = OperatorBasis(run.length, EVEN_SHAPES)
    values = np.stack([gauge_basis.values(state) for state in gauge_spins])
    handed = traditional_handoff_from_values(final_bias, values)
    explicit = values @ final_couplings
    difference = handed - explicit
    centered = difference - difference.mean()
    handoff = {
        "rule": "U_next=-V_frozen",
        "reference_raw_array_sha256": gauge_record["raw_array_sha256"],
        "configurations": run.gauge_configurations,
        "additive_constant": float(difference.mean()),
        "maximum_gauge_centered_residual": float(np.max(np.abs(centered))),
        "absolute_tolerance": float(protocol.gates["local_delta_atol"]),
    }
    handoff["status"] = (
        "PASS"
        if handoff["maximum_gauge_centered_residual"] <= handoff["absolute_tolerance"]
        else "FAIL"
    )
    atomic_write_json(root / "handoff.json", handoff)

    autocorrelation = _autocorrelation_report(
        run,
        couplings,
        final_bias,
        micro_basis,
        block_basis,
        float(gates["autocorrelation_ratio_upper"]),
    )
    atomic_write_json(root / "autocorrelation.json", autocorrelation)

    correctness_passed = local_delta["status"] == "PASS" and handoff["status"] == "PASS"
    scientific_passed = all(
        item["status"] == "PASS"
        for item in (convergence, validation, principal, autocorrelation)
    )
    if not correctness_passed:
        classification = "CORRECTNESS_FAILURE"
        reason = "B0_DETERMINISTIC_GATE_FAILED"
    elif preset != "formal":
        classification = "SCIENTIFIC_NEGATIVE"
        reason = "SMOKE_STATISTICALLY_INSUFFICIENT"
    elif scientific_passed:
        classification = "EASY_GOAL_SUCCESS"
        reason = "B0_STAGE_CERTIFIED"
    else:
        classification = "SCIENTIFIC_NEGATIVE"
        reason = "B0_SCIENTIFIC_GATE_FAILED"

    elapsed = time.perf_counter() - started
    resources = {
        "elapsed_seconds": elapsed,
        "peak_rss_kib": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
        "threads": run.walkers,
        "hardware_class": "local_cpu",
        "preset": preset,
    }
    atomic_write_json(root / "resources.json", resources)
    artifact_names = (
        "basis.json",
        "trajectory.npz",
        "convergence.json",
        "frozen_validation.json",
        "local_energy_delta.json",
        "principal_couplings.json",
        "handoff.json",
        "autocorrelation.json",
        "resources.json",
        "gauge_reference/gauge_reference.json",
        "gauge_reference/gauge_reference.npz",
    )
    artifact_hashes = {name: sha256_file(root / name) for name in artifact_names}
    manifest = {
        "schema_version": 1,
        "stage": "B0",
        "scope": "B0_STAGE_ONLY",
        "preset": preset,
        "classification": classification,
        "reason": reason,
        "protocol_sha256": protocol.protocol_sha256,
        "b0_config_sha256": b0_config_sha256,
        "basis_sha256": protocol.operator_basis_sha256,
        "physical": {
            "length": run.length,
            "coupling": run.coupling,
            "block_size": run.block_size,
            "boundary": "periodic",
        },
        "final_bias": final_bias.tolist(),
        "final_renormalized_couplings": final_couplings.tolist(),
        "correctness_gates": {
            "local_energy_delta": local_delta["status"],
            "handoff": handoff["status"],
        },
        "scientific_gates": {
            "convergence": convergence["status"],
            "frozen_validation": validation["status"],
            "principal_couplings": principal["status"],
            "autocorrelation": autocorrelation["status"],
        },
        "artifacts": artifact_hashes,
    }
    atomic_write_json(root / "manifest.json", manifest)
    return {
        **manifest,
        "local_energy_delta": local_delta,
        "handoff": handoff,
        "convergence": convergence,
        "frozen_validation": validation,
        "principal_couplings": principal,
        "autocorrelation": autocorrelation,
        "resources": resources,
    }

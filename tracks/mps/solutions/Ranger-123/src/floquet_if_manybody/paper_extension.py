"""Resumable publication-grid orchestration for the N=3 extension."""

from __future__ import annotations

import copy
import json
import math
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
from scipy.integrate import trapezoid

from .adaptive import (
    AdaptiveResult,
    AdaptiveSchedule,
    UniformAdaptiveSchedule,
    run_adaptive,
    run_uniform_adaptive,
    run_uniform_compression_audit,
)
from .backends.floquet_markov import FloquetMarkovBackend
from .convergence import ConvergenceCache, atomic_write_result, fingerprint
from .correlations import superoperator_period_correlation
from .dark_channels import (
    dark_candidates,
    floquet_matrix_elements,
    harmonic_sum_rule,
    period_variance,
)
from .error_map import audit_grid_manifest, build_error_record
from .floquet import solve_floquet
from .heat_current import heat_current_spectrum
from .model_comparison import model_variants
from .n2_heat import N2HeatPoint, prepare_n2_triplet, run_n2_heat_point
from .n3_heat import N3HeatPoint, prepare_n3_sector, run_n3_heat_point

ENGINE_REVISION = "215cc9dbab236d77e0a89e276e3d1ff2b0e26d1f"
N2_ENGINE_REVISION = "f995eace0d7939b34b599cfbce6baef235f66f7f"
PHASE_QUADRATURE_EVIDENCE = {
    "model": "N3 reflection-even, J=0.5, M=12, K=3, epsrel=1e-5",
    "full_phase_fingerprint": (
        "b1903593b5ebdbfd0257697086531cf6ff4701fd2deb1153e97a1bb3aa625a0d"
    ),
    "three_phase_fingerprint": (
        "50eeb896cbb9385cb96da4731544cb11a7c2567780709562fe07af2759a07455"
    ),
    "correlation_residual": 2.140601839862832e-4,
    "heat_residual": 6.878849326613947e-4,
    "maximum_absolute_heat_difference": 3.707806353551828e-5,
}
ExactBackend = Literal["uniform_tempo", "oqupy"]


def publication_schedule() -> AdaptiveSchedule:
    return AdaptiveSchedule(
        memory_steps=(3, 4, 5),
        steps_per_period=(12, 18),
        epsrel=(1e-5, 3e-6),
        state_threshold=8e-2,
        correlation_threshold=8e-2,
        heat_threshold=8e-2,
        phase_threshold=2e-3,
        trace_threshold=5e-3,
    )


def uniform_publication_schedule() -> UniformAdaptiveSchedule:
    return UniformAdaptiveSchedule(
        steps_per_period=(60, 90, 120),
        tolerances=(3e-7, 1e-7, 3e-8),
        phase_samples=(3, 15),
        state_threshold=5e-2,
        correlation_threshold=8e-2,
        heat_threshold=8e-2,
        phase_threshold=1e-3,
        trace_threshold=5e-3,
        hermiticity_threshold=5e-3,
    )


def uniform_error_schedule() -> UniformAdaptiveSchedule:
    """Use a deeper compression ladder for the inexpensive N=2 error grid."""
    return replace(
        uniform_publication_schedule(),
        tolerances=(3e-7, 1e-7, 3e-8, 1e-8, 3e-9),
    )


def n4_pilot_schedule() -> UniformAdaptiveSchedule:
    """A bounded two-rung gate before spending publication-scale N=4 resources."""
    return UniformAdaptiveSchedule(
        steps_per_period=(30, 60),
        tolerances=(1e-5, 3e-6),
        phase_samples=(3, 15),
        state_threshold=8e-2,
        correlation_threshold=1e-1,
        heat_threshold=1e-1,
        phase_threshold=2e-3,
        trace_threshold=5e-3,
        hermiticity_threshold=5e-3,
    )


def n2_correlation_delay_periods(alpha: float) -> int:
    """Choose a weak-coupling correlation window with a fixed decay budget."""
    if alpha <= 0:
        raise ValueError("alpha must be positive")
    return max(4, math.ceil(0.3 / alpha))


def _runner(point: N3HeatPoint, cache: ConvergenceCache | None) -> dict[str, Any]:
    result = run_n3_heat_point(
        point,
        cache,
        commit=ENGINE_REVISION if point.backend == "oqupy" else None,
    )
    if point.backend == "uniform_tempo":
        return result
    diagnostics = result["diagnostics"]
    accepted = (
        float(diagnostics["trace_error"]) < 2e-2
        and float(diagnostics["minimum_density_eigenvalue"]) > -5e-2
        and float(diagnostics["phase_residual"]) < 1e-2
        and float(diagnostics["connected_tail_amplitude"]) < 1e-1
    )
    return {**result, "converged": accepted}


def _n2_runner(point: N2HeatPoint, cache: ConvergenceCache | None) -> dict[str, Any]:
    result = run_n2_heat_point(
        point,
        cache,
        commit=N2_ENGINE_REVISION if point.backend == "oqupy" else None,
    )
    if point.backend == "uniform_tempo":
        return result
    diagnostics = result["diagnostics"]
    accepted = (
        float(diagnostics["trace_error"]) < 2e-2
        and float(diagnostics["minimum_density_eigenvalue"]) > -5e-2
        and float(diagnostics["phase_residual"]) < 1e-2
        and float(diagnostics["connected_tail_amplitude"]) < 1e-1
    )
    return {**result, "converged": accepted}


def n2_publication_schedule() -> AdaptiveSchedule:
    return AdaptiveSchedule(
        memory_steps=(4, 5, 6),
        steps_per_period=(16, 24),
        epsrel=(1e-5, 3e-6),
        state_threshold=8e-2,
        correlation_threshold=8e-2,
        heat_threshold=8e-2,
        phase_threshold=2e-3,
        trace_threshold=5e-3,
    )


def _adaptive_payload(result: AdaptiveResult) -> dict[str, Any]:
    payload = dict(result.final_result)
    payload["adaptive_status"] = result.status
    payload["adaptive_converged"] = result.converged
    payload["evidence"] = [asdict(item) for item in result.evidence]
    payload["final_point"] = asdict(result.final_point)
    payload["failed_parameter"] = result.failed_parameter
    return payload


def _odd_equivalent_payload(
    reference: dict[str, Any],
    j: float,
) -> dict[str, Any]:
    """Reuse an odd-sector record after proving the projected model is identical."""
    payload = copy.deepcopy(reference)
    point = N3HeatPoint(**payload["final_point"])
    target_point = replace(point, j=j)
    prepared_reference = prepare_n3_sector(point)
    prepared_target = prepare_n3_sector(target_point)
    h0_residual = float(np.linalg.norm(prepared_reference.h0 - prepared_target.h0))
    coupling_residual = float(
        np.linalg.norm(prepared_reference.coupling - prepared_target.coupling)
    )
    drive_residual = float(
        np.linalg.norm(prepared_reference.drive - prepared_target.drive)
    )
    if (
        h0_residual > 1e-13
        or coupling_residual > 1e-13
        or drive_residual > 1e-13
    ):
        raise ValueError("odd-sector projected models are not equivalent")

    source_fingerprint = str(reference["fingerprint"])
    payload["point"]["j"] = j
    payload["final_point"]["j"] = j
    payload["model"]["j"] = j
    payload["bright_gap"] = prepared_target.bright_gap
    payload["model_hash"] = fingerprint(
        {
            "model": asdict(prepared_target.model),
            "bath": asdict(prepared_target.bath),
            "sector": "odd",
        },
        "scientific-model-v1",
    )
    payload["projected_model_hash"] = reference["projected_model_hash"]
    payload["fingerprint"] = fingerprint(
        {
            "kind": "exact-odd-sector-equivalence",
            "source_fingerprint": source_fingerprint,
            "target_j": j,
            "projected_model_hash": payload["projected_model_hash"],
        },
        str(reference.get("source_commit", "unknown")),
    )
    payload["numerical_reuse"] = {
        "reason": "reflection-odd projected Hamiltonian and coupling are J-independent",
        "source_j": point.j,
        "source_fingerprint": source_fingerprint,
        "h0_frobenius_residual": h0_residual,
        "coupling_frobenius_residual": coupling_residual,
        "drive_frobenius_residual": drive_residual,
    }
    return payload


def _complex_values(values: np.ndarray[Any, np.dtype[np.complex128]]) -> dict[str, Any]:
    return {
        "real": np.real(values).astype(float).tolist(),
        "imag": np.imag(values).astype(float).tolist(),
    }


def _complex_array(value: dict[str, Any]) -> np.ndarray[Any, np.dtype[np.complex128]]:
    return cast(
        np.ndarray[Any, np.dtype[np.complex128]],
        np.asarray(value["real"], dtype=float)
        + 1j * np.asarray(value["imag"], dtype=float),
    )


def _markov_result(point: N3HeatPoint, model_hash: str) -> dict[str, Any]:
    prepared = prepare_n3_sector(point)
    model = prepared.model

    def hamiltonian(time: float) -> np.ndarray[Any, np.dtype[np.complex128]]:
        return np.asarray(
            prepared.h0
            + model.drive_amplitude
            * np.cos(model.drive_frequency * time)
            * prepared.drive,
            dtype=np.complex128,
        )

    backend = FloquetMarkovBackend()
    run = backend.run(
        hamiltonian,
        prepared.coupling,
        prepared.bath,
        model.period,
        point.steps_per_period,
        harmonic_cutoff=5,
    )
    if run.step_maps is None:
        raise RuntimeError("Floquet-Markov backend returned no step maps")
    delay_steps = point.delay_periods * point.steps_per_period
    correlation = superoperator_period_correlation(
        run.step_maps,
        run.density_matrices[:-1],
        prepared.coupling,
        model.period / point.steps_per_period,
        delay_steps,
        model.drive_frequency,
    )
    frequencies = np.linspace(0, point.frequency_max, point.frequency_points)
    heat = heat_current_spectrum(correlation, prepared.bath, frequencies)
    return {
        "method": "floquet_markov_qr",
        "converged": run.converged,
        "model_hash": model_hash,
        "model": asdict(model),
        "bath": asdict(prepared.bath),
        "diagnostics": run.diagnostics,
        "phase_state": _complex_values(run.density_matrices[0]),
        "correlation": {
            "delay": correlation.delays.tolist(),
            "connected": _complex_values(correlation.connected),
        },
        "frequency": heat.frequencies.tolist(),
        "continuous": heat.continuous.tolist(),
        "delta_peaks": [asdict(peak) for peak in heat.delta_peaks],
    }


def _markov_n2_result(point: N2HeatPoint, model_hash: str) -> dict[str, Any]:
    prepared = prepare_n2_triplet(point)
    model = prepared.model

    def hamiltonian(time: float) -> np.ndarray[Any, np.dtype[np.complex128]]:
        return np.asarray(
            prepared.h0
            + model.drive_amplitude
            * np.cos(model.drive_frequency * time)
            * prepared.coupling,
            dtype=np.complex128,
        )

    backend = FloquetMarkovBackend()
    run = backend.run(
        hamiltonian,
        prepared.coupling,
        prepared.bath,
        model.period,
        point.steps_per_period,
        harmonic_cutoff=5,
    )
    if run.step_maps is None:
        raise RuntimeError("Floquet-Markov backend returned no step maps")
    delay_steps = point.delay_periods * point.steps_per_period
    correlation = superoperator_period_correlation(
        run.step_maps,
        run.density_matrices[:-1],
        prepared.coupling,
        model.period / point.steps_per_period,
        delay_steps,
        model.drive_frequency,
    )
    frequencies = np.linspace(0, point.frequency_max, point.frequency_points)
    heat = heat_current_spectrum(correlation, prepared.bath, frequencies)
    return {
        "method": "floquet_markov_qr",
        "converged": run.converged,
        "model_hash": model_hash,
        "model": asdict(model),
        "bath": asdict(prepared.bath),
        "diagnostics": run.diagnostics,
        "phase_state": _complex_values(run.density_matrices[0]),
        "correlation": {
            "delay": correlation.delays.tolist(),
            "connected": _complex_values(correlation.connected),
        },
        "frequency": heat.frequencies.tolist(),
        "continuous": heat.continuous.tolist(),
        "delta_peaks": [asdict(peak) for peak in heat.delta_peaks],
    }


def _dark_diagnostic(result: dict[str, Any]) -> dict[str, Any]:
    point = N3HeatPoint(**result["final_point"])
    prepared = prepare_n3_sector(point)

    def hamiltonian(time: float) -> np.ndarray[Any, np.dtype[np.complex128]]:
        return np.asarray(
            prepared.h0
            + prepared.model.drive_amplitude
            * np.cos(prepared.model.drive_frequency * time)
            * prepared.drive,
            dtype=np.complex128,
        )

    solution = solve_floquet(
        hamiltonian, prepared.model.period, max(96, 4 * point.steps_per_period)
    )
    harmonic_cutoff = min(40, len(solution.step_propagators) // 2 - 1)
    records = floquet_matrix_elements(
        solution,
        prepared.coupling,
        harmonic_cutoff=harmonic_cutoff,
        threshold=1e-14,
    )
    candidates = dark_candidates(records, relative_threshold=1e-5)
    strongest = sorted(records, key=lambda item: item.weight, reverse=True)[:24]
    phase_states = _complex_array(result["phase_states"])
    heat = np.asarray(result["continuous"], dtype=float)
    frequencies = np.asarray(result["frequency"], dtype=float)
    return {
        "j": point.j,
        "sector": point.sector,
        "model_hash": result["model_hash"],
        "integrated_continuous_heat": float(trapezoid(heat, frequencies)),
        "period_variance": period_variance(phase_states, prepared.coupling),
        "harmonic_sum_rule_residual": harmonic_sum_rule(
            solution, prepared.coupling, harmonic_cutoff
        ),
        "harmonic_cutoff": harmonic_cutoff,
        "strongest_transitions": [asdict(item) for item in strongest],
        "small_matrix_element_candidates": [
            {
                "transition": asdict(item.transition),
                "relative_weight": item.relative_weight,
            }
            for item in candidates[:24]
        ],
    }


def run_n3_heat_grid(
    output: Path,
    cache_directory: Path,
    *,
    schedule: AdaptiveSchedule | UniformAdaptiveSchedule | None = None,
    exact_backend: ExactBackend = "uniform_tempo",
) -> dict[str, Any]:
    cache = ConvergenceCache(cache_directory)
    if exact_backend == "uniform_tempo":
        active_schedule: AdaptiveSchedule | UniformAdaptiveSchedule = (
            uniform_publication_schedule() if schedule is None else schedule
        )
        if not isinstance(active_schedule, UniformAdaptiveSchedule):
            raise TypeError("uniform_tempo requires UniformAdaptiveSchedule")
    else:
        active_schedule = publication_schedule() if schedule is None else schedule
        if not isinstance(active_schedule, AdaptiveSchedule):
            raise TypeError("oqupy requires AdaptiveSchedule")
    records: list[dict[str, Any]] = []
    odd_reference: dict[str, Any] | None = None
    for sector in ("even", "odd"):
        for j in (0.25, 0.5, 1.0):
            if (
                exact_backend == "uniform_tempo"
                and sector == "odd"
                and odd_reference is not None
            ):
                payload = _odd_equivalent_payload(odd_reference, j)
                atomic_write_result(output / f"n3_{sector}_j{j:.2f}.json", payload)
                records.append(payload)
                continue
            if exact_backend == "uniform_tempo":
                uniform_schedule = cast(UniformAdaptiveSchedule, active_schedule)
                point = N3HeatPoint(
                    j=j,
                    sector=sector,
                    backend="uniform_tempo",
                    steps_per_period=uniform_schedule.steps_per_period[0],
                    epsrel=uniform_schedule.tolerances[0],
                    phase_samples=uniform_schedule.phase_samples[0],
                    uniform_low_rank_svd=True,
                    uniform_truncation="abs",
                    uniform_cap_rank=5_000,
                    uniform_max_rank=10_000,
                )
                adaptive = run_uniform_adaptive(
                    point,
                    uniform_schedule,
                    _runner,
                    cache,
                )
            else:
                point = N3HeatPoint(j=j, sector=sector, phase_samples=3)
                adaptive = run_adaptive(
                    point,
                    cast(AdaptiveSchedule, active_schedule),
                    _runner,
                    cache,
                )
            payload = _adaptive_payload(adaptive)
            if exact_backend == "uniform_tempo" and sector == "odd":
                odd_reference = payload
            atomic_write_result(output / f"n3_{sector}_j{j:.2f}.json", payload)
            records.append(payload)
    diagnostics = []
    for item in records:
        diagnostic = _dark_diagnostic(item)
        diagnostic["pt_convergence_status"] = item["adaptive_status"]
        diagnostic["heat_feature_accepted"] = item["adaptive_converged"]
        diagnostics.append(diagnostic)
    odd = [item for item in records if item["sector"] == "odd"]
    odd_difference = None
    if len(odd) == 3:
        curves = [np.asarray(item["continuous"], dtype=float) for item in odd]
        denominator = max(float(np.max(abs(curves[0]))), 1e-15)
        odd_difference = float(
            max(np.max(abs(curve - curves[0])) for curve in curves[1:]) / denominator
        )
    manifest = {
        "method": (
            "uniform_tempo_floquet_multitime"
            if exact_backend == "uniform_tempo"
            else "pt_tempo_multitime"
        ),
        "exact_backend": exact_backend,
        "converged": all(item["adaptive_converged"] for item in records),
        "schedule": asdict(active_schedule),
        "engine_revision": (
            records[0].get("source_commit", "unknown")
            if exact_backend == "uniform_tempo" and records
            else ENGINE_REVISION
        ),
        "phase_quadrature_evidence": (
            {
                "source": "per-point adaptive evidence",
                "phase_samples": list(
                    cast(UniformAdaptiveSchedule, active_schedule).phase_samples
                ),
            }
            if exact_backend == "uniform_tempo"
            else PHASE_QUADRATURE_EVIDENCE
        ),
        "points": records,
        "dark_diagnostics": diagnostics,
        "odd_cross_j_relative_max_difference": odd_difference,
    }
    atomic_write_result(output / "n3_heat_manifest.json", manifest)
    return manifest


def run_n3_error_map(
    exact_manifest: Path,
    output: Path,
) -> dict[str, Any]:
    """Compare every converged N=3 production point to the same-model Markov result."""
    source = json.loads(exact_manifest.read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise ValueError("N=3 exact manifest must be a JSON object")
    records: list[dict[str, Any]] = []
    for exact in source.get("points", []):
        j = float(exact["model"]["j"])
        sector = str(exact["sector"])
        if not bool(exact.get("adaptive_converged", exact.get("converged", False))):
            records.append(
                {
                    "j": j,
                    "sector": sector,
                    "status": "resource_ceiling",
                    "metrics": None,
                }
            )
            continue
        point = N3HeatPoint(**exact["final_point"])
        markov = _markov_result(point, str(exact["model_hash"]))
        compatible_exact = {**exact, "converged": True}
        comparison = build_error_record(compatible_exact, markov)
        record = {"j": j, "sector": sector, **comparison}
        records.append(record)
        atomic_write_result(
            output / f"n3_error_{sector}_j{j:.2f}.json",
            {
                "exact_fingerprint": exact.get("fingerprint"),
                "exact": compatible_exact,
                "markov": markov,
                "comparison": record,
            },
        )
    manifest = {
        "method": "n3_uniform_tempo_vs_floquet_markov_qr",
        "exact_backend": source.get("exact_backend"),
        "model_scope": "same N=3 sector, Hamiltonian, drive and bath parameters",
        "source_manifest": str(exact_manifest),
        "converged": bool(records) and all(
            item["status"] == "converged" for item in records
        ),
        "points": records,
    }
    atomic_write_result(output / "n3_error_map_manifest.json", manifest)
    return manifest


def run_n4_pilot(
    output: Path,
    cache_directory: Path,
    *,
    sector: Literal["even", "odd"],
    j: float = 0.25,
) -> dict[str, Any]:
    """Run a convergence-gated N=4 sector point and a same-model Markov check."""
    schedule = n4_pilot_schedule()
    point = N3HeatPoint(
        n=4,
        j=j,
        sector=sector,
        backend="uniform_tempo",
        alpha=0.05,
        steps_per_period=schedule.steps_per_period[0],
        epsrel=schedule.tolerances[0],
        phase_samples=schedule.phase_samples[0],
        delay_periods=6 if sector == "even" else 3,
        uniform_low_rank_svd=True,
        uniform_truncation="abs",
        uniform_cap_rank=5_000,
        uniform_max_rank=10_000,
    )
    adaptive = run_uniform_adaptive(
        point,
        schedule,
        _runner,
        ConvergenceCache(cache_directory),
    )
    exact = _adaptive_payload(adaptive)
    exact["converged"] = adaptive.converged
    payload: dict[str, Any] = {
        "method": "n4_uniform_tempo_convergence_pilot",
        "n": 4,
        "sector": sector,
        "j": j,
        "schedule": asdict(schedule),
        "adaptive_status": adaptive.status,
        "converged": adaptive.converged,
        "failed_parameter": adaptive.failed_parameter,
        "exact": exact,
        "markov": None,
        "comparison": None,
    }
    if adaptive.converged:
        final_point = adaptive.final_point
        markov = _markov_result(final_point, str(exact["model_hash"]))
        payload["markov"] = markov
        payload["comparison"] = build_error_record(exact, markov)
    atomic_write_result(output / f"n4_{sector}_j{j:.2f}.json", payload)
    return payload


def run_error_grid(
    output: Path,
    cache_directory: Path,
    *,
    schedule: AdaptiveSchedule | UniformAdaptiveSchedule | None = None,
    exact_backend: ExactBackend = "uniform_tempo",
) -> dict[str, Any]:
    cache = ConvergenceCache(cache_directory)
    if exact_backend == "uniform_tempo":
        active_schedule: AdaptiveSchedule | UniformAdaptiveSchedule = (
            uniform_error_schedule() if schedule is None else schedule
        )
        if not isinstance(active_schedule, UniformAdaptiveSchedule):
            raise TypeError("uniform_tempo requires UniformAdaptiveSchedule")
    else:
        active_schedule = n2_publication_schedule() if schedule is None else schedule
        if not isinstance(active_schedule, AdaptiveSchedule):
            raise TypeError("oqupy requires AdaptiveSchedule")
    points: list[dict[str, Any]] = []
    for alpha in (0.025, 0.05, 0.1):
        for ratio in (0.75, 1.0, 1.25):
            if exact_backend == "uniform_tempo":
                uniform_schedule = cast(UniformAdaptiveSchedule, active_schedule)
                base = N2HeatPoint(
                    j=0.5,
                    backend="uniform_tempo",
                    alpha=alpha,
                    drive_ratio=ratio,
                    steps_per_period=uniform_schedule.steps_per_period[0],
                    epsrel=uniform_schedule.tolerances[0],
                    phase_samples=uniform_schedule.phase_samples[0],
                    delay_periods=n2_correlation_delay_periods(alpha),
                    uniform_low_rank_svd=True,
                    uniform_truncation="abs",
                    uniform_cap_rank=5_000,
                    uniform_max_rank=10_000,
                )
                adaptive = cast(
                    Any,
                    run_uniform_adaptive(
                        cast(Any, base),
                        uniform_schedule,
                        cast(Any, _n2_runner),
                        cache,
                    ),
                )
            else:
                base = N2HeatPoint(
                    j=0.5,
                    alpha=alpha,
                    drive_ratio=ratio,
                )
                adaptive = cast(
                    Any,
                    run_adaptive(
                        cast(Any, base),
                        cast(AdaptiveSchedule, active_schedule),
                        cast(Any, _n2_runner),
                        cache,
                    ),
                )
            if not adaptive.converged:
                points.append(
                    {
                        "alpha": alpha,
                        "drive_ratio": ratio,
                        "status": "resource_ceiling",
                        "metrics": None,
                        "failed_parameter": (
                            adaptive.failed_parameter or "steady_state_gate"
                        ),
                        "adaptive_status": adaptive.status,
                        "evidence": [asdict(item) for item in adaptive.evidence],
                    }
                )
                continue
            exact = _adaptive_payload(adaptive)
            exact["converged"] = True
            markov = _markov_n2_result(adaptive.final_point, exact["model_hash"])
            record = build_error_record(exact, markov)
            points.append({"alpha": alpha, "drive_ratio": ratio, **record})
            atomic_write_result(
                output / f"error_a{alpha:.3f}_r{ratio:.2f}.json",
                {"exact": exact, "markov": markov, "comparison": record},
            )
    manifest: dict[str, Any] = {
        "method": (
            "uniform_tempo_vs_floquet_markov_qr"
            if exact_backend == "uniform_tempo"
            else "pt_tempo_vs_floquet_markov_qr"
        ),
        "exact_backend": exact_backend,
        "model_scope": "N=2 interacting triplet calibration",
        "points": points,
        "schedule": asdict(active_schedule),
        "engine_revision": (
            "per-point-source-commit"
            if exact_backend == "uniform_tempo"
            else N2_ENGINE_REVISION
        ),
        "phase_quadrature_evidence": (
            {
                "source": "per-point adaptive evidence",
                "phase_samples": list(
                    cast(UniformAdaptiveSchedule, active_schedule).phase_samples
                ),
            }
            if exact_backend == "uniform_tempo"
            else PHASE_QUADRATURE_EVIDENCE
        ),
    }
    audit = audit_grid_manifest(manifest)
    manifest["audit"] = audit
    manifest["converged"] = audit["masked_points"] == 0
    atomic_write_result(output / "error_map_manifest.json", manifest)
    return manifest


def run_model_comparison(
    output: Path,
    cache_directory: Path,
    *,
    schedule: AdaptiveSchedule | UniformAdaptiveSchedule | None = None,
    exact_backend: ExactBackend = "uniform_tempo",
    full_kac: bool = False,
) -> dict[str, Any]:
    cache = ConvergenceCache(cache_directory)
    if exact_backend == "uniform_tempo":
        active_schedule: AdaptiveSchedule | UniformAdaptiveSchedule = (
            uniform_publication_schedule() if schedule is None else schedule
        )
        if not isinstance(active_schedule, UniformAdaptiveSchedule):
            raise TypeError("uniform_tempo requires UniformAdaptiveSchedule")
        uniform_schedule = active_schedule
        bath_point = N3HeatPoint(
            j=0.5,
            sector="even",
            backend="uniform_tempo",
            steps_per_period=uniform_schedule.steps_per_period[0],
            epsrel=uniform_schedule.tolerances[0],
            phase_samples=uniform_schedule.phase_samples[0],
            uniform_low_rank_svd=True,
            uniform_truncation="abs",
            uniform_cap_rank=5_000,
            uniform_max_rank=10_000,
        )
    else:
        active_schedule = publication_schedule() if schedule is None else schedule
        if not isinstance(active_schedule, AdaptiveSchedule):
            raise TypeError("oqupy requires AdaptiveSchedule")
        bath_point = N3HeatPoint(j=0.5, sector="even", phase_samples=3)
    prepared = prepare_n3_sector(bath_point)
    variants = model_variants(
        n=3,
        j=0.5,
        bath=prepared.bath,
        drive_frequency=prepared.bright_gap,
    )
    records: list[dict[str, Any]] = []
    for variant in variants:
        point = replace(
            bath_point,
            normalization=variant.config.normalization,
            counterterm=variant.config.counterterm,
            drive_frequency=variant.config.drive_frequency,
        )
        if exact_backend == "uniform_tempo":
            if variant.config.normalization == "kac" and not full_kac:
                adaptive = run_uniform_compression_audit(
                    point,
                    cast(UniformAdaptiveSchedule, active_schedule),
                    _runner,
                    cache,
                )
            else:
                adaptive = run_uniform_adaptive(
                    point,
                    cast(UniformAdaptiveSchedule, active_schedule),
                    _runner,
                    cache,
                )
            payload = _adaptive_payload(adaptive)
        else:
            raw = _runner(point, cache)
            payload = {
                **raw,
                "adaptive_status": "exploratory_unconverged",
                "adaptive_converged": False,
                "evidence": [],
                "final_point": asdict(point),
                "failed_parameter": "publication_convergence_resource_ceiling",
            }
        payload["variant"] = variant.name
        payload["variant_metadata"] = variant.metadata
        eta = variant.config.eta
        payload["continuous_eta_rescaled"] = (
            np.asarray(payload["continuous"], dtype=float) / eta**2
        ).tolist()
        atomic_write_result(output / f"model_{variant.name}.json", payload)
        records.append(payload)
    bounded_complete = all(
        item.get("adaptive_converged") is True
        for item in records
        if str(item.get("variant", "")).startswith("bounded_")
    )
    kac_locally_audited = all(
        item.get("adaptive_converged") is True
        or (
            item.get("adaptive_status") == "resource_ceiling"
            and item.get("failed_parameter") == "steps_per_period"
            and any(
                evidence.get("parameter") == "epsrel"
                and evidence.get("passed") is True
                for evidence in item.get("evidence", [])
            )
        )
        for item in records
        if str(item.get("variant", "")).startswith("kac_")
    )
    locally_complete = (
        len(records) == 4 and bounded_complete and kac_locally_audited
    )
    manifest = {
        "method": (
            "uniform_tempo_model_variants"
            if exact_backend == "uniform_tempo"
            else "pt_tempo_model_variants"
        ),
        "exact_backend": exact_backend,
        "converged": all(item["adaptive_converged"] for item in records),
        "complete": len(records) == 4,
        "locally_complete": locally_complete,
        "status": (
            "converged"
            if records and all(item["adaptive_converged"] for item in records)
            else (
                "local_resource_ceiling"
                if locally_complete
                else "resource_ceiling"
            )
        ),
        "points": records,
        "schedule": asdict(active_schedule),
        "engine_revision": (
            records[0].get("source_commit", "unknown")
            if exact_backend == "uniform_tempo" and records
            else ENGINE_REVISION
        ),
        "phase_quadrature_evidence": (
            {
                "source": "per-point adaptive evidence",
                "phase_samples": list(
                    cast(UniformAdaptiveSchedule, active_schedule).phase_samples
                ),
            }
            if exact_backend == "uniform_tempo"
            else PHASE_QUADRATURE_EVIDENCE
        ),
        "resource_policy": {
            "full_kac": full_kac,
            "local_default": (
                "Kac variants stop after compression convergence; use "
                "--full-kac on a cluster for timestep and phase refinement"
            ),
        },
    }
    atomic_write_result(output / "model_comparison_manifest.json", manifest)
    return manifest


def audit_paper_results(directory: Path) -> tuple[bool, list[str]]:
    """Audit the three publication manifests against the declared final gates."""

    def evidence_failures(
        records: Any,
        label: str,
    ) -> list[str]:
        local: list[str] = []
        if not isinstance(records, list):
            return [f"{label} has no convergence evidence"]
        passed = [item for item in records if item.get("passed") is True]
        parameters = {item.get("parameter") for item in passed}
        required = {"epsrel", "steps_per_period", "phase_samples"}
        if not required.issubset(parameters):
            local.append(
                f"{label} lacks passed compression/timestep/phase evidence"
            )
            return local
        timestep_records = [
            item for item in passed if item.get("parameter") == "steps_per_period"
        ]
        compression_steps = {
            int(item["refined_steps_per_period"])
            for item in passed
            if item.get("parameter") == "epsrel"
            and item.get("refined_steps_per_period") is not None
        }
        for item in timestep_records:
            compared = {
                int(item["coarse_steps_per_period"]),
                int(item["refined_steps_per_period"]),
            }
            if not compared.issubset(compression_steps):
                local.append(
                    f"{label} did not converge compression on both timestep grids"
                )
                break
        return local

    def point_failures(point: dict[str, Any], label: str) -> list[str]:
        local: list[str] = []
        if point.get("adaptive_status") != "converged":
            local.append(f"{label} status is not converged")
        if point.get("adaptive_converged") is not True:
            local.append(f"{label} adaptive_converged is not true")
        diagnostics = point.get("diagnostics", {})
        gates = {
            "fixed_point_residual": (1e-3, "maximum"),
            "trace_error": (5e-3, "maximum"),
            "hermiticity_error": (5e-3, "maximum"),
            "connected_tail_amplitude": (5e-2, "maximum"),
            "minimum_density_eigenvalue": (-5e-3, "minimum"),
        }
        for name, (threshold, direction) in gates.items():
            try:
                value = float(diagnostics[name])
            except (KeyError, TypeError, ValueError):
                local.append(f"{label} lacks finite diagnostic {name}")
                continue
            if not np.isfinite(value):
                local.append(f"{label} diagnostic {name} is non-finite")
            elif direction == "maximum" and value > threshold:
                local.append(f"{label} diagnostic {name} exceeds {threshold:g}")
            elif direction == "minimum" and value < threshold:
                local.append(f"{label} diagnostic {name} is below {threshold:g}")
        local.extend(evidence_failures(point.get("evidence"), label))
        return local

    failures: list[str] = []
    required = (
        "n3_heat_manifest.json",
        "error_map_manifest.json",
        "model_comparison_manifest.json",
    )
    import json

    loaded: dict[str, dict[str, Any]] = {}
    for name in required:
        path = directory / name
        if not path.is_file():
            failures.append(f"missing {name}")
            continue
        loaded[name] = json.loads(path.read_text(encoding="utf-8"))
    if "n3_heat_manifest.json" in loaded:
        value = loaded["n3_heat_manifest.json"]
        points = value.get("points", [])
        if value.get("exact_backend") != "uniform_tempo":
            failures.append("N=3 manifest does not use uniform_tempo")
        if value.get("converged") is not True:
            failures.append("N=3 manifest is not converged")
        if len(points) != 6:
            failures.append("N=3 manifest must contain six points")
        observed = {
            (point.get("sector"), float(point.get("model", {}).get("j", np.nan)))
            for point in points
        }
        expected = {
            (sector, j)
            for sector in ("even", "odd")
            for j in (0.25, 0.5, 1.0)
        }
        if observed != expected:
            failures.append("N=3 manifest sector/J grid is incomplete")
        for point in points:
            label = (
                f"N=3 {point.get('sector')} "
                f"J={point.get('model', {}).get('j')}"
            )
            failures.extend(point_failures(point, label))
        if value.get("odd_cross_j_relative_max_difference") is None:
            failures.append("N=3 odd-sector invariance diagnostic is missing")
        elif float(value["odd_cross_j_relative_max_difference"]) > 1e-12:
            failures.append("N=3 odd-sector J-invariance check failed")
    if "error_map_manifest.json" in loaded:
        try:
            value = loaded["error_map_manifest.json"]
            audit = audit_grid_manifest(value)
            if value.get("exact_backend") != "uniform_tempo":
                failures.append("error map does not use uniform_tempo")
            if audit["masked_points"] != 0 or value.get("converged") is not True:
                failures.append("error map contains unconverged or masked points")
            for point in value.get("points", []):
                label = (
                    f"error grid alpha={point.get('alpha')} "
                    f"ratio={point.get('drive_ratio')}"
                )
                metrics = point.get("metrics", {})
                if set(metrics) != {"trace_distance", "correlation", "heat"}:
                    failures.append(f"{label} lacks the three error metrics")
                elif not all(np.isfinite(float(item)) for item in metrics.values()):
                    failures.append(f"{label} has a non-finite error metric")
                failures.extend(
                    evidence_failures(point.get("convergence_evidence"), label)
                )
        except ValueError as exc:
            failures.append(str(exc))
    if "model_comparison_manifest.json" in loaded:
        value = loaded["model_comparison_manifest.json"]
        points = value.get("points", [])
        if value.get("exact_backend") != "uniform_tempo":
            failures.append("model comparison does not use uniform_tempo")
        if len(points) != 4:
            failures.append("model manifest must contain four variants")
        if not value.get("complete"):
            failures.append("model comparison is incomplete")
        if value.get("locally_complete") is not True:
            failures.append("model comparison has not reached its declared local endpoint")
        if len({point.get("variant") for point in points}) != 4:
            failures.append("model comparison variants are not distinct")
        for point in points:
            label = f"model variant {point.get('variant')}"
            if point.get("adaptive_converged") is True:
                failures.extend(point_failures(point, label))
                continue
            if not str(point.get("variant", "")).startswith("kac_"):
                failures.append(f"{label} is not converged")
                continue
            if (
                point.get("adaptive_status") != "resource_ceiling"
                or point.get("failed_parameter") != "steps_per_period"
            ):
                failures.append(f"{label} lacks an audited timestep resource ceiling")
            compression = [
                item
                for item in point.get("evidence", [])
                if item.get("parameter") == "epsrel" and item.get("passed") is True
            ]
            if not compression:
                failures.append(f"{label} lacks passed compression evidence")
    return not failures, failures

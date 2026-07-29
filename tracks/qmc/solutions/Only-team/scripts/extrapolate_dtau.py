#!/usr/bin/env python3
"""Extrapolate fitted critical fields linearly in the actual time-step squared."""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from scipy.optimize import least_squares

from fit_binder_scaling import (
    YI,
    YT,
    BootstrapResult,
    FitResult,
    FitSpec,
    _read_csv,
    binder_model,
    bootstrap_variant,
    fit_variant,
)


STEP_SIZES = {
    "triangular": (32, 40, 48),
    "honeycomb": (24, 28, 32),
}
STEP_FIELDS = {
    "triangular": (4.76711, 4.76761, 4.76811, 4.76861, 4.76911),
    "honeycomb": (2.1315, 2.1320, 2.1325, 2.1330, 2.1335),
}
REQUESTED_STEPS = (0.013, 0.016, 0.020)
TERMS = frozenset({"a2"})


@dataclass(frozen=True)
class StepFitSpec:
    lattice: str
    FixedDltau: float
    sizes: tuple[int, ...]
    fields: tuple[float, ...]
    terms: frozenset[str] = TERMS


@dataclass
class StepCriticalField:
    spec: StepFitSpec
    fit: FitResult
    bootstrap: BootstrapResult
    actual_dtau2_mean: float
    actual_dtau2_min: float
    actual_dtau2_max: float


@dataclass
class ExtrapolationResult:
    h_c_zero: float
    h_c_zero_error: float
    slope: float
    slope_error: float
    covariance: np.ndarray
    chi2: float
    dof: int
    chi2_per_dof: float


@dataclass
class RatioResult:
    median: float
    mean: float
    standard_error: float
    ci68: tuple[float, float]
    ci95: tuple[float, float]
    delta_sqrt5: float
    delta_over_sigma: float
    draws: np.ndarray


@dataclass
class JointFitResult:
    lattice: str
    parameters: dict[str, float]
    errors: dict[str, float]
    chi2: float
    dof: int
    chi2_per_dof: float
    converged: bool
    boundary_contact: bool


def _matches(value: float, candidates: Sequence[float]) -> bool:
    return any(math.isclose(value, candidate, rel_tol=0.0, abs_tol=1e-10) for candidate in candidates)


def _step_rows(rows: list[dict[str, Any]], spec: StepFitSpec) -> list[dict[str, Any]]:
    selected = [
        row
        for row in rows
        if row["lattice"] == spec.lattice
        and int(row["L"]) in spec.sizes
        and math.isclose(
            float(row["FixedDltau"]), spec.FixedDltau, rel_tol=0.0, abs_tol=1e-12
        )
        and _matches(float(row["hTrfd"]), spec.fields)
    ]
    expected = len(spec.sizes) * len(spec.fields)
    if len(selected) != expected:
        raise ValueError(
            f"{spec.lattice} dt={spec.FixedDltau} has {len(selected)} cells; "
            f"expected {expected}"
        )
    return selected


def _normalise_requested_step(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalised = []
    for row in rows:
        copy = dict(row)
        copy["FixedDltau"] = 0.013
        normalised.append(copy)
    return normalised


def fit_step_group(
    rows: list[dict[str, Any]],
    fit_spec: StepFitSpec,
) -> tuple[FitResult, list[dict[str, Any]]]:
    selected = _step_rows(rows, fit_spec)
    normalised = _normalise_requested_step(selected)
    fit = fit_variant(
        normalised,
        fit_spec.lattice,
        min(fit_spec.sizes),
        fit_spec.terms,
    )
    fit.variant_id = f"{fit_spec.lattice}-dt{fit_spec.FixedDltau:.3f}-a2"
    return fit, selected


def linear_dtau2_fit(points: Sequence[dict[str, float]]) -> ExtrapolationResult:
    if len(points) < 3:
        raise ValueError("at least three time-step points are required")
    x = np.array([float(point["dtau2"]) for point in points])
    y = np.array([float(point["h_c"]) for point in points])
    errors = np.array([float(point["error"]) for point in points])
    if np.any(~np.isfinite(errors)) or np.any(errors <= 0.0):
        raise ValueError("time-step uncertainties must be finite and positive")
    design = np.column_stack((np.ones_like(x), x))
    weighted_design = design / errors[:, None]
    weighted_y = y / errors
    parameters, *_ = np.linalg.lstsq(weighted_design, weighted_y, rcond=None)
    residuals = (y - design @ parameters) / errors
    chi2 = float(residuals @ residuals)
    dof = len(points) - 2
    covariance = np.linalg.inv(weighted_design.T @ weighted_design)
    parameter_errors = np.sqrt(np.diag(covariance))
    return ExtrapolationResult(
        h_c_zero=float(parameters[0]),
        h_c_zero_error=float(parameter_errors[0]),
        slope=float(parameters[1]),
        slope_error=float(parameter_errors[1]),
        covariance=covariance,
        chi2=chi2,
        dof=dof,
        chi2_per_dof=chi2 / dof if dof > 0 else math.nan,
    )


def ratio_bootstrap(
    triangular_draws: np.ndarray,
    honeycomb_draws: np.ndarray,
) -> RatioResult:
    count = min(len(triangular_draws), len(honeycomb_draws))
    if count < 2:
        raise ValueError("at least two paired bootstrap draws are required")
    draws = np.asarray(triangular_draws[:count], dtype=float) / np.asarray(
        honeycomb_draws[:count], dtype=float
    )
    median = float(np.median(draws))
    standard_error = float(np.std(draws, ddof=1))
    delta = median - math.sqrt(5.0)
    return RatioResult(
        median=median,
        mean=float(np.mean(draws)),
        standard_error=standard_error,
        ci68=tuple(float(value) for value in np.quantile(draws, [0.16, 0.84])),
        ci95=tuple(float(value) for value in np.quantile(draws, [0.025, 0.975])),
        delta_sqrt5=delta,
        delta_over_sigma=delta / standard_error,
        draws=draws,
    )


def _step_bootstrap(
    cells: list[dict[str, Any]],
    bins: list[dict[str, Any]],
    spec: StepFitSpec,
    *,
    samples: int,
    rng: np.random.Generator,
) -> StepCriticalField:
    fit, selected = fit_step_group(cells, spec)
    labels = {(str(row["run_id"]), str(row["cell_id"])) for row in selected}
    selected_bins = [
        row for row in bins if (str(row["run_id"]), str(row["cell_id"])) in labels
    ]
    normalised_cells = _normalise_requested_step(selected)
    normalised_bins = _normalise_requested_step(selected_bins)
    bootstrap = bootstrap_variant(
        normalised_bins,
        FitSpec(
            normalised_cells,
            spec.lattice,
            min(spec.sizes),
            spec.terms,
        ),
        samples,
        rng,
    )
    bootstrap.variant_id = fit.variant_id
    dtau2 = np.array([float(row["Dltau"]) ** 2 for row in selected])
    return StepCriticalField(
        spec=spec,
        fit=fit,
        bootstrap=bootstrap,
        actual_dtau2_mean=float(np.mean(dtau2)),
        actual_dtau2_min=float(np.min(dtau2)),
        actual_dtau2_max=float(np.max(dtau2)),
    )


def _bootstrap_extrapolation(
    steps: list[StepCriticalField],
) -> tuple[np.ndarray, np.ndarray]:
    count = min(len(step.bootstrap.draws) for step in steps)
    errors = [step.bootstrap.h_c_std for step in steps]
    intercepts = np.empty(count)
    slopes = np.empty(count)
    for replica in range(count):
        points = [
            {
                "dtau2": step.actual_dtau2_mean,
                "h_c": float(step.bootstrap.draws[replica]),
                "error": error,
            }
            for step, error in zip(steps, errors, strict=True)
        ]
        result = linear_dtau2_fit(points)
        intercepts[replica] = result.h_c_zero
        slopes[replica] = result.slope
    return intercepts, slopes


def joint_actual_dtau_fit(
    rows: list[dict[str, Any]],
    lattice: str,
    initial: ExtrapolationResult,
) -> JointFitResult:
    selected = []
    for requested_dt in REQUESTED_STEPS:
        spec = StepFitSpec(
            lattice,
            requested_dt,
            STEP_SIZES[lattice],
            STEP_FIELDS[lattice],
        )
        selected.extend(_step_rows(rows, spec))
    sizes = np.array([float(row["L"]) for row in selected])
    fields = np.array([float(row["hTrfd"]) for row in selected])
    dtau2 = np.array([float(row["Dltau"]) ** 2 for row in selected])
    observed = np.array([float(row["binder_Q"]) for row in selected])
    errors = np.array([float(row["binder_Q_error"]) for row in selected])
    field_min = float(np.min(fields))
    field_max = float(np.max(fields))
    span = field_max - field_min
    names = ("h_c_zero", "c_tau", "Q_star", "a1", "b1", "a2")
    x0 = np.array(
        [
            initial.h_c_zero,
            initial.slope,
            float(np.median(observed)),
            -0.05,
            0.0,
            0.0,
        ]
    )
    lower = np.array([field_min - 2.0 * span, -500.0, -1.0, -100.0, -100.0, -100.0])
    upper = np.array([field_max + 2.0 * span, 500.0, 2.0, 100.0, 100.0, 100.0])

    def residual(vector: np.ndarray) -> np.ndarray:
        h_c = vector[0] + vector[1] * dtau2
        x = fields - h_c
        model = (
            vector[2]
            + vector[3] * x * sizes**YT
            + vector[4] * sizes**YI
            + vector[5] * x**2 * sizes ** (2.0 * YT)
        )
        return (observed - model) / errors

    solution = least_squares(
        residual,
        x0,
        bounds=(lower, upper),
        xtol=1e-13,
        ftol=1e-13,
        gtol=1e-13,
        max_nfev=10000,
        x_scale="jac",
    )
    chi2 = float(solution.fun @ solution.fun)
    dof = len(selected) - len(names)
    covariance = np.linalg.pinv(solution.jac.T @ solution.jac) * (chi2 / dof)
    parameter_errors = np.sqrt(np.clip(np.diag(covariance), 0.0, math.inf))
    distance = np.minimum(solution.x - lower, upper - solution.x)
    boundary_contact = bool(
        np.any(distance <= 1e-7 * np.maximum(1.0, np.abs(solution.x)))
    )
    return JointFitResult(
        lattice=lattice,
        parameters=dict(zip(names, map(float, solution.x), strict=True)),
        errors=dict(zip(names, map(float, parameter_errors), strict=True)),
        chi2=chi2,
        dof=dof,
        chi2_per_dof=chi2 / dof,
        converged=bool(solution.success),
        boundary_contact=boundary_contact,
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    name: format(value, ".17g") if isinstance(value, float) else value
                    for name, value in row.items()
                }
            )


def run_analysis(
    cells: list[dict[str, Any]],
    bins: list[dict[str, Any]],
    *,
    samples: int,
    seed: int,
) -> dict[str, Any]:
    output: dict[str, Any] = {"steps": {}, "extrapolations": {}, "draws": {}, "joint": {}}
    child_seeds = iter(np.random.SeedSequence(seed).spawn(6))
    for lattice in ("triangular", "honeycomb"):
        steps = []
        for requested_dt in REQUESTED_STEPS:
            spec = StepFitSpec(
                lattice,
                requested_dt,
                STEP_SIZES[lattice],
                STEP_FIELDS[lattice],
            )
            step = _step_bootstrap(
                cells,
                bins,
                spec,
                samples=samples,
                rng=np.random.default_rng(next(child_seeds)),
            )
            steps.append(step)
            print(
                f"{lattice} dt={requested_dt:.3f}: "
                f"h_c={step.fit.parameters['h_c']:.9f}, "
                f"bootstrap={step.bootstrap.successful_samples}/{samples}",
                flush=True,
            )
        points = [
            {
                "dtau2": step.actual_dtau2_mean,
                "h_c": step.fit.parameters["h_c"],
                "error": step.bootstrap.h_c_std,
            }
            for step in steps
        ]
        extrapolation = linear_dtau2_fit(points)
        intercept_draws, slope_draws = _bootstrap_extrapolation(steps)
        joint = joint_actual_dtau_fit(cells, lattice, extrapolation)
        output["steps"][lattice] = steps
        output["extrapolations"][lattice] = extrapolation
        output["draws"][lattice] = {
            "h_c_zero": intercept_draws,
            "slope": slope_draws,
        }
        output["joint"][lattice] = joint
        print(
            f"{lattice} dt->0: h_c={extrapolation.h_c_zero:.9f}, "
            f"chi2/dof={extrapolation.chi2_per_dof:.3g}, "
            f"joint={joint.parameters['h_c_zero']:.9f}",
            flush=True,
        )
    output["ratio"] = ratio_bootstrap(
        output["draws"]["triangular"]["h_c_zero"],
        output["draws"]["honeycomb"]["h_c_zero"],
    )
    return output


def _read_optional_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None:
        return []
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def _finite_size_stability(
    fits: list[dict[str, str]],
    sensitivities: list[dict[str, str]],
) -> dict[str, Any]:
    accepted_families = {"a2", "a2+b2", "a2+c1"}
    result: dict[str, Any] = {
        "accepted_correction_families": sorted(accepted_families),
        "by_lattice": {},
    }
    for lattice in ("triangular", "honeycomb"):
        adjacent = [
            {
                "variant_id": row["variant_id"],
                "Lmin": int(row["Lmin"]),
                "h_c_at_dtau_approximately_0p013": float(row["h_c"]),
            }
            for row in fits
            if row["lattice"] == lattice and row["terms"] == "a2"
        ]
        corrections = [
            {
                "variant_id": row["variant_id"],
                "terms": row["terms"],
                "h_c_at_dtau_approximately_0p013": float(row["h_c"]),
            }
            for row in fits
            if row["lattice"] == lattice
            and int(row["Lmin"]) == 16
            and row["terms"] in accepted_families
            and float(row["bootstrap_success_fraction"]) >= 0.95
        ]
        largest = [
            {
                "variant_id": row["variant_id"],
                "h_c_at_dtau_approximately_0p013": float(row["h_c"]),
            }
            for row in sensitivities
            if row["lattice"] == lattice and row["drop_largest"] == "True"
        ]
        rounded = {
            format(item["h_c_at_dtau_approximately_0p013"], ".5f")
            for item in adjacent + corrections + largest
        }
        result["by_lattice"][lattice] = {
            "adjacent_Lmin": adjacent,
            "accepted_correction_terms": corrections,
            "drop_largest": largest,
            "main_grid_fifth_decimal_values": sorted(rounded),
            "main_grid_fifth_decimal_stable": len(rounded) == 1,
        }
    return result


def write_outputs(
    output_dir: Path,
    analysis: dict[str, Any],
    *,
    finite_size_fits_path: Path | None = None,
    sensitivities_path: Path | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fit_rows = []
    bootstrap_rows = []
    for lattice in ("triangular", "honeycomb"):
        steps: list[StepCriticalField] = analysis["steps"][lattice]
        for step in steps:
            fit_rows.append(
                {
                    "record_type": "step",
                    "lattice": lattice,
                    "FixedDltau": step.spec.FixedDltau,
                    "actual_dtau2_mean": step.actual_dtau2_mean,
                    "actual_dtau2_min": step.actual_dtau2_min,
                    "actual_dtau2_max": step.actual_dtau2_max,
                    "h_c": step.fit.parameters["h_c"],
                    "h_c_error": step.bootstrap.h_c_std,
                    "slope": math.nan,
                    "slope_error": math.nan,
                    "chi2": step.fit.chi2,
                    "dof": step.fit.dof,
                    "chi2_per_dof": step.fit.chi2_per_dof,
                    "converged": step.fit.converged,
                    "boundary_contact": step.fit.boundary_contact,
                    "inside_field_scan": step.fit.h_c_inside_scan,
                    "bootstrap_successful": step.bootstrap.successful_samples,
                    "bootstrap_failed": step.bootstrap.failed_samples,
                }
            )
            for replica, value in enumerate(step.bootstrap.draws):
                bootstrap_rows.append(
                    {
                        "record_type": "step",
                        "lattice": lattice,
                        "FixedDltau": step.spec.FixedDltau,
                        "replica": replica,
                        "h_c": float(value),
                        "slope": math.nan,
                    }
                )
        extrapolation: ExtrapolationResult = analysis["extrapolations"][lattice]
        fit_rows.append(
            {
                "record_type": "extrapolation",
                "lattice": lattice,
                "FixedDltau": 0.0,
                "actual_dtau2_mean": 0.0,
                "actual_dtau2_min": 0.0,
                "actual_dtau2_max": 0.0,
                "h_c": extrapolation.h_c_zero,
                "h_c_error": float(np.std(analysis["draws"][lattice]["h_c_zero"], ddof=1)),
                "slope": extrapolation.slope,
                "slope_error": extrapolation.slope_error,
                "chi2": extrapolation.chi2,
                "dof": extrapolation.dof,
                "chi2_per_dof": extrapolation.chi2_per_dof,
                "converged": True,
                "boundary_contact": False,
                "inside_field_scan": True,
                "bootstrap_successful": len(analysis["draws"][lattice]["h_c_zero"]),
                "bootstrap_failed": 0,
            }
        )
        joint: JointFitResult = analysis["joint"][lattice]
        fit_rows.append(
            {
                "record_type": "joint_sensitivity",
                "lattice": lattice,
                "FixedDltau": math.nan,
                "actual_dtau2_mean": math.nan,
                "actual_dtau2_min": math.nan,
                "actual_dtau2_max": math.nan,
                "h_c": joint.parameters["h_c_zero"],
                "h_c_error": joint.errors["h_c_zero"],
                "slope": joint.parameters["c_tau"],
                "slope_error": joint.errors["c_tau"],
                "chi2": joint.chi2,
                "dof": joint.dof,
                "chi2_per_dof": joint.chi2_per_dof,
                "converged": joint.converged,
                "boundary_contact": joint.boundary_contact,
                "inside_field_scan": True,
                "bootstrap_successful": 0,
                "bootstrap_failed": 0,
            }
        )
        for replica, (intercept, slope) in enumerate(
            zip(
                analysis["draws"][lattice]["h_c_zero"],
                analysis["draws"][lattice]["slope"],
                strict=True,
            )
        ):
            bootstrap_rows.append(
                {
                    "record_type": "extrapolation",
                    "lattice": lattice,
                    "FixedDltau": 0.0,
                    "replica": replica,
                    "h_c": float(intercept),
                    "slope": float(slope),
                }
            )
    _write_csv(output_dir / "dtau_fits.csv", fit_rows)
    _write_csv(output_dir / "dtau_bootstrap.csv", bootstrap_rows)

    ratio: RatioResult = analysis["ratio"]
    finite_size_stability = _finite_size_stability(
        _read_optional_csv(finite_size_fits_path),
        _read_optional_csv(sensitivities_path),
    )
    pre_triangular = 4.76811
    pre_triangular_error = 9.0e-5
    pre_honeycomb = 2.13250
    pre_honeycomb_error = 4.0e-5
    pre_ratio = pre_triangular / pre_honeycomb
    pre_ratio_error = pre_ratio * math.hypot(
        pre_triangular_error / pre_triangular,
        pre_honeycomb_error / pre_honeycomb,
    )
    final = {
        "schema_version": 1,
        "fit_selection": {
            "terms": ["a2"],
            "Lmin": 16,
            "selection_basis": "fit_quality_stability_and_parsimony_before_ratio",
        },
        "critical_fields": {},
        "ratio": {
            "median": ratio.median,
            "mean": ratio.mean,
            "standard_error": ratio.standard_error,
            "ci68": ratio.ci68,
            "ci95": ratio.ci95,
            "sqrt5": math.sqrt(5.0),
            "delta_sqrt5": ratio.delta_sqrt5,
            "delta_over_sigma": ratio.delta_over_sigma,
            "precision_target": 1.19e-5,
            "precision_target_pass": ratio.standard_error <= 1.19e-5,
            "sqrt5_verdict": (
                "cannot_distinguish"
                if ratio.ci95[0] <= math.sqrt(5.0) <= ratio.ci95[1]
                else "excludes"
            ),
        },
        "finite_size_stability": finite_size_stability,
        "pre_comparison": {
            "triangular": {
                "h_c": pre_triangular,
                "standard_error": pre_triangular_error,
            },
            "honeycomb": {
                "h_c": pre_honeycomb,
                "standard_error": pre_honeycomb_error,
            },
            "ratio": {
                "value": pre_ratio,
                "standard_error": pre_ratio_error,
            },
        },
    }
    targets = {"triangular": 1.8e-5, "honeycomb": 8.0e-6}
    for lattice in ("triangular", "honeycomb"):
        draws = analysis["draws"][lattice]["h_c_zero"]
        extrapolation = analysis["extrapolations"][lattice]
        error = float(np.std(draws, ddof=1))
        joint = analysis["joint"][lattice]
        final["critical_fields"][lattice] = {
            "h_c_zero": extrapolation.h_c_zero,
            "bootstrap_mean": float(np.mean(draws)),
            "standard_error": error,
            "ci68": tuple(float(value) for value in np.quantile(draws, [0.16, 0.84])),
            "ci95": tuple(float(value) for value in np.quantile(draws, [0.025, 0.975])),
            "slope": extrapolation.slope,
            "dtau2_chi2_per_dof": extrapolation.chi2_per_dof,
            "joint_h_c_zero": joint.parameters["h_c_zero"],
            "joint_difference": joint.parameters["h_c_zero"] - extrapolation.h_c_zero,
            "precision_target": targets[lattice],
            "precision_target_pass": error <= targets[lattice],
            "improvement_factor_over_PRE": (
                pre_triangular_error / error
                if lattice == "triangular"
                else pre_honeycomb_error / error
            ),
        }
    final["pre_comparison"]["ratio"]["improvement_factor"] = (
        pre_ratio_error / ratio.standard_error
    )
    joint_stable = all(
        abs(final["critical_fields"][lattice]["joint_difference"]) < 0.5e-5
        for lattice in ("triangular", "honeycomb")
    )
    main_grid_stable = all(
        finite_size_stability["by_lattice"][lattice][
            "main_grid_fifth_decimal_stable"
        ]
        for lattice in ("triangular", "honeycomb")
    )
    final["fifth_decimal_stability"] = {
        "pass": joint_stable and main_grid_stable,
        "joint_time_step_pass": joint_stable,
        "main_grid_variant_pass": main_grid_stable,
        "reason": (
            "Two-stage versus joint time-step fits and/or main-grid finite-size "
            "variants do not round to one common fifth decimal."
        ),
    }
    final["limitations"] = [
        "All triangular step-specific critical fields lie outside their measured field windows.",
        "The two-stage and joint actual-Dltau fits disagree beyond the fifth-decimal target.",
        "The achieved bootstrap uncertainties exceed every declared precision target.",
    ]
    (output_dir / "final_results.json").write_text(
        json.dumps(final, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cells", type=Path, required=True)
    parser.add_argument("--bins", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260731)
    parser.add_argument("--finite-size-fits", type=Path)
    parser.add_argument("--finite-size-sensitivities", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    analysis = run_analysis(
        _read_csv(args.cells),
        _read_csv(args.bins),
        samples=args.bootstrap,
        seed=args.seed,
    )
    write_outputs(
        args.output_dir,
        analysis,
        finite_size_fits_path=args.finite_size_fits,
        sensitivities_path=args.finite_size_sensitivities,
    )
    print(
        json.dumps(
            {
                "ratio": analysis["ratio"].median,
                "ratio_error": analysis["ratio"].standard_error,
                "delta_sqrt5": analysis["ratio"].delta_sqrt5,
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

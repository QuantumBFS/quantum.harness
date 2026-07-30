#!/usr/bin/env python3
"""Fit the declared finite-size Binder-ratio scaling model."""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy.optimize import least_squares


YT = 1.587
YI = -0.815
OPTIONAL_TERMS = ("a2", "b2", "c1")
BASE_PARAMETERS = ("h_c", "Q_star", "a1", "b1")


def parameter_names(terms: frozenset[str]) -> tuple[str, ...]:
    unknown = terms.difference(OPTIONAL_TERMS)
    if unknown:
        raise ValueError(f"unknown correction terms: {sorted(unknown)}")
    return BASE_PARAMETERS + tuple(name for name in OPTIONAL_TERMS if name in terms)


def _theta_mapping(
    theta: Mapping[str, float] | Sequence[float],
    terms: frozenset[str],
) -> dict[str, float]:
    if isinstance(theta, Mapping):
        return {name: float(theta.get(name, 0.0)) for name in parameter_names(terms)}
    values = np.asarray(theta, dtype=float)
    names = parameter_names(terms)
    if len(values) != len(names):
        raise ValueError("parameter vector length does not match terms")
    return dict(zip(names, values, strict=True))


def binder_model(
    theta: Mapping[str, float] | Sequence[float],
    L: np.ndarray,
    h: np.ndarray,
    terms: frozenset[str],
) -> np.ndarray:
    """Evaluate the fixed-exponent Binder-ratio scaling model."""
    parameters = _theta_mapping(theta, terms)
    sizes = np.asarray(L, dtype=float)
    fields = np.asarray(h, dtype=float)
    x = fields - parameters["h_c"]
    values = (
        parameters["Q_star"]
        + parameters["a1"] * x * sizes**YT
        + parameters["b1"] * sizes**YI
    )
    if "a2" in terms:
        values = values + parameters["a2"] * x**2 * sizes ** (2.0 * YT)
    if "b2" in terms:
        values = values + parameters["b2"] * sizes ** (2.0 * YI)
    if "c1" in terms:
        values = values + parameters["c1"] * x * sizes ** (YT + YI)
    return values


@dataclass
class FitResult:
    variant_id: str
    lattice: str
    Lmin: int
    terms: frozenset[str]
    drop_largest: bool
    excluded_labels: tuple[str, ...]
    point_count: int
    size_count: int
    field_min: float
    field_max: float
    parameters: dict[str, float]
    errors: dict[str, float]
    covariance: np.ndarray
    chi2: float
    dof: int
    chi2_per_dof: float
    converged: bool
    message: str
    boundary_contact: bool
    h_c_inside_scan: bool

    def summary_row(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "variant_id": self.variant_id,
            "lattice": self.lattice,
            "Lmin": self.Lmin,
            "terms": "+".join(sorted(self.terms)) or "base",
            "drop_largest": self.drop_largest,
            "excluded_labels": ";".join(self.excluded_labels),
            "point_count": self.point_count,
            "size_count": self.size_count,
            "field_min": self.field_min,
            "field_max": self.field_max,
            "chi2": self.chi2,
            "dof": self.dof,
            "chi2_per_dof": self.chi2_per_dof,
            "converged": self.converged,
            "message": self.message,
            "boundary_contact": self.boundary_contact,
            "h_c_inside_scan": self.h_c_inside_scan,
        }
        for name in BASE_PARAMETERS + OPTIONAL_TERMS:
            row[name] = self.parameters.get(name, math.nan)
            row[f"{name}_error"] = self.errors.get(name, math.nan)
        return row


@dataclass(frozen=True)
class FitSpec:
    rows: list[dict[str, Any]]
    lattice: str
    Lmin: int
    terms: frozenset[str]
    drop_largest: bool = False
    excluded_labels: frozenset[str] = frozenset()


@dataclass
class BootstrapResult:
    variant_id: str
    requested_samples: int
    successful_samples: int
    failed_samples: int
    draws: np.ndarray
    h_c_mean: float
    h_c_std: float
    h_c_ci68: tuple[float, float]
    h_c_ci95: tuple[float, float]

    @property
    def success_fraction(self) -> float:
        return self.successful_samples / self.requested_samples


def variant_name(
    lattice: str,
    Lmin: int,
    terms: frozenset[str],
    *,
    drop_largest: bool = False,
    suffix: str = "",
) -> str:
    term_label = "-".join(name for name in OPTIONAL_TERMS if name in terms) or "base"
    largest_label = "-dropmax" if drop_largest else ""
    return f"{lattice}-Lmin{Lmin}-{term_label}{largest_label}{suffix}"


def _cell_label(row: Mapping[str, Any]) -> str:
    return f"{row['run_id']}/{row['cell_id']}"


def select_rows(
    rows: Iterable[dict[str, Any]],
    lattice: str,
    Lmin: int,
    *,
    drop_largest: bool = False,
    excluded_labels: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    selected = [
        row
        for row in rows
        if row["lattice"] == lattice
        and int(row["L"]) >= Lmin
        and math.isclose(float(row["FixedDltau"]), 0.013, rel_tol=0.0, abs_tol=1e-12)
        and _cell_label(row) not in excluded_labels
    ]
    if drop_largest and selected:
        largest = max(int(row["L"]) for row in selected)
        selected = [row for row in selected if int(row["L"]) != largest]
    return sorted(
        selected,
        key=lambda row: (int(row["L"]), float(row["hTrfd"]), _cell_label(row)),
    )


def fit_variant(
    rows: list[dict[str, Any]],
    lattice: str,
    Lmin: int,
    terms: frozenset[str],
    *,
    drop_largest: bool = False,
    excluded_labels: frozenset[str] = frozenset(),
    initial: Mapping[str, float] | None = None,
) -> FitResult:
    selected = select_rows(
        rows,
        lattice,
        Lmin,
        drop_largest=drop_largest,
        excluded_labels=excluded_labels,
    )
    names = parameter_names(terms)
    if len(selected) <= len(names):
        raise ValueError("not enough points for the requested scaling fit")
    sizes = np.array([float(row["L"]) for row in selected])
    fields = np.array([float(row["hTrfd"]) for row in selected])
    observed = np.array([float(row["binder_Q"]) for row in selected])
    errors = np.array([float(row["binder_Q_error"]) for row in selected])
    if np.any(~np.isfinite(errors)) or np.any(errors <= 0.0):
        raise ValueError("every Binder-ratio uncertainty must be finite and positive")

    field_min = float(np.min(fields))
    field_max = float(np.max(fields))
    span = max(field_max - field_min, 1.0e-4)
    start_values = {
        "h_c": float(np.median(fields)),
        "Q_star": float(np.median(observed)),
        "a1": -0.05,
        "b1": 0.0,
        "a2": 0.0,
        "b2": 0.0,
        "c1": 0.0,
    }
    if initial:
        start_values.update({name: float(value) for name, value in initial.items()})
    x0 = np.array([start_values[name] for name in names])
    lower_map = {
        "h_c": -math.inf,
        "Q_star": -1.0,
        "a1": -100.0,
        "b1": -100.0,
        "a2": -100.0,
        "b2": -100.0,
        "c1": -100.0,
    }
    upper_map = {
        "h_c": math.inf,
        "Q_star": 2.0,
        "a1": 100.0,
        "b1": 100.0,
        "a2": 100.0,
        "b2": 100.0,
        "c1": 100.0,
    }
    lower = np.array([lower_map[name] for name in names])
    upper = np.array([upper_map[name] for name in names])

    def residual(vector: np.ndarray) -> np.ndarray:
        return (observed - binder_model(vector, sizes, fields, terms)) / errors

    solution = least_squares(
        residual,
        x0,
        bounds=(lower, upper),
        xtol=1e-13,
        ftol=1e-13,
        gtol=1e-13,
        max_nfev=5000,
        x_scale="jac",
    )
    chi2 = float(np.dot(solution.fun, solution.fun))
    dof = len(selected) - len(names)
    covariance = np.full((len(names), len(names)), math.nan)
    parameter_errors = np.full(len(names), math.nan)
    if dof > 0:
        try:
            covariance = np.linalg.pinv(solution.jac.T @ solution.jac) * (chi2 / dof)
            parameter_errors = np.sqrt(np.clip(np.diag(covariance), 0.0, math.inf))
        except np.linalg.LinAlgError:
            pass
    distance = np.minimum(solution.x - lower, upper - solution.x)
    scale = np.maximum(1.0, np.abs(solution.x))
    boundary_contact = bool(np.any(distance <= 1e-7 * scale))
    parameters = dict(zip(names, (float(value) for value in solution.x), strict=True))
    errors_by_name = dict(
        zip(names, (float(value) for value in parameter_errors), strict=True)
    )
    return FitResult(
        variant_id=variant_name(
            lattice,
            Lmin,
            terms,
            drop_largest=drop_largest,
            suffix="-exclude-drift" if excluded_labels else "",
        ),
        lattice=lattice,
        Lmin=Lmin,
        terms=terms,
        drop_largest=drop_largest,
        excluded_labels=tuple(sorted(excluded_labels)),
        point_count=len(selected),
        size_count=len(set(sizes)),
        field_min=field_min,
        field_max=field_max,
        parameters=parameters,
        errors=errors_by_name,
        covariance=covariance,
        chi2=chi2,
        dof=dof,
        chi2_per_dof=chi2 / dof if dof > 0 else math.nan,
        converged=bool(solution.success and np.all(np.isfinite(solution.x))),
        message=str(solution.message),
        boundary_contact=boundary_contact,
        h_c_inside_scan=field_min <= parameters["h_c"] <= field_max,
    )


def _trimmed_bin_mean(values: np.ndarray) -> float:
    if len(values) < 3:
        raise ValueError("at least three bins are required for extrema trimming")
    ordered = np.sort(values)
    return float(np.mean(ordered[1:-1]))


def bootstrap_variant(
    bin_rows: list[dict[str, Any]],
    fit_spec: FitSpec,
    samples: int,
    rng: np.random.Generator,
) -> BootstrapResult:
    selected = select_rows(
        fit_spec.rows,
        fit_spec.lattice,
        fit_spec.Lmin,
        drop_largest=fit_spec.drop_largest,
        excluded_labels=fit_spec.excluded_labels,
    )
    by_cell: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in bin_rows:
        by_cell.setdefault((str(row["run_id"]), str(row["cell_id"])), []).append(row)
    prepared: list[tuple[dict[str, Any], np.ndarray]] = []
    for row in selected:
        key = (str(row["run_id"]), str(row["cell_id"]))
        cell_bins = sorted(by_cell[key], key=lambda item: int(item["bin"]))
        values = np.array([float(item["Q_bin"]) for item in cell_bins if int(item["bin"]) > 1])
        if len(values) != 31:
            raise ValueError(f"{key} does not contain 31 post-discard bins")
        prepared.append((row, values))

    draws: list[float] = []
    failed = 0
    initial_fit = fit_variant(
        fit_spec.rows,
        fit_spec.lattice,
        fit_spec.Lmin,
        fit_spec.terms,
        drop_largest=fit_spec.drop_largest,
        excluded_labels=fit_spec.excluded_labels,
    )
    for _ in range(samples):
        replica_rows = []
        for row, values in prepared:
            resampled = values[rng.integers(0, len(values), size=len(values))]
            replica = dict(row)
            replica["binder_Q"] = _trimmed_bin_mean(resampled)
            replica_rows.append(replica)
        try:
            fit = fit_variant(
                replica_rows,
                fit_spec.lattice,
                fit_spec.Lmin,
                fit_spec.terms,
                drop_largest=False,
                initial=initial_fit.parameters,
            )
            if fit.converged and not fit.boundary_contact and math.isfinite(
                fit.parameters["h_c"]
            ):
                draws.append(fit.parameters["h_c"])
            else:
                failed += 1
        except (KeyError, ValueError, np.linalg.LinAlgError):
            failed += 1
    draw_array = np.asarray(draws, dtype=float)
    if len(draw_array) == 0:
        intervals = (math.nan, math.nan), (math.nan, math.nan)
        mean = std = math.nan
    else:
        intervals = (
            tuple(float(value) for value in np.quantile(draw_array, [0.16, 0.84])),
            tuple(float(value) for value in np.quantile(draw_array, [0.025, 0.975])),
        )
        mean = float(np.mean(draw_array))
        std = float(np.std(draw_array, ddof=1)) if len(draw_array) > 1 else math.nan
    return BootstrapResult(
        variant_id=initial_fit.variant_id,
        requested_samples=samples,
        successful_samples=len(draw_array),
        failed_samples=failed,
        draws=draw_array,
        h_c_mean=mean,
        h_c_std=std,
        h_c_ci68=intervals[0],
        h_c_ci95=intervals[1],
    )


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    integer_columns = {"L", "LTrot", "nprocs", "nWarm", "NmBin", "NSwep", "NmMeaConfg", "bin"}
    float_columns = {
        "hTrfd",
        "FixedDltau",
        "Dltau",
        "m2",
        "m2_error",
        "binder_Q",
        "binder_Q_error",
        "z_m2",
        "z_Q",
        "m2_bin",
        "m4_bin",
        "Q_bin",
    }
    for row in rows:
        for name in integer_columns.intersection(row):
            row[name] = int(row[name])
        for name in float_columns.intersection(row):
            row[name] = float(row[name])
    return rows


def all_term_sets() -> list[frozenset[str]]:
    return [
        frozenset(name for name, included in zip(OPTIONAL_TERMS, flags) if included)
        for flags in itertools.product((False, True), repeat=len(OPTIONAL_TERMS))
    ]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("cannot write an empty table")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: format(value, ".17g") if isinstance(value, float) else value
                    for key, value in row.items()
                }
            )


def run_all_variants(
    cells: list[dict[str, Any]],
    bins: list[dict[str, Any]],
    *,
    samples: int,
    seed: int,
    progress_every: int = 1,
) -> tuple[list[FitResult], list[BootstrapResult]]:
    fits: list[FitResult] = []
    bootstraps: list[BootstrapResult] = []
    variants = [
        (lattice, lmin, terms)
        for lattice in ("triangular", "honeycomb")
        for lmin in (12, 16, 20, 24)
        for terms in all_term_sets()
    ]
    seed_sequence = np.random.SeedSequence(seed)
    child_seeds = seed_sequence.spawn(len(variants))
    for index, ((lattice, lmin, terms), child_seed) in enumerate(
        zip(variants, child_seeds, strict=True),
        start=1,
    ):
        fit = fit_variant(cells, lattice, lmin, terms)
        bootstrap = bootstrap_variant(
            bins,
            FitSpec(cells, lattice, lmin, terms),
            samples,
            np.random.default_rng(child_seed),
        )
        fits.append(fit)
        bootstraps.append(bootstrap)
        if index % progress_every == 0 or index == len(variants):
            print(
                f"fit {index}/{len(variants)} {fit.variant_id}: "
                f"h_c={fit.parameters['h_c']:.9f}, "
                f"chi2/dof={fit.chi2_per_dof:.3g}, "
                f"bootstrap={bootstrap.successful_samples}/{samples}",
                flush=True,
            )
    return fits, bootstraps


def write_fit_outputs(
    output_dir: Path,
    fits: list[FitResult],
    bootstraps: list[BootstrapResult],
    *,
    fit_filename: str = "finite_size_fits.csv",
    bootstrap_filename: str = "finite_size_bootstrap.csv",
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    bootstrap_by_id = {result.variant_id: result for result in bootstraps}
    fit_rows = []
    for fit in fits:
        row = fit.summary_row()
        bootstrap = bootstrap_by_id[fit.variant_id]
        row.update(
            {
                "bootstrap_requested": bootstrap.requested_samples,
                "bootstrap_successful": bootstrap.successful_samples,
                "bootstrap_failed": bootstrap.failed_samples,
                "bootstrap_success_fraction": bootstrap.success_fraction,
                "h_c_bootstrap_mean": bootstrap.h_c_mean,
                "h_c_bootstrap_std": bootstrap.h_c_std,
                "h_c_ci68_low": bootstrap.h_c_ci68[0],
                "h_c_ci68_high": bootstrap.h_c_ci68[1],
                "h_c_ci95_low": bootstrap.h_c_ci95[0],
                "h_c_ci95_high": bootstrap.h_c_ci95[1],
            }
        )
        fit_rows.append(row)
    _write_csv(output_dir / fit_filename, fit_rows)
    draw_rows = []
    for bootstrap in bootstraps:
        successful = iter(bootstrap.draws)
        for replica in range(bootstrap.requested_samples):
            if replica < bootstrap.successful_samples:
                draw_rows.append(
                    {
                        "variant_id": bootstrap.variant_id,
                        "replica": replica,
                        "success": True,
                        "h_c": float(next(successful)),
                    }
                )
            else:
                draw_rows.append(
                    {
                        "variant_id": bootstrap.variant_id,
                        "replica": replica,
                        "success": False,
                        "h_c": math.nan,
                    }
                )
    _write_csv(output_dir / bootstrap_filename, draw_rows)


def run_sensitivity_variants(
    cells: list[dict[str, Any]],
    bins: list[dict[str, Any]],
    *,
    drift_labels: frozenset[str],
    samples: int,
    seed: int,
) -> tuple[list[FitResult], list[BootstrapResult]]:
    specs = [
        FitSpec(cells, "triangular", 16, frozenset({"a2"}), drop_largest=True),
        FitSpec(cells, "honeycomb", 16, frozenset({"a2"}), drop_largest=True),
    ]
    if drift_labels:
        specs.append(
            FitSpec(
                cells,
                "triangular",
                16,
                frozenset({"a2"}),
                excluded_labels=drift_labels,
            )
        )
    child_seeds = np.random.SeedSequence(seed).spawn(len(specs))
    fits = []
    bootstraps = []
    for index, (spec, child_seed) in enumerate(zip(specs, child_seeds, strict=True), 1):
        fit = fit_variant(
            spec.rows,
            spec.lattice,
            spec.Lmin,
            spec.terms,
            drop_largest=spec.drop_largest,
            excluded_labels=spec.excluded_labels,
        )
        bootstrap = bootstrap_variant(
            bins,
            spec,
            samples,
            np.random.default_rng(child_seed),
        )
        fits.append(fit)
        bootstraps.append(bootstrap)
        print(
            f"sensitivity {index}/{len(specs)} {fit.variant_id}: "
            f"h_c={fit.parameters['h_c']:.9f}, "
            f"bootstrap={bootstrap.successful_samples}/{samples}",
            flush=True,
        )
    return fits, bootstraps


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cells", type=Path, required=True)
    parser.add_argument("--bins", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument("--progress-every", type=int, default=1)
    parser.add_argument("--only-sensitivities", action="store_true")
    parser.add_argument("--selection", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    cells = _read_csv(args.cells)
    bins = _read_csv(args.bins)
    if args.only_sensitivities:
        if args.selection is None:
            raise ValueError("--selection is required with --only-sensitivities")
        selection = json.loads(args.selection.read_text(encoding="utf-8"))
        fits, bootstraps = run_sensitivity_variants(
            cells,
            bins,
            drift_labels=frozenset(selection["sensitivity_exclusions"]),
            samples=args.bootstrap,
            seed=args.seed,
        )
        write_fit_outputs(
            args.output_dir,
            fits,
            bootstraps,
            fit_filename="finite_size_sensitivities.csv",
            bootstrap_filename="finite_size_sensitivity_bootstrap.csv",
        )
        return
    fits, bootstraps = run_all_variants(
        cells,
        bins,
        samples=args.bootstrap,
        seed=args.seed,
        progress_every=args.progress_every,
    )
    write_fit_outputs(args.output_dir, fits, bootstraps)
    print(
        json.dumps(
            {
                "fit_count": len(fits),
                "stable_bootstrap_count": sum(
                    result.success_fraction >= 0.95 for result in bootstraps
                ),
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

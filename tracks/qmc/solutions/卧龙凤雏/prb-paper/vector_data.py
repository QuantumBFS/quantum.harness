"""Typed, hash-gated numeric inputs for native vector manuscript figures."""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from paper_data import load_paper_data


EXPECTED_LEARNING_SHA256 = (
    "cc08a6e6d6d414046c744b4d29d48f112d44526dfc2145b867aae01f07d53c33"
)


@dataclass(frozen=True)
class CleanFreeEnergyPoint:
    width: int
    exact: float
    monte_carlo: float
    monte_carlo_se: float
    coarse_grid: float


@dataclass(frozen=True)
class ChargeFit:
    minimum_width: int
    method: str
    value: float
    standard_error: float | None
    interval: tuple[float, float] | None
    role: str


@dataclass(frozen=True)
class FiniteSizePoint:
    width: int
    value: float
    standard_error: float
    fitted: float
    residual: float


@dataclass(frozen=True)
class BootstrapPoint:
    sample: int
    primary: float
    alternate: float


@dataclass(frozen=True)
class FitVariant:
    name: str
    mean: float
    standard_error: float
    interval: tuple[float, float]


@dataclass(frozen=True)
class EvidencePoint:
    phi_pi: float
    score: float


@dataclass(frozen=True)
class Estimate:
    value: float
    standard_error: float
    interval: tuple[float, float]


@dataclass(frozen=True)
class EntanglementData:
    value: float
    standard_error: float
    interval: tuple[float, float]
    chord_log: tuple[float, ...]
    entropy: tuple[float, ...]
    fitted_chord: tuple[float, ...]
    uncertainty: tuple[float, ...]
    widths: tuple[int, ...]
    per_width_values: tuple[float, ...]
    per_width_standard_errors: tuple[float, ...]
    fitted_widths: tuple[float, ...]
    residuals: tuple[float, ...]
    model_weights: tuple[tuple[str, float], ...]
    covariance_condition: float


@dataclass(frozen=True)
class CasimirData:
    value: float
    standard_error: float
    interval: tuple[float, float]
    amplitude: float
    widths: tuple[int, ...]
    gamma: tuple[float, ...]
    fitted: tuple[float, ...]
    residuals: tuple[float, ...]


@dataclass(frozen=True)
class AnisotropyData:
    alpha: float
    interval: tuple[float, float]
    stable: bool
    spatial: tuple[tuple[float, float], ...]
    temporal: tuple[tuple[float, float], ...]
    window_estimates: tuple[tuple[str, float], ...]
    window_relative_spread: float


@dataclass(frozen=True)
class EstimatorComparison:
    agrees: bool
    difference: float
    combined_95_threshold: float


@dataclass(frozen=True)
class CleanVectorData:
    free_energy: tuple[CleanFreeEnergyPoint, ...]
    fits: tuple[ChargeFit, ...]
    primary_mc_charge: float


@dataclass(frozen=True)
class NishimoriVectorData:
    free_energy: tuple[FiniteSizePoint, ...]
    bootstrap: tuple[BootstrapPoint, ...]
    primary_charge: float


@dataclass(frozen=True)
class WeakVectorData:
    finite_size: tuple[FiniteSizePoint, ...]
    fit_variants: tuple[FitVariant, ...]
    primary_charge: float
    self_duality_log_ratio: float
    effective_sample_size: float


@dataclass(frozen=True)
class LearningVectorData:
    xy_evidence: tuple[EvidencePoint, ...]
    diii_evidence: tuple[EvidencePoint, ...]
    xy_bracket: tuple[float, float]
    diii_bracket: tuple[float, float] | None
    candidate_phi_pi: float
    entanglement: EntanglementData
    casimir: CasimirData
    anisotropy: AnisotropyData
    estimator_comparison: EstimatorComparison
    central_charge_published: bool
    claim_reasons: tuple[str, ...]


@dataclass(frozen=True)
class VectorPlotData:
    clean: CleanVectorData
    nishimori: NishimoriVectorData
    weak: WeakVectorData
    learning: LearningVectorData


def load_vector_plot_data(repo_root: Path) -> VectorPlotData:
    """Load every plotted number from the immutable, validated result bundle."""

    root = Path(repo_root).resolve()
    headline = load_paper_data(root)
    if headline.learning.summary_sha256 != EXPECTED_LEARNING_SHA256:
        raise ValueError("learning summary hash differs from the approved frozen input")

    clean_dir = root / "tracks/qmc/results/clean-ising-20260729-120302/processed"
    nish_dir = (
        root / "tracks/qmc/results/nishimori-ising-20260729-refinement1/processed"
    )
    weak_dir = (
        root / "tracks/qmc/results/weak-self-dual-20260729-154737/processed"
    )
    learning_path = (
        root / "tracks/qmc/results/learning-mit-production-v2-20260730-132322/summary.json"
    )

    clean_energy = tuple(
        CleanFreeEnergyPoint(
            width=_integer(row["L"], "clean width"),
            exact=_number(row["g_exact"], "clean exact free energy"),
            monte_carlo=_number(row["g_mc_129"], "clean Monte Carlo free energy"),
            monte_carlo_se=_number(row["g_mc_129_se"], "clean free-energy error"),
            coarse_grid=_number(row["g_mc_65"], "clean coarse-grid free energy"),
        )
        for row in _csv_rows(clean_dir / "free_energies.csv")
    )
    clean_fits = tuple(
        ChargeFit(
            minimum_width=_integer(row["L_min"], "clean fit minimum width"),
            method=str(row["method"]),
            value=_number(row["c"], "clean fitted charge"),
            standard_error=_optional_number(row["standard_error"]),
            interval=_optional_interval(row["ci_low"], row["ci_high"]),
            role=str(row["role"]),
        )
        for row in _csv_rows(clean_dir / "central_charge_fits.csv")
    )

    nish_energy = tuple(
        FiniteSizePoint(
            width=_integer(row["width"], "Nishimori width"),
            value=_number(row["phi"], "Nishimori free energy"),
            standard_error=_number(row["standard_error"], "Nishimori error"),
            fitted=_number(row["fitted_phi"], "Nishimori fitted free energy"),
            residual=_number(row["residual"], "Nishimori residual"),
        )
        for row in _csv_rows(nish_dir / "free_energy.csv")
    )
    nish_bootstrap = tuple(
        BootstrapPoint(
            sample=_integer(row["sample"], "bootstrap sample"),
            primary=_number(row["c_lmin4"], "primary bootstrap charge"),
            alternate=_number(row["c_lmin6"], "alternate bootstrap charge"),
        )
        for row in _csv_rows(nish_dir / "central_charge_bootstrap.csv")
    )

    weak_size = tuple(
        FiniteSizePoint(
            width=_integer(row["width"], "weak-self-dual width"),
            value=_number(row["gamma"], "weak-self-dual Lyapunov sum"),
            standard_error=_number(row["standard_error"], "weak-self-dual error"),
            fitted=_number(row["fitted_gamma"], "weak-self-dual fitted value"),
            residual=_number(row["residual"], "weak-self-dual residual"),
        )
        for row in _csv_rows(weak_dir / "finite_size.csv")
    )
    weak_variants = tuple(
        FitVariant(
            name=str(row["variant"]),
            mean=_number(row["mean"], "weak-self-dual fit value"),
            standard_error=_number(row["standard_error"], "weak-self-dual fit error"),
            interval=(
                _number(row["ci95_low"], "weak-self-dual lower interval"),
                _number(row["ci95_high"], "weak-self-dual upper interval"),
            ),
        )
        for row in _csv_rows(weak_dir / "fit_variants.csv")
    )
    weak_summary = _json(weak_dir / "summary.json")

    learning = _json(learning_path)
    ent = _mapping(learning["entanglement_c_eff"], "entanglement_c_eff")
    chord = _mapping(ent["chord_fit"], "entanglement chord fit")
    per_width = tuple(ent["per_width"])
    cas = _mapping(learning["casimir"], "casimir")
    cas_eff = _mapping(learning["casimir_c_eff"], "casimir_c_eff")
    anis = _mapping(learning["anisotropy"], "anisotropy")
    comparison = _mapping(learning["estimator_comparison"], "estimator comparison")

    result = VectorPlotData(
        clean=CleanVectorData(
            free_energy=clean_energy,
            fits=clean_fits,
            primary_mc_charge=headline.clean.c_eff,
        ),
        nishimori=NishimoriVectorData(
            free_energy=nish_energy,
            bootstrap=nish_bootstrap,
            primary_charge=headline.nishimori.c_eff,
        ),
        weak=WeakVectorData(
            finite_size=weak_size,
            fit_variants=weak_variants,
            primary_charge=headline.weak.c_eff,
            self_duality_log_ratio=_number(
                weak_summary["gates"]["by_name"]["self_duality"]["value"],
                "self-duality diagnostic",
            ),
            effective_sample_size=_number(
                weak_summary["gates"]["by_name"]["effective_sample_size"]["value"],
                "effective sample size",
            ),
        ),
        learning=LearningVectorData(
            xy_evidence=_evidence(learning["xy"]["evidence"], "XY"),
            diii_evidence=_evidence(learning["diii"]["evidence"], "class-DIII"),
            xy_bracket=_json_interval(learning["xy"]["bracket"], "XY bracket"),
            diii_bracket=(
                None
                if learning["diii"]["bracket"] is None
                else _json_interval(learning["diii"]["bracket"], "class-DIII bracket")
            ),
            candidate_phi_pi=_number(
                learning["candidate_selection"]["candidate_phi_pi"], "candidate phi/pi"
            ),
            entanglement=EntanglementData(
                value=_number(ent["value"], "entanglement estimate"),
                standard_error=_number(ent["standard_error"], "entanglement error"),
                interval=_json_interval(ent["interval"], "entanglement interval"),
                chord_log=_numbers(chord["chord_log"], "chord coordinates"),
                entropy=_numbers(chord["entropy"], "entropies"),
                fitted_chord=_numbers(chord["fitted"], "fitted entropies"),
                uncertainty=_numbers(chord["uncertainty"], "entropy uncertainties"),
                widths=tuple(_integer(value, "entanglement width") for value in ent["widths"]),
                per_width_values=tuple(
                    _number(row[1], "per-width charge") for row in per_width
                ),
                per_width_standard_errors=tuple(
                    _number(row[2], "per-width charge error") for row in per_width
                ),
                fitted_widths=_numbers(ent["fitted"], "fitted width trend"),
                residuals=_numbers(ent["residuals"], "entanglement residuals"),
                model_weights=tuple(
                    (str(name), _number(value, f"model weight {name}"))
                    for name, value in ent["model_weights"].items()
                ),
                covariance_condition=_number(
                    ent["covariance_condition"], "entanglement covariance condition"
                ),
            ),
            casimir=CasimirData(
                value=_number(cas_eff["value"], "Casimir estimate"),
                standard_error=_number(cas_eff["standard_error"], "Casimir error"),
                interval=_json_interval(cas_eff["interval"], "Casimir interval"),
                amplitude=_number(cas["amplitude"], "Casimir amplitude"),
                widths=tuple(_integer(value, "Casimir width") for value in cas["widths"]),
                gamma=_numbers(cas["gamma"], "Casimir data"),
                fitted=_numbers(cas["fitted"], "Casimir fit"),
                residuals=_numbers(cas["residuals"], "Casimir residuals"),
            ),
            anisotropy=AnisotropyData(
                alpha=_number(anis["alpha"], "anisotropy alpha"),
                interval=_json_interval(anis["alpha_interval"], "anisotropy interval"),
                stable=bool(anis["alpha_stable"]),
                spatial=_pairs(anis["spatial"], "spatial anisotropy"),
                temporal=_pairs(anis["temporal"], "temporal anisotropy"),
                window_estimates=_window_pairs(anis["window_estimates"]),
                window_relative_spread=_number(
                    anis["window_relative_spread"], "anisotropy window spread"
                ),
            ),
            estimator_comparison=EstimatorComparison(
                agrees=bool(comparison["agrees"]),
                difference=_number(comparison["difference"], "estimator difference"),
                combined_95_threshold=_number(
                    comparison["combined_95_threshold"], "estimator agreement threshold"
                ),
            ),
            central_charge_published=bool(learning["central_charge"]["published"]),
            claim_reasons=tuple(str(reason) for reason in learning["claim"]["reasons"]),
        ),
    )
    _validate(result)
    return result


def _csv_rows(path: Path) -> tuple[dict[str, str], ...]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = tuple(dict(row) for row in csv.DictReader(handle))
    if not rows:
        raise ValueError(f"empty numeric table: {path}")
    return rows


def _json(path: Path) -> Mapping[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    return _mapping(value, str(path))


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def _number(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} is not numeric") from error
    if not math.isfinite(result):
        raise ValueError(f"{label} is not finite")
    return result


def _integer(value: Any, label: str) -> int:
    result = _number(value, label)
    if not result.is_integer():
        raise ValueError(f"{label} is not an integer")
    return int(result)


def _optional_number(value: Any) -> float | None:
    return None if value in ("", None) else _number(value, "optional numeric value")


def _optional_interval(low: Any, high: Any) -> tuple[float, float] | None:
    if low in ("", None) and high in ("", None):
        return None
    return (_number(low, "interval lower bound"), _number(high, "interval upper bound"))


def _json_interval(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{label} must contain exactly two values")
    interval = (_number(value[0], label), _number(value[1], label))
    if interval[0] > interval[1]:
        raise ValueError(f"{label} is reversed")
    return interval


def _numbers(values: Any, label: str) -> tuple[float, ...]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{label} must be a nonempty list")
    return tuple(_number(value, label) for value in values)


def _pairs(values: Any, label: str) -> tuple[tuple[float, float], ...]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{label} must be a nonempty list")
    return tuple(
        (_number(row[0], label), _number(row[1], label))
        for row in values
        if isinstance(row, list) and len(row) >= 2
    )


def _window_pairs(values: Any) -> tuple[tuple[str, float], ...]:
    if not isinstance(values, list) or not values:
        raise ValueError("anisotropy window estimates must be a nonempty list")
    pairs: list[tuple[str, float]] = []
    for row in values:
        if isinstance(row, dict):
            window = row.get(
                "window",
                row.get("minimum_width", row.get("l_min", row.get("width"))),
            )
            estimate = row.get("alpha")
        elif isinstance(row, list) and len(row) >= 2:
            window, estimate = row[:2]
        else:
            raise ValueError("malformed anisotropy window estimate")
        if window is None:
            raise ValueError("anisotropy window label is missing")
        pairs.append((str(window), _number(estimate, "window alpha")))
    return tuple(pairs)


def _evidence(values: Any, label: str) -> tuple[EvidencePoint, ...]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"{label} evidence must be a nonempty list")
    return tuple(
        EvidencePoint(
            _number(row["phi_pi"], f"{label} phi/pi"),
            _number(row["score"], f"{label} score"),
        )
        for row in values
    )


def _validate(data: VectorPlotData) -> None:
    for label, points in (
        ("clean", data.clean.free_energy),
        ("Nishimori", data.nishimori.free_energy),
        ("weak-self-dual", data.weak.finite_size),
    ):
        widths = tuple(point.width for point in points)
        if widths != tuple(sorted(set(widths))):
            raise ValueError(f"{label} widths must be unique and increasing")
    ent = data.learning.entanglement
    if not (
        len(ent.chord_log)
        == len(ent.entropy)
        == len(ent.fitted_chord)
        == len(ent.uncertainty)
    ):
        raise ValueError("entanglement chord-fit arrays have unequal lengths")
    if not (
        len(ent.widths)
        == len(ent.per_width_values)
        == len(ent.per_width_standard_errors)
        == len(ent.fitted_widths)
        == len(ent.residuals)
    ):
        raise ValueError("entanglement finite-size arrays have unequal lengths")
    cas = data.learning.casimir
    if not (
        len(cas.widths) == len(cas.gamma) == len(cas.fitted) == len(cas.residuals)
    ):
        raise ValueError("Casimir finite-size arrays have unequal lengths")

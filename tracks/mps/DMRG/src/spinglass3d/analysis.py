"""Hash-bound Stage 8 analysis of immutable Stage 7 disorder summaries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from types import MappingProxyType

import numpy as np

from vmcrg_ref.artifacts import sha256_file

from .statistics import (
    BootstrapCrossingResult,
    BootstrapFSSResult,
    BootstrapInterval,
    DisorderSeries,
    FSSFitResult,
    FSSVariant,
    FitFailure,
    NonlinearBounds,
    PairCrossingSample,
    RecordIdentity,
    SystematicSpread,
    bootstrap_fss,
    bootstrap_pair_crossings,
)


_OBSERVABLES = ("xi_over_l", "binder")
_VARIANT_FIELDS = {
    "l_min",
    "temperature_window",
    "polynomial_order",
    "parity",
    "parity_order",
    "fixed_omega",
    "fixed_omega_p",
}
_BOUND_FIELDS = {"tc", "nu", "omega", "omega_p"}
_BOOTSTRAP_FIELDS = {
    "seed",
    "n_resamples",
    "minimum_success_count",
    "minimum_success_fraction",
}
_TRACK_ROOT = Path(__file__).resolve().parents[2]
_RUNTIME_SOURCE_FILES = {
    "src/spinglass3d/analysis.py": Path(__file__).resolve(),
    "src/spinglass3d/statistics.py": Path(__file__).with_name("statistics.py").resolve(),
    "scripts/hard_goal_analyze.py": (
        _TRACK_ROOT / "scripts/hard_goal_analyze.py"
    ).resolve(),
}


@dataclass(frozen=True)
class ProductionAnalysisInput:
    """Validated Stage 6 protocol plus its complete Stage 7 input inventory."""

    production_summary_path: Path
    production_summary_sha256: str
    protocol_path: Path
    protocol_sha256: str
    records: tuple[DisorderSeries, ...]
    variants: tuple[FSSVariant, ...]
    nonlinear_bounds: NonlinearBounds
    bootstrap_seed: int
    n_resamples: int
    minimum_success_count: int
    minimum_success_fraction: float
    source_inventory: Mapping[str, str]
    summary_inventory: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "records", tuple(self.records))
        object.__setattr__(self, "variants", tuple(self.variants))
        object.__setattr__(
            self,
            "source_inventory",
            MappingProxyType(dict(self.source_inventory)),
        )
        object.__setattr__(
            self,
            "summary_inventory",
            MappingProxyType(dict(self.summary_inventory)),
        )


@dataclass(frozen=True)
class Stage8AnalysisResult:
    """Complete separate/joint fits and crossing distributions for Stage 8."""

    production_summary_sha256: str
    protocol_sha256: str
    ordered_variants: tuple[FSSVariant, ...]
    nonlinear_bounds: NonlinearBounds
    bootstrap_seed: int
    n_resamples: int
    minimum_success_count: int
    minimum_success_fraction: float
    source_inventory: Mapping[str, str]
    summary_inventory: Mapping[str, str]
    fit_table: Mapping[str, BootstrapFSSResult]
    crossings: Mapping[str, BootstrapCrossingResult]
    interval_compatibility: Mapping[str, bool]

    def __post_init__(self) -> None:
        object.__setattr__(self, "ordered_variants", tuple(self.ordered_variants))
        for name in (
            "source_inventory",
            "summary_inventory",
            "fit_table",
            "crossings",
            "interval_compatibility",
        ):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))


class _DuplicateJSONKey(ValueError):
    pass


def _json_pairs(pairs: Sequence[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJSONKey(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON number {value!r}")


def _decode_json_object(payload: bytes, *, label: str) -> dict[str, object]:
    try:
        decoded = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_json_pairs,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, _DuplicateJSONKey) as error:
        raise ValueError(f"{label} is not valid JSON: {error}") from error
    if not isinstance(decoded, dict):
        raise ValueError(f"{label} must contain one JSON object")
    return decoded


def _read_json_object(path: Path, *, label: str) -> tuple[dict[str, object], str]:
    payload = path.read_bytes()
    return _decode_json_object(payload, label=label), hashlib.sha256(payload).hexdigest()


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError(f"{label} must be a JSON array")
    return value


def _sha256(value: object, *, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"{label} must be one lowercase SHA-256 digest")
    return value


def _integer(value: object, *, label: str, minimum: int | None = None) -> int:
    if type(value) is not int:
        raise ValueError(f"{label} must be an integer")
    result = int(value)
    if minimum is not None and result < minimum:
        raise ValueError(f"{label} must be at least {minimum}")
    return result


def _number(value: object, *, label: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{label} must be numeric")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(f"{label} must be finite") from error
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _optional_number(value: object, *, label: str) -> float | None:
    return None if value is None else _number(value, label=label)


def _require_stage(payload: Mapping[str, object], *, stage: str, label: str) -> None:
    if _integer(payload.get("schema_version"), label=f"{label} schema_version") != 1:
        raise ValueError(f"{label} schema_version must equal one")
    if payload.get("stage") != stage:
        raise ValueError(f"{label} stage must be {stage!r}")


def _bound_file(root: Path, value: object, *, label: str) -> tuple[str, Path]:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} path must be a nonempty string")
    relative = Path(value)
    if relative.is_absolute() or relative == Path("."):
        raise ValueError(f"{label} path must be relative to the production root")
    resolved_root = root.resolve()
    resolved = (resolved_root / relative).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as error:
        raise ValueError(f"{label} path escapes the production root") from error
    if not resolved.is_file():
        raise FileNotFoundError(f"{label} file is missing: {value}")
    return relative.as_posix(), resolved


def _hashed_json_descriptor(
    root: Path,
    value: object,
    *,
    label: str,
) -> tuple[str, Path, dict[str, object], str]:
    descriptor = _mapping(value, label=f"{label} descriptor")
    relative, path = _bound_file(root, descriptor.get("path"), label=label)
    expected = _sha256(descriptor.get("sha256"), label=f"{label} sha256")
    payload, actual = _read_json_object(path, label=label)
    if actual != expected:
        raise ValueError(
            f"{label} hash mismatch for {relative}: expected {expected}, got {actual}"
        )
    return relative, path, payload, actual


def _inventory(value: object, *, label: str) -> dict[str, str]:
    raw = _mapping(value, label=label)
    if not raw:
        raise ValueError(f"{label} must not be empty")
    result: dict[str, str] = {}
    for relative in sorted(raw):
        if not isinstance(relative, str) or not relative:
            raise ValueError(f"{label} paths must be nonempty strings")
        result[relative] = _sha256(raw[relative], label=f"{label} hash")
    return result


def _verify_source_inventory(inventory: Mapping[str, str]) -> None:
    missing = sorted(set(_RUNTIME_SOURCE_FILES) - set(inventory))
    if missing:
        raise ValueError(f"source inventory is missing runtime source files: {missing}")
    for relative, expected in inventory.items():
        if relative in _RUNTIME_SOURCE_FILES:
            normalized = relative
            path = _RUNTIME_SOURCE_FILES[relative]
        else:
            normalized, path = _bound_file(
                _TRACK_ROOT,
                relative,
                label="runtime source inventory",
            )
        actual = sha256_file(path)
        if actual != expected:
            raise ValueError(
                "runtime source hash mismatch for "
                f"{normalized}: expected {expected}, got {actual}"
            )


def _numeric_array(value: object, *, label: str) -> np.ndarray:
    raw = _sequence(value, label=label)
    parsed: list[float] = []
    for item in raw:
        if type(item) not in (int, float):
            raise ValueError(f"{label} must contain only finite JSON numbers")
        try:
            converted = float(item)
        except OverflowError as error:
            raise ValueError(
                f"{label} must contain only finite JSON numbers"
            ) from error
        if not math.isfinite(converted):
            raise ValueError(f"{label} must contain only finite JSON numbers")
        parsed.append(converted)
    return np.asarray(parsed, dtype=np.float64)


def _variant(value: object, *, index: int) -> FSSVariant:
    raw = _mapping(value, label=f"variant {index}")
    if set(raw) != _VARIANT_FIELDS:
        missing = sorted(_VARIANT_FIELDS - set(raw))
        extra = sorted(set(raw) - _VARIANT_FIELDS)
        raise ValueError(
            f"variant {index} fields do not match the frozen schema; "
            f"missing={missing}, extra={extra}"
        )
    window = _sequence(raw["temperature_window"], label=f"variant {index} window")
    if len(window) != 2:
        raise ValueError(f"variant {index} window must contain two values")
    parity_order = _integer(
        raw["parity_order"],
        label=f"variant {index} parity_order",
        minimum=0,
    )
    parity = raw["parity"]
    if type(parity) is not bool:
        raise ValueError(f"variant {index} parity must be a boolean")
    if not parity and parity_order != 0:
        raise ValueError(
            f"variant {index} parity_order must be zero when parity is disabled"
        )
    return FSSVariant(
        l_min=_integer(raw["l_min"], label=f"variant {index} l_min", minimum=2),
        temperature_window=(
            _number(window[0], label=f"variant {index} window lower"),
            _number(window[1], label=f"variant {index} window upper"),
        ),
        polynomial_order=_integer(
            raw["polynomial_order"],
            label=f"variant {index} polynomial_order",
            minimum=1,
        ),
        parity=parity,
        parity_order=parity_order,
        fixed_omega=_optional_number(
            raw["fixed_omega"], label=f"variant {index} fixed_omega"
        ),
        fixed_omega_p=_optional_number(
            raw["fixed_omega_p"], label=f"variant {index} fixed_omega_p"
        ),
    )


def _bounds(value: object) -> NonlinearBounds:
    raw = _mapping(value, label="nonlinear_bounds")
    if set(raw) != _BOUND_FIELDS:
        raise ValueError("nonlinear_bounds must explicitly declare tc, nu, omega, and omega_p")
    parsed: dict[str, tuple[float, float]] = {}
    for name in ("tc", "nu", "omega", "omega_p"):
        pair = _sequence(raw[name], label=f"{name} bounds")
        if len(pair) != 2:
            raise ValueError(f"{name} bounds must contain two values")
        parsed[name] = (
            _number(pair[0], label=f"{name} lower bound"),
            _number(pair[1], label=f"{name} upper bound"),
        )
    return NonlinearBounds(**parsed)


def _bootstrap_settings(value: object) -> tuple[int, int, int, float]:
    raw = _mapping(value, label="bootstrap")
    if set(raw) != _BOOTSTRAP_FIELDS:
        raise ValueError(
            "bootstrap must explicitly declare seed, n_resamples, "
            "minimum_success_count, and minimum_success_fraction"
        )
    seed = _integer(raw["seed"], label="bootstrap seed", minimum=0)
    count = _integer(raw["n_resamples"], label="bootstrap n_resamples", minimum=2)
    minimum_count = _integer(
        raw["minimum_success_count"],
        label="bootstrap minimum_success_count",
        minimum=1,
    )
    fraction = _number(
        raw["minimum_success_fraction"],
        label="bootstrap minimum_success_fraction",
    )
    if not 0.0 < fraction <= 1.0:
        raise ValueError("bootstrap minimum_success_fraction must lie in (0, 1]")
    if minimum_count > count:
        raise ValueError("bootstrap minimum_success_count exceeds n_resamples")
    return seed, count, minimum_count, fraction


def _record_from_summary(
    payload: Mapping[str, object],
    *,
    source_hash: str,
    label: str,
) -> DisorderSeries:
    if _integer(payload.get("schema_version"), label=f"{label} schema_version") != 1:
        raise ValueError(f"{label} schema_version must equal one")
    temperatures = _numeric_array(
        payload.get("temperatures"),
        label=f"{label} temperatures",
    )
    raw_observables = _mapping(payload.get("observables"), label=f"{label} observables")
    missing = [name for name in _OBSERVABLES if name not in raw_observables]
    if missing:
        raise ValueError(f"{label} is missing observable {missing[0]!r}")
    observables: dict[str, np.ndarray] = {}
    for name, values in raw_observables.items():
        if not isinstance(name, str) or not name:
            raise ValueError(f"{label} observable names must be nonempty strings")
        observables[name] = _numeric_array(
            values,
            label=f"{label} observable {name!r}",
        )
    return DisorderSeries(
        j_id=payload.get("j_id"),
        length=_integer(payload.get("length"), label=f"{label} length", minimum=2),
        temperatures=temperatures,
        observables=observables,
        source_hash=source_hash,
    )


def load_production_summary(path: str | Path) -> ProductionAnalysisInput:
    """Load Stage 7 summaries only after validating every frozen hash binding."""

    manifest_path = Path(path).resolve()
    if not manifest_path.is_file():
        raise FileNotFoundError(f"production summary is missing: {manifest_path}")
    manifest, manifest_hash = _read_json_object(
        manifest_path,
        label="production summary",
    )
    _require_stage(manifest, stage="stage7", label="production summary")
    if manifest.get("classification") != "PASS":
        raise ValueError("production summary classification must be PASS")
    root = manifest_path.parent

    _, protocol_path, protocol, protocol_hash = _hashed_json_descriptor(
        root,
        manifest.get("analysis_protocol"),
        label="analysis protocol",
    )
    _require_stage(protocol, stage="stage6", label="analysis protocol")
    variant_values = _sequence(protocol.get("variants"), label="analysis variants")
    if not variant_values:
        raise ValueError("analysis protocol must declare at least one ordered variant")
    variants = tuple(_variant(value, index=index) for index, value in enumerate(variant_values))
    nonlinear_bounds = _bounds(protocol.get("nonlinear_bounds"))
    seed, count, minimum_count, minimum_fraction = _bootstrap_settings(
        protocol.get("bootstrap")
    )

    protocol_sources = _inventory(
        protocol.get("source_inventory"),
        label="analysis protocol source_inventory",
    )
    manifest_sources = _inventory(
        manifest.get("frozen_source_inventory"),
        label="production summary frozen_source_inventory",
    )
    if manifest_sources != protocol_sources:
        raise ValueError(
            "production summary frozen source inventory does not match the Stage 6 protocol"
        )
    _verify_source_inventory(protocol_sources)

    descriptors = _sequence(manifest.get("summaries"), label="production summaries")
    if not descriptors:
        raise ValueError("production summary must list at least one per-J summary")
    records: list[DisorderSeries] = []
    summary_inventory: dict[str, str] = {}
    identities: set[tuple[int, str]] = set()
    for index, descriptor in enumerate(descriptors):
        relative, _, payload, digest = _hashed_json_descriptor(
            root,
            descriptor,
            label=f"summary file {index}",
        )
        if relative in summary_inventory:
            raise ValueError(f"duplicate summary path {relative!r}")
        record = _record_from_summary(
            payload,
            source_hash=digest,
            label=f"summary file {relative}",
        )
        identity = (record.length, record.j_id)
        if identity in identities:
            raise ValueError(f"duplicate summary record L={record.length}, j_id={record.j_id!r}")
        identities.add(identity)
        summary_inventory[relative] = digest
        records.append(record)

    return ProductionAnalysisInput(
        production_summary_path=manifest_path,
        production_summary_sha256=manifest_hash,
        protocol_path=protocol_path,
        protocol_sha256=protocol_hash,
        records=tuple(sorted(records, key=lambda value: (value.length, value.j_id))),
        variants=variants,
        nonlinear_bounds=nonlinear_bounds,
        bootstrap_seed=seed,
        n_resamples=count,
        minimum_success_count=minimum_count,
        minimum_success_fraction=minimum_fraction,
        source_inventory=protocol_sources,
        summary_inventory=dict(sorted(summary_inventory.items())),
    )


def _intervals_overlap(left: BootstrapInterval, right: BootstrapInterval) -> bool:
    return max(left.lower, right.lower) <= min(left.upper, right.upper)


def _verify_shared_replay(
    reference: BootstrapFSSResult,
    others: Sequence[BootstrapFSSResult | BootstrapCrossingResult],
) -> None:
    expected_axes = dict(reference.record_axes)
    for result in others:
        if dict(result.record_axes) != expected_axes:
            raise RuntimeError("Stage 8 analyses do not share one bootstrap record axis")
        if set(result.resample_indices) != set(reference.resample_indices):
            raise RuntimeError("Stage 8 analyses do not share one bootstrap size inventory")
        for length, expected in reference.resample_indices.items():
            if not np.array_equal(result.resample_indices[length], expected):
                raise RuntimeError("Stage 8 analyses do not share exact bootstrap matrices")


def run_stage8_analysis(source: ProductionAnalysisInput) -> Stage8AnalysisResult:
    """Run preregistered xi/L, Binder, joint, and crossing bootstrap analyses."""

    if not isinstance(source, ProductionAnalysisInput):
        raise TypeError("source must be a validated ProductionAnalysisInput")
    common = {
        "variants": source.variants,
        "n_resamples": source.n_resamples,
        "seed": source.bootstrap_seed,
        "minimum_success_count": source.minimum_success_count,
        "minimum_success_fraction": source.minimum_success_fraction,
        "nonlinear_bounds": source.nonlinear_bounds,
    }
    xi_fit = bootstrap_fss(source.records, "xi_over_l", **common)
    replay = {
        "resample_indices": xi_fit.resample_indices,
        "record_axes": xi_fit.record_axes,
    }
    binder_fit = bootstrap_fss(source.records, "binder", **common, **replay)
    joint_fit = bootstrap_fss(
        source.records,
        ("xi_over_l", "binder"),
        **common,
        **replay,
    )
    xi_crossings = bootstrap_pair_crossings(
        source.records,
        "xi_over_l",
        n_resamples=source.n_resamples,
        seed=source.bootstrap_seed,
        **replay,
    )
    binder_crossings = bootstrap_pair_crossings(
        source.records,
        "binder",
        n_resamples=source.n_resamples,
        seed=source.bootstrap_seed,
        **replay,
    )
    _verify_shared_replay(
        xi_fit,
        (binder_fit, joint_fit, xi_crossings, binder_crossings),
    )

    fits = {
        "xi_over_l": xi_fit,
        "binder": binder_fit,
        "joint": joint_fit,
    }
    xi_interval = xi_fit.statistical_intervals["tc"]
    binder_interval = binder_fit.statistical_intervals["tc"]
    joint_interval = joint_fit.statistical_intervals["tc"]
    compatibility = {
        "xi_vs_binder": _intervals_overlap(xi_interval, binder_interval),
        "xi_vs_joint": _intervals_overlap(xi_interval, joint_interval),
        "binder_vs_joint": _intervals_overlap(binder_interval, joint_interval),
    }
    compatibility["all_primary"] = all(compatibility.values())
    return Stage8AnalysisResult(
        production_summary_sha256=source.production_summary_sha256,
        protocol_sha256=source.protocol_sha256,
        ordered_variants=source.variants,
        nonlinear_bounds=source.nonlinear_bounds,
        bootstrap_seed=source.bootstrap_seed,
        n_resamples=source.n_resamples,
        minimum_success_count=source.minimum_success_count,
        minimum_success_fraction=source.minimum_success_fraction,
        source_inventory=source.source_inventory,
        summary_inventory=source.summary_inventory,
        fit_table=fits,
        crossings={
            "xi_over_l": xi_crossings,
            "binder": binder_crossings,
        },
        interval_compatibility=compatibility,
    )


def _identity_dict(value: RecordIdentity) -> dict[str, object]:
    return {
        "length": value.length,
        "j_id": value.j_id,
        "source_hash": value.source_hash,
    }


def _variant_dict(value: FSSVariant) -> dict[str, object]:
    return {
        "l_min": value.l_min,
        "temperature_window": list(value.temperature_window),
        "polynomial_order": value.polynomial_order,
        "parity": value.parity,
        "parity_order": value.parity_order,
        "fixed_omega": value.fixed_omega,
        "fixed_omega_p": value.fixed_omega_p,
    }


def _bounds_dict(value: NonlinearBounds) -> dict[str, list[float]]:
    return {
        "tc": list(value.tc),
        "nu": list(value.nu),
        "omega": list(value.omega),
        "omega_p": list(value.omega_p),
    }


def _interval_dict(value: BootstrapInterval) -> dict[str, float]:
    return {"lower": value.lower, "median": value.median, "upper": value.upper}


def _systematic_dict(value: SystematicSpread) -> dict[str, float]:
    return {
        "minimum": value.minimum,
        "maximum": value.maximum,
        "half_range": value.half_range,
    }


def _failure_dict(value: FitFailure) -> dict[str, object]:
    return {
        "resample_index": value.resample_index,
        "variant_index": value.variant_index,
        "reason": value.reason,
        "bound_hits": list(value.bound_hits),
    }


def _fit_dict(value: FSSFitResult) -> dict[str, object]:
    return {
        "observable_names": list(value.observable_names),
        "tc": value.tc,
        "nu": value.nu,
        "omega": value.omega,
        "omega_p": value.omega_p,
        "coefficients": {
            name: coefficients.tolist()
            for name, coefficients in value.coefficients.items()
        },
        "working_parameter_covariance": value.working_parameter_covariance.tolist(),
        "whitened_rss": value.whitened_rss,
        "whitened_rss_per_dof": value.whitened_rss_per_dof,
        "dof": value.dof,
        "residual_diagnostic": value.residual_diagnostic,
        "covariance_diagnostic": value.covariance_diagnostic,
        "covariance_condition_max": value.covariance_condition_max,
        "bound_hits": list(value.bound_hits),
        "failed_resamples": list(value.failed_resamples),
        "l_min": value.l_min,
        "temperature_window": list(value.temperature_window),
        "polynomial_order": value.polynomial_order,
        "parity_order": value.parity_order,
        "parity_model": value.parity_model,
        "omega_treatment": value.omega_treatment,
        "omega_p_treatment": value.omega_p_treatment,
        "nonlinear_bounds": _bounds_dict(value.nonlinear_bounds),
        "selected_records": [_identity_dict(item) for item in value.selected_records],
        "excluded_records": [_identity_dict(item) for item in value.excluded_records],
        "optimizer_message": value.optimizer_message,
        "nfev": value.nfev,
        "multistart_attempts": value.multistart_attempts,
        "multistart_successes": value.multistart_successes,
    }


def _bootstrap_fit_dict(value: BootstrapFSSResult) -> dict[str, object]:
    return {
        "selected_variant_index": value.selected_variant_index,
        "declared_variants": [_variant_dict(item) for item in value.declared_variants],
        "seed": value.seed,
        "resample_mode": value.resample_mode,
        "minimum_success_count": value.minimum_success_count,
        "minimum_success_fraction": value.minimum_success_fraction,
        "required_success_count": value.required_success_count,
        "adequate_variant_indices": list(value.adequate_variant_indices),
        "bootstrap_success_counts": {
            str(index): count for index, count in value.bootstrap_success_counts.items()
        },
        "bootstrap_success_fractions": {
            str(index): fraction
            for index, fraction in value.bootstrap_success_fractions.items()
        },
        "statistical_intervals": {
            name: _interval_dict(interval)
            for name, interval in value.statistical_intervals.items()
        },
        "bootstrap_intervals_by_variant": {
            str(index): {
                name: _interval_dict(interval) for name, interval in intervals.items()
            }
            for index, intervals in value.bootstrap_intervals_by_variant.items()
        },
        "finite_size_systematic": {
            name: _systematic_dict(spread)
            for name, spread in value.finite_size_systematic.items()
        },
        "headline_fit": _fit_dict(value.fit),
        "central_fits_by_variant": {
            str(index): _fit_dict(fit)
            for index, fit in value.central_fits_by_variant.items()
        },
        "failed_resamples": [_failure_dict(item) for item in value.failed_resamples],
        "variant_failures": [_failure_dict(item) for item in value.variant_failures],
    }


def _crossing_sample_dict(value: PairCrossingSample) -> dict[str, object]:
    return {
        "resample_index": value.resample_index,
        "sizes": list(value.sizes),
        "common_temperature_window": (
            list(value.common_temperature_window)
            if value.common_temperature_window is not None
            else None
        ),
        "temperatures": list(value.temperatures),
        "failed": value.failed,
        "reason": value.reason,
    }


def _crossing_dict(value: BootstrapCrossingResult) -> dict[str, object]:
    return {
        "observable": value.observable,
        "seed": value.seed,
        "resample_mode": value.resample_mode,
        "samples_by_pair": {
            f"{left}:{right}": [_crossing_sample_dict(item) for item in samples]
            for (left, right), samples in value.samples_by_pair.items()
        },
    }


def _result_dict(value: Stage8AnalysisResult) -> dict[str, object]:
    replay = value.fit_table["xi_over_l"]
    return {
        "schema_version": 1,
        "stage": "stage8",
        "production_summary_sha256": value.production_summary_sha256,
        "protocol_sha256": value.protocol_sha256,
        "ordered_variants": [_variant_dict(item) for item in value.ordered_variants],
        "nonlinear_bounds": _bounds_dict(value.nonlinear_bounds),
        "bootstrap": {
            "seed": value.bootstrap_seed,
            "resample_mode": replay.resample_mode,
            "n_resamples": value.n_resamples,
            "minimum_success_count": value.minimum_success_count,
            "minimum_success_fraction": value.minimum_success_fraction,
            "record_axes": {
                str(length): [_identity_dict(item) for item in identities]
                for length, identities in replay.record_axes.items()
            },
            "resample_indices": {
                str(length): matrix.tolist()
                for length, matrix in replay.resample_indices.items()
            },
        },
        "source_inventory": dict(value.source_inventory),
        "summary_inventory": dict(value.summary_inventory),
        "fit_table": {
            name: _bootstrap_fit_dict(fit) for name, fit in value.fit_table.items()
        },
        "crossings": {
            name: _crossing_dict(crossing)
            for name, crossing in value.crossings.items()
        },
        "interval_compatibility": dict(value.interval_compatibility),
    }


def write_stage8_analysis(result: Stage8AnalysisResult, path: str | Path) -> Path:
    """Atomically write one deterministic, non-overwriting Stage 8 JSON artifact."""

    if not isinstance(result, Stage8AnalysisResult):
        raise TypeError("result must be a Stage8AnalysisResult")
    destination = Path(path)
    payload = (
        json.dumps(
            _result_dict(result),
            ensure_ascii=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("ascii")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError as error:
            raise FileExistsError(
                f"refusing to overwrite Stage 8 analysis: {destination}"
            ) from error
        temporary.unlink()
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return destination

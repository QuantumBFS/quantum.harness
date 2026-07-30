from __future__ import annotations

import copy
import hashlib
import math
import stat
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
from scipy.optimize import least_squares

from .fss import _load_validated_cell, _read_canonical_json
from .paper_scan import validate_paper_scan_plan
from .planning import _write_immutable
from .provenance import canonical_json


Y_T = 1.587
Y_I = -0.815
_STAGE = "paper-aligned QMC_SSE finite-size reproduction"
_PARAMETERS = ("tc", "Q", "a1", "a2", "a3", "b1", "c1")
_HEX = frozenset("0123456789abcdef")


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _hash(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _HEX for character in value)
    ):
        raise ValueError(f"{label} must be lowercase hexadecimal SHA-256")
    return value


def _finite_vector(value: object, label: str) -> npt.NDArray[np.float64]:
    result = np.asarray(value, dtype=np.float64)
    if result.ndim != 1 or result.size < 2 or not np.all(np.isfinite(result)):
        raise ValueError(f"{label} must be a finite one-dimensional vector")
    return result


def _model(
    parameters: npt.ArrayLike,
    field: npt.NDArray[np.float64],
    length: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    tc, q, a1, a2, a3, b1, c1 = np.asarray(parameters, dtype=np.float64)
    delta = field - tc
    return (
        q
        + a1 * delta * length**Y_T
        + a2 * delta**2 * length ** (2.0 * Y_T)
        + a3 * delta**3 * length ** (3.0 * Y_T)
        + b1 * length**Y_I
        + c1 * delta * length ** (Y_I + Y_T)
    )


def _coordinate_data(
    points: Sequence[Mapping[str, Any]], lattice: str
) -> tuple[
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    list[list[tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]]],
]:
    expected_lengths = (
        set(range(6, 21, 2)) if lattice == "triangular" else set(range(10, 21, 2))
    )
    selected = [point for point in points if point.get("lattice") == lattice]
    if len(selected) != len(expected_lengths) * 5:
        raise ValueError(f"{lattice} points do not cover the frozen design")
    selected.sort(key=lambda point: (int(point["length"]), float(point["field"])))
    fields: list[float] = []
    lengths: list[float] = []
    binders: list[float] = []
    errors: list[float] = []
    chain_data = []
    seen: set[tuple[int, float]] = set()
    grouped_fields: dict[int, set[float]] = defaultdict(set)
    for point in selected:
        try:
            length = int(point["length"])
            field = float(point["field"])
            chains_value = point["chains"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("malformed paper Binder point") from exc
        if (
            length not in expected_lengths
            or not math.isfinite(field)
            or field <= 0
            or not isinstance(chains_value, Sequence)
            or isinstance(chains_value, (str, bytes))
            or len(chains_value) != 2
            or (length, field) in seen
        ):
            raise ValueError("paper Binder point violates the frozen design")
        seen.add((length, field))
        grouped_fields[length].add(field)
        chains = []
        for chain in chains_value:
            if not isinstance(chain, Mapping):
                raise ValueError("malformed primitive-moment chain")
            m2 = _finite_vector(chain.get("m2"), "chain m2")
            m4 = _finite_vector(chain.get("m4"), "chain m4")
            if m2.shape != m4.shape or np.any(m4 <= 0):
                raise ValueError("primitive moments must be paired with positive m4")
            chains.append((m2, m4))
        if chains[0][0].size != chains[1][0].size:
            raise ValueError("complete chains must contain equal bin counts")
        all_m2 = np.concatenate([chain[0] for chain in chains])
        all_m4 = np.concatenate([chain[1] for chain in chains])
        binder = float(all_m2.mean() ** 2 / all_m4.mean())
        leave = np.asarray(
            [
                float(chain[0].mean() ** 2 / chain[1].mean())
                for chain in reversed(chains)
            ]
        )
        error = math.sqrt(0.5 * float(np.sum((leave - leave.mean()) ** 2)))
        if not math.isfinite(binder) or not math.isfinite(error) or error <= 0:
            raise ValueError("complete-chain Binder estimate is invalid")
        fields.append(field)
        lengths.append(float(length))
        binders.append(binder)
        errors.append(error)
        chain_data.append(chains)
    if set(grouped_fields) != expected_lengths or any(
        len(values) != 5 for values in grouped_fields.values()
    ):
        raise ValueError(f"{lattice} field grid violates the frozen design")
    return (
        np.asarray(fields),
        np.asarray(lengths),
        np.asarray(binders),
        np.asarray(errors),
        chain_data,
    )


def _solve(
    field: npt.NDArray[np.float64],
    length: npt.NDArray[np.float64],
    binder: npt.NDArray[np.float64],
    error: npt.NDArray[np.float64],
    *,
    enforce_diagnostics: bool,
) -> tuple[npt.NDArray[np.float64], dict[str, Any]]:
    lower_field = float(field.min())
    upper_field = float(field.max())
    initial = np.asarray(
        [(lower_field + upper_field) / 2.0, float(np.median(binder)), 0, 0, 0, 0, 0],
        dtype=np.float64,
    )

    def residual(parameters: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        return (_model(parameters, field, length) - binder) / error

    fit = least_squares(
        residual,
        initial,
        bounds=(
            np.asarray([lower_field, -np.inf, -np.inf, -np.inf, -np.inf, -np.inf, -np.inf]),
            np.asarray([upper_field, np.inf, np.inf, np.inf, np.inf, np.inf, np.inf]),
        ),
        method="trf",
        x_scale="jac",
        max_nfev=10000,
    )
    values = np.asarray(fit.x, dtype=np.float64)
    standardized = residual(values)
    rank = int(np.linalg.matrix_rank(fit.jac))
    degrees = field.size - len(_PARAMETERS)
    chi_square = float(np.dot(standardized, standardized))
    reduced = chi_square / degrees
    rms = float(np.sqrt(np.mean(standardized**2)))
    diagnostics = {
        "chi_square": chi_square,
        "degrees_of_freedom": degrees,
        "reduced_chi_square": reduced,
        "standardized_residual_rms": rms,
        "maximum_absolute_standardized_residual": float(
            np.max(np.abs(standardized))
        ),
        "jacobian_rank": rank,
    }
    margin = max(1e-12, (upper_field - lower_field) * 1e-8)
    if (
        not fit.success
        or rank != len(_PARAMETERS)
        or not np.all(np.isfinite(values))
        or not np.all(np.isfinite(standardized))
        or not lower_field + margin < values[0] < upper_field - margin
    ):
        raise ValueError("Eq. (23) fit is rank-deficient, non-finite, or out of range")
    if enforce_diagnostics and (
        not math.isfinite(reduced)
        or reduced > 10.0
        or diagnostics["maximum_absolute_standardized_residual"] > 8.0
    ):
        raise ValueError("Eq. (23) fit residual diagnostics are unacceptable")
    return values, diagnostics


def _fit_lattice(
    points: Sequence[Mapping[str, Any]], lattice: str
) -> dict[str, Any]:
    field, length, binder, error, chains = _coordinate_data(points, lattice)
    parameters, diagnostics = _solve(
        field, length, binder, error, enforce_diagnostics=True
    )
    replicates = []
    for coordinate_index, coordinate_chains in enumerate(chains):
        for retained_chain in coordinate_chains:
            replicate_binder = binder.copy()
            replicate_error = error.copy()
            replicate_binder[coordinate_index] = float(
                retained_chain[0].mean() ** 2 / retained_chain[1].mean()
            )
            # Preserve the pre-registered coordinate weight; the resampling
            # changes the complete-chain estimate, not the design matrix.
            replicate, _ = _solve(
                field,
                length,
                replicate_binder,
                replicate_error,
                enforce_diagnostics=False,
            )
            replicates.append(replicate)
    jackknife = np.asarray(replicates)
    count = jackknife.shape[0]
    centered = jackknife - jackknife.mean(axis=0)
    covariance = (count - 1.0) / count * centered.T @ centered
    if (
        covariance.shape != (7, 7)
        or not np.all(np.isfinite(covariance))
        or covariance[0, 0] <= 0
    ):
        raise ValueError("delete-one-complete-chain covariance is invalid")
    return {
        "lattice": lattice,
        "parameters": {
            name: float(value) for name, value in zip(_PARAMETERS, parameters, strict=True)
        },
        "parameter_order": list(_PARAMETERS),
        "parameter_covariance": covariance.tolist(),
        "tc": float(parameters[0]),
        "tc_standard_error": float(math.sqrt(covariance[0, 0])),
        "point_count": int(field.size),
        "complete_chain_count": int(count),
        **diagnostics,
    }


def analyze_paper_points(
    points: Sequence[Mapping[str, Any]],
    *,
    plan_sha256: str,
    source_sha256: str,
    evidence_bindings: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    _hash(plan_sha256, "plan_sha256")
    _hash(source_sha256, "source_sha256")
    if len(points) != 70:
        raise ValueError("paper analysis requires exactly 70 physical coordinates")
    if len(evidence_bindings) != 140:
        raise ValueError("paper analysis requires exactly 140 evidence bindings")
    fits = [_fit_lattice(points, lattice) for lattice in ("triangular", "honeycomb")]
    triangular, honeycomb = fits
    ratio = triangular["tc"] / honeycomb["tc"]
    ratio_error = abs(ratio) * math.hypot(
        triangular["tc_standard_error"] / triangular["tc"],
        honeycomb["tc_standard_error"] / honeycomb["tc"],
    )
    if not math.isfinite(ratio_error) or ratio_error <= 0:
        raise ValueError("critical-field ratio uncertainty is invalid")
    root_five = math.sqrt(5.0)
    result: dict[str, Any] = {
        "schema_version": "challenge148-paper-fss-analysis-v1",
        "stage": _STAGE,
        "interpretation": (
            "Paper-aligned low-precision QMC_SSE reproduction; this is not the "
            "final independent two-code verdict."
        ),
        "plan_sha256": plan_sha256,
        "source_sha256": source_sha256,
        "input_bindings": [dict(binding) for binding in evidence_bindings],
        "binder_ratio": "<m^2>^2/<m^4>",
        "fit": {
            "equation": (
                "Q+a1*d*L^yt+a2*d^2*L^(2yt)+a3*d^3*L^(3yt)"
                "+b1*L^yi+c1*d*L^(yi+yt), d=t-tc"
            ),
            "fixed_exponents": {"y_t": Y_T, "y_i": Y_I},
            "covariance": "delete-one-complete-chain-jackknife-v1",
            "lattices": fits,
        },
        "comparison": {
            "triangular_divided_by_honeycomb": ratio,
            "standard_error": ratio_error,
            "sqrt_5": root_five,
            "difference": ratio - root_five,
            "normalized_difference": (ratio - root_five) / ratio_error,
        },
    }
    result["evidence_sha256"] = _digest(result["input_bindings"])
    result["analysis_sha256"] = _digest(result)
    return result


def load_validated_paper_root(
    production_root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    root = Path(production_root).resolve()
    if not root.is_dir() or stat.S_ISLNK(root.lstat().st_mode):
        raise ValueError("paper production root must be a real directory")
    _, plan = _read_canonical_json(root / "plan.json", "paper plan", indented=True)
    validate_paper_scan_plan(plan)
    cells = plan["cells"]
    if len(cells) != 140:
        raise ValueError("paper plan must contain exactly 140 cells")
    cells_root = root / "cells"
    if not cells_root.is_dir() or stat.S_ISLNK(cells_root.lstat().st_mode):
        raise ValueError("paper cells root must be a real directory")
    expected = {cell["cell_id"] for cell in cells}
    if {path.name for path in cells_root.iterdir()} != expected:
        raise ValueError("paper root must contain exactly the 140 planned cells")
    grouped: dict[tuple[str, int, float], list[dict[str, Any]]] = defaultdict(list)
    bindings = []
    for index, cell in enumerate(cells):
        records, binding = _load_validated_cell(root, plan, cell, index)
        grouped[(cell["lattice"], cell["length"], float(cell["field"]))].append(
            {
                "m2": [
                    record["m2_sum"] / record["sample_count"] for record in records
                ],
                "m4": [
                    record["m4_sum"] / record["sample_count"] for record in records
                ],
            }
        )
        bindings.append(binding)
    points = [
        {
            "lattice": coordinate[0],
            "length": coordinate[1],
            "field": coordinate[2],
            "chains": chains,
        }
        for coordinate, chains in sorted(grouped.items())
    ]
    if len(points) != 70 or any(len(point["chains"]) != 2 for point in points):
        raise ValueError("paper evidence must form exactly 70 paired coordinates")
    return plan, points, bindings


def analyze_paper_root(production_root: Path) -> dict[str, Any]:
    plan, points, bindings = load_validated_paper_root(production_root)
    return analyze_paper_points(
        points,
        plan_sha256=plan["plan_sha256"],
        source_sha256=plan["build_info"]["source_hash"],
        evidence_bindings=bindings,
    )


def write_paper_analysis(path: Path, analysis: Mapping[str, Any]) -> None:
    value = copy.deepcopy(dict(analysis))
    digest = value.pop("analysis_sha256", None)
    if digest != _digest(value):
        raise ValueError("analysis_sha256 does not bind the analysis content")
    import json

    payload = (
        json.dumps(analysis, allow_nan=False, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode()
    _write_immutable(Path(path), payload)

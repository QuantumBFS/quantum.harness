#!/usr/bin/env python3
"""Preregistered verification harness for quantum.harness issue 121.

Random-word runs are implementation audits, not proofs. Exact certificates
record the algebraic statements used by the theorem draft. Durable outputs are
atomic and COMPLETE is created only when every preregistered cell passes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from itertools import combinations, permutations
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Sequence

import mpmath as mp
import numpy as np
import scipy
from scipy.linalg import expm

SOLUTION_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SOLUTION_DIR))
import sign_problem_hunter as sph

Array = np.ndarray
CSV_FIELDS = (
    "cell_id", "kind", "sample", "dimension", "n", "depth", "regime",
    "component", "det_class", "det_method", "det_sign", "log_abs_det",
    "determinant_decimal", "sigma_min_i_plus_t", "structural_diagnostic",
    "fock_checked", "fock_abs_error", "word_sha256",
)


@dataclass(frozen=True)
class Cell:
    cell_id: str
    kind: str
    parameters: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def atomic_write_json(path: Path, payload: object) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def atomic_write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temporary, path)


def parse_fraction(value: Any) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, float):
        return Fraction(str(value))
    if isinstance(value, str):
        return Fraction(value)
    raise TypeError(f"cannot parse Fraction from {type(value).__name__}")

def fraction_string(value: Fraction) -> str:
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def permutation_matrices_3() -> tuple[tuple[tuple[int, ...], Array], ...]:
    return tuple(
        (perm, np.eye(3, dtype=float)[list(perm), :])
        for perm in permutations(range(3))
    )


def ab_generator(epsilon: Any, kappa: Any, family: str = "A") -> Array:
    eps = float(parse_fraction(epsilon))
    kap = float(parse_fraction(kappa))
    if eps <= 0.0 or kap <= 0.0 or 40.0 * eps + 59.0 * kap >= 2.0:
        raise ValueError(
            "A/B parameters require epsilon>0, kappa>0, "
            "40 epsilon + 59 kappa < 2"
        )
    matrix = np.array(
        [
            [-1.0 - eps - kap, 1.0, -eps],
            [0.0, -1.0 - kap, 1.0],
            [2.0, 0.0, -2.0 - kap],
        ]
    )
    if family == "A":
        return matrix
    if family == "B":
        signs = np.diag([1.0, 1.0, -1.0])
        return signs @ matrix @ signs
    raise ValueError("family must be A or B")


def ab_orbit(epsilon: Any, kappa: Any) -> tuple[tuple[str, int, Array], ...]:
    result: list[tuple[str, int, Array]] = []
    for family in ("A", "B"):
        base = ab_generator(epsilon, kappa, family)
        for index, (_, permutation_matrix) in enumerate(permutation_matrices_3()):
            result.append(
                (family, index, permutation_matrix @ base @ permutation_matrix.T)
            )
    return tuple(result)


def mu_infinity(matrix: Array) -> float:
    square = np.asarray(matrix, dtype=float)
    diagonal = np.diag(square)
    row_values = diagonal + np.sum(np.abs(square), axis=1) - np.abs(diagonal)
    return float(np.max(row_values))


def fraction_ab_generator(
    epsilon: Fraction,
    kappa: Fraction,
    family: str,
) -> list[list[Fraction]]:
    matrix = [
        [-1 - epsilon - kappa, Fraction(1), -epsilon],
        [Fraction(0), -1 - kappa, Fraction(1)],
        [Fraction(2), Fraction(0), -2 - kappa],
    ]
    if family == "A":
        return matrix
    if family != "B":
        raise ValueError("family must be A or B")
    signs = (Fraction(1), Fraction(1), Fraction(-1))
    return [
        [signs[i] * matrix[i][j] * signs[j] for j in range(3)]
        for i in range(3)
    ]


def permute_fraction_matrix(
    matrix: Sequence[Sequence[Fraction]],
    perm: Sequence[int],
) -> list[list[Fraction]]:
    return [[matrix[perm[i]][perm[j]] for j in range(3)] for i in range(3)]


def fraction_rank(rows: Sequence[Sequence[Fraction]]) -> int:
    work = [list(map(parse_fraction, row)) for row in rows]
    if not work:
        return 0
    rank = 0
    column_count = len(work[0])
    for column in range(column_count):
        pivot = next(
            (row for row in range(rank, len(work)) if work[row][column] != 0),
            None,
        )
        if pivot is None:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        pivot_value = work[rank][column]
        work[rank] = [value / pivot_value for value in work[rank]]
        for row in range(len(work)):
            if row == rank or work[row][column] == 0:
                continue
            multiplier = work[row][column]
            work[row] = [
                work[row][entry] - multiplier * work[rank][entry]
                for entry in range(column_count)
            ]
        rank += 1
        if rank == len(work):
            break
    return rank


def matmul_fraction(
    left: Sequence[Sequence[Fraction]],
    right: Sequence[Sequence[Fraction]],
) -> list[list[Fraction]]:
    rows = len(left)
    inner = len(right)
    columns = len(right[0])
    return [
        [sum(left[i][k] * right[k][j] for k in range(inner)) for j in range(columns)]
        for i in range(rows)
    ]


def trace_fraction(matrix: Sequence[Sequence[Fraction]]) -> Fraction:
    return sum(matrix[index][index] for index in range(len(matrix)))


def twirl_tau2_coefficients(
    matrix: Sequence[Sequence[Fraction]],
) -> tuple[Fraction, Fraction]:
    square = matmul_fraction(matrix, matrix)
    a_value = sum(sum(row) for row in matrix) / 3
    b_value = sum(sum(row) for row in square) / 3
    trace_value = trace_fraction(matrix)
    square_trace = trace_fraction(square)
    interaction = (
        (trace_value**2 - square_trace) / 2
        - trace_value * a_value
        + b_value
    )
    non_gaussian = interaction - (trace_value - a_value) ** 2 / 4
    return interaction, non_gaussian


def determinant_2_fraction(matrix: Sequence[Sequence[Fraction]]) -> Fraction:
    return matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]


def matmul_2_fraction(
    left: Sequence[Sequence[Fraction]],
    right: Sequence[Sequence[Fraction]],
) -> list[list[Fraction]]:
    return [
        [sum(left[i][k] * right[k][j] for k in range(2)) for j in range(2)]
        for i in range(2)
    ]


def exact_component_weights() -> dict[str, str]:
    boost = [
        [Fraction(5, 3), Fraction(4, 3)],
        [Fraction(4, 3), Fraction(5, 3)],
    ]
    representatives = {
        "++": [[Fraction(1), Fraction(0)], [Fraction(0), Fraction(1)]],
        "--": [[Fraction(-1), Fraction(0)], [Fraction(0), Fraction(-1)]],
        "-+": [[Fraction(-1), Fraction(0)], [Fraction(0), Fraction(1)]],
        "+-": [[Fraction(1), Fraction(0)], [Fraction(0), Fraction(-1)]],
    }
    weights: dict[str, str] = {}
    for component, representative in representatives.items():
        product = matmul_2_fraction(representative, boost)
        shifted = [
            [
                product[i][j] + (Fraction(1) if i == j else Fraction(0))
                for j in range(2)
            ]
            for i in range(2)
        ]
        weights[component] = fraction_string(determinant_2_fraction(shifted))
    return weights


def exact_certificates(manifest: dict[str, Any]) -> dict[str, Any]:
    center = next(
        item for item in manifest["candidate"]["regimes"] if item["id"] == "center"
    )
    epsilon = parse_fraction(center["epsilon"])
    kappa = parse_fraction(center["kappa"])
    numerator = 2 - 40 * epsilon - 59 * kappa
    upper = -numerator / (13 * (2 - 8 * epsilon - 13 * kappa))
    lower = numerator / (7 * (6 + 8 * epsilon + 7 * kappa))

    support: list[list[Fraction]] = []
    row_rates: list[Fraction] = []
    for family in ("A", "B"):
        base = fraction_ab_generator(epsilon, kappa, family)
        for perm in permutations(range(3)):
            matrix = permute_fraction_matrix(base, perm)
            support.append([value for row in matrix for value in row])
            for row in range(3):
                row_rates.append(
                    matrix[row][row]
                    + sum(
                        abs(matrix[row][column])
                        for column in range(3)
                        if column != row
                    )
                )

    epsilon_star = Fraction(2, 3)
    polynomial_minimum = (
        2 * epsilon_star**3 + epsilon_star**2 - 4 * epsilon_star + 3
    )
    components = exact_component_weights()

    twirl_coefficients = {
        family: twirl_tau2_coefficients(
            fraction_ab_generator(epsilon, kappa, family)
        )
        for family in ("A", "B")
    }
    expected_twirl_coefficients = {
        "A": (Fraction(15062013, 3000000), Fraction(363599, 360000)),
        "B": (Fraction(3056033, 3000000), Fraction(797, 120000)),
    }

    t_value = Fraction(3, 4)
    a_value = Fraction(1)
    b_value = epsilon
    c_value = Fraction(1)
    d_value = Fraction(2)
    delta_1 = delta_2 = delta_3 = kappa
    g_value = (
        d_value * t_value * (1 - t_value)
        - b_value * (1 + t_value)
        - c_value * (1 - t_value)
        - delta_1 - delta_2 - delta_3 * t_value**2
    )
    p_value = (2 + t_value) * (
        (1 - t_value) * (d_value - c_value)
        - b_value * (1 + t_value)
        - delta_1 - delta_2 - delta_3 * t_value
    )
    q_value = (2 - t_value) * (
        (1 - t_value) * (c_value + d_value)
        + b_value * (1 + t_value)
        + delta_1 + delta_2 - delta_3 * t_value
    )
    checks = {
        "open_region": (
            epsilon > 0 and kappa > 0 and 40 * epsilon + 59 * kappa < 2
        ),
        "all_exact_row_rates_minus_kappa": all(
            value == -kappa for value in row_rates
        ),
        "opposite_edge_product": -2 * epsilon < 0,
        "full_support_fraction_rank_9": fraction_rank(support) == 9,
        "no_common_quadratic_bounds_disjoint": upper < 0 < lower,
        "standard_polynomial_minimum_positive": (
            polynomial_minimum == Fraction(37, 27)
        ),
        "split_boost_identity": (
            Fraction(25, 9) - Fraction(16, 9) == 1
        ),
        "component_weights": components
        == {"++": "16/3", "--": "-4/3", "-+": "0", "+-": "0"},
        "twirl_tau2_coefficients": (
            twirl_coefficients == expected_twirl_coefficients
        ),
        "seven_parameter_t_3_4": (
            (g_value, p_value, q_value)
            == (Fraction(1679, 16000), Fraction(10109, 16000), Fraction(15375, 16000))
        ),
    }
    return {
        "schema_version": 1,
        "status": "pass" if all(checks.values()) else "fail",
        "parameters": {
            "epsilon": fraction_string(epsilon),
            "kappa": fraction_string(kappa),
        },
        "certificates": {
            "mu_infinity": fraction_string(-kappa),
            "opposite_edge_product_A13_A31": fraction_string(-2 * epsilon),
            "support_span_rank": fraction_rank(support),
            "no_common_H_upper_bound": fraction_string(upper),
            "no_common_H_lower_bound": fraction_string(lower),
            "standard_polynomial": "2 epsilon^3 + epsilon^2 - 4 epsilon + 3",
            "standard_polynomial_minimizer_nonnegative_axis": "2/3",
            "standard_polynomial_minimum": fraction_string(polynomial_minimum),
            "o11_component_det_I_plus": components,
            "twirl_tau2": {
                family: {
                    "interaction": fraction_string(values[0]),
                    "non_gaussian": fraction_string(values[1]),
                }
                for family, values in twirl_coefficients.items()
            },
            "seven_parameter_at_t_3_4": {
                "G": fraction_string(g_value),
                "p": fraction_string(p_value),
                "q": fraction_string(q_value),
            },
        },
        "checks": checks,
        "interpretation": (
            "Exact Fraction arithmetic; these certify formulas, not "
            "literature priority."
        ),
    }


def load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_manifest(payload)
    return payload


def validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported manifest schema_version")
    candidate = manifest["candidate"]
    regime_ids = [item["id"] for item in candidate["regimes"]]
    if len(regime_ids) != len(set(regime_ids)) or "center" not in regime_ids:
        raise ValueError("candidate regime ids must be unique and include center")
    if min(candidate["dimensions"]) < 3:
        raise ValueError("candidate dimensions must be at least three")
    sample_count = int(candidate["samples_per_cell"])
    indices = list(manifest["fock_oracle"]["sample_indices"])
    if len(indices) != 3 or len(set(indices)) != 3:
        raise ValueError("exactly three distinct Fock sample indices are required")
    if min(indices) < 0 or max(indices) >= sample_count:
        raise ValueError("Fock sample index is outside its candidate cell")
    for regime in candidate["regimes"]:
        if regime["kind"] != "fixed":
            continue
        epsilon = parse_fraction(regime["epsilon"])
        kappa = parse_fraction(regime["kappa"])
        if not (epsilon > 0 and kappa > 0 and 40 * epsilon + 59 * kappa < 2):
            raise ValueError(f"fixed regime {regime['id']} is outside the open triangle")

    expected = manifest["expected_workload"]
    candidate_cells = (
        len(candidate["dimensions"])
        * len(candidate["depths"])
        * len(candidate["regimes"])
    )
    candidate_words = candidate_cells * sample_count
    split = manifest["positive_anchors"]["split_orthogonal"]
    semigroup = manifest["positive_anchors"]["semigroup_cone"]
    controls = manifest["component_controls"]
    if set(controls["components"]) != {"++", "--", "-+", "+-"}:
        raise ValueError("component controls must cover all four O(n,n) components")

    split_cells = len(split["n_values"]) * len(split["depths"])
    semigroup_cells = len(semigroup["n_values"]) * len(semigroup["depths"])
    component_cells = (
        len(controls["n_values"])
        * len(controls["depths"])
        * len(controls["components"])
    )
    split_words = split_cells * int(split["samples_per_cell"])
    semigroup_words = semigroup_cells * int(semigroup["samples_per_cell"])
    component_words = component_cells * int(controls["samples_per_cell"])
    total_cells = candidate_cells + split_cells + semigroup_cells + component_cells

    fock_maximum_dimension = int(manifest["fock_oracle"]["maximum_dimension"])
    fock_candidate_cells = (
        sum(
            int(dimension) <= fock_maximum_dimension
            for dimension in candidate["dimensions"]
        )
        * len(candidate["depths"])
        * len(candidate["regimes"])
    )
    fock_oracle_checks = fock_candidate_cells * len(indices)

    physical = manifest["physical_benchmark"]
    if int(physical["sites"]) != 4 or physical["boundary"] != "open":
        raise ValueError("physical benchmark must be the four-site open chain")
    if parse_fraction(physical["chemical_potential"]) != 0:
        raise ValueError("physical benchmark must remain at chemical potential zero")
    if any(parse_fraction(value) <= 0 for value in physical["couplings"].values()):
        raise ValueError("physical benchmark couplings must be positive")
    physical_words = (
        len(physical["betas"]) * int(physical["poisson_samples_per_beta"])
    )
    core_words = candidate_words + split_words + semigroup_words + component_words
    computed = {
        "candidate_cells": candidate_cells,
        "candidate_words": candidate_words,
        "split_cells": split_cells,
        "split_words": split_words,
        "semigroup_cells": semigroup_cells,
        "semigroup_words": semigroup_words,
        "component_cells": component_cells,
        "component_words": component_words,
        "total_cells": total_cells,
        "total_words": core_words,
        "fock_oracle_checks": fock_oracle_checks,
        "physical_poisson_words": physical_words,
        "total_random_words_including_physical": core_words + physical_words,
    }
    for key, value in computed.items():
        if int(expected[key]) != value:
            raise ValueError(f"expected_workload.{key}={expected[key]} but protocol gives {value}")


def build_cells(manifest: dict[str, Any]) -> tuple[Cell, ...]:
    cells: list[Cell] = []
    candidate = manifest["candidate"]
    for regime in candidate["regimes"]:
        for dimension in candidate["dimensions"]:
            for depth in candidate["depths"]:
                cells.append(
                    Cell(
                        f"candidate__{regime['id']}__d{dimension:02d}__m{depth:03d}",
                        "candidate",
                        {
                            "regime": regime["id"],
                            "dimension": int(dimension),
                            "depth": int(depth),
                        },
                    )
                )

    for kind, key in (
        ("split_orthogonal", "split_orthogonal"),
        ("semigroup_cone", "semigroup_cone"),
    ):
        config = manifest["positive_anchors"][key]
        for n in config["n_values"]:
            for depth in config["depths"]:
                cells.append(
                    Cell(
                        f"{kind}__n{n:02d}__m{depth:03d}",
                        kind,
                        {"n": int(n), "dimension": 2 * int(n), "depth": int(depth)},
                    )
                )

    controls = manifest["component_controls"]
    for component in controls["components"]:
        for n in controls["n_values"]:
            for depth in controls["depths"]:
                label = component.replace("+", "p").replace("-", "m")
                cells.append(
                    Cell(
                        f"component__{label}__n{n:02d}__m{depth:03d}",
                        "component_control",
                        {
                            "component": component,
                            "n": int(n),
                            "dimension": 2 * int(n),
                            "depth": int(depth),
                        },
                    )
                )
    return tuple(cells)


def derive_seed(base_seed: int, cell_id: str) -> int:
    digest = hashlib.sha256(f"{base_seed}:{cell_id}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def regime_by_id(manifest: dict[str, Any], regime_id: str) -> dict[str, Any]:
    return next(
        item for item in manifest["candidate"]["regimes"] if item["id"] == regime_id
    )


def sample_ab_parameters(
    regime: dict[str, Any],
    rng: np.random.Generator,
) -> tuple[float, float]:
    if regime["kind"] == "fixed":
        return float(parse_fraction(regime["epsilon"])), float(parse_fraction(regime["kappa"]))
    if regime["kind"] != "dirichlet_open_triangle":
        raise ValueError(f"unsupported candidate regime kind {regime['kind']}")
    alpha = np.asarray(regime["alpha"], dtype=float)
    x, y, _ = rng.dirichlet(alpha)
    epsilon = float(x / 20.0)
    kappa = float(2.0 * y / 59.0)
    if not (epsilon > 0.0 and kappa > 0.0 and 40.0 * epsilon + 59.0 * kappa < 2.0):
        raise RuntimeError("Dirichlet map left the open A/B triangle")
    return epsilon, kappa


def sample_log_uniform(
    rng: np.random.Generator,
    distribution: dict[str, Any],
) -> float:
    if distribution["kind"] != "log_uniform":
        raise ValueError("only log_uniform time distributions are supported")
    minimum = float(distribution["minimum"])
    maximum = float(distribution["maximum"])
    if not (0.0 < minimum <= maximum):
        raise ValueError("log_uniform bounds must obey 0 < minimum <= maximum")
    return float(math.exp(rng.uniform(math.log(minimum), math.log(maximum))))


def mp_matrix(matrix: Array) -> mp.matrix:
    square = np.asarray(matrix)
    return mp.matrix(
        [
            [mp.mpf(format(float(square[i, j]), ".17g")) for j in range(square.shape[1])]
            for i in range(square.shape[0])
        ]
    )


def high_precision_product(
    factor_specs: Sequence[dict[str, Any]],
    dimension: int,
) -> mp.matrix:
    product = mp.eye(dimension)
    for spec in factor_specs:
        matrix = mp_matrix(spec["matrix"])
        if spec["kind"] == "exponential":
            factor = mp.expm(matrix)
        elif spec["kind"] == "matrix":
            factor = matrix
        else:
            raise ValueError(f"unknown high-precision factor kind {spec['kind']}")
        product = factor * product
    return product


def stable_determinant_i_plus(
    product: Array,
    factor_specs: Sequence[dict[str, Any]],
    precision: dict[str, Any],
) -> dict[str, Any]:
    square = np.asarray(product, dtype=float)
    shifted = np.eye(square.shape[0]) + square
    sign, log_abs = np.linalg.slogdet(shifted)
    singular_values = np.linalg.svd(shifted, compute_uv=False)
    sigma_min = float(singular_values[-1])
    threshold = float(precision["sigma_min_escalation"])
    needs_high_precision = (
        not np.isfinite(log_abs) or sign <= 0 or sigma_min < threshold
    )

    base = {
        "double_sign": int(sign),
        "double_log_abs_det": float(log_abs),
        "sigma_min_i_plus_t": sigma_min,
        "escalated": bool(needs_high_precision),
    }
    if not needs_high_precision:
        maximum_log = math.log(sys.float_info.max)
        if float(log_abs) <= maximum_log:
            determinant: float | None = float(sign * math.exp(float(log_abs)))
            determinant_decimal = format(determinant, ".17g")
            method = "numpy_slogdet"
        else:
            log_ten = math.log(10.0)
            exponent = math.floor(float(log_abs) / log_ten)
            mantissa = float(sign) * math.exp(float(log_abs) - exponent * log_ten)
            determinant = None
            determinant_decimal = f"{mantissa:.16g}e{exponent:+d}"
            method = "numpy_slogdet_log_only"
        return {
            **base,
            "classification": "positive" if sign > 0 else "negative",
            "method": method,
            "sign": int(sign),
            "log_abs_det": float(log_abs),
            "determinant_decimal": determinant_decimal,
            "determinant_float": determinant,
        }

    if not factor_specs:
        return {
            **base,
            "classification": "inconclusive",
            "method": "unavailable_high_precision_rebuild",
            "sign": 0,
            "log_abs_det": float(log_abs),
            "determinant_decimal": "unresolved",
            "determinant_float": None,
        }

    dps = int(precision["mpmath_dps"])
    zero_tolerance = mp.mpf(str(precision["high_precision_zero_tolerance"]))
    imaginary_tolerance = mp.mpf(str(precision["high_precision_imag_tolerance"]))
    try:
        with mp.workdps(dps):
            rebuilt = high_precision_product(factor_specs, square.shape[0])
            determinant_mp = mp.det(mp.eye(square.shape[0]) + rebuilt)
            imaginary = abs(mp.im(determinant_mp))
            real = mp.re(determinant_mp)
            if imaginary > imaginary_tolerance:
                classification = "inconclusive"
                resolved_sign = 0
            elif abs(real) <= zero_tolerance:
                classification = "inconclusive"
                resolved_sign = 0
            else:
                classification = "positive" if real > 0 else "negative"
                resolved_sign = 1 if real > 0 else -1
            log_mp = mp.log(abs(real)) if real != 0 else mp.ninf
            decimal = mp.nstr(real, 40)
            determinant_float = float(real) if abs(real) < mp.mpf("1e308") else None
            return {
                **base,
                "classification": classification,
                "method": f"mpmath_{dps}dps",
                "sign": resolved_sign,
                "log_abs_det": float(log_mp),
                "determinant_decimal": decimal,
                "determinant_float": determinant_float,
                "high_precision_imag_abs": mp.nstr(imaginary, 12),
            }
    except Exception as error:
        return {
            **base,
            "classification": "inconclusive",
            "method": f"mpmath_{dps}dps_failed",
            "sign": 0,
            "log_abs_det": float(log_abs),
            "determinant_decimal": "unresolved",
            "determinant_float": None,
            "high_precision_error": f"{type(error).__name__}: {error}",
        }


def sector_indices(orbitals: int, particles: int) -> list[int]:
    return [state for state in range(1 << orbitals) if state.bit_count() == particles]


def direct_fock_trace(factor_specs: Sequence[dict[str, Any]]) -> complex:
    if not factor_specs or any(spec["kind"] != "exponential" for spec in factor_specs):
        raise ValueError("direct Fock oracle requires a nonempty exponential word")
    orbitals = np.asarray(factor_specs[0]["matrix"]).shape[0]
    indices = [sector_indices(orbitals, particles) for particles in range(orbitals + 1)]
    sector_products = {
        particles: np.eye(len(indices[particles]), dtype=float)
        for particles in range(orbitals + 1)
    }
    for spec in factor_specs:
        generator = np.asarray(spec["matrix"], dtype=float)
        lifted = sph.bilinear_fock_operator(generator)
        for particles in range(orbitals + 1):
            block_indices = indices[particles]
            block = lifted[np.ix_(block_indices, block_indices)]
            sector_products[particles] = expm(block) @ sector_products[particles]
    return complex(sum(np.trace(block) for block in sector_products.values()))


def exterior_representation(matrix: Array, particles: int) -> Array:
    dimension = np.asarray(matrix).shape[0]
    subsets = list(combinations(range(dimension), particles))
    if particles == 0:
        return np.ones((1, 1))
    result = np.zeros((len(subsets), len(subsets)))
    for row, destination in enumerate(subsets):
        for column, source in enumerate(subsets):
            result[row, column] = np.linalg.det(
                np.asarray(matrix)[np.ix_(destination, source)]
            )
    return result


def twirl_sector_diagnostics(matrix: Array, tau: float) -> dict[str, float]:
    operator = np.zeros((8, 8))
    for _, permutation_matrix in permutation_matrices_3():
        generator = tau * permutation_matrix @ matrix @ permutation_matrix.T
        operator += expm(sph.bilinear_fock_operator(generator))
    operator /= 6.0
    one_indices = sector_indices(3, 1)
    two_indices = sector_indices(3, 2)
    block_one = operator[np.ix_(one_indices, one_indices)]
    block_two = operator[np.ix_(two_indices, two_indices)]
    permutation_data = permutation_matrices_3()
    p_trivial = sum(
        exterior_representation(permutation_matrix, 1)
        for _, permutation_matrix in permutation_data
    ) / 6.0
    p_sign = sum(
        int(round(np.linalg.det(permutation_matrix)))
        * exterior_representation(permutation_matrix, 2)
        for _, permutation_matrix in permutation_data
    ) / 6.0
    alpha = float(np.trace(p_trivial @ block_one))
    beta = float((np.trace(block_one) - alpha) / 2.0)
    d_two = float(np.trace(p_sign @ block_two))
    gamma = float((np.trace(block_two) - d_two) / 2.0)
    zeta = float(operator[7, 7])
    return {
        "vacuum": float(operator[0, 0]),
        "alpha": alpha,
        "beta": beta,
        "gamma": gamma,
        "d2": d_two,
        "zeta": zeta,
        "gaussian_gap_d2_minus_beta2": d_two - beta * beta,
        "gaussian_gap_gamma_minus_alpha_beta": gamma - alpha * beta,
        "gaussian_gap_zeta_minus_alpha_beta2": zeta - alpha * beta * beta,
        "hermiticity_residual_fro": float(
            np.linalg.norm(operator - operator.T.conj(), ord="fro")
        ),
    }


def run_twirl_checks(manifest: dict[str, Any]) -> dict[str, Any]:
    config = manifest["twirl_checks"]
    epsilon = config["epsilon"]
    kappa = config["kappa"]
    tau = float(parse_fraction(config["tau"]))
    results = {
        family: twirl_sector_diagnostics(ab_generator(epsilon, kappa, family), tau)
        for family in ("A", "B")
    }
    hermiticity_tolerance = float(config["hermiticity_tolerance"])
    nongaussian_minimum = float(config["nongaussian_gap_minimum_abs"])
    checks = {
        family: {
            "hermitian": values["hermiticity_residual_fro"] <= hermiticity_tolerance,
            "non_gaussian": abs(values["gaussian_gap_d2_minus_beta2"])
            >= nongaussian_minimum,
        }
        for family, values in results.items()
    }
    return {
        "schema_version": 1,
        "status": "pass" if all(all(item.values()) for item in checks.values()) else "fail",
        "parameters": {"epsilon": epsilon, "kappa": kappa, "tau": tau},
        "families": results,
        "checks": checks,
    }


def embed_generator(local: Array, sites: Sequence[int], dimension: int) -> Array:
    result = np.zeros((dimension, dimension))
    result[np.ix_(sites, sites)] = local
    return result


def embedded_factor(local_generator: Array, sites: Sequence[int], dimension: int) -> Array:
    result = np.eye(dimension)
    result[np.ix_(sites, sites)] = expm(local_generator)
    return result


def word_digest(descriptor: object) -> str:
    return sha256_bytes(canonical_json(descriptor).encode("utf-8"))


def sample_candidate_word(
    manifest: dict[str, Any],
    cell: Cell,
    rng: np.random.Generator,
) -> tuple[Array, list[dict[str, Any]], list[dict[str, Any]], float]:
    config = manifest["candidate"]
    dimension = int(cell.parameters["dimension"])
    depth = int(cell.parameters["depth"])
    regime = regime_by_id(manifest, str(cell.parameters["regime"]))
    triples = tuple(combinations(range(dimension), 3))
    permutation_data = permutation_matrices_3()
    product = np.eye(dimension)
    factor_specs: list[dict[str, Any]] = []
    descriptor: list[dict[str, Any]] = []
    sum_kappa_time = 0.0
    for _ in range(depth):
        epsilon, kappa = sample_ab_parameters(regime, rng)
        family = "A" if int(rng.integers(0, 2)) == 0 else "B"
        permutation_index = int(rng.integers(0, len(permutation_data)))
        triple_index = int(rng.integers(0, len(triples)))
        sites = triples[triple_index]
        propagation_time = sample_log_uniform(rng, config["time_distribution"])
        permutation_matrix = permutation_data[permutation_index][1]
        local = permutation_matrix @ ab_generator(epsilon, kappa, family) @ permutation_matrix.T
        local_generator = propagation_time * local
        full_generator = embed_generator(local_generator, sites, dimension)
        product = embedded_factor(local_generator, sites, dimension) @ product
        factor_specs.append({"kind": "exponential", "matrix": full_generator})
        descriptor.append(
            {
                "family": family,
                "permutation": permutation_index,
                "triple": triple_index,
                "epsilon": format(epsilon, ".17g"),
                "kappa": format(kappa, ".17g"),
                "time": format(propagation_time, ".17g"),
            }
        )
        sum_kappa_time += kappa * propagation_time
    return product, factor_specs, descriptor, sum_kappa_time


def result_row(
    cell: Cell,
    sample: int,
    determinant: dict[str, Any],
    *,
    structural_diagnostic: float,
    digest: str,
    fock_checked: bool = False,
    fock_abs_error: float | None = None,
) -> dict[str, Any]:
    return {
        "cell_id": cell.cell_id,
        "kind": cell.kind,
        "sample": sample,
        "dimension": cell.parameters.get("dimension", ""),
        "n": cell.parameters.get("n", ""),
        "depth": cell.parameters.get("depth", ""),
        "regime": cell.parameters.get("regime", ""),
        "component": cell.parameters.get("component", ""),
        "det_class": determinant["classification"],
        "det_method": determinant["method"],
        "det_sign": determinant["sign"],
        "log_abs_det": format(float(determinant["log_abs_det"]), ".17g"),
        "determinant_decimal": determinant["determinant_decimal"],
        "sigma_min_i_plus_t": format(
            float(determinant["sigma_min_i_plus_t"]), ".17g"
        ),
        "structural_diagnostic": format(float(structural_diagnostic), ".17g"),
        "fock_checked": int(fock_checked),
        "fock_abs_error": "" if fock_abs_error is None else format(fock_abs_error, ".17g"),
        "word_sha256": digest,
    }


def run_candidate_cell(
    manifest: dict[str, Any],
    cell: Cell,
    rng: np.random.Generator,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    config = manifest["candidate"]
    thresholds = manifest["thresholds"]
    precision = manifest["determinant_precision"]
    sample_count = int(config["samples_per_cell"])
    dimension = int(cell.parameters["dimension"])
    fock_config = manifest["fock_oracle"]
    fock_indices = (
        set(map(int, fock_config["sample_indices"]))
        if dimension <= int(fock_config["maximum_dimension"])
        else set()
    )
    contraction_tolerance = float(thresholds["contraction_abs"])
    fock_atol = float(fock_config["absolute_tolerance"])
    fock_rtol = float(fock_config["relative_tolerance"])
    rows: list[dict[str, Any]] = []
    passed = True
    minimum_log_abs = math.inf
    maximum_norm_violation = 0.0
    maximum_fock_error = 0.0
    high_precision_count = 0
    inconclusive_count = 0
    fock_count = 0

    for sample in range(sample_count):
        product, factor_specs, descriptor, sum_kappa_time = sample_candidate_word(
            manifest, cell, rng
        )
        determinant = stable_determinant_i_plus(product, factor_specs, precision)
        high_precision_count += int(determinant["escalated"])
        inconclusive_count += int(determinant["classification"] == "inconclusive")
        norm = float(np.linalg.norm(product, ord=np.inf))
        bound = math.exp(-sum_kappa_time) if dimension == 3 else 1.0
        norm_violation = max(0.0, norm - bound)
        maximum_norm_violation = max(maximum_norm_violation, norm_violation)
        minimum_log_abs = min(minimum_log_abs, float(determinant["log_abs_det"]))
        sample_pass = (
            determinant["classification"] == "positive"
            and norm_violation <= contraction_tolerance
        )
        fock_checked = sample in fock_indices
        fock_error: float | None = None
        if fock_checked:
            fock_count += 1
            fock_trace = direct_fock_trace(factor_specs)
            determinant_float = determinant["determinant_float"]
            if determinant_float is None:
                sample_pass = False
                fock_error = math.inf
            else:
                fock_error = abs(fock_trace - determinant_float)
                imaginary_ok = abs(fock_trace.imag) <= fock_atol
                tolerance = fock_atol + fock_rtol * abs(determinant_float)
                sample_pass = sample_pass and imaginary_ok and fock_error <= tolerance
            maximum_fock_error = max(maximum_fock_error, float(fock_error))
        passed = passed and sample_pass
        rows.append(
            result_row(
                cell,
                sample,
                determinant,
                structural_diagnostic=norm - bound,
                digest=word_digest(descriptor),
                fock_checked=fock_checked,
                fock_abs_error=fock_error,
            )
        )

    expected_fock = 3 if dimension <= int(fock_config["maximum_dimension"]) else 0
    passed = passed and fock_count == expected_fock
    summary = {
        "schema_version": 1,
        "cell_id": cell.cell_id,
        "kind": cell.kind,
        "parameters": cell.parameters,
        "status": "pass" if passed else "fail",
        "sample_count": sample_count,
        "minimum_log_abs_det": minimum_log_abs,
        "maximum_infinity_norm_violation": maximum_norm_violation,
        "high_precision_escalations": high_precision_count,
        "inconclusive_determinants": inconclusive_count,
        "fock_checks": fock_count,
        "maximum_abs_fock_error": maximum_fock_error,
        "theorem_boundary": (
            "d=3 uses exp(-sum kappa_j t_j); embedded d>3 words use the "
            "non-strict common infinity-norm bound 1."
        ),
    }
    return summary, rows


def sample_split_word(
    n: int,
    depth: int,
    rng: np.random.Generator,
    config: dict[str, Any],
) -> tuple[Array, list[dict[str, Any]], list[dict[str, Any]], float]:
    dimension = 2 * n
    eta = sph.split_metric(n)
    product = np.eye(dimension)
    factor_specs: list[dict[str, Any]] = []
    descriptor: list[dict[str, Any]] = []
    maximum_lie_residual = 0.0
    for _ in range(depth):
        generator = sph.random_split_generator(
            n,
            rng,
            scale=float(config["generator_scale"]),
        )
        propagation_time = sample_log_uniform(rng, config["time_distribution"])
        timed_generator = propagation_time * generator
        product = expm(timed_generator) @ product
        factor_specs.append({"kind": "exponential", "matrix": timed_generator})
        maximum_lie_residual = max(
            maximum_lie_residual,
            float(np.linalg.norm(timed_generator.T @ eta + eta @ timed_generator, ord="fro")),
        )
        descriptor.append(
            {
                "time": format(propagation_time, ".17g"),
                "generator_sha256": sha256_bytes(timed_generator.tobytes()),
            }
        )
    return product, factor_specs, descriptor, maximum_lie_residual


def run_split_cell(
    manifest: dict[str, Any],
    cell: Cell,
    rng: np.random.Generator,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    config = manifest["positive_anchors"]["split_orthogonal"]
    thresholds = manifest["thresholds"]
    precision = manifest["determinant_precision"]
    sample_count = int(config["samples_per_cell"])
    n = int(cell.parameters["n"])
    depth = int(cell.parameters["depth"])
    eta = sph.split_metric(n)
    lie_tolerance = float(thresholds["split_lie_abs"])
    group_tolerance = float(thresholds["split_group_abs"])
    rows: list[dict[str, Any]] = []
    passed = True
    maximum_lie_residual = 0.0
    maximum_group_residual = 0.0
    high_precision_count = 0
    inconclusive_count = 0

    for sample in range(sample_count):
        product, factor_specs, descriptor, lie_residual = sample_split_word(
            n, depth, rng, config
        )
        determinant = stable_determinant_i_plus(product, factor_specs, precision)
        group_residual = float(
            np.linalg.norm(product.T @ eta @ product - eta, ord="fro")
        )
        maximum_lie_residual = max(maximum_lie_residual, lie_residual)
        maximum_group_residual = max(maximum_group_residual, group_residual)
        high_precision_count += int(determinant["escalated"])
        inconclusive_count += int(determinant["classification"] == "inconclusive")
        try:
            component = sph.classify_split_component(
                product,
                eta,
                atol=max(group_tolerance * 10.0, 1e-9),
            )
        except ValueError:
            component = "unclassified"
        sample_pass = (
            determinant["classification"] == "positive"
            and component == "++"
            and lie_residual <= lie_tolerance
            and group_residual <= group_tolerance
        )
        passed = passed and sample_pass
        rows.append(
            result_row(
                cell,
                sample,
                determinant,
                structural_diagnostic=group_residual,
                digest=word_digest(descriptor),
            )
        )

    summary = {
        "schema_version": 1,
        "cell_id": cell.cell_id,
        "kind": cell.kind,
        "parameters": cell.parameters,
        "status": "pass" if passed else "fail",
        "sample_count": sample_count,
        "maximum_generator_lie_residual": maximum_lie_residual,
        "maximum_group_residual": maximum_group_residual,
        "high_precision_escalations": high_precision_count,
        "inconclusive_determinants": inconclusive_count,
    }
    return summary, rows


def sample_semigroup_word(
    n: int,
    depth: int,
    sample_index: int,
    rng: np.random.Generator,
    config: dict[str, Any],
) -> tuple[Array, list[dict[str, Any]], list[dict[str, Any]], float, int, int, int]:
    """Sample the Lie wedge A^T eta + eta A >= 0.

    Writing A = K + eta Q/2 with K in o(n,n) and Q positive semidefinite
    makes the infinitesimal inequality exactly Q >= 0. Full-rank and
    rank-deficient Q alternate deterministically within every cell. A random
    QR basis with nonzero eigenvalues in [0.25, 1] avoids accidental Wishart
    ill-conditioning, and the realized numerical rank is still checked against
    the intended rank.
    """
    dimension = 2 * n
    eta = sph.split_metric(n)
    product = np.eye(dimension)
    factor_specs: list[dict[str, Any]] = []
    descriptor: list[dict[str, Any]] = []
    minimum_generator_eigenvalue = math.inf
    full_rank_factors = 0
    deficient_rank_factors = 0
    rank_validation_failures = 0
    strength_config = config["dissipation_strength"]

    for factor_index in range(depth):
        full_rank = (sample_index + factor_index) % 2 == 0
        row_count = dimension if full_rank else max(1, n)
        raw_basis = rng.normal(size=(dimension, dimension))
        orthogonal_basis, _ = np.linalg.qr(raw_basis)
        basis = orthogonal_basis[:, :row_count]
        unscaled_eigenvalues = rng.uniform(0.25, 1.0, size=row_count)
        q_matrix = (basis * unscaled_eigenvalues) @ basis.T
        maximum_eigenvalue = float(np.max(unscaled_eigenvalues))
        strength = float(
            rng.uniform(
                float(strength_config["minimum"]),
                float(strength_config["maximum"]),
            )
        )
        q_matrix *= strength / maximum_eigenvalue

        split_part = sph.random_split_generator(
            n,
            rng,
            scale=float(config["split_generator_scale"]),
        )
        generator = split_part + 0.5 * eta @ q_matrix
        propagation_time = sample_log_uniform(rng, config["time_distribution"])
        timed_generator = propagation_time * generator
        lmi = timed_generator.T @ eta + eta @ timed_generator
        lmi = 0.5 * (lmi + lmi.T)
        minimum_generator_eigenvalue = min(
            minimum_generator_eigenvalue,
            float(np.linalg.eigvalsh(lmi)[0]),
        )
        product = expm(timed_generator) @ product
        factor_specs.append({"kind": "exponential", "matrix": timed_generator})
        numerical_rank = int(
            np.linalg.matrix_rank(
                q_matrix,
                tol=float(config["rank_tolerance"]),
            )
        )
        expected_rank = dimension if full_rank else row_count
        rank_valid = numerical_rank == expected_rank
        full_rank_factors += int(numerical_rank == dimension)
        deficient_rank_factors += int(numerical_rank < dimension)
        rank_validation_failures += int(not rank_valid)
        descriptor.append(
            {
                "time": format(propagation_time, ".17g"),
                "q_rank": numerical_rank,
                "q_expected_rank": expected_rank,
                "q_rank_valid": rank_valid,
                "q_kind": "full" if full_rank else "rank_deficient",
                "q_sampler": "qr_bounded_spectrum",
                "q_strength": format(strength, ".17g"),
                "q_unscaled_eigenvalue_floor": format(
                    float(np.min(unscaled_eigenvalues)), ".17g"
                ),
                "generator_sha256": sha256_bytes(timed_generator.tobytes()),
            }
        )

    return (
        product,
        factor_specs,
        descriptor,
        minimum_generator_eigenvalue,
        full_rank_factors,
        deficient_rank_factors,
        rank_validation_failures,
    )


def run_semigroup_cell(
    manifest: dict[str, Any],
    cell: Cell,
    rng: np.random.Generator,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    config = manifest["positive_anchors"]["semigroup_cone"]
    thresholds = manifest["thresholds"]
    precision = manifest["determinant_precision"]
    sample_count = int(config["samples_per_cell"])
    n = int(cell.parameters["n"])
    eta = sph.split_metric(n)
    generator_tolerance = float(thresholds["semigroup_generator_eigenvalue_abs"])
    product_tolerance = float(thresholds["semigroup_product_eigenvalue_abs"])
    rows: list[dict[str, Any]] = []
    passed = True
    minimum_generator_eigenvalue = math.inf
    minimum_product_eigenvalue = math.inf
    high_precision_count = 0
    inconclusive_count = 0
    full_rank_factors = 0
    deficient_rank_factors = 0
    rank_validation_failures = 0

    for sample in range(sample_count):
        (
            product,
            factor_specs,
            descriptor,
            generator_eigenvalue,
            sample_full_rank,
            sample_deficient_rank,
            sample_rank_failures,
        ) = sample_semigroup_word(n, int(cell.parameters["depth"]), sample, rng, config)
        determinant = stable_determinant_i_plus(product, factor_specs, precision)
        product_lmi = product.T @ eta @ product - eta
        product_lmi = 0.5 * (product_lmi + product_lmi.T)
        product_eigenvalue = float(np.linalg.eigvalsh(product_lmi)[0])
        minimum_generator_eigenvalue = min(
            minimum_generator_eigenvalue, generator_eigenvalue
        )
        minimum_product_eigenvalue = min(
            minimum_product_eigenvalue, product_eigenvalue
        )
        high_precision_count += int(determinant["escalated"])
        inconclusive_count += int(determinant["classification"] == "inconclusive")
        full_rank_factors += sample_full_rank
        deficient_rank_factors += sample_deficient_rank
        rank_validation_failures += sample_rank_failures
        sample_pass = (
            determinant["classification"] == "positive"
            and generator_eigenvalue >= -generator_tolerance
            and product_eigenvalue >= -product_tolerance
            and sample_rank_failures == 0
        )
        passed = passed and sample_pass
        rows.append(
            result_row(
                cell,
                sample,
                determinant,
                structural_diagnostic=product_eigenvalue,
                digest=word_digest(descriptor),
            )
        )

    passed = (
        passed
        and full_rank_factors > 0
        and deficient_rank_factors > 0
        and rank_validation_failures == 0
    )
    summary = {
        "schema_version": 1,
        "cell_id": cell.cell_id,
        "kind": cell.kind,
        "parameters": cell.parameters,
        "status": "pass" if passed else "fail",
        "sample_count": sample_count,
        "minimum_generator_lmi_eigenvalue": minimum_generator_eigenvalue,
        "minimum_product_lmi_eigenvalue": minimum_product_eigenvalue,
        "full_rank_q_factors": full_rank_factors,
        "rank_deficient_q_factors": deficient_rank_factors,
        "q_rank_validation_failures": rank_validation_failures,
        "high_precision_escalations": high_precision_count,
        "inconclusive_determinants": inconclusive_count,
    }
    return summary, rows


def run_component_cell(
    manifest: dict[str, Any],
    cell: Cell,
    rng: np.random.Generator,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    config = manifest["component_controls"]
    thresholds = manifest["thresholds"]
    precision = manifest["determinant_precision"]
    n = int(cell.parameters["n"])
    depth = int(cell.parameters["depth"])
    component = str(cell.parameters["component"])
    eta = sph.split_metric(n)
    representative = sph.split_component_representative(n, component)
    group_tolerance = float(thresholds["split_group_abs"])
    zero_sigma_tolerance = float(thresholds["component_zero_sigma"])
    rows: list[dict[str, Any]] = []
    passed = True
    maximum_group_residual = 0.0
    maximum_zero_sigma = 0.0
    classified_counts: dict[str, int] = {}
    determinant_counts: dict[str, int] = {}

    high_precision_count = 0
    inconclusive_count = 0
    is_expected_exact_zero_component = component in {"-+", "+-"}
    expected_exact_zero_controls = 0
    unexpected_inconclusive_count = 0
    for sample in range(int(config["samples_per_cell"])):
        identity_product, identity_specs, descriptor, _ = sample_split_word(
            n, depth, rng, config
        )
        product = representative @ identity_product
        factor_specs = [*identity_specs, {"kind": "matrix", "matrix": representative}]
        descriptor = [*descriptor, {"component_representative": component}]
        determinant = stable_determinant_i_plus(product, factor_specs, precision)
        high_precision_count += int(determinant["escalated"])
        inconclusive_count += int(determinant["classification"] == "inconclusive")
        expected_exact_zero_controls += int(is_expected_exact_zero_component)
        unexpected_inconclusive_count += int(
            determinant["classification"] == "inconclusive"
            and not is_expected_exact_zero_component
        )
        group_residual = float(
            np.linalg.norm(product.T @ eta @ product - eta, ord="fro")
        )
        maximum_group_residual = max(maximum_group_residual, group_residual)
        try:
            classified = sph.classify_split_component(
                product,
                eta,
                atol=max(group_tolerance * 10.0, 1e-9),
            )
        except ValueError:
            classified = "unclassified"
        classified_counts[classified] = classified_counts.get(classified, 0) + 1
        det_class = str(determinant["classification"])
        determinant_counts[det_class] = determinant_counts.get(det_class, 0) + 1

        if component == "++":
            determinant_ok = det_class == "positive"
        elif component == "--":
            determinant_ok = det_class == "negative"
        else:
            determinant_ok = (
                det_class == "inconclusive"
                and float(determinant["sigma_min_i_plus_t"])
                <= zero_sigma_tolerance
            )
            maximum_zero_sigma = max(
                maximum_zero_sigma,
                float(determinant["sigma_min_i_plus_t"]),
            )
        sample_pass = (
            classified == component
            and group_residual <= group_tolerance
            and determinant_ok
        )
        passed = passed and sample_pass
        rows.append(
            result_row(
                cell,
                sample,
                determinant,
                structural_diagnostic=group_residual,
                digest=word_digest(descriptor),
            )
        )

    summary = {
        "schema_version": 1,
        "cell_id": cell.cell_id,
        "kind": cell.kind,
        "parameters": cell.parameters,
        "status": "pass" if passed else "fail",
        "sample_count": int(config["samples_per_cell"]),
        "maximum_group_residual": maximum_group_residual,
        "maximum_mixed_component_sigma_min": maximum_zero_sigma,
        "classified_component_counts": classified_counts,
        "determinant_class_counts": determinant_counts,
        "high_precision_escalations": high_precision_count,
        "inconclusive_determinants": inconclusive_count,
        "raw_inconclusive_determinants": inconclusive_count,
        "expected_exact_zero_controls": expected_exact_zero_controls,
        "unexpected_inconclusive_determinants": unexpected_inconclusive_count,
        "expected_weight": (
            "strictly_positive" if component == "++" else
            "strictly_negative" if component == "--" else
            "exactly_zero_by_component_theorem"
        ),
    }
    return summary, rows


def physical_vertex_catalog(
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], Array, Array]:
    sites = int(config["sites"])
    if sites != 4 or str(config["boundary"]) != "open":
        raise ValueError("the preregistered physical benchmark is the four-site open chain")
    epsilon = config["epsilon"]
    kappa = config["kappa"]
    tau = float(parse_fraction(config["tau"]))
    chemical_potential = parse_fraction(config["chemical_potential"])
    if chemical_potential != 0:
        raise ValueError("the positive Poisson benchmark is preregistered at mu=0")
    triangles = [tuple(map(int, triangle)) for triangle in config["triangles"]]
    permutation_data = permutation_matrices_3()
    catalog: list[dict[str, Any]] = []
    fock_dimension = 1 << sites
    interaction_operator = np.zeros((fock_dimension, fock_dimension))
    one_particle_twirl = np.zeros((sites, sites))

    for triangle_index, triangle in enumerate(triangles):
        if len(triangle) != 3 or len(set(triangle)) != 3:
            raise ValueError("every benchmark triangle must contain three distinct sites")
        if min(triangle) < 0 or max(triangle) >= sites:
            raise ValueError("benchmark triangle site is outside the chain")
        for family in ("A", "B"):
            coupling = float(parse_fraction(config["couplings"][family]))
            if coupling <= 0.0:
                raise ValueError("physical benchmark couplings must be positive")
            scalar_weight = coupling / len(permutation_data)
            base = ab_generator(epsilon, kappa, family)
            for permutation_index, (_, permutation_matrix) in enumerate(permutation_data):
                local_generator = tau * permutation_matrix @ base @ permutation_matrix.T
                generator = embed_generator(local_generator, triangle, sites)
                one_particle_factor = expm(generator)
                fock_factor = expm(sph.bilinear_fock_operator(generator))
                interaction_operator += scalar_weight * fock_factor
                one_particle_twirl += scalar_weight * one_particle_factor
                catalog.append(
                    {
                        "id": (
                            f"triangle{triangle_index}_{family}_"
                            f"perm{permutation_index}"
                        ),
                        "triangle": triangle,
                        "family": family,
                        "permutation": permutation_index,
                        "weight": scalar_weight,
                        "generator": generator,
                        "one_particle_factor": one_particle_factor,
                        "fock_factor": fock_factor,
                    }
                )
    return catalog, interaction_operator, one_particle_twirl


def deterministic_partition_expansion(
    interaction_operator: Array,
    beta: float,
    order: int,
    energy_shift: float,
) -> dict[str, Any]:
    """Controlled Taylor fixture for Z_bar=Tr exp[-beta(G0 I-V)]."""
    dimension = interaction_operator.shape[0]
    power = np.eye(dimension)
    coefficient = 1.0
    series = complex(np.trace(power))
    terms = [{"order": 0, "real": float(series.real), "imag_abs": float(abs(series.imag))}]
    for expansion_order in range(1, order + 1):
        power = power @ interaction_operator
        coefficient *= beta / expansion_order
        term = coefficient * complex(np.trace(power))
        series += term
        terms.append(
            {
                "order": expansion_order,
                "real": float(term.real),
                "imag_abs": float(abs(term.imag)),
            }
        )
    normalization = math.exp(-beta * energy_shift)
    z_bar_series = normalization * series
    for term in terms:
        term["real"] *= normalization
        term["imag_abs"] *= normalization
    norm_argument = beta * float(np.linalg.norm(interaction_operator, ord=2))
    remainder_bound = (
        normalization
        * dimension
        * math.exp(norm_argument)
        * norm_argument ** (order + 1)
        / math.factorial(order + 1)
    )
    return {
        "order": order,
        "energy_shift_G0": energy_shift,
        "shift_normalization_exp_minus_beta_G0": normalization,
        "z_bar_estimate_real": float(z_bar_series.real),
        "z_bar_estimate_imag_abs": float(abs(z_bar_series.imag)),
        "partition_estimate_real": float(z_bar_series.real),
        "partition_estimate_imag_abs": float(abs(z_bar_series.imag)),
        "operator_norm_argument": norm_argument,
        "remainder_bound": remainder_bound,
        "terms": terms,
    }


def poisson_partition_estimate(
    catalog: Sequence[dict[str, Any]],
    beta: float,
    sample_count: int,
    rng: np.random.Generator,
    precision: dict[str, Any],
) -> dict[str, Any]:
    """Estimate shifted Z_bar with the normalized positive Poisson expansion."""
    weights = np.asarray([float(vertex["weight"]) for vertex in catalog])
    total_weight = float(np.sum(weights))
    probabilities = weights / total_weight
    sites = np.asarray(catalog[0]["one_particle_factor"]).shape[0]
    fock_dimension = np.asarray(catalog[0]["fock_factor"]).shape[0]
    contributions = np.empty(sample_count)
    minimum_fock_weight = math.inf
    minimum_determinant_weight = math.inf
    minimum_record: dict[str, Any] | None = None
    maximum_fock_determinant_error = 0.0
    maximum_fock_imaginary_part = 0.0
    negative_or_unresolved = 0
    orders: list[int] = []

    for sample in range(sample_count):
        expansion_order = int(rng.poisson(beta * total_weight))
        labels = (
            rng.choice(len(catalog), size=expansion_order, p=probabilities)
            if expansion_order
            else np.empty(0, dtype=int)
        )
        one_particle_product = np.eye(sites)
        fock_product = np.eye(fock_dimension)
        factor_specs: list[dict[str, Any]] = []
        identifiers: list[str] = []
        for label_value in labels:
            vertex = catalog[int(label_value)]
            one_particle_product = (
                np.asarray(vertex["one_particle_factor"]) @ one_particle_product
            )
            fock_product = np.asarray(vertex["fock_factor"]) @ fock_product
            factor_specs.append(
                {"kind": "exponential", "matrix": np.asarray(vertex["generator"])}
            )
            identifiers.append(str(vertex["id"]))

        determinant = stable_determinant_i_plus(
            one_particle_product,
            factor_specs,
            precision,
        )
        fock_weight = complex(np.trace(fock_product))
        maximum_fock_imaginary_part = max(
            maximum_fock_imaginary_part,
            float(abs(fock_weight.imag)),
        )
        determinant_float = determinant["determinant_float"]
        if determinant_float is None:
            mismatch = math.inf
            negative_or_unresolved += 1
            determinant_value = math.nan
        else:
            determinant_value = float(determinant_float)
            mismatch = abs(fock_weight - determinant_value)
            if determinant["classification"] != "positive":
                negative_or_unresolved += 1
        maximum_fock_determinant_error = max(
            maximum_fock_determinant_error,
            float(mismatch),
        )
        contributions[sample] = float(fock_weight.real)
        orders.append(expansion_order)
        minimum_fock_weight = min(minimum_fock_weight, float(fock_weight.real))
        if np.isfinite(determinant_value):
            minimum_determinant_weight = min(
                minimum_determinant_weight, determinant_value
            )
        if (
            minimum_record is None
            or float(fock_weight.real) < float(minimum_record["fock_weight"])
        ):
            minimum_record = {
                "sample": sample,
                "order": expansion_order,
                "fock_weight": float(fock_weight.real),
                "determinant_decimal": determinant["determinant_decimal"],
                "word_sha256": word_digest(identifiers),
            }

    standard_error = (
        float(np.std(contributions, ddof=1) / math.sqrt(sample_count))
        if sample_count > 1
        else math.inf
    )
    z_bar_estimate = float(np.mean(contributions))
    return {
        "sample_count": sample_count,
        "poisson_mean_beta_G0": beta * total_weight,
        "poisson_mean": beta * total_weight,
        "energy_shift_G0": total_weight,
        "total_vertex_weight": total_weight,
        "z_bar_estimate": z_bar_estimate,
        "partition_estimate": z_bar_estimate,
        "standard_error": standard_error,
        "minimum_fock_configuration_weight": minimum_fock_weight,
        "minimum_determinant_configuration_weight": minimum_determinant_weight,
        "minimum_configuration": minimum_record,
        "maximum_fock_determinant_abs_error": maximum_fock_determinant_error,
        "maximum_fock_imaginary_part": maximum_fock_imaginary_part,
        "negative_or_unresolved_configurations": negative_or_unresolved,
        "minimum_sampled_order": min(orders),
        "maximum_sampled_order": max(orders),
    }


def run_physical_benchmark(manifest: dict[str, Any]) -> dict[str, Any]:
    config = manifest["physical_benchmark"]
    catalog, interaction_operator, one_particle_twirl = physical_vertex_catalog(config)
    energy_shift = float(sum(float(vertex["weight"]) for vertex in catalog))
    h_bar = energy_shift * np.eye(interaction_operator.shape[0]) - interaction_operator
    hermiticity_residual = float(np.linalg.norm(h_bar - h_bar.T.conj(), ord="fro"))
    hermitian_h_bar = 0.5 * (h_bar + h_bar.T.conj())
    minimum_h_bar_eigenvalue = float(np.linalg.eigvalsh(hermitian_h_bar)[0])
    precision = manifest["determinant_precision"]
    fock_config = manifest["fock_oracle"]
    samples = int(config["poisson_samples_per_beta"])
    confidence_sigma = float(config["confidence_sigma"])
    relative_error_floor = float(config["relative_error_floor"])
    weight_tolerance = float(config["weight_tolerance"])
    expansion_order = int(config["deterministic_truncation_order"])
    results: list[dict[str, Any]] = []
    passed = (
        hermiticity_residual <= float(config["hermiticity_tolerance"])
        and minimum_h_bar_eigenvalue >= -weight_tolerance
    )

    for beta_value in config["betas"]:
        beta = float(parse_fraction(beta_value))
        exact_complex = complex(np.trace(expm(-beta * h_bar)))
        exact_z_bar = float(exact_complex.real)
        deterministic = deterministic_partition_expansion(
            interaction_operator, beta, expansion_order, energy_shift
        )
        deterministic_error = abs(deterministic["z_bar_estimate_real"] - exact_z_bar)
        beta_seed = derive_seed(
            int(config["seed"]),
            f"physical_beta_{fraction_string(parse_fraction(beta_value))}",
        )
        poisson = poisson_partition_estimate(
            catalog,
            beta,
            samples,
            np.random.default_rng(beta_seed),
            precision,
        )
        statistical_error = abs(poisson["z_bar_estimate"] - exact_z_bar)
        statistical_allowance = max(
            confidence_sigma * poisson["standard_error"],
            relative_error_floor * abs(exact_z_bar),
        )
        beta_pass = (
            abs(exact_complex.imag) <= float(config["partition_imag_tolerance"])
            and poisson["negative_or_unresolved_configurations"] == 0
            and poisson["minimum_fock_configuration_weight"] >= -weight_tolerance
            and poisson["maximum_fock_imaginary_part"]
            <= float(config["partition_imag_tolerance"])
            and poisson["maximum_fock_determinant_abs_error"]
            <= float(fock_config["absolute_tolerance"])
            + float(fock_config["relative_tolerance"])
            * max(1.0, poisson["minimum_fock_configuration_weight"])
            and statistical_error <= statistical_allowance
            and deterministic_error
            <= deterministic["remainder_bound"]
            + float(config["deterministic_roundoff_allowance"])
        )
        passed = passed and beta_pass
        results.append(
            {
                "beta": fraction_string(parse_fraction(beta_value)),
                "status": "pass" if beta_pass else "fail",
                "exact_z_bar": exact_z_bar,
                "exact_fock_partition_function": exact_z_bar,
                "exact_partition_imag_abs": float(abs(exact_complex.imag)),
                "poisson": poisson,
                "poisson_abs_error": statistical_error,
                "poisson_allowed_error": statistical_allowance,
                "deterministic_expansion": deterministic,
                "deterministic_abs_error": deterministic_error,
            }
        )

    return {
        "schema_version": 1,
        "status": "pass" if passed else "fail",
        "interpretation": (
            "For H_bar=G0 I-V, the exact 16-dimensional Z_bar is compared "
            "with the normalized positive Poisson operator-string estimator "
            "and a controlled shifted deterministic expansion."
        ),
        "parameters": config,
        "catalog_size": len(catalog),
        "hamiltonian_dimension": int(h_bar.shape[0]),
        "energy_shift_G0": energy_shift,
        "minimum_h_bar_eigenvalue": minimum_h_bar_eigenvalue,
        "h_bar_psd_tolerance": weight_tolerance,
        "hamiltonian_hermiticity_residual_fro": hermiticity_residual,
        "one_particle_twirl_sha256": sha256_bytes(one_particle_twirl.tobytes()),
        "interaction_V_sha256": sha256_bytes(interaction_operator.tobytes()),
        "h_bar_sha256": sha256_bytes(h_bar.tobytes()),
        "hamiltonian_sha256": sha256_bytes(h_bar.tobytes()),
        "beta_results": results,
    }


def run_cell(
    manifest: dict[str, Any],
    cell: Cell,
    rng: np.random.Generator,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if cell.kind == "candidate":
        return run_candidate_cell(manifest, cell, rng)
    if cell.kind == "split_orthogonal":
        return run_split_cell(manifest, cell, rng)
    if cell.kind == "semigroup_cone":
        return run_semigroup_cell(manifest, cell, rng)
    if cell.kind == "component_control":
        return run_component_cell(manifest, cell, rng)
    raise ValueError(f"unknown cell kind {cell.kind}")


def expected_cell_samples(manifest: dict[str, Any], cell: Cell) -> int:
    if cell.kind == "candidate":
        return int(manifest["candidate"]["samples_per_cell"])
    if cell.kind in {"split_orthogonal", "semigroup_cone"}:
        return int(manifest["positive_anchors"][cell.kind]["samples_per_cell"])
    if cell.kind == "component_control":
        return int(manifest["component_controls"]["samples_per_cell"])
    raise ValueError(f"unknown cell kind {cell.kind}")


def git_revision() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=SOLUTION_DIR,
            check=True,
            text=True,
            capture_output=True,
        )
        return completed.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def csv_row_count(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CSV_FIELDS:
            raise ValueError(f"unexpected CSV schema in {path}")
        return sum(1 for _ in reader)


def load_reusable_cell(
    summary_path: Path,
    rows_path: Path,
    *,
    cell: Cell,
    expected_samples: int,
    protocol_id: str,
) -> dict[str, Any] | None:
    if not summary_path.is_file() or not rows_path.is_file():
        return None
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        valid = (
            summary["cell_id"] == cell.cell_id
            and summary["protocol_id"] == protocol_id
            and int(summary["sample_count"]) == expected_samples
            and int(summary["row_count"]) == expected_samples
            and summary["rows_sha256"] == sha256_file(rows_path)
            and csv_row_count(rows_path) == expected_samples
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None
    return summary if valid else None


def run_or_resume_stage(
    output_path: Path,
    builder: Any,
    *,
    protocol_id: str,
) -> dict[str, Any]:
    if output_path.is_file():
        try:
            existing = json.loads(output_path.read_text(encoding="utf-8"))
            if existing.get("protocol_id") == protocol_id:
                return existing
        except (OSError, json.JSONDecodeError):
            pass
    started = time.monotonic()
    result = builder()
    result["protocol_id"] = protocol_id
    result["completed_at"] = utc_now()
    result["elapsed_seconds"] = time.monotonic() - started
    atomic_write_json(output_path, result)
    return result


def consolidate_rows(
    output_path: Path,
    cells: Sequence[Cell],
    row_paths: dict[str, Path],
    summaries: dict[str, dict[str, Any]],
) -> int:
    rows: list[dict[str, Any]] = []
    for cell in cells:
        if cell.cell_id not in summaries:
            continue
        with row_paths[cell.cell_id].open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != CSV_FIELDS:
                raise ValueError(f"unexpected row schema for {cell.cell_id}")
            rows.extend(dict(row) for row in reader)
    atomic_write_csv(output_path, rows)
    return len(rows)


def artifact_entry(path: Path, output_dir: Path, *, rows: int | None = None) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "path": str(path.relative_to(output_dir)),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }
    if rows is not None:
        entry["rows"] = rows
    return entry


def aggregate_cell_results(
    cells: Sequence[Cell],
    summaries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    kind_counts: dict[str, dict[str, int]] = {}
    high_precision_escalations = 0
    raw_inconclusive_determinants = 0
    expected_exact_zero_controls = 0
    unexpected_inconclusive_determinants = 0
    fock_checks = 0
    maximum_fock_error = 0.0
    for cell in cells:
        summary = summaries.get(cell.cell_id)
        if summary is None:
            continue
        counts = kind_counts.setdefault(cell.kind, {"pass": 0, "fail": 0})
        counts[str(summary["status"])] += 1
        high_precision_escalations += int(summary.get("high_precision_escalations", 0))
        raw_inconclusive = int(summary.get("inconclusive_determinants", 0))
        expected_exact_zero = int(summary.get("expected_exact_zero_controls", 0))
        unexpected_inconclusive = int(
            summary.get(
                "unexpected_inconclusive_determinants",
                max(0, raw_inconclusive - expected_exact_zero),
            )
        )
        raw_inconclusive_determinants += raw_inconclusive
        expected_exact_zero_controls += expected_exact_zero
        unexpected_inconclusive_determinants += unexpected_inconclusive
        fock_checks += int(summary.get("fock_checks", 0))
        maximum_fock_error = max(
            maximum_fock_error,
            float(summary.get("maximum_abs_fock_error", 0.0)),
        )
    return {
        "cell_status_by_kind": kind_counts,
        "high_precision_escalations": high_precision_escalations,
        "inconclusive_determinants": raw_inconclusive_determinants,
        "raw_inconclusive_determinants": raw_inconclusive_determinants,
        "expected_exact_zero_controls": expected_exact_zero_controls,
        "unexpected_inconclusive_determinants": unexpected_inconclusive_determinants,
        "fock_checks": fock_checks,
        "maximum_abs_fock_error": maximum_fock_error,
    }


def report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Issue 121 preregistered verification report",
        "",
        f"- Status: {report['status']}",
        f"- Protocol: `{report['protocol_id']}`",
        f"- Completed cells: {report['completed_cells']} / {report['total_cells']}",
        f"- Consolidated random-word rows: {report['sample_rows']}",
        f"- Exact certificates: {report['stage_status']['exact_certificates']}",
        f"- Twirl checks: {report['stage_status']['twirl_checks']}",
        f"- Four-site physical benchmark: {report['stage_status']['physical_benchmark']}",
        (
            "- Raw numeric inconclusive classifications: "
            f"{report['aggregates']['raw_inconclusive_determinants']}"
        ),
        (
            "- Expected exact-zero mixed O(1,1) controls: "
            f"{report['aggregates']['expected_exact_zero_controls']}"
        ),
        f"- Unexpected inconclusive determinants: {report['aggregates']['unexpected_inconclusive_determinants']}",
        "",
        "Random-word checks are implementation audits, not proofs. The exact",
        "Fraction certificates and theorem documents carry the algebraic claims.",
        "A COMPLETE sentinel is emitted only for an all-pass full protocol.",
        "",
    ]
    if report["failed_cells"]:
        lines.extend(["## Failed cells", ""])
        lines.extend(f"- `{cell_id}`" for cell_id in report["failed_cells"])
        lines.append("")
    if report["pending_cells"]:
        lines.extend(["## Pending cells", ""])
        lines.extend(f"- `{cell_id}`" for cell_id in report["pending_cells"])
        lines.append("")
    return "\n".join(lines)


def run_verification(
    manifest_path: Path,
    output_dir: Path,
    *,
    max_new_cells: int | None = None,
    cell_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    cells = build_cells(manifest)
    cell_by_id = {cell.cell_id: cell for cell in cells}
    requested_cell_ids = (
        None if cell_ids is None else list(dict.fromkeys(map(str, cell_ids)))
    )
    if requested_cell_ids is not None:
        unknown_cell_ids = [
            cell_id for cell_id in requested_cell_ids if cell_id not in cell_by_id
        ]
        if unknown_cell_ids:
            raise ValueError(
                "unknown --cell-id value(s): " + ", ".join(unknown_cell_ids)
            )
    environment_signature = {
        "python_major": int(sys.version_info.major),
        "python_full": sys.version,
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "mpmath": mp.__version__,
    }
    manifest_hash = sha256_bytes(canonical_json(manifest).encode("utf-8"))
    verifier_hash = sha256_file(Path(__file__))
    support_module_hash = sha256_file(SOLUTION_DIR / "sign_problem_hunter.py")
    protocol_id = sha256_bytes(
        canonical_json(
            {
                "manifest_sha256": manifest_hash,
                "verifier_sha256": verifier_hash,
                "sign_problem_hunter_sha256": support_module_hash,
                "environment_signature": environment_signature,
            }
        ).encode("utf-8")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    complete_path = output_dir / "COMPLETE"
    report_path = output_dir / "report.json"
    report_md_path = output_dir / "report.md"
    if complete_path.exists():
        try:
            sentinel = json.loads(complete_path.read_text(encoding="utf-8"))
            prior_report = json.loads(report_path.read_text(encoding="utf-8"))
            current_report_hash = sha256_file(report_path)
            current_report_md_hash = sha256_file(report_md_path)
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(
                "COMPLETE exists but its report artifacts are invalid"
            ) from error
        if (
            sentinel.get("protocol_id") == protocol_id
            and prior_report.get("protocol_id") == protocol_id
            and prior_report.get("status") == "pass"
            and sentinel.get("report_json_sha256") == current_report_hash
            and sentinel.get("report_markdown_sha256") == current_report_md_hash
        ):
            return prior_report
        raise RuntimeError("COMPLETE sentinel or report integrity check failed")

    manifest_copy = output_dir / "manifest.json"
    if manifest_copy.is_file():
        existing_manifest = json.loads(manifest_copy.read_text(encoding="utf-8"))
        existing_hash = sha256_bytes(canonical_json(existing_manifest).encode("utf-8"))
        if existing_hash != manifest_hash:
            raise RuntimeError("output directory contains a different manifest")
    else:
        atomic_write_json(manifest_copy, manifest)

    run_path = output_dir / "run.json"
    if run_path.is_file():
        run_payload = json.loads(run_path.read_text(encoding="utf-8"))
        if run_payload.get("protocol_id") != protocol_id:
            raise RuntimeError("output directory was created by a different verifier")
    else:
        run_payload = {
            "schema_version": 1,
            "status": "running",
            "started_at": utc_now(),
            "protocol_id": protocol_id,
            "manifest_sha256": manifest_hash,
            "verifier_sha256": verifier_hash,
            "sign_problem_hunter_sha256": support_module_hash,
            "git_revision": git_revision(),
            "base_seed": int(manifest["seed"]),
            "total_cells": len(cells),
            "environment_signature": environment_signature,
            "environment": environment_signature,
        }
        atomic_write_json(run_path, run_payload)

    stage_specs = (
        ("exact_certificates", exact_certificates),
        ("twirl_checks", run_twirl_checks),
        ("physical_benchmark", run_physical_benchmark),
    )
    stages: dict[str, dict[str, Any]] = {}
    stage_paths: dict[str, Path] = {}
    for stage_name, builder in stage_specs:
        stage_path = output_dir / f"{stage_name}.json"
        stages[stage_name] = run_or_resume_stage(
            stage_path,
            lambda builder=builder: builder(manifest),
            protocol_id=protocol_id,
        )
        stage_paths[stage_name] = stage_path

    cell_dir = output_dir / "cells"
    row_dir = output_dir / "cell_rows"
    cell_dir.mkdir(parents=True, exist_ok=True)
    row_dir.mkdir(parents=True, exist_ok=True)
    summaries: dict[str, dict[str, Any]] = {}
    row_paths = {cell.cell_id: row_dir / f"{cell.cell_id}.csv" for cell in cells}
    summary_paths = {cell.cell_id: cell_dir / f"{cell.cell_id}.json" for cell in cells}

    for cell in cells:
        reusable = load_reusable_cell(
            summary_paths[cell.cell_id],
            row_paths[cell.cell_id],
            cell=cell,
            expected_samples=expected_cell_samples(manifest, cell),
            protocol_id=protocol_id,
        )
        if reusable is not None:
            summaries[cell.cell_id] = reusable

    pending = [cell for cell in cells if cell.cell_id not in summaries]
    selected_pending = (
        pending
        if requested_cell_ids is None
        else [
            cell for cell in pending if cell.cell_id in set(requested_cell_ids)
        ]
    )
    if max_new_cells is not None:
        if max_new_cells < 0:
            raise ValueError("max_new_cells must be nonnegative")
        pending_to_run = selected_pending[:max_new_cells]
    else:
        pending_to_run = selected_pending

    progress_path = output_dir / "progress.json"
    progress_stride = max(1, math.ceil(len(cells) / 25))
    for new_cell_index, cell in enumerate(pending_to_run, start=1):
        seed = derive_seed(int(manifest["seed"]), cell.cell_id)
        started = time.monotonic()
        summary, rows = run_cell(
            manifest,
            cell,
            np.random.default_rng(seed),
        )
        if len(rows) != expected_cell_samples(manifest, cell):
            raise RuntimeError(f"cell {cell.cell_id} emitted the wrong row count")
        atomic_write_csv(row_paths[cell.cell_id], rows)
        summary.update(
            {
                "protocol_id": protocol_id,
                "seed": seed,
                "completed_at": utc_now(),
                "elapsed_seconds": time.monotonic() - started,
                "row_count": len(rows),
                "rows_file": str(row_paths[cell.cell_id].relative_to(output_dir)),
                "rows_sha256": sha256_file(row_paths[cell.cell_id]),
            }
        )
        atomic_write_json(summary_paths[cell.cell_id], summary)
        summaries[cell.cell_id] = summary
        atomic_write_json(
            progress_path,
            {
                "schema_version": 1,
                "protocol_id": protocol_id,
                "updated_at": utc_now(),
                "completed_cells": len(summaries),
                "total_cells": len(cells),
                "last_completed_cell": cell.cell_id,
            },
        )

        if (
            new_cell_index % progress_stride == 0
            or new_cell_index == len(pending_to_run)
        ):
            print(
                canonical_json(
                    {
                        "event": "cell_progress",
                        "completed_cells": len(summaries),
                        "total_cells": len(cells),
                        "new_cells_this_invocation": new_cell_index,
                        "last_completed_cell": cell.cell_id,
                    }
                ),
                flush=True,
            )
    samples_path = output_dir / "samples.csv"
    sample_rows = consolidate_rows(samples_path, cells, row_paths, summaries)
    failed_cells = [
        cell.cell_id
        for cell in cells
        if summaries.get(cell.cell_id, {}).get("status") == "fail"
    ]
    pending_cells = [cell.cell_id for cell in cells if cell.cell_id not in summaries]
    stages_pass = all(stage["status"] == "pass" for stage in stages.values())
    if pending_cells:
        status = "partial"
    elif failed_cells or not stages_pass:
        status = "fail"
    else:
        status = "pass"

    artifacts = {
        "manifest": artifact_entry(manifest_copy, output_dir),
        "samples": artifact_entry(samples_path, output_dir, rows=sample_rows),
    }
    artifacts.update(
        {
            stage_name: artifact_entry(stage_paths[stage_name], output_dir)
            for stage_name in stage_paths
        }
    )
    report = {
        "schema_version": 1,
        "status": status,
        "generated_at": utc_now(),
        "protocol_id": protocol_id,
        "manifest_sha256": manifest_hash,
        "verifier_sha256": verifier_hash,
        "sign_problem_hunter_sha256": support_module_hash,
        "environment_signature": environment_signature,
        "total_cells": len(cells),
        "completed_cells": len(summaries),
        "requested_cell_ids": requested_cell_ids,
        "failed_cells": failed_cells,
        "pending_cells": pending_cells,
        "sample_rows": sample_rows,
        "expected_full_sample_rows": int(manifest["expected_workload"]["total_words"]),
        "stage_status": {name: stage["status"] for name, stage in stages.items()},
        "aggregates": aggregate_cell_results(cells, summaries),
        "artifacts": artifacts,
        "resource_note": manifest["execution"],
        "claim_boundary": (
            "Passing establishes reproducibility of the preregistered checks. "
            "It is neither a proof by sampling nor a literature-priority claim."
        ),
    }
    atomic_write_json(report_path, report)
    report_md_path = output_dir / "report.md"
    atomic_write_text(report_md_path, report_markdown(report))

    run_payload.update(
        {
            "status": status,
            "updated_at": utc_now(),
            "completed_cells": len(summaries),
            "report_json_sha256": sha256_file(report_path),
            "report_markdown_sha256": sha256_file(report_md_path),
        }
    )
    atomic_write_json(run_path, run_payload)
    atomic_write_json(
        progress_path,
        {
            "schema_version": 1,
            "protocol_id": protocol_id,
            "updated_at": utc_now(),
            "status": status,
            "completed_cells": len(summaries),
            "total_cells": len(cells),
            "failed_cells": failed_cells,
            "pending_cells": pending_cells,
        },
    )
    if status == "pass":
        if sample_rows != int(manifest["expected_workload"]["total_words"]):
            raise RuntimeError("all cells completed but consolidated row count is wrong")
        atomic_write_text(
            complete_path,
            canonical_json(
                {
                    "protocol_id": protocol_id,
                    "report_json_sha256": sha256_file(report_path),
                    "report_markdown_sha256": sha256_file(report_md_path),
                    "completed_at": utc_now(),
                }
            )
            + "\n",
        )
    return report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=SOLUTION_DIR / "issue121_full_run.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=SOLUTION_DIR / "issue121_full_run",
    )
    parser.add_argument(
        "--cell-id",
        dest="cell_ids",
        action="append",
        default=None,
        metavar="CELL_ID",
        help="run only this cell if pending; repeat to select multiple pilot cells",
    )
    parser.add_argument(
        "--max-new-cells",
        type=int,
        default=None,
        help="run at most this many not-yet-completed cells, for resumable pilots",
    )
    parser.add_argument("--list-cells", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = load_manifest(args.manifest)
    if args.list_cells:
        for cell in build_cells(manifest):
            print(cell.cell_id)
        return 0
    if args.validate_only:
        print(canonical_json(manifest["expected_workload"]))
        return 0
    report = run_verification(
        args.manifest,
        args.output,
        max_new_cells=args.max_new_cells,
        cell_ids=args.cell_ids,
    )
    print(
        canonical_json(
            {
                "status": report["status"],
                "completed_cells": report["completed_cells"],
                "total_cells": report["total_cells"],
                "report": str(args.output / "report.json"),
            }
        )
    )
    return 1 if report["status"] == "fail" else 0


if __name__ == "__main__":
    raise SystemExit(main())

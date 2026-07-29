"""Remote-only discovery runner for non-induced exterior-grade cones.

The exact candidate is a five-dimensional, four-letter transpose-closed
alphabet.  Its two base atoms are signed rational chord perturbations of one
strictly totally-positive Jacobi-factor core.  Grade two uses an exact
rational Givens gauge and grade three uses its conjugate under the fixed
Euclidean Hodge identification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp

from .exterior_cone import determinant_from_compound_traces, subset_basis
from .exterior_exact5_shared_cone import exact_compound_matrix


SCHEMA = "tp-exterior-extension-cell-v1"
CANDIDATE_SCHEMA = "tp-exterior-candidate-v1"
BASIS_CONVENTION = "zero-based-lexicographic-subsets"
HODGE_CONVENTION = (
    "star(e_I)=sign(I,I_complement)e_(I_complement),"
    " positive orientation e_0^e_1^e_2^e_3^e_4"
)

CONDITION_NUMBER_LIMIT = 1.0e10
RELATIVE_ENTRY_MARGIN_THRESHOLD = 1.0e-8
NEGATIVE_MINOR_THRESHOLD = 1.0e-6
NON_INDUCED_RESIDUAL_THRESHOLD = 1.0e-6

_REDUCED_LONGEST_WORD = (0, 1, 2, 3, 0, 1, 2, 0, 1, 0)
_CHORD_PATTERNS = (
    ((0, 2), (3, 1)),
    ((0, 3), (4, 2)),
    ((0, 2), (2, 4), (4, 0)),
)
_GIVENS_PLANES = (
    (0, 7),  # e01 with e23
    (0, 8),  # e01 with e24
    (0, 9),  # e01 with e34
    (1, 5),  # e02 with e13
    (1, 6),  # e02 with e14
    (1, 9),  # e02 with e34
)
_RATIONAL_KEYS = {"numerator", "denominator"}
_PARAMETER_KEYS = {
    "jacobi_strength",
    "diagonal_condition_ratio",
    "chord_shear_magnitude",
    "chord_pattern",
    "givens_half_angle",
    "givens_plane",
    "two_atom_scale_ratio",
}
_BINDING_THRESHOLDS = {
    "condition_number_limit": CONDITION_NUMBER_LIMIT,
    "relative_entry_margin_threshold": RELATIVE_ENTRY_MARGIN_THRESHOLD,
    "negative_minor_threshold": NEGATIVE_MINOR_THRESHOLD,
    "non_induced_residual_threshold": NON_INDUCED_RESIDUAL_THRESHOLD,
}


StressFunction = Callable[..., dict[str, object]]


def _parse_rational(value: object, *, name: str) -> Fraction:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be rational, not boolean")
    if isinstance(value, Mapping):
        if set(value) != _RATIONAL_KEYS:
            raise ValueError(
                f"{name} rational object requires numerator and denominator"
            )
        numerator = value["numerator"]
        denominator = value["denominator"]
        if (
            not isinstance(numerator, int)
            or isinstance(numerator, bool)
            or not isinstance(denominator, int)
            or isinstance(denominator, bool)
            or denominator == 0
        ):
            raise TypeError(f"{name} rational fields must be valid integers")
        result = Fraction(numerator, denominator)
    elif isinstance(value, int):
        result = Fraction(value)
    elif isinstance(value, str):
        try:
            result = Fraction(value)
        except (ValueError, ZeroDivisionError) as error:
            raise ValueError(f"{name} must be a rational string") from error
    elif isinstance(value, (float, np.floating)):
        if not math.isfinite(float(value)):
            raise ValueError(f"{name} must be finite")
        result = Fraction(str(float(value)))
    else:
        raise TypeError(f"{name} must be an exact rational value")
    return result


def _rational_payload(value: Fraction | sp.Rational | int) -> dict[str, int]:
    rational = sp.Rational(value)
    return {
        "numerator": int(rational.p),
        "denominator": int(rational.q),
    }


def _canonical_parameters(params: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(params, Mapping):
        raise TypeError("params must be an object")
    missing = _PARAMETER_KEYS - set(params)
    unknown = set(params) - _PARAMETER_KEYS
    if missing or unknown:
        raise ValueError(
            "params must contain exactly "
            + ", ".join(sorted(_PARAMETER_KEYS))
        )

    positive_names = (
        "jacobi_strength",
        "diagonal_condition_ratio",
        "two_atom_scale_ratio",
    )
    rationals: dict[str, Fraction] = {}
    for name in positive_names:
        rationals[name] = _parse_rational(params[name], name=name)
        if rationals[name] <= 0:
            raise ValueError(f"{name} must be strictly positive")
    if rationals["diagonal_condition_ratio"] < 1:
        raise ValueError("diagonal_condition_ratio must be at least one")

    for name in ("chord_shear_magnitude", "givens_half_angle"):
        rationals[name] = _parse_rational(params[name], name=name)
        if rationals[name] < 0:
            raise ValueError(f"{name} must be nonnegative")

    raw_pattern = params["chord_pattern"]
    if (
        not isinstance(raw_pattern, Sequence)
        or isinstance(raw_pattern, (str, bytes))
    ):
        raise TypeError("chord_pattern must be a sequence of directed pairs")
    try:
        pattern = tuple(
            (int(edge[0]), int(edge[1]))
            for edge in raw_pattern
            if isinstance(edge, Sequence)
            and not isinstance(edge, (str, bytes))
            and len(edge) == 2
        )
    except (TypeError, ValueError, IndexError) as error:
        raise ValueError("chord_pattern contains an invalid edge") from error
    if len(pattern) != len(raw_pattern) or pattern not in _CHORD_PATTERNS:
        raise ValueError("chord_pattern is outside the frozen protocol")

    raw_plane = params["givens_plane"]
    if (
        not isinstance(raw_plane, Sequence)
        or isinstance(raw_plane, (str, bytes))
        or len(raw_plane) != 2
    ):
        raise TypeError("givens_plane must be one coordinate-index pair")
    plane = (int(raw_plane[0]), int(raw_plane[1]))
    if plane not in _GIVENS_PLANES:
        raise ValueError("givens_plane is outside the frozen protocol")

    return {
        "jacobi_strength": _rational_payload(rationals["jacobi_strength"]),
        "diagonal_condition_ratio": _rational_payload(
            rationals["diagonal_condition_ratio"]
        ),
        "chord_shear_magnitude": _rational_payload(
            rationals["chord_shear_magnitude"]
        ),
        "chord_pattern": [list(edge) for edge in pattern],
        "givens_half_angle": _rational_payload(rationals["givens_half_angle"]),
        "givens_plane": list(plane),
        "two_atom_scale_ratio": _rational_payload(
            rationals["two_atom_scale_ratio"]
        ),
    }


def _canonical_json(payload: Mapping[str, object]) -> str:
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _validated_cell_id(cell_id: object) -> str:
    if not isinstance(cell_id, str):
        raise TypeError("cell_id must be a string")
    if (
        not cell_id
        or cell_id == "."
        or ".." in cell_id
        or "/" in cell_id
        or "\\" in cell_id
        or ":" in cell_id
        or "\x00" in cell_id
    ):
        raise ValueError("cell_id must be one safe path component")
    return cell_id


def _fingerprint_from_canonical(
    cell_id: str,
    canonical_params: Mapping[str, object],
    resolved_settings: Mapping[str, object],
) -> str:
    payload = {
        "schema": SCHEMA,
        "cell_id": _validated_cell_id(cell_id),
        "parameters": dict(canonical_params),
        "resolved_settings": dict(resolved_settings),
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def cell_fingerprint(
    cell_id: str,
    params: Mapping[str, object],
    settings: Mapping[str, object],
) -> str:
    """Hash the complete resume identity for one resolved cell."""

    return _fingerprint_from_canonical(
        _validated_cell_id(cell_id),
        _canonical_parameters(params),
        _validated_settings(settings),
    )


def _as_sympy_rational(payload: object, *, name: str) -> sp.Rational:
    value = _parse_rational(payload, name=name)
    return sp.Rational(value.numerator, value.denominator)


def _adjacent_jacobi(index: int, strength: sp.Rational, *, lower: bool) -> sp.Matrix:
    result = sp.eye(5)
    row, column = (
        (index + 1, index) if lower else (index, index + 1)
    )
    result[row, column] = strength
    return result


def strict_totally_positive_core(
    *,
    jacobi_strength: sp.Rational,
    diagonal_condition_ratio: sp.Rational,
) -> sp.ImmutableMatrix:
    """Build the exact Loewner-Whitney big-cell factorization in dimension five."""

    strength = sp.Rational(jacobi_strength)
    ratio = sp.Rational(diagonal_condition_ratio)
    if strength <= 0:
        raise ValueError("jacobi_strength must be strictly positive")
    if ratio < 1:
        raise ValueError("diagonal_condition_ratio must be at least one")

    lower = sp.eye(5)
    for index in _REDUCED_LONGEST_WORD:
        lower = lower * _adjacent_jacobi(index, strength, lower=True)
    upper = sp.eye(5)
    for index in reversed(_REDUCED_LONGEST_WORD):
        upper = upper * _adjacent_jacobi(index, strength, lower=False)
    diagonal = sp.diag(1, 1, 1, 1, ratio)
    return sp.ImmutableMatrix(lower * diagonal * upper)


def _signed_chord_product(
    pattern: Sequence[tuple[int, int]],
    magnitude: sp.Rational,
    *,
    polarity: int,
) -> sp.ImmutableMatrix:
    product = sp.eye(5)
    for index, (row, column) in enumerate(pattern):
        factor = sp.eye(5)
        alternating_sign = 1 if index % 2 == 0 else -1
        factor[row, column] = polarity * alternating_sign * magnitude
        product = product * factor
    return sp.ImmutableMatrix(product)


def hodge_basis_map() -> sp.ImmutableMatrix:
    """Map the lexicographic grade-two basis to the grade-three Hodge basis."""

    grade2 = subset_basis(5, 2)
    grade3 = subset_basis(5, 3)
    grade3_index = {indices: index for index, indices in enumerate(grade3)}
    result = sp.zeros(10, 10)
    for column, pair in enumerate(grade2):
        complement = tuple(index for index in range(5) if index not in pair)
        joined = pair + complement
        inversions = sum(
            joined[left] > joined[right]
            for left in range(5)
            for right in range(left + 1, 5)
        )
        result[grade3_index[complement], column] = (
            -1 if inversions % 2 else 1
        )
    return sp.ImmutableMatrix(result)


def _rational_givens(
    half_angle: sp.Rational,
    plane: tuple[int, int],
) -> sp.ImmutableMatrix:
    t = sp.Rational(half_angle)
    if t < 0:
        raise ValueError("givens_half_angle must be nonnegative")
    cosine = (1 - t * t) / (1 + t * t)
    sine = 2 * t / (1 + t * t)
    first, second = plane
    result = sp.eye(10)
    result[first, first] = cosine
    result[first, second] = -sine
    result[second, first] = sine
    result[second, second] = cosine
    return sp.ImmutableMatrix(result)


def _candidate_card(canonical: Mapping[str, object]) -> dict[str, object]:
    return {
        "schema": CANDIDATE_SCHEMA,
        "dimension": 5,
        "atom_order": ["A_plus", "A_plus_transpose", "A_minus", "A_minus_transpose"],
        "basis_convention": BASIS_CONVENTION,
        "hodge_convention": HODGE_CONVENTION,
        "parameters": dict(canonical),
        "construction": {
            "core": {
                "kind": "positive-lower-diagonal-upper-jacobi",
                "lower_reduced_word": list(_REDUCED_LONGEST_WORD),
                "upper_reduced_word": list(reversed(_REDUCED_LONGEST_WORD)),
                "diagonal": ["1", "1", "1", "1", "diagonal_condition_ratio"],
            },
            "signed_chords": {
                "placement": "left-of-core",
                "sign_rule": "polarity*(-1)^edge_position",
                "base_atom_polarities": [1, -1],
            },
            "grade_gauges": {
                "Q1": "identity",
                "Q2": "rational-half-angle-givens",
                "Q3": "hodge*Q2*hodge_inverse",
                "Q4": "identity",
            },
            "transformed_compound_formula": "Qk.T @ C_k(A) @ Qk",
        },
    }


def construct_candidate(params: Mapping[str, object]) -> dict[str, object]:
    """Construct the exact atoms, gauges, and canonical replay identity."""

    canonical = _canonical_parameters(params)
    strength = _as_sympy_rational(
        canonical["jacobi_strength"], name="jacobi_strength"
    )
    condition_ratio = _as_sympy_rational(
        canonical["diagonal_condition_ratio"],
        name="diagonal_condition_ratio",
    )
    shear = _as_sympy_rational(
        canonical["chord_shear_magnitude"],
        name="chord_shear_magnitude",
    )
    half_angle = _as_sympy_rational(
        canonical["givens_half_angle"], name="givens_half_angle"
    )
    scale = _as_sympy_rational(
        canonical["two_atom_scale_ratio"],
        name="two_atom_scale_ratio",
    )
    pattern = tuple(
        (int(edge[0]), int(edge[1]))
        for edge in canonical["chord_pattern"]
    )
    plane = tuple(int(value) for value in canonical["givens_plane"])

    core = strict_totally_positive_core(
        jacobi_strength=strength,
        diagonal_condition_ratio=condition_ratio,
    )
    positive_shear = _signed_chord_product(pattern, shear, polarity=1)
    negative_shear = _signed_chord_product(pattern, shear, polarity=-1)
    first = sp.ImmutableMatrix(positive_shear * core)
    second = sp.ImmutableMatrix(scale * negative_shear * core)
    atoms = (first, first.T, second, second.T)

    q2 = _rational_givens(half_angle, (plane[0], plane[1]))
    hodge = hodge_basis_map()
    gauges = {
        1: sp.ImmutableMatrix(sp.eye(5)),
        2: q2,
        3: sp.ImmutableMatrix(hodge * q2 * hodge.T),
        4: sp.ImmutableMatrix(sp.eye(5)),
    }
    card = _candidate_card(canonical)
    identity_payload = {
        "schema": CANDIDATE_SCHEMA,
        "parameters": canonical,
    }
    candidate_id = hashlib.sha256(
        _canonical_json(identity_payload).encode("utf-8")
    ).hexdigest()
    return {
        "candidate_id": candidate_id,
        "candidate_card": card,
        "exact_atoms": atoms,
        "exact_gauges": gauges,
        "exact_core": core,
        "hodge_basis_map": hodge,
    }


def exact_transformed_compounds(
    atoms: Sequence[sp.MatrixBase],
    gauges: Mapping[int, sp.MatrixBase],
) -> dict[int, tuple[sp.ImmutableMatrix, ...]]:
    """Replay every declared transformed compound with exact rationals."""

    if len(atoms) != 4:
        raise ValueError("the protocol requires exactly four alphabet atoms")
    transformed: dict[int, tuple[sp.ImmutableMatrix, ...]] = {}
    for grade in range(1, 5):
        gauge = sp.ImmutableMatrix(gauges[grade])
        expected_dimension = len(subset_basis(5, grade))
        if gauge.shape != (expected_dimension, expected_dimension):
            raise ValueError("gauge dimension does not match its exterior grade")
        transformed[grade] = tuple(
            sp.ImmutableMatrix(
                gauge.T * exact_compound_matrix(atom, grade) * gauge
            )
            for atom in atoms
        )
    return transformed


def _float_matrix(matrix: sp.MatrixBase) -> np.ndarray:
    return np.asarray(matrix.tolist(), dtype=float)


def atom_admissibility_gate(
    atoms: Sequence[sp.MatrixBase],
    settings: Mapping[str, object],
) -> dict[str, object]:
    """Gate finite, invertible, positive-determinant, conditioned atoms."""

    limit = float(settings["condition_number_limit"])
    records: list[dict[str, object]] = []
    passed = True
    for atom_index, exact_atom in enumerate(atoms):
        array = _float_matrix(exact_atom)
        finite = bool(np.all(np.isfinite(array)))
        determinant = sp.factor(sp.det(exact_atom))
        positive_determinant = bool(determinant > 0)
        invertible = bool(determinant != 0)
        condition = (
            float(np.linalg.cond(array)) if finite and invertible else float("inf")
        )
        acceptable_condition = bool(
            math.isfinite(condition) and condition < limit
        )
        atom_passed = (
            finite
            and invertible
            and positive_determinant
            and acceptable_condition
        )
        passed = passed and atom_passed
        records.append(
            {
                "atom_index": atom_index,
                "finite": finite,
                "invertible": invertible,
                "positive_determinant": positive_determinant,
                "determinant": _rational_payload(determinant),
                "condition_number": condition,
                "condition_below_limit": acceptable_condition,
            }
        )
    return {
        "passed": passed,
        "status": "passed" if passed else "failed",
        "condition_number_limit": limit,
        "maximum_condition_number": max(
            (float(record["condition_number"]) for record in records),
            default=float("inf"),
        ),
        "minimum_determinant": min(
            (
                float(
                    Fraction(
                        int(record["determinant"]["numerator"]),
                        int(record["determinant"]["denominator"]),
                    )
                )
                for record in records
            ),
            default=float("nan"),
        ),
        "atoms": records,
    }


def transformed_compound_gate(
    atoms: Sequence[sp.MatrixBase],
    gauges: Mapping[int, sp.MatrixBase],
    settings: Mapping[str, object],
) -> dict[str, object]:
    """Require a strict relative positive-entry margin in grades one to four."""

    threshold = float(settings["relative_entry_margin_threshold"])
    transformed = exact_transformed_compounds(atoms, gauges)
    records: list[dict[str, object]] = []
    global_relative = float("inf")
    global_entry = float("inf")
    passed = True
    for grade in range(1, 5):
        for atom_index, exact_matrix in enumerate(transformed[grade]):
            array = _float_matrix(exact_matrix)
            finite = bool(np.all(np.isfinite(array)))
            maximum_absolute = (
                float(np.max(np.abs(array))) if finite else float("inf")
            )
            minimum_entry = (
                float(np.min(array)) if finite else float("-inf")
            )
            relative_margin = (
                minimum_entry / maximum_absolute
                if finite and maximum_absolute > 0.0
                else float("-inf")
            )
            entry_passed = bool(
                finite and relative_margin > threshold
            )
            passed = passed and entry_passed
            global_relative = min(global_relative, relative_margin)
            global_entry = min(global_entry, minimum_entry)
            records.append(
                {
                    "grade": grade,
                    "atom_index": atom_index,
                    "finite": finite,
                    "minimum_entry": minimum_entry,
                    "maximum_absolute_entry": maximum_absolute,
                    "relative_entry_margin": relative_margin,
                    "passed": entry_passed,
                }
            )
    return {
        "passed": passed,
        "status": "passed" if passed else "failed",
        "relative_entry_margin_threshold": threshold,
        "minimum_relative_entry_margin": global_relative,
        "minimum_entry": global_entry,
        "records": records,
    }


def non_tn_minor_gate(
    atoms: Sequence[sp.MatrixBase],
    settings: Mapping[str, object],
) -> dict[str, object]:
    """Require an original order-two minor strictly below the frozen cutoff."""

    threshold = float(settings["negative_minor_threshold"])
    minimum = float("inf")
    witness: dict[str, object] | None = None
    basis = subset_basis(5, 2)
    for atom_index, atom in enumerate(atoms):
        compound = exact_compound_matrix(atom, 2)
        for row in range(compound.rows):
            for column in range(compound.cols):
                value = float(compound[row, column])
                if value < minimum:
                    minimum = value
                    witness = {
                        "atom_index": atom_index,
                        "rows": list(basis[row]),
                        "columns": list(basis[column]),
                        "value": _rational_payload(compound[row, column]),
                    }
    passed = bool(minimum < -threshold)
    return {
        "passed": passed,
        "status": "passed" if passed else "failed",
        "negative_minor_threshold": threshold,
        "minimum_order2_minor": minimum,
        "witness": witness,
    }


def klein_pluecker_residual(gauge: sp.MatrixBase | np.ndarray) -> float:
    """Return the largest columnwise Gr(2,5) Pluecker-relation residual.

    Every column of an induced exterior-square map is a decomposable
    bivector.  For each column and each i<j<k<l, decomposability requires
    p_ij p_kl - p_ik p_jl + p_il p_jk = 0.  The frozen coordinate planes
    mix disjoint basis bivectors, so this inexpensive witness is nonzero
    exactly away from the zero-angle control in the declared family.
    """

    array = (
        _float_matrix(gauge)
        if isinstance(gauge, sp.MatrixBase)
        else np.asarray(gauge, dtype=float)
    )
    if array.shape != (10, 10) or not np.all(np.isfinite(array)):
        raise ValueError("grade-two gauge must be a finite ten-by-ten matrix")
    basis = subset_basis(5, 2)
    coordinate = {pair: index for index, pair in enumerate(basis)}
    residual = 0.0
    for column in range(10):
        vector = array[:, column]
        for i, j, k, l in combinations(range(5), 4):
            relation = (
                vector[coordinate[(i, j)]] * vector[coordinate[(k, l)]]
                - vector[coordinate[(i, k)]] * vector[coordinate[(j, l)]]
                + vector[coordinate[(i, l)]] * vector[coordinate[(j, k)]]
            )
            residual = max(residual, abs(float(relation)))
    return residual


def non_induced_gauge_gate(
    grade2_gauge: sp.MatrixBase,
    settings: Mapping[str, object],
) -> dict[str, object]:
    """Require the frozen non-induced Klein/Pluecker witness."""

    threshold = float(settings["non_induced_residual_threshold"])
    residual = klein_pluecker_residual(grade2_gauge)
    passed = bool(residual > threshold)
    return {
        "passed": passed,
        "status": "passed" if passed else "failed",
        "non_induced_residual_threshold": threshold,
        "klein_pluecker_residual": residual,
        "witness": "maximum-columnwise-Gr(2,5)-Pluecker-relation",
    }


def _decode_word(code: int, depth: int, alphabet_size: int) -> str:
    symbols: list[str] = []
    for _ in range(depth):
        symbols.append(str(code % alphabet_size))
        code //= alphabet_size
    return "".join(reversed(symbols))


def mixed_word_determinant_stress(
    atoms: Sequence[sp.MatrixBase],
    *,
    max_depth: int = 6,
    max_level_matrices: int = 2_000_000,
) -> dict[str, object]:
    """Exhaust mixed words only after all four structural gates pass."""

    if (
        not isinstance(max_depth, int)
        or isinstance(max_depth, bool)
        or max_depth < 1
    ):
        raise ValueError("max_depth must be a positive integer")
    if (
        not isinstance(max_level_matrices, int)
        or isinstance(max_level_matrices, bool)
        or max_level_matrices < 1
    ):
        raise ValueError("max_level_matrices must be a positive integer")
    float_atoms = tuple(_float_matrix(atom) for atom in atoms)
    if len(float_atoms) != 4:
        raise ValueError("mixed-word stress requires four atoms")
    level = [np.eye(5, dtype=float)]
    alphabet_size = len(float_atoms)
    minimum = float("inf")
    witness = ""
    witness_depth = 0
    word_count = 0
    per_depth: list[dict[str, object]] = []
    for depth in range(1, max_depth + 1):
        next_count = alphabet_size * len(level)
        if next_count > max_level_matrices:
            return {
                "passed": False,
                "completed_requested_depth": False,
                "status": "resource-limit",
                "max_depth_requested": max_depth,
                "max_depth_reached": depth - 1,
                "word_count": word_count,
                "next_level_matrices": next_count,
                "max_level_matrices": max_level_matrices,
                "minimum_determinant": minimum,
                "witness": witness,
                "witness_depth": witness_depth,
                "per_depth": per_depth,
            }
        level = [
            atom @ product
            for atom in float_atoms
            for product in level
        ]
        local_minimum = float("inf")
        local_witness = ""
        finite = True
        positive = True
        for code, product in enumerate(level):
            with np.errstate(over="ignore", invalid="ignore"):
                determinant = determinant_from_compound_traces(product)
            value = float(np.real(determinant))
            valid = (
                math.isfinite(value)
                and math.isfinite(float(np.imag(determinant)))
                and abs(float(np.imag(determinant))) <= 1.0e-8
            )
            if not valid:
                finite = False
                positive = False
                value = float("-inf")
            elif value <= 0.0:
                positive = False
            if value < local_minimum:
                local_minimum = value
                local_witness = _decode_word(code, depth, alphabet_size)
        word_count += next_count
        if local_minimum < minimum:
            minimum = local_minimum
            witness = local_witness
            witness_depth = depth
        per_depth.append(
            {
                "depth": depth,
                "word_count": next_count,
                "minimum_determinant": local_minimum,
                "witness": local_witness,
            }
        )
        if not finite or not positive:
            return {
                "passed": False,
                "completed_requested_depth": False,
                "status": (
                    "nonfinite-or-complex"
                    if not finite
                    else "nonpositive-word-found"
                ),
                "max_depth_requested": max_depth,
                "max_depth_reached": depth,
                "word_count": word_count,
                "minimum_determinant": minimum,
                "witness": witness,
                "witness_depth": witness_depth,
                "per_depth": per_depth,
            }
    return {
        "passed": True,
        "completed_requested_depth": True,
        "status": "all-tested-words-positive",
        "max_depth_requested": max_depth,
        "max_depth_reached": max_depth,
        "word_count": word_count,
        "minimum_determinant": minimum,
        "witness": witness,
        "witness_depth": witness_depth,
        "per_depth": per_depth,
    }


def _validated_settings(settings: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(settings, Mapping):
        raise TypeError("settings must be an object")
    result = dict(settings)
    for name, frozen in _BINDING_THRESHOLDS.items():
        if name in result:
            supplied = float(result[name])
            if not math.isfinite(supplied) or supplied != frozen:
                raise ValueError(f"{name} is binding at {frozen}")
        result[name] = frozen
    depth = result.get("mixed_word_depth", 6)
    level_limit = result.get("max_level_matrices", 2_000_000)
    if (
        not isinstance(depth, int)
        or isinstance(depth, bool)
        or depth < 1
    ):
        raise ValueError("mixed_word_depth must be a positive integer")
    if (
        not isinstance(level_limit, int)
        or isinstance(level_limit, bool)
        or level_limit < 1
    ):
        raise ValueError("max_level_matrices must be a positive integer")
    result["mixed_word_depth"] = depth
    result["max_level_matrices"] = level_limit
    return result


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, np.generic):
        return _json_safe(value.item())
    if isinstance(value, sp.Rational):
        return _rational_payload(value)
    if isinstance(value, (float, np.floating)) and not math.isfinite(float(value)):
        return None
    return value


def _error_record(error: Exception) -> dict[str, object]:
    return {
        "status": "compute-error",
        "error_type": type(error).__name__,
        "error": str(error),
    }


def _candidate_score(manifest: Mapping[str, object]) -> dict[str, object]:
    atom = manifest.get("atom_admissibility", {})
    compounds = manifest.get("structural_compounds", {})
    minor = manifest.get("non_tn_minor", {})
    gauge = manifest.get("non_induced_gauge", {})
    stress = manifest.get("mixed_word_stress", {})
    assert isinstance(atom, Mapping)
    assert isinstance(compounds, Mapping)
    assert isinstance(minor, Mapping)
    assert isinstance(gauge, Mapping)
    assert isinstance(stress, Mapping)
    return {
        "klein_pluecker_residual": gauge.get("klein_pluecker_residual"),
        "maximum_condition_number": atom.get("maximum_condition_number"),
        "minimum_determinant": atom.get("minimum_determinant"),
        "minimum_mixed_word_determinant": stress.get("minimum_determinant"),
        "minimum_order2_minor": minor.get("minimum_order2_minor"),
        "minimum_relative_entry_margin": compounds.get(
            "minimum_relative_entry_margin"
        ),
    }


def _finish(
    manifest: dict[str, object],
    started: float,
    *,
    classification: str,
    compute_success: bool,
    first_failure: str | None,
) -> dict[str, object]:
    manifest["classification"] = classification
    manifest["compute_success"] = compute_success
    manifest["first_failure"] = first_failure
    manifest["candidate_score"] = _candidate_score(manifest)
    manifest["elapsed_seconds"] = time.perf_counter() - started
    return manifest


def _not_run(manifest: dict[str, object], reason: str) -> None:
    manifest["mixed_word_stress"] = {
        "status": "not-run",
        "reason": reason,
    }


def _is_zero_rational(payload: object) -> bool:
    return _parse_rational(payload, name="control parameter") == 0


def run_cell(
    cell_id: str,
    params: Mapping[str, object],
    settings: Mapping[str, object],
    provenance: Mapping[str, object],
    *,
    stress_fn: StressFunction = mixed_word_determinant_stress,
) -> dict[str, object]:
    """Run one cell through the frozen early-stop gates."""

    started = time.perf_counter()
    validated_cell_id = _validated_cell_id(cell_id)
    manifest: dict[str, object] = {
        "schema": SCHEMA,
        "cell_id": validated_cell_id,
        "params": _json_safe(dict(params)),
        "settings": _json_safe(dict(settings)),
        "provenance": _json_safe(dict(provenance)),
        "gate_thresholds": dict(_BINDING_THRESHOLDS),
    }
    try:
        resolved_settings = _validated_settings(settings)
    except Exception as error:
        manifest["settings_validation"] = _error_record(error)
        _not_run(manifest, "settings-error")
        return _finish(
            manifest,
            started,
            classification="compute-error",
            compute_success=False,
            first_failure="settings-error",
        )

    try:
        candidate = construct_candidate(params)
    except Exception as error:
        manifest["candidate_construction"] = _error_record(error)
        _not_run(manifest, "candidate-construction-error")
        return _finish(
            manifest,
            started,
            classification="compute-error",
            compute_success=False,
            first_failure="candidate-construction-error",
        )
    manifest["candidate_id"] = candidate["candidate_id"]
    manifest["candidate_card"] = candidate["candidate_card"]
    canonical = candidate["candidate_card"]["parameters"]
    assert isinstance(canonical, Mapping)
    manifest["resolved_settings"] = _json_safe(resolved_settings)
    manifest["cell_fingerprint"] = _fingerprint_from_canonical(
        validated_cell_id,
        canonical,
        resolved_settings,
    )
    manifest["exact_replay"] = {
        "module": "oracle.tp_exterior_extension",
        "function": "construct_candidate",
        "identity": "candidate_card.parameters",
    }
    atoms = candidate["exact_atoms"]
    gauges = candidate["exact_gauges"]

    try:
        atom_gate = atom_admissibility_gate(atoms, resolved_settings)
    except Exception as error:
        manifest["atom_admissibility"] = _error_record(error)
        _not_run(manifest, "atom-admissibility-error")
        return _finish(
            manifest,
            started,
            classification="compute-error",
            compute_success=False,
            first_failure="atom-admissibility-error",
        )
    manifest["atom_admissibility"] = atom_gate
    if atom_gate.get("passed") is not True:
        _not_run(manifest, "atom-admissibility-gate")
        return _finish(
            manifest,
            started,
            classification="atom-admissibility-failed",
            compute_success=True,
            first_failure="atom-admissibility-gate",
        )

    try:
        compound_gate = transformed_compound_gate(
            atoms, gauges, resolved_settings
        )
    except Exception as error:
        manifest["structural_compounds"] = _error_record(error)
        _not_run(manifest, "structural-compound-error")
        return _finish(
            manifest,
            started,
            classification="compute-error",
            compute_success=False,
            first_failure="structural-compound-error",
        )
    manifest["structural_compounds"] = compound_gate
    if compound_gate.get("passed") is not True:
        _not_run(manifest, "structural-compound-gate")
        return _finish(
            manifest,
            started,
            classification="structural-compound-failed",
            compute_success=True,
            first_failure="structural-compound-gate",
        )

    known_tn_control = (
        _is_zero_rational(canonical["chord_shear_magnitude"])
        and _is_zero_rational(canonical["givens_half_angle"])
    )
    if known_tn_control:
        manifest["known_mechanism"] = "strict-totally-positive"
        manifest["non_tn_minor"] = {
            "passed": False,
            "status": "known-control",
            "reason": "zero-chord-shear",
        }
        manifest["non_induced_gauge"] = {
            "passed": False,
            "status": "known-control",
            "reason": "zero-givens-angle",
            "klein_pluecker_residual": 0.0,
        }
        _not_run(manifest, "known-tn-control")
        return _finish(
            manifest,
            started,
            classification="known-tn-control",
            compute_success=True,
            first_failure="known-tn-control",
        )

    try:
        minor_gate = non_tn_minor_gate(atoms, resolved_settings)
    except Exception as error:
        manifest["non_tn_minor"] = _error_record(error)
        _not_run(manifest, "non-tn-minor-error")
        return _finish(
            manifest,
            started,
            classification="compute-error",
            compute_success=False,
            first_failure="non-tn-minor-error",
        )
    manifest["non_tn_minor"] = minor_gate
    if minor_gate.get("passed") is not True:
        _not_run(manifest, "non-tn-minor-gate")
        return _finish(
            manifest,
            started,
            classification="known-tn-or-minor-failed",
            compute_success=True,
            first_failure="non-tn-minor-gate",
        )

    try:
        gauge_gate = non_induced_gauge_gate(gauges[2], resolved_settings)
    except Exception as error:
        manifest["non_induced_gauge"] = _error_record(error)
        _not_run(manifest, "non-induced-gauge-error")
        return _finish(
            manifest,
            started,
            classification="compute-error",
            compute_success=False,
            first_failure="non-induced-gauge-error",
        )
    manifest["non_induced_gauge"] = gauge_gate
    if gauge_gate.get("passed") is not True:
        _not_run(manifest, "non-induced-gauge-gate")
        return _finish(
            manifest,
            started,
            classification="induced-or-near-induced-gauge",
            compute_success=True,
            first_failure="non-induced-gauge-gate",
        )

    try:
        stress = stress_fn(
            atoms,
            max_depth=int(resolved_settings["mixed_word_depth"]),
            max_level_matrices=int(resolved_settings["max_level_matrices"]),
        )
    except Exception as error:
        manifest["mixed_word_stress"] = _error_record(error)
        return _finish(
            manifest,
            started,
            classification="compute-error",
            compute_success=False,
            first_failure="mixed-word-stress-error",
        )
    manifest["mixed_word_stress"] = stress
    if stress.get("status") == "resource-limit":
        return _finish(
            manifest,
            started,
            classification="mixed-word-stress-incomplete",
            compute_success=False,
            first_failure="mixed-word-stress-incomplete",
        )
    if stress.get("passed") is not True:
        return _finish(
            manifest,
            started,
            classification="determinant-stress-failed",
            compute_success=True,
            first_failure="mixed-word-stress-gate",
        )
    return _finish(
        manifest,
        started,
        classification="candidate-survivor",
        compute_success=True,
        first_failure=None,
    )


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(
                json.dumps(
                    _json_safe(payload),
                    allow_nan=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
        temporary.replace(path)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def _successful_manifest(
    path: Path,
    *,
    cell_id: str,
    cell_fingerprint_value: str,
) -> bool:
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        isinstance(payload, Mapping)
        and payload.get("schema") == SCHEMA
        and payload.get("cell_id") == cell_id
        and payload.get("cell_fingerprint") == cell_fingerprint_value
        and payload.get("compute_success") is True
    )


def _manifest_path(run_dir: Path, cell_id: str) -> Path:
    safe_cell_id = _validated_cell_id(cell_id)
    resolved_run_dir = run_dir.resolve()
    cells_root = (resolved_run_dir / "cells").resolve()
    if cells_root.parent != resolved_run_dir:
        raise ValueError("resolved cells directory must remain under run_dir")
    cell_directory = (cells_root / safe_cell_id).resolve()
    if cell_directory.parent != cells_root:
        raise ValueError("resolved cell manifest must remain under run_dir/cells")
    return cell_directory / "manifest.json"


def run_spec(
    path: str | Path,
    *,
    workers: int = 1,
    worker_index: int = 0,
    worker_count: int = 1,
    stress_fn: StressFunction = mixed_word_determinant_stress,
) -> dict[str, int]:
    """Execute one deterministic positional virtual-worker shard."""

    if not isinstance(workers, int) or isinstance(workers, bool) or workers < 1:
        raise ValueError("workers must be a positive integer")
    if (
        not isinstance(worker_count, int)
        or isinstance(worker_count, bool)
        or worker_count < 1
        or not isinstance(worker_index, int)
        or isinstance(worker_index, bool)
        or not 0 <= worker_index < worker_count
    ):
        raise ValueError("require 0 <= worker_index < worker_count")

    spec_path = Path(path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    cells = spec.get("cells")
    if not isinstance(cells, list):
        raise ValueError("run_spec.json requires a cells list")
    shared_settings = spec.get("settings", {})
    shared_provenance = spec.get("provenance", {})
    if not isinstance(shared_settings, Mapping):
        raise ValueError("shared settings must be an object")
    if not isinstance(shared_provenance, Mapping):
        raise ValueError("shared provenance must be an object")
    _validated_settings(shared_settings)

    cell_ids: set[str] = set()
    fingerprints: dict[str, str] = {}
    for cell in cells:
        if (
            not isinstance(cell, Mapping)
            or "cell_id" not in cell
            or "params" not in cell
        ):
            raise ValueError("each cell requires cell_id and params")
        cell_id = _validated_cell_id(cell["cell_id"])
        if cell_id in cell_ids:
            raise ValueError(f"duplicate cell_id: {cell_id}")
        cell_ids.add(cell_id)
        cell_settings = cell.get("settings", {})
        cell_provenance = cell.get("provenance", {})
        if not isinstance(cell_settings, Mapping):
            raise ValueError("cell settings must be an object")
        if not isinstance(cell_provenance, Mapping):
            raise ValueError("cell provenance must be an object")
        resolved_settings = _validated_settings(
            {**shared_settings, **dict(cell_settings)}
        )
        canonical_params = _canonical_parameters(cell["params"])
        fingerprints[cell_id] = _fingerprint_from_canonical(
            cell_id,
            canonical_params,
            resolved_settings,
        )

    run_dir_value = spec.get("run_dir")
    if run_dir_value is None:
        run_dir = spec_path.parent
    else:
        declared_run_dir = Path(run_dir_value)
        run_dir = (
            declared_run_dir
            if declared_run_dir.is_absolute()
            else spec_path.parent / declared_run_dir
        )
    selected = [
        cell
        for position, cell in enumerate(cells)
        if position % worker_count == worker_index
    ]
    pending: list[Mapping[str, object]] = []
    reused = 0
    for cell in selected:
        cell_id = _validated_cell_id(cell["cell_id"])
        manifest_path = _manifest_path(run_dir, cell_id)
        if _successful_manifest(
            manifest_path,
            cell_id=cell_id,
            cell_fingerprint_value=fingerprints[cell_id],
        ):
            reused += 1
        else:
            pending.append(cell)

    def execute(cell: Mapping[str, object]) -> dict[str, object]:
        cell_id = _validated_cell_id(cell["cell_id"])
        cell_settings = {
            **dict(shared_settings),
            **dict(cell.get("settings", {})),
        }
        cell_provenance = {
            **dict(shared_provenance),
            **dict(cell.get("provenance", {})),
        }
        manifest = run_cell(
            cell_id,
            cell["params"],
            cell_settings,
            cell_provenance,
            stress_fn=stress_fn,
        )
        _write_json_atomic(
            _manifest_path(run_dir, cell_id),
            manifest,
        )
        return manifest

    completed = 0
    compute_errors = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(execute, cell) for cell in pending]
        for future in as_completed(futures):
            manifest = future.result()
            completed += 1
            if manifest["compute_success"] is not True:
                compute_errors += 1
    return {
        "selected": len(selected),
        "completed": completed,
        "reused": reused,
        "compute_errors": compute_errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_spec", help="path to generic run_spec.json")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--worker-index", type=int, default=0)
    parser.add_argument("--worker-count", type=int, default=1)
    arguments = parser.parse_args()
    print(
        json.dumps(
            run_spec(
                arguments.run_spec,
                workers=arguments.workers,
                worker_index=arguments.worker_index,
                worker_count=arguments.worker_count,
            ),
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":  # pragma: no cover - remote CLI entry point
    main()


__all__ = [
    "CANDIDATE_SCHEMA",
    "SCHEMA",
    "atom_admissibility_gate",
    "cell_fingerprint",
    "construct_candidate",
    "exact_transformed_compounds",
    "hodge_basis_map",
    "klein_pluecker_residual",
    "main",
    "mixed_word_determinant_stress",
    "non_induced_gauge_gate",
    "non_tn_minor_gate",
    "run_cell",
    "run_spec",
    "strict_totally_positive_core",
    "transformed_compound_gate",
]

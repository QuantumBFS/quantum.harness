"""Exact Hodge reduction of the oddcycle grade-(3,4) sector."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

import numpy as np
import sympy as sp

from .exterior_exact5_shared_cone import exact_compound_matrix
from .oddcycle_pair_physical import leading_pair_matrices
from .symmetric_oddcycle_discovery import compound_matrix


SCHEMA = "oddcycle-grade34-hodge-reduction-v1"
_GRADE4_GAUGE = sp.diag(1, 1, 1, -1, 1)
_EDGE_TO_TRIPLE = (0, 1, 3, 6, 2, 4, 7, 5, 8, 9)
_HODGE_SIGNS = (1, 1, -1, 1, 1, -1, 1, -1, 1, -1)


def _decode_symbol_word(code: int, depth: int, alphabet_size: int) -> str:
    symbols = ["0"] * depth
    for index in range(depth - 1, -1, -1):
        symbols[index] = str(code % alphabet_size)
        code //= alphabet_size
    return "".join(symbols)


def _hodge_transform() -> sp.ImmutableMatrix:
    transform = sp.zeros(10)
    for edge, triple in enumerate(_EDGE_TO_TRIPLE):
        transform[edge, triple] = _HODGE_SIGNS[edge]
    return sp.ImmutableMatrix(transform)


def exact_symbolic_hodge_identity() -> dict[str, object]:
    """Verify ``wedge^2(P)=8 H wedge^3(B) H^T`` for symbolic ``p``."""

    p = sp.symbols("p", positive=True)
    matrix = sp.ImmutableMatrix(
        [
            [0, 0, 2, 0, 0],
            [2, 0, 0, 0, 0],
            [0, 2, 0, p, 0],
            [0, 0, 0, 1, 1],
            [0, 0, -1, 0, 1],
        ]
    )
    positive_grade4 = sp.ImmutableMatrix(
        _GRADE4_GAUGE
        * exact_compound_matrix(matrix, 4)
        * _GRADE4_GAUGE
    )
    transform = _hodge_transform()
    left = exact_compound_matrix(positive_grade4, 2)
    right = sp.ImmutableMatrix(
        8
        * transform
        * exact_compound_matrix(matrix, 3)
        * transform.T
    )
    identity = left == right
    transpose_identity = (
        exact_compound_matrix(positive_grade4.T, 2)
        == sp.ImmutableMatrix(
            8
            * transform
            * exact_compound_matrix(matrix.T, 3)
            * transform.T
        )
    )
    if not identity or not transpose_identity:
        raise RuntimeError("symbolic Hodge identity failed")
    return {
        "schema": SCHEMA,
        "status": "exact-symbolic-hodge-identity",
        "determinant_per_letter": 8,
        "grade4_atom_entrywise_nonnegative_for_p_positive": all(
            entry.is_nonnegative is not False for entry in positive_grade4
        ),
        "forward_identity": identity,
        "transpose_identity": transpose_identity,
        "edge_to_triple_permutation": _EDGE_TO_TRIPLE,
        "hodge_signs": _HODGE_SIGNS,
        "word_consequence": (
            "wedge^2(P_w)=8^n H wedge^3(W) H^T"
        ),
    }


def exact_word_grade34_reduction(word: str = "012301") -> dict[str, object]:
    """Replay the grade-(3,4) scalar reduction for one four-letter word."""

    pair = leading_pair_matrices()
    atoms = (pair[0], pair[0].T, pair[1], pair[1].T)
    product = sp.eye(5)
    positive_product = sp.eye(5)
    for symbol in word:
        if symbol not in {"0", "1", "2", "3"}:
            raise ValueError("word must contain only symbols 0,1,2,3")
        atom = atoms[int(symbol)]
        product = atom * product
        positive_atom = (
            _GRADE4_GAUGE
            * exact_compound_matrix(atom, 4)
            * _GRADE4_GAUGE
        )
        positive_product = positive_atom * positive_product
    length = len(word)
    determinant_growth = 8**length
    chi3 = sp.trace(exact_compound_matrix(product, 3))
    chi4 = sp.trace(exact_compound_matrix(product, 4))
    e2_positive = sp.trace(exact_compound_matrix(positive_product, 2))
    trace_positive = sp.trace(positive_product)
    hodge_matrix_identity = (
        exact_compound_matrix(positive_product, 2)
        == sp.ImmutableMatrix(
            determinant_growth
            * _hodge_transform()
            * exact_compound_matrix(product, 3)
            * _hodge_transform().T
        )
    )
    scalar_identity = (
        e2_positive + determinant_growth * trace_positive
        == determinant_growth * (chi3 + chi4)
    )
    if not hodge_matrix_identity or not scalar_identity:
        raise RuntimeError("word-level Hodge reduction failed")
    return {
        "schema": SCHEMA,
        "status": "exact-word-grade34-reduction",
        "word": word,
        "length": length,
        "determinant_growth": determinant_growth,
        "hodge_matrix_identity": hodge_matrix_identity,
        "scalar_identity": scalar_identity,
        "chi3": int(chi3),
        "chi4": int(chi4),
        "positive_grade4_trace": int(trace_positive),
        "positive_grade4_e2": int(e2_positive),
        "reduced_target": (
            "e2(P_w)+8^n trace(P_w)>0"
        ),
    }


def joint_hodge_margin_profile(
    points: Sequence[Sequence[float]],
    *,
    max_depth: int = 10,
    max_level_matrices: int = 2_000_000,
) -> dict[str, object]:
    """Enumerate the exact-reduction scalar margin in float64 discovery mode."""

    from .oddcycle_joint_words import joint_alphabet

    if max_depth < 1:
        raise ValueError("max_depth must be positive")
    gauge = np.diag([1.0, 1.0, 1.0, -1.0, 1.0])
    atoms = np.asarray(
        [
            gauge @ compound_matrix(atom, 4) @ gauge
            for atom in joint_alphabet(points)
        ]
    )
    if float(np.min(atoms)) < -1.0e-12:
        raise ValueError("the grade-four atoms are not nonnegative")
    alphabet_size = len(atoms)
    level = np.eye(5, dtype=float)[None, :, :]
    codes = np.zeros(1, dtype=np.int64)
    per_depth = []
    status = "complete"
    for depth in range(1, max_depth + 1):
        next_count = alphabet_size * len(level)
        if next_count > max_level_matrices:
            status = "resource-limit"
            break
        level = np.matmul(
            atoms[:, None, :, :], level[None, :, :, :]
        ).reshape(next_count, 5, 5)
        codes = np.concatenate(
            [codes * alphabet_size + symbol for symbol in range(alphabet_size)]
        )
        traces = np.trace(level, axis1=1, axis2=2)
        traces_squared = np.einsum("bij,bji->b", level, level)
        e2_values = 0.5 * (np.square(traces) - traces_squared)
        determinant_growth = float(8**depth)
        targets = e2_values + determinant_growth * traces
        relative = targets / (determinant_growth * traces)
        index = int(np.argmin(relative))
        per_depth.append(
            {
                "depth": depth,
                "word_count": next_count,
                "minimum_relative_margin": float(relative[index]),
                "grade34_sum": float(targets[index] / determinant_growth),
                "grade4_trace": float(traces[index]),
                "grade4_e2": float(e2_values[index]),
                "witness_code": int(codes[index]),
                "witness": _decode_symbol_word(
                    int(codes[index]), depth, alphabet_size
                ),
            }
        )
        if targets[index] <= 0.0:
            status = "floating-nonpositive-requires-exact-replay"
            break
    return {
        "schema": SCHEMA,
        "status": status,
        "alphabet_size": alphabet_size,
        "max_depth_requested": max_depth,
        "max_depth_reached": len(per_depth),
        "next_level_matrices": (
            alphabet_size * len(level) if status == "resource-limit" else None
        ),
        "per_depth": per_depth,
    }


def joint_positive_compound_trace_profile(
    points: Sequence[Sequence[float]],
    *,
    compound_grade: int,
    max_depth: int = 16,
    max_level_matrices: int = 2_000_000,
) -> dict[str, object]:
    """Enumerate trace signs of one compound grade of the positive ``P`` word."""

    from .oddcycle_joint_words import joint_alphabet

    if compound_grade not in {1, 2, 3, 4, 5}:
        raise ValueError("compound_grade must lie between one and five")
    if max_depth < 1:
        raise ValueError("max_depth must be positive")
    gauge = np.diag([1.0, 1.0, 1.0, -1.0, 1.0])
    positive_atoms = tuple(
        gauge @ compound_matrix(atom, 4) @ gauge
        for atom in joint_alphabet(points)
    )
    atoms = np.asarray(
        [
            compound_matrix(atom, compound_grade)
            for atom in positive_atoms
        ]
    )
    alphabet_size = len(atoms)
    dimension = atoms.shape[-1]
    level = np.eye(dimension, dtype=float)[None, :, :]
    codes = np.zeros(1, dtype=np.int64)
    per_depth = []
    status = "complete"
    for depth in range(1, max_depth + 1):
        next_count = alphabet_size * len(level)
        if next_count > max_level_matrices:
            status = "resource-limit"
            break
        level = np.matmul(
            atoms[:, None, :, :], level[None, :, :, :]
        ).reshape(next_count, dimension, dimension)
        codes = np.concatenate(
            [codes * alphabet_size + symbol for symbol in range(alphabet_size)]
        )
        traces = np.trace(level, axis1=1, axis2=2)
        index = int(np.argmin(traces))
        minimum = float(traces[index])
        per_depth.append(
            {
                "depth": depth,
                "word_count": next_count,
                "minimum_trace": minimum,
                "witness": _decode_symbol_word(
                    int(codes[index]), depth, alphabet_size
                ),
            }
        )
        if minimum < 0.0:
            status = "floating-negative-requires-exact-replay"
            break
    return {
        "schema": SCHEMA,
        "status": status,
        "compound_grade": compound_grade,
        "representation_dimension": dimension,
        "max_depth_reached": len(per_depth),
        "per_depth": per_depth,
    }


def joint_low_sector_pair_profile(
    points: Sequence[Sequence[float]],
    *,
    max_depth: int = 18,
    max_level_matrices: int = 2_000_000,
) -> dict[str, object]:
    """Enumerate ``chi1(W)+chi2(W)`` for every word at each depth."""

    from .oddcycle_joint_words import joint_alphabet

    if max_depth < 1:
        raise ValueError("max_depth must be positive")
    one_particle_atoms = np.asarray(joint_alphabet(points))
    grade2_atoms = np.asarray(
        [compound_matrix(atom, 2) for atom in one_particle_atoms]
    )
    alphabet_size = len(one_particle_atoms)
    level1 = np.eye(5, dtype=float)[None, :, :]
    level2 = np.eye(10, dtype=float)[None, :, :]
    codes = np.zeros(1, dtype=np.int64)
    per_depth = []
    status = "complete"
    for depth in range(1, max_depth + 1):
        next_count = alphabet_size * len(level1)
        if next_count > max_level_matrices:
            status = "resource-limit"
            break
        level1 = np.matmul(
            one_particle_atoms[:, None, :, :], level1[None, :, :, :]
        ).reshape(next_count, 5, 5)
        level2 = np.matmul(
            grade2_atoms[:, None, :, :], level2[None, :, :, :]
        ).reshape(next_count, 10, 10)
        codes = np.concatenate(
            [codes * alphabet_size + symbol for symbol in range(alphabet_size)]
        )
        chi1 = np.trace(level1, axis1=1, axis2=2)
        chi2 = np.trace(level2, axis1=1, axis2=2)
        pair_sum = chi1 + chi2
        index = int(np.argmin(pair_sum))
        minimum = float(pair_sum[index])
        per_depth.append(
            {
                "depth": depth,
                "word_count": next_count,
                "minimum_pair_sum": minimum,
                "chi1": float(chi1[index]),
                "chi2": float(chi2[index]),
                "witness": _decode_symbol_word(
                    int(codes[index]), depth, alphabet_size
                ),
            }
        )
        if minimum < 0.0:
            status = "floating-negative-requires-exact-replay"
            break
    return {
        "schema": SCHEMA,
        "status": status,
        "max_depth_reached": len(per_depth),
        "per_depth": per_depth,
    }


__all__: Sequence[str] = (
    "SCHEMA",
    "exact_symbolic_hodge_identity",
    "exact_word_grade34_reduction",
    "joint_hodge_margin_profile",
    "joint_low_sector_pair_profile",
    "joint_positive_compound_trace_profile",
)


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--point",
        nargs=3,
        type=float,
        action="append",
        metavar=("P", "Q", "R"),
    )
    parser.add_argument("--profile-depth", type=int, default=0)
    parser.add_argument("--compound-grade", type=int, default=0)
    parser.add_argument("--low-sector-pair", action="store_true")
    parser.add_argument("--max-level-matrices", type=int, default=2_000_000)
    parser.add_argument("--word", default="")
    arguments = parser.parse_args()
    if arguments.low_sector_pair:
        if not arguments.point or not arguments.profile_depth:
            parser.error("--point and --profile-depth are required")
        payload = joint_low_sector_pair_profile(
            arguments.point,
            max_depth=arguments.profile_depth,
            max_level_matrices=arguments.max_level_matrices,
        )
    elif arguments.compound_grade:
        if not arguments.point or not arguments.profile_depth:
            parser.error("--point and --profile-depth are required")
        payload = joint_positive_compound_trace_profile(
            arguments.point,
            compound_grade=arguments.compound_grade,
            max_depth=arguments.profile_depth,
            max_level_matrices=arguments.max_level_matrices,
        )
    elif arguments.profile_depth:
        if not arguments.point:
            parser.error("--point is required for a profile")
        payload = joint_hodge_margin_profile(
            arguments.point,
            max_depth=arguments.profile_depth,
            max_level_matrices=arguments.max_level_matrices,
        )
    elif arguments.word:
        payload = exact_word_grade34_reduction(arguments.word)
    else:
        payload = exact_symbolic_hodge_identity()
    print(json.dumps(payload, indent=2, sort_keys=True), flush=True)


if __name__ == "__main__":  # pragma: no cover - CLI
    _main()

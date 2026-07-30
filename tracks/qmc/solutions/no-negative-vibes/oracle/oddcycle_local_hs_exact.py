"""Exact promotion and diagonal-sign audit for local odd-cycle generators."""

from __future__ import annotations

import hashlib
import json
from collections import deque
from collections.abc import Sequence
from fractions import Fraction

import numpy as np
import sympy as sp

from oracle.oddcycle_local_hs_scan import (
    LocalitySpec,
    forbidden_label_indices,
)
from oracle.oddcycle_word_operator import (
    WordPairColumn,
    reconstruct_normal_ordered,
)


SCHEMA = "oddcycle-local-hs-exact-v1"


def _canonical_rational(value: sp.Expr) -> dict[str, int]:
    rational = sp.Rational(sp.cancel(value))
    return {
        "numerator": int(rational.p),
        "denominator": int(rational.q),
    }


def _payload_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def exact_positive_null_vector(
    matrix: sp.MatrixBase,
    approximate: np.ndarray,
    *,
    max_denominator: int = 10**9,
) -> tuple[sp.Rational, ...]:
    """Promote an approximate normalized positive kernel vector exactly."""

    if not isinstance(matrix, sp.MatrixBase):
        raise TypeError("matrix must be a SymPy matrix")
    if (
        not isinstance(max_denominator, int)
        or isinstance(max_denominator, bool)
        or max_denominator < 1
    ):
        raise ValueError("max_denominator must be a positive integer")
    approximate_array = np.asarray(approximate, dtype=float)
    if (
        approximate_array.shape != (matrix.cols,)
        or not np.all(np.isfinite(approximate_array))
    ):
        raise ValueError("approximate must be one finite value per column")

    basis = matrix.nullspace()
    if not basis:
        raise ValueError("exact forbidden matrix has a trivial nullspace")
    nullspace = sp.Matrix.hstack(*basis)
    if len(basis) == 1:
        candidate = tuple(sp.cancel(value) for value in basis[0])
    else:
        coefficients, *_ = np.linalg.lstsq(
            np.asarray(nullspace, dtype=float),
            approximate_array,
            rcond=None,
        )
        limited = [
            Fraction(float(value)).limit_denominator(max_denominator)
            for value in coefficients
        ]
        rational_coefficients = sp.Matrix(
            [
                sp.Rational(value.numerator, value.denominator)
                for value in limited
            ]
        )
        candidate = tuple(
            sp.cancel(value)
            for value in nullspace * rational_coefficients
        )

    total = sp.cancel(sum(candidate))
    if total == 0:
        raise ValueError("rationalized exact null vector has zero total")
    normalized = tuple(sp.cancel(value / total) for value in candidate)
    if any(value <= 0 for value in normalized):
        raise ValueError(
            "rationalized exact null vector is not strictly positive"
        )
    if matrix * sp.Matrix(normalized) != sp.zeros(matrix.rows, 1):
        raise ArithmeticError("rationalized weights do not replay exactly")
    return tuple(sp.Rational(value) for value in normalized)


def _normalize_blocks(
    dimension: int,
    blocks: Sequence[Sequence[int]] | None,
) -> tuple[tuple[int, ...], ...]:
    if blocks is None:
        return (tuple(range(dimension)),)
    normalized = tuple(tuple(block) for block in blocks)
    flattened = tuple(vertex for block in normalized for vertex in block)
    if (
        any(not block for block in normalized)
        or any(
            not isinstance(vertex, int)
            or isinstance(vertex, bool)
            or vertex < 0
            or vertex >= dimension
            for vertex in flattened
        )
        or len(set(flattened)) != len(flattened)
        or set(flattened) != set(range(dimension))
    ):
        raise ValueError("blocks must partition the Hamiltonian indices")
    return normalized


def _edge_constraint(value: sp.Expr) -> int:
    if value.is_real is not True:
        raise ValueError("Hamiltonian off-diagonal entries must be real")
    sign = sp.sign(value)
    if sign not in (-1, 1):
        raise ValueError("Hamiltonian edge sign is not exactly decidable")
    return -int(sign)


def _tree_conflict_cycle(
    left: int,
    right: int,
    parent: dict[int, int | None],
) -> tuple[int, ...]:
    left_path = []
    vertex: int | None = left
    while vertex is not None:
        left_path.append(vertex)
        vertex = parent[vertex]
    left_positions = {
        vertex: index for index, vertex in enumerate(left_path)
    }
    right_path = []
    vertex = right
    while vertex not in left_positions:
        right_path.append(vertex)
        ancestor = parent[vertex]
        if ancestor is None:
            raise ArithmeticError("conflict vertices have no common ancestor")
        vertex = ancestor
    ancestor = vertex
    return tuple(
        (
            *left_path[: left_positions[ancestor] + 1],
            *reversed(right_path),
        )
    )


def diagonal_sign_gauge_audit(
    hamiltonian: sp.MatrixBase,
    blocks: Sequence[Sequence[int]] | None = None,
) -> dict[str, object]:
    """Audit whether exact diagonal signs make every off-diagonal nonpositive."""

    if (
        not isinstance(hamiltonian, sp.MatrixBase)
        or hamiltonian.rows != hamiltonian.cols
    ):
        raise ValueError("hamiltonian must be a square SymPy matrix")
    if hamiltonian != hamiltonian.T:
        raise ValueError("hamiltonian must be exactly symmetric")

    dimension = hamiltonian.rows
    normalized_blocks = _normalize_blocks(dimension, blocks)
    block_of = {
        vertex: block_index
        for block_index, block in enumerate(normalized_blocks)
        for vertex in block
    }
    for left in range(dimension):
        for right in range(left + 1, dimension):
            if (
                hamiltonian[left, right] != 0
                and block_of[left] != block_of[right]
            ):
                raise ValueError("hamiltonian has a nonzero cross-block edge")

    gauge: dict[int, int] = {}
    edge_count = 0
    for block in normalized_blocks:
        block_set = set(block)
        adjacency: dict[int, list[tuple[int, int]]] = {
            vertex: [] for vertex in block
        }
        for offset, left in enumerate(block):
            for right in block[offset + 1 :]:
                value = hamiltonian[left, right]
                if value == 0:
                    continue
                required_product = _edge_constraint(value)
                adjacency[left].append((right, required_product))
                adjacency[right].append((left, required_product))
                edge_count += 1

        for root in block:
            if root in gauge:
                continue
            gauge[root] = 1
            parent: dict[int, int | None] = {root: None}
            queue = deque([root])
            while queue:
                left = queue.popleft()
                for right, required_product in adjacency[left]:
                    if right not in block_set:
                        raise ArithmeticError("adjacency escaped its block")
                    proposed = gauge[left] * required_product
                    if right not in gauge:
                        gauge[right] = proposed
                        parent[right] = left
                        queue.append(right)
                        continue
                    if gauge[right] == proposed:
                        continue
                    cycle = _tree_conflict_cycle(left, right, parent)
                    cycle_constraints = tuple(
                        _edge_constraint(
                            hamiltonian[
                                cycle[index],
                                cycle[(index + 1) % len(cycle)],
                            ]
                        )
                        for index in range(len(cycle))
                    )
                    replay_product = int(np.prod(cycle_constraints))
                    if replay_product != -1:
                        raise ArithmeticError(
                            "reported gauge conflict did not replay exactly"
                        )
                    return {
                        "status": "exact-gauge-frustrated",
                        "dimension": dimension,
                        "block_count": len(normalized_blocks),
                        "edge_count": edge_count,
                        "conflict_cycle_zero_based": cycle,
                        "conflict_constraints": cycle_constraints,
                        "constraint_product": replay_product,
                    }

    ordered_gauge = tuple(gauge[index] for index in range(dimension))
    for left in range(dimension):
        for right in range(left + 1, dimension):
            value = hamiltonian[left, right]
            if value != 0 and ordered_gauge[left] * value * ordered_gauge[right] > 0:
                raise ArithmeticError("constructed gauge failed exact replay")
    return {
        "status": "exact-diagonal-gauge-stoquastic",
        "dimension": dimension,
        "block_count": len(normalized_blocks),
        "edge_count": edge_count,
        "gauge": ordered_gauge,
    }


def _inconclusive_payload(reason: str, nullity: int | None) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema": SCHEMA,
        "status": "exact-promotion-inconclusive",
        "reason": reason,
    }
    if nullity is not None:
        payload["exact_forbidden_nullity"] = nullity
    payload["exact_certificate_sha256"] = _payload_sha256(payload)
    return payload


def exact_local_hs_certificate(
    columns: Sequence[WordPairColumn],
    weights: np.ndarray,
    spec: LocalitySpec,
) -> dict[str, object]:
    """Promote one numerical local-generator survivor and replay exact gates."""

    normalized_columns = tuple(columns)
    if not normalized_columns:
        return _inconclusive_payload("no active columns", None)
    if not isinstance(spec, LocalitySpec):
        raise TypeError("spec must be a LocalitySpec")
    approximate = np.asarray(weights, dtype=float)
    if (
        approximate.shape != (len(normalized_columns),)
        or not np.all(np.isfinite(approximate))
    ):
        return _inconclusive_payload(
            "weights must be one finite value per active column",
            None,
        )

    labels = tuple(normalized_columns[0].coordinates)
    if any(
        set(column.coordinates) != set(labels)
        for column in normalized_columns
    ):
        raise ValueError("columns must use one common coordinate basis")
    forbidden = forbidden_label_indices(labels, spec)
    forbidden_entries = [
        column.coordinates[labels[index]]
        for index in forbidden
        for column in normalized_columns
    ]
    forbidden_matrix = sp.ImmutableMatrix(
        len(forbidden),
        len(normalized_columns),
        forbidden_entries,
    )
    nullity = len(forbidden_matrix.nullspace())
    try:
        exact_weights = exact_positive_null_vector(
            forbidden_matrix,
            approximate,
        )
    except (ArithmeticError, ValueError) as error:
        return _inconclusive_payload(str(error), nullity)

    dimension = normalized_columns[0].fock_pair.rows
    if (
        normalized_columns[0].fock_pair.cols != dimension
        or dimension < 1
        or dimension & (dimension - 1)
        or any(
            column.fock_pair.shape != (dimension, dimension)
            for column in normalized_columns
        )
    ):
        raise ValueError("columns must have one power-of-two Fock dimension")
    modes = dimension.bit_length() - 1

    generator = sp.ImmutableMatrix(
        sum(
            (
                weight * column.fock_pair
                for column, weight in zip(
                    normalized_columns,
                    exact_weights,
                    strict=True,
                )
            ),
            sp.zeros(dimension),
        )
    )
    generator_coordinates = {
        label: sp.cancel(
            sum(
                (
                    weight * column.coordinates[label]
                    for column, weight in zip(
                        normalized_columns,
                        exact_weights,
                        strict=True,
                    )
                ),
                sp.Integer(0),
            )
        )
        for label in labels
    }
    scalar_labels = tuple(
        label for label in labels if label.body_order == 0
    )
    if len(scalar_labels) != 1:
        raise ValueError("coordinate basis must contain one scalar label")
    scalar_label = scalar_labels[0]
    scalar = generator_coordinates[scalar_label]
    physical_coordinates = {
        label: sp.cancel(-coefficient)
        for label, coefficient in generator_coordinates.items()
        if label != scalar_label
    }
    hamiltonian = reconstruct_normal_ordered(physical_coordinates, modes)
    coordinate_replay = reconstruct_normal_ordered(
        generator_coordinates,
        modes,
    )
    expected_hamiltonian = sp.ImmutableMatrix(
        -(generator - scalar * sp.eye(dimension))
    )

    exact_forbidden_zero = all(
        generator_coordinates[labels[index]] == 0
        for index in forbidden
    )
    nonzero_two_body = any(
        label.body_order == 2 and coefficient != 0
        for label, coefficient in physical_coordinates.items()
    )
    no_higher_body = all(
        coefficient == 0
        for label, coefficient in physical_coordinates.items()
        if label.body_order > 2
    )
    exact_full_fock_equality = (
        coordinate_replay == generator
        and hamiltonian == expected_hamiltonian
    )
    exact_hermitian = (
        generator == generator.T and hamiltonian == hamiltonian.T
    )
    strictly_positive = all(weight > 0 for weight in exact_weights)
    gates = {
        "exact_generator_reconstructed": coordinate_replay == generator,
        "exact_forbidden_coordinates_zero": exact_forbidden_zero,
        "nonzero_body_order_two_term": nonzero_two_body,
        "no_body_order_above_two": no_higher_body,
        "exact_full_fock_equality": exact_full_fock_equality,
        "strictly_positive_exact_weights": strictly_positive,
        "exact_hermitian": exact_hermitian,
    }

    particle_number_blocks = tuple(
        tuple(
            state
            for state in range(dimension)
            if state.bit_count() == particles
        )
        for particles in range(modes + 1)
    )
    gauge_audit = diagonal_sign_gauge_audit(
        hamiltonian,
        particle_number_blocks,
    )
    fields = [
        {
            "word": list(column.word),
            "transpose_word": list(column.transpose_word),
            "weight": _canonical_rational(weight),
        }
        for column, weight in zip(
            normalized_columns,
            exact_weights,
            strict=True,
        )
    ]
    physical_terms = [
        {
            "create_zero_based": list(label.create),
            "annihilate_zero_based": list(label.annihilate),
            "body_order": label.body_order,
            "support_zero_based": sorted(label.support),
            "coefficient": _canonical_rational(coefficient),
        }
        for label, coefficient in physical_coordinates.items()
        if coefficient != 0
    ]
    payload: dict[str, object] = {
        "schema": SCHEMA,
        "status": (
            "exact-local-interacting-hs-survivor"
            if all(gates.values())
            else "exact-local-hs-gate-failed"
        ),
        "locality_spec": {
            "name": spec.name,
            "max_body_order": spec.max_body_order,
            "allowed_supports_zero_based": [
                sorted(support) for support in spec.allowed_supports
            ],
        },
        "exact_forbidden_nullity": nullity,
        "scalar_coordinate_dropped": _canonical_rational(scalar),
        "fields": fields,
        "physical_terms": physical_terms,
        "gates": gates,
        "novelty": {
            "diagonal_sign_gauge_audit_on": "H=-V modulo scalar",
            "diagonal_sign_gauge": gauge_audit,
            "exact_gauge_frustrated": (
                gauge_audit["status"] == "exact-gauge-frustrated"
            ),
        },
        "arbitrary_history_theorem": {
            "module": "oracle.oddcycle_path_metric",
            "certificate": "exact_last_letter_path_metric_certificate",
            "status": "frozen-exact-arbitrary-word-determinant-positive",
            "reduction": (
                "each macro-history concatenates to a word over "
                "{B0,B0.T,B1,B1.T}"
            ),
        },
    }
    payload["exact_certificate_sha256"] = _payload_sha256(payload)
    return payload


__all__ = [
    "SCHEMA",
    "diagonal_sign_gauge_audit",
    "exact_local_hs_certificate",
    "exact_positive_null_vector",
]

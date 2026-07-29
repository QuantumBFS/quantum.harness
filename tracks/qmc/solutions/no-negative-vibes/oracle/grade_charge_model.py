"""Grouped grade-charge ancillas for the graded-monomial model.

This module is a model implementation of the already proved graded-monomial
mechanism.  It is *not* a new positivity theorem.  Assigning one conserved
ancilla to every edge makes each Hamiltonian vertex three-mode local, but that
local ancilla realization does not change the underlying cycle-factor proof or
its known Majorana-reflection-positive projected sector.

For a physical dilated transposition ``B_e`` and the grade group ``g=alpha(e)``,
the extended one-particle field is

``Btilde_e = B_e direct-sum (-r_e)_g direct-sum I_other``.

For a history ``h`` its full Fock trace factorizes as

``det(I + D_h) * product_g [1 + x_g (-1)^k_g R_g]``.

Here ``x_g`` is an optional positive fugacity, ``k_g`` counts vertices in group
``g``, and ``R_g`` is their dilation product.  The default ``x_g=1`` is the
ordinary full ancilla trace.  The tight all-history safety condition for one
group is ``x_g >= 1/min_(e in g) r_e``; below it, the minimum-dilation
one-edge history is already a negative witness.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal, Sequence

import numpy as np

from oracle.graded_monomial import (
    ancilla_extended_real_generator,
    dilated_transposition_propagator,
)
from oracle.tn_bond_hs import number_conserving_gaussian_fock_matrix


Edge = tuple[int, int]
TriangleLayout = Literal["global", "per_edge", "partitioned"]


@dataclass(frozen=True)
class GradeChargeModel:
    """One grouped grade-charge Hamiltonian specification."""

    physical_modes: int
    edges: tuple[Edge, ...]
    dilations: tuple[float, ...]
    couplings: tuple[float, ...]
    grade_groups: tuple[int, ...]

    @property
    def group_count(self) -> int:
        """Number of conserved grade-charge modes."""

        return 1 + max(self.grade_groups)

    @property
    def total_modes(self) -> int:
        """Physical plus ancillary fermion modes."""

        return self.physical_modes + self.group_count

    def ancilla_mode(self, edge_index: int) -> int:
        """Return the ancillary mode used by one edge vertex."""

        _validate_edge_index(self, edge_index)
        return self.physical_modes + self.grade_groups[edge_index]


@dataclass(frozen=True)
class GradeChargeHistoryWeight:
    """Direct and factorized weights for one ordered edge history."""

    edge_indices: tuple[int, ...]
    fugacities: tuple[float, ...]
    group_counts: tuple[int, ...]
    group_dilation_products: tuple[float, ...]
    physical_determinant: float
    ancilla_factor: float
    closed_form_trace: float
    direct_extended_determinant: float
    direct_fock_trace: float | None
    taylor_prefactor: float
    total_weight: float


def grade_charge_model(
    *,
    physical_modes: int,
    edges: Sequence[Edge],
    dilations: Sequence[float],
    couplings: Sequence[float],
    grade_groups: Sequence[int],
) -> GradeChargeModel:
    """Validate and return a grouped grade-charge model."""

    edge_sequence = tuple((int(left), int(right)) for left, right in edges)
    dilation_sequence = tuple(float(value) for value in dilations)
    coupling_sequence = tuple(float(value) for value in couplings)
    group_sequence = tuple(int(value) for value in grade_groups)
    if physical_modes < 2:
        raise ValueError("physical_modes must be at least two")
    if not edge_sequence:
        raise ValueError("at least one edge is required")
    if not (
        len(edge_sequence)
        == len(dilation_sequence)
        == len(coupling_sequence)
        == len(group_sequence)
    ):
        raise ValueError(
            "edges, dilations, couplings, and grade_groups must have equal length"
        )
    if len(set(edge_sequence)) != len(edge_sequence):
        raise ValueError("edges must be distinct")
    for left, right in edge_sequence:
        if not 0 <= left < physical_modes or not 0 <= right < physical_modes:
            raise ValueError("edges must identify physical modes")
        if left == right:
            raise ValueError("self edges are not allowed")
    if any(
        not math.isfinite(value) or value <= 1.0
        for value in dilation_sequence
    ):
        raise ValueError("all dilations must be finite and greater than one")
    if any(
        not math.isfinite(value) or value <= 0.0
        for value in coupling_sequence
    ):
        raise ValueError("all couplings must be finite and positive")
    if any(group < 0 for group in group_sequence):
        raise ValueError("grade groups must be nonnegative")
    if set(group_sequence) != set(range(1 + max(group_sequence))):
        raise ValueError("grade groups must be contiguous and start at zero")
    return GradeChargeModel(
        physical_modes=int(physical_modes),
        edges=edge_sequence,
        dilations=dilation_sequence,
        couplings=coupling_sequence,
        grade_groups=group_sequence,
    )


def triangle_grade_charge_model(
    layout: TriangleLayout,
    *,
    dilations: Sequence[float] = (1.2, 1.4, 1.7),
    couplings: Sequence[float] = (0.7, 1.1, 0.9),
) -> GradeChargeModel:
    """Return the triangle with global, per-edge, or two-group ancillas."""

    layouts: dict[TriangleLayout, tuple[int, int, int]] = {
        "global": (0, 0, 0),
        "per_edge": (0, 1, 2),
        "partitioned": (0, 0, 1),
    }
    if layout not in layouts:
        raise ValueError(f"unknown triangle layout: {layout}")
    return grade_charge_model(
        physical_modes=3,
        edges=((0, 1), (1, 2), (0, 2)),
        dilations=dilations,
        couplings=couplings,
        grade_groups=layouts[layout],
    )


def _validate_edge_index(model: GradeChargeModel, edge_index: int) -> int:
    candidate = int(edge_index)
    if not 0 <= candidate < len(model.edges):
        raise ValueError("edge index is outside the model")
    return candidate


def _validated_history(
    model: GradeChargeModel,
    edge_indices: Sequence[int],
) -> tuple[int, ...]:
    return tuple(_validate_edge_index(model, index) for index in edge_indices)


def _validated_fugacities(
    model: GradeChargeModel,
    fugacities: Sequence[float] | None,
) -> tuple[float, ...]:
    if fugacities is None:
        return (1.0,) * model.group_count
    values = tuple(float(value) for value in fugacities)
    if len(values) != model.group_count:
        raise ValueError("one fugacity is required for every grade group")
    if any(not math.isfinite(value) or value <= 0.0 for value in values):
        raise ValueError("fugacities must be finite and positive")
    return values


def physical_edge_propagator(
    model: GradeChargeModel,
    edge_index: int,
) -> np.ndarray:
    """Return the physical dilated-transposition field for one edge."""

    index = _validate_edge_index(model, edge_index)
    left, right = model.edges[index]
    return dilated_transposition_propagator(
        sites=model.physical_modes,
        first_mode=left,
        second_mode=right,
        dilation=model.dilations[index],
    )


def extended_edge_propagator(
    model: GradeChargeModel,
    edge_index: int,
) -> np.ndarray:
    """Return ``B_e`` with ``-r_e`` on its assigned grade mode."""

    index = _validate_edge_index(model, edge_index)
    result = np.eye(model.total_modes)
    result[: model.physical_modes, : model.physical_modes] = (
        physical_edge_propagator(model, index)
    )
    result[model.ancilla_mode(index), model.ancilla_mode(index)] = (
        -model.dilations[index]
    )
    return result


def extended_edge_real_generator(
    model: GradeChargeModel,
    edge_index: int,
) -> np.ndarray:
    """Return the explicit real logarithm of one extended edge field."""

    index = _validate_edge_index(model, edge_index)
    left, right = model.edges[index]
    return ancilla_extended_real_generator(
        sites=model.total_modes,
        first_mode=left,
        second_mode=right,
        ancilla_mode=model.ancilla_mode(index),
        dilation=model.dilations[index],
    )


def extended_edge_fock_vertex(
    model: GradeChargeModel,
    edge_index: int,
) -> np.ndarray:
    """Return the Hermitian Gaussian Fock vertex ``Gamma(Btilde_e)``."""

    return number_conserving_gaussian_fock_matrix(
        extended_edge_propagator(model, edge_index)
    )


def grade_charge_fock_hamiltonian(model: GradeChargeModel) -> np.ndarray:
    """Return ``H=-sum_e q_e Gamma(Btilde_e)`` in full Fock space."""

    dimension = 1 << model.total_modes
    result = np.zeros((dimension, dimension), dtype=float)
    for edge_index, coupling in enumerate(model.couplings):
        result -= coupling * extended_edge_fock_vertex(model, edge_index)
    return result


def vertex_mode_support(
    model: GradeChargeModel,
    edge_index: int,
    *,
    tolerance: float = 1e-12,
) -> tuple[int, ...]:
    """Return the nonidentity one-particle modes of one edge vertex."""

    if tolerance < 0.0:
        raise ValueError("tolerance must be nonnegative")
    candidate = extended_edge_propagator(model, edge_index)
    rows, columns = np.nonzero(
        np.abs(candidate - np.eye(model.total_modes)) > tolerance
    )
    return tuple(sorted(set(rows.tolist()) | set(columns.tolist())))


def fugacity_safety_bounds(model: GradeChargeModel) -> tuple[float, ...]:
    """Return the tight all-history lower bound ``1/min(r_e)`` per group.

    ``x_g >= 1`` is a simple universal choice, but subunit fugacities remain
    safe down to this group-dependent boundary.  Below it, the one-vertex
    history on a minimum-dilation edge is already a negative witness.
    """

    minima = [math.inf] * model.group_count
    for dilation, group in zip(
        model.dilations,
        model.grade_groups,
        strict=True,
    ):
        minima[group] = min(minima[group], dilation)
    return tuple(1.0 / value for value in minima)


def fugacities_are_uniformly_safe(
    model: GradeChargeModel,
    fugacities: Sequence[float],
    *,
    tolerance: float = 1e-12,
) -> bool:
    """Return whether every odd group factor has the compensating sign."""

    if tolerance < 0.0:
        raise ValueError("tolerance must be nonnegative")
    values = _validated_fugacities(model, fugacities)
    return all(
        value >= bound - tolerance
        for value, bound in zip(
            values,
            fugacity_safety_bounds(model),
            strict=True,
        )
    )


def unsafe_fugacity_witness_edge(
    model: GradeChargeModel,
    fugacities: Sequence[float],
    *,
    tolerance: float = 1e-12,
) -> int | None:
    """Return a one-vertex negative-witness edge, if the bound is violated."""

    if tolerance < 0.0:
        raise ValueError("tolerance must be nonnegative")
    values = _validated_fugacities(model, fugacities)
    for edge_index, (dilation, group) in enumerate(
        zip(model.dilations, model.grade_groups, strict=True)
    ):
        if values[group] * dilation < 1.0 - tolerance:
            return edge_index
    return None


def _fugacity_single_particle_matrix(
    model: GradeChargeModel,
    fugacities: tuple[float, ...],
) -> np.ndarray:
    result = np.eye(model.total_modes)
    for group, value in enumerate(fugacities):
        mode = model.physical_modes + group
        result[mode, mode] = value
    return result


def grade_charge_history_weight(
    model: GradeChargeModel,
    edge_indices: Sequence[int],
    *,
    fugacities: Sequence[float] | None = None,
    beta: float = 1.0,
    compute_direct_fock_trace: bool = True,
) -> GradeChargeHistoryWeight:
    """Evaluate one history by direct Fock trace and the closed factorization."""

    history = _validated_history(model, edge_indices)
    fugacity_values = _validated_fugacities(model, fugacities)
    inverse_temperature = float(beta)
    if not math.isfinite(inverse_temperature) or inverse_temperature < 0.0:
        raise ValueError("beta must be finite and nonnegative")

    physical_product = np.eye(model.physical_modes)
    extended_product = np.eye(model.total_modes)
    group_counts = [0] * model.group_count
    group_products = [1.0] * model.group_count
    coupling_product = 1.0
    fock_product: np.ndarray | None = None
    if compute_direct_fock_trace:
        fock_product = np.eye(1 << model.total_modes)

    for edge_index in history:
        physical_product = (
            physical_edge_propagator(model, edge_index) @ physical_product
        )
        extended_product = (
            extended_edge_propagator(model, edge_index) @ extended_product
        )
        if fock_product is not None:
            fock_product = (
                extended_edge_fock_vertex(model, edge_index) @ fock_product
            )
        group = model.grade_groups[edge_index]
        group_counts[group] += 1
        group_products[group] *= model.dilations[edge_index]
        coupling_product *= model.couplings[edge_index]

    physical_determinant = float(
        np.linalg.det(np.eye(model.physical_modes) + physical_product)
    )
    group_factors = tuple(
        1.0
        + fugacity
        * ((-1.0) ** count)
        * dilation_product
        for fugacity, count, dilation_product in zip(
            fugacity_values,
            group_counts,
            group_products,
            strict=True,
        )
    )
    ancilla_factor = math.prod(group_factors)
    closed_form_trace = physical_determinant * ancilla_factor

    fugacity_matrix = _fugacity_single_particle_matrix(
        model,
        fugacity_values,
    )
    direct_extended_determinant = float(
        np.linalg.det(
            np.eye(model.total_modes)
            + fugacity_matrix @ extended_product
        )
    )

    direct_fock_trace: float | None = None
    if fock_product is not None:
        fugacity_fock = number_conserving_gaussian_fock_matrix(
            fugacity_matrix
        )
        direct_fock_trace = float(np.trace(fugacity_fock @ fock_product))

    taylor_prefactor = (
        (inverse_temperature ** len(history))
        / math.factorial(len(history))
        * coupling_product
    )
    return GradeChargeHistoryWeight(
        edge_indices=history,
        fugacities=fugacity_values,
        group_counts=tuple(group_counts),
        group_dilation_products=tuple(group_products),
        physical_determinant=physical_determinant,
        ancilla_factor=ancilla_factor,
        closed_form_trace=closed_form_trace,
        direct_extended_determinant=direct_extended_determinant,
        direct_fock_trace=direct_fock_trace,
        taylor_prefactor=taylor_prefactor,
        total_weight=taylor_prefactor * closed_form_trace,
    )

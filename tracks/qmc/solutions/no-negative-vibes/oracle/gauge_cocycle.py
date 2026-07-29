"""Exact GF(2) audit for a minimal edge-gauge fermion-sign compensator.

The ansatz studied here is deliberately narrow and executable.  A link bit
``a_e`` lives on every hopping edge.  Gauss' law identifies the fermion
occupation parity at a vertex with the parity of its incident link bits,

``n_v = q_v + sum_(e incident v) a_e  (mod 2)``.

A fermion hop along ``e`` toggles both endpoint occupations and ``a_e``.  The
module asks whether the Jordan--Wigner matrix-element sign can be supplied by
an affine phase depending on only nearby link bits.  This is the first
edge-electric Gauss ansatz, not a classification of all lattice
bosonizations or gauge encodings.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


Edge = tuple[int, int]


@dataclass(frozen=True)
class LadderGaugeInstance:
    """Two-row open ladder with one link bit on every hopping edge."""

    columns: int
    sites: int
    edges: tuple[Edge, ...]
    plaquettes: tuple[tuple[int, int, int, int], ...]
    rung_edge_indices: tuple[int, ...]


@dataclass(frozen=True)
class AffineCompensation:
    """Phase ``constant + coefficient_mask dot a`` over GF(2)."""

    coefficient_mask: int
    constant: int


@dataclass(frozen=True)
class TransitionAudit:
    """Exhaustive one-hop checks on one finite gauge instance."""

    gauge_states: int
    legal_transitions: int
    sign_failures: int
    gauss_law_failures: int
    reverse_phase_failures: int


def ladder_gauge_instance(columns: int) -> LadderGaugeInstance:
    """Return the canonical open ``2 x columns`` ladder."""

    if columns < 2:
        raise ValueError("columns must be at least two")
    sites = 2 * columns
    raw_edges = [
        *((column, column + 1) for column in range(columns - 1)),
        *(
            (columns + column, columns + column + 1)
            for column in range(columns - 1)
        ),
        *((column, columns + column) for column in range(columns)),
    ]
    edges = tuple(sorted(raw_edges))
    edge_index = {edge: index for index, edge in enumerate(edges)}
    rung_edge_indices = tuple(
        edge_index[(column, columns + column)]
        for column in range(columns)
    )
    plaquettes = tuple(
        (
            edge_index[(column, column + 1)],
            edge_index[(column + 1, columns + column + 1)],
            edge_index[(columns + column, columns + column + 1)],
            edge_index[(column, columns + column)],
        )
        for column in range(columns - 1)
    )
    return LadderGaugeInstance(
        columns=columns,
        sites=sites,
        edges=edges,
        plaquettes=plaquettes,
        rung_edge_indices=rung_edge_indices,
    )


def _validate_bit_mask(mask: int, *, width: int, name: str) -> int:
    candidate = int(mask)
    if candidate < 0 or candidate >= 1 << width:
        raise ValueError(f"{name} does not fit in {width} bits")
    return candidate


def boundary_edge_mask(
    instance: LadderGaugeInstance,
    vertex_mask: int,
) -> int:
    """Return the GF(2) edge boundary of a vertex subset."""

    vertices = _validate_bit_mask(
        vertex_mask,
        width=instance.sites,
        name="vertex_mask",
    )
    boundary = 0
    for edge_index, (left, right) in enumerate(instance.edges):
        if ((vertices >> left) ^ (vertices >> right)) & 1:
            boundary |= 1 << edge_index
    return boundary


def gauss_occupation_mask(
    instance: LadderGaugeInstance,
    gauge_mask: int,
    *,
    background_charge_mask: int = 0,
) -> int:
    """Compute ``n = boundary(a) + q`` in the electric-link basis."""

    gauge = _validate_bit_mask(
        gauge_mask,
        width=len(instance.edges),
        name="gauge_mask",
    )
    occupation = _validate_bit_mask(
        background_charge_mask,
        width=instance.sites,
        name="background_charge_mask",
    )
    for edge_index, (left, right) in enumerate(instance.edges):
        if gauge & (1 << edge_index):
            occupation ^= (1 << left) | (1 << right)
    return occupation


def fermion_interval_vertex_mask(edge: Edge) -> int:
    """Sites strictly between the endpoints in the fixed Fock ordering."""

    left, right = sorted(edge)
    interval = 0
    for site in range(left + 1, right):
        interval |= 1 << site
    return interval


def fermion_hop_sign_exponent(occupation_mask: int, edge: Edge) -> int:
    """Return the Jordan--Wigner hop sign as a bit exponent."""

    interval = fermion_interval_vertex_mask(edge)
    return (int(occupation_mask) & interval).bit_count() & 1


def affine_phase_exponent(
    compensation: AffineCompensation,
    gauge_mask: int,
) -> int:
    """Evaluate an affine link phase over GF(2)."""

    return (
        compensation.constant
        ^ ((compensation.coefficient_mask & int(gauge_mask)).bit_count() & 1)
    )


def raw_gauss_compensation(
    instance: LadderGaugeInstance,
    edge_index: int,
    *,
    background_charge_mask: int = 0,
) -> AffineCompensation:
    """Substitute Gauss' law into the fermion ordering sign exactly."""

    if not 0 <= edge_index < len(instance.edges):
        raise ValueError("edge_index is outside the instance")
    background = _validate_bit_mask(
        background_charge_mask,
        width=instance.sites,
        name="background_charge_mask",
    )
    interval = fermion_interval_vertex_mask(instance.edges[edge_index])
    return AffineCompensation(
        coefficient_mask=boundary_edge_mask(instance, interval),
        constant=(interval & background).bit_count() & 1,
    )


def _site_distances(
    instance: LadderGaugeInstance,
    sources: tuple[int, int],
) -> tuple[int, ...]:
    adjacency = [[] for _ in range(instance.sites)]
    for left, right in instance.edges:
        adjacency[left].append(right)
        adjacency[right].append(left)
    distances = [-1] * instance.sites
    queue: deque[int] = deque()
    for source in sources:
        distances[source] = 0
        queue.append(source)
    while queue:
        site = queue.popleft()
        for neighbor in adjacency[site]:
            if distances[neighbor] < 0:
                distances[neighbor] = distances[site] + 1
                queue.append(neighbor)
    return tuple(distances)


def compensation_radius(
    instance: LadderGaugeInstance,
    edge_index: int,
    coefficient_mask: int,
) -> int:
    """Maximum graph distance of a phase link from the hopped link."""

    if not 0 <= edge_index < len(instance.edges):
        raise ValueError("edge_index is outside the instance")
    coefficients = _validate_bit_mask(
        coefficient_mask,
        width=len(instance.edges),
        name="coefficient_mask",
    )
    if coefficients == 0:
        return 0
    distances = _site_distances(instance, instance.edges[edge_index])
    return max(
        min(distances[left], distances[right])
        for support_index, (left, right) in enumerate(instance.edges)
        if coefficients & (1 << support_index)
    )


def minimum_legal_compensation(
    instance: LadderGaugeInstance,
    edge_index: int,
    *,
    background_charge_mask: int = 0,
) -> AffineCompensation:
    """Minimize the affine phase on the subspace where the hop is legal.

    On a legal hop exactly one endpoint is occupied.  Two affine phases may
    therefore differ by that affine constraint.  These are the only two
    possibilities when no additional link constraints are imposed.
    """

    raw = raw_gauss_compensation(
        instance,
        edge_index,
        background_charge_mask=background_charge_mask,
    )
    left, right = instance.edges[edge_index]
    endpoint_mask = (1 << left) | (1 << right)
    legal_linear_mask = boundary_edge_mask(instance, endpoint_mask)
    background_parity = (
        (int(background_charge_mask) & endpoint_mask).bit_count() & 1
    )
    shifted = AffineCompensation(
        coefficient_mask=raw.coefficient_mask ^ legal_linear_mask,
        constant=raw.constant ^ 1 ^ background_parity,
    )

    def locality_key(candidate: AffineCompensation) -> tuple[int, int, int, int]:
        return (
            compensation_radius(
                instance,
                edge_index,
                candidate.coefficient_mask,
            ),
            candidate.coefficient_mask.bit_count(),
            candidate.coefficient_mask,
            candidate.constant,
        )

    return min((raw, shifted), key=locality_key)


def compensation_support_edges(
    instance: LadderGaugeInstance,
    compensation: AffineCompensation,
) -> tuple[Edge, ...]:
    """List the link variables used by one affine phase."""

    return tuple(
        edge
        for edge_index, edge in enumerate(instance.edges)
        if compensation.coefficient_mask & (1 << edge_index)
    )


def hop_is_legal(
    instance: LadderGaugeInstance,
    occupation_mask: int,
    edge_index: int,
) -> bool:
    """Return whether exactly one endpoint of the edge is occupied."""

    left, right = instance.edges[edge_index]
    return ((occupation_mask >> left) ^ (occupation_mask >> right)) & 1 == 1


def apply_gauge_hop(
    instance: LadderGaugeInstance,
    occupation_mask: int,
    gauge_mask: int,
    edge_index: int,
) -> tuple[int, int]:
    """Toggle both matter endpoints and the traversed electric link."""

    left, right = instance.edges[edge_index]
    return (
        int(occupation_mask) ^ (1 << left) ^ (1 << right),
        int(gauge_mask) ^ (1 << edge_index),
    )


def audit_all_legal_transitions(
    instance: LadderGaugeInstance,
    *,
    background_charge_mask: int = 0,
) -> TransitionAudit:
    """Exhaust all link states and all legal one-hop transitions."""

    compensations = tuple(
        minimum_legal_compensation(
            instance,
            edge_index,
            background_charge_mask=background_charge_mask,
        )
        for edge_index in range(len(instance.edges))
    )
    legal_transitions = 0
    sign_failures = 0
    gauss_law_failures = 0
    reverse_phase_failures = 0
    gauge_states = 1 << len(instance.edges)
    for gauge_mask in range(gauge_states):
        occupation = gauss_occupation_mask(
            instance,
            gauge_mask,
            background_charge_mask=background_charge_mask,
        )
        for edge_index, edge in enumerate(instance.edges):
            if not hop_is_legal(instance, occupation, edge_index):
                continue
            legal_transitions += 1
            compensation = compensations[edge_index]
            fermion_phase = fermion_hop_sign_exponent(occupation, edge)
            gauge_phase = affine_phase_exponent(compensation, gauge_mask)
            if fermion_phase ^ gauge_phase:
                sign_failures += 1
            new_occupation, new_gauge = apply_gauge_hop(
                instance,
                occupation,
                gauge_mask,
                edge_index,
            )
            expected_occupation = gauss_occupation_mask(
                instance,
                new_gauge,
                background_charge_mask=background_charge_mask,
            )
            if new_occupation != expected_occupation:
                gauss_law_failures += 1
            reverse_fermion_phase = fermion_hop_sign_exponent(
                new_occupation,
                edge,
            )
            reverse_gauge_phase = affine_phase_exponent(
                compensation,
                new_gauge,
            )
            if (
                reverse_fermion_phase != fermion_phase
                or reverse_gauge_phase != gauge_phase
            ):
                reverse_phase_failures += 1
    return TransitionAudit(
        gauge_states=gauge_states,
        legal_transitions=legal_transitions,
        sign_failures=sign_failures,
        gauss_law_failures=gauss_law_failures,
        reverse_phase_failures=reverse_phase_failures,
    )


def closed_legal_word_counts(
    instance: LadderGaugeInstance,
    *,
    maximum_depth: int,
    background_charge_mask: int = 0,
) -> tuple[int, ...]:
    """Count closed legal hopping words at every depth, summed over states."""

    if maximum_depth < 1:
        raise ValueError("maximum_depth must be positive")
    gauge_states = 1 << len(instance.edges)
    adjacency: list[tuple[int, ...]] = []
    for gauge_mask in range(gauge_states):
        occupation = gauss_occupation_mask(
            instance,
            gauge_mask,
            background_charge_mask=background_charge_mask,
        )
        adjacency.append(
            tuple(
                gauge_mask ^ (1 << edge_index)
                for edge_index in range(len(instance.edges))
                if hop_is_legal(instance, occupation, edge_index)
            )
        )

    totals = [0] * maximum_depth
    for initial_state in range(gauge_states):
        counts = {initial_state: 1}
        for depth in range(maximum_depth):
            next_counts: dict[int, int] = {}
            for state, multiplicity in counts.items():
                for target in adjacency[state]:
                    next_counts[target] = (
                        next_counts.get(target, 0) + multiplicity
                    )
            counts = next_counts
            totals[depth] += counts.get(initial_state, 0)
    return tuple(totals)


def central_rung_locality(columns: int) -> dict[str, int]:
    """Return the exact affine-support obstruction for a central rung."""

    instance = ladder_gauge_instance(columns)
    rung_column = (columns - 1) // 2
    edge_index = instance.rung_edge_indices[rung_column]
    compensation = minimum_legal_compensation(instance, edge_index)
    rung_support = sum(
        edge in {
            instance.edges[index]
            for index in instance.rung_edge_indices
        }
        for edge in compensation_support_edges(instance, compensation)
    )
    return {
        "columns": columns,
        "rung_column": rung_column,
        "link_variables": len(instance.edges),
        "phase_support": compensation.coefficient_mask.bit_count(),
        "rung_variables_in_phase": rung_support,
        "locality_radius": compensation_radius(
            instance,
            edge_index,
            compensation.coefficient_mask,
        ),
    }

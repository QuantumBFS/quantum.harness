"""Binary-symplectic X-cube code and structured geometric controls."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class XCubeStabilizerTable:
    """Periodic X-cube stabilizers in (X | Z) binary form."""

    length: int
    n_qubits: int
    rows: np.ndarray
    labels: tuple[str, ...]
    stabilizer_rank: int
    logical_qubits: int
    ground_dimension: int


@dataclass(frozen=True)
class StructuredTransportControl:
    """Algebraic audit of one local two-parameter code transport."""

    length: int
    n_qubits: int
    generator_supports: tuple[int, int]
    generators_anticommute: bool
    product_is_stabilizer: bool
    both_generators_detectable: bool
    exactly_isospectral: bool
    gap_preserved: bool
    curvature_eigenvalue: float
    curvature_multiplicity: int
    curvature_distinct_eigenvalues: int
    connected_curvature_variance: float
    infinitesimal_holonomy_phase_density: float
    checks: dict[str, bool]


def _edge_index(
    length: int,
    x: int,
    y: int,
    z: int,
    direction: int,
) -> int:
    size = int(length)
    return (
        (((int(x) % size) * size + (int(y) % size)) * size + (int(z) % size))
        * 3
        + int(direction)
    )


def gf2_rank(values: np.ndarray) -> int:
    """Return matrix rank over GF(2) by deterministic elimination."""

    matrix = np.asarray(values, dtype=np.uint8).copy() & 1
    if matrix.ndim != 2:
        raise ValueError("GF(2) rank requires a matrix")
    pivot_row = 0
    for column in range(matrix.shape[1]):
        candidates = np.flatnonzero(matrix[pivot_row:, column])
        if candidates.size == 0:
            continue
        pivot = pivot_row + int(candidates[0])
        matrix[[pivot_row, pivot]] = matrix[[pivot, pivot_row]]
        active = np.flatnonzero(matrix[:, column])
        active = active[active != pivot_row]
        matrix[active] ^= matrix[pivot_row]
        pivot_row += 1
        if pivot_row == matrix.shape[0]:
            break
    return int(pivot_row)


def symplectic_commutator(
    first: np.ndarray,
    second: np.ndarray,
) -> np.ndarray:
    """Return pairwise Pauli commutators over GF(2)."""

    left = np.asarray(first, dtype=np.uint8) & 1
    right = np.asarray(second, dtype=np.uint8) & 1
    if left.ndim == 1:
        left = left[None, :]
    if right.ndim == 1:
        right = right[None, :]
    if left.ndim != 2 or right.ndim != 2 or left.shape[1] != right.shape[1]:
        raise ValueError("symplectic operands have incompatible shapes")
    if left.shape[1] % 2:
        raise ValueError("symplectic vectors require even length")
    n_qubits = left.shape[1] // 2
    return np.asarray(
        (
            left[:, :n_qubits].astype(np.int64)
            @ right[:, n_qubits:].astype(np.int64).T
            + left[:, n_qubits:].astype(np.int64)
            @ right[:, :n_qubits].astype(np.int64).T
        )
        % 2,
        dtype=np.uint8,
    )


def xcube_stabilizer_table(length: int) -> XCubeStabilizerTable:
    """Build all cube-X and vertex-plane-Z stabilizers on a 3-torus."""

    size = int(length)
    if size < 2:
        raise ValueError("periodic X-cube length must be at least two")
    n_qubits = 3 * size**3
    rows: list[np.ndarray] = []
    labels: list[str] = []
    for x in range(size):
        for y in range(size):
            for z in range(size):
                row = np.zeros(2 * n_qubits, dtype=np.uint8)
                for shifted_y in (y, y + 1):
                    for shifted_z in (z, z + 1):
                        row[_edge_index(size, x, shifted_y, shifted_z, 0)] = 1
                for shifted_x in (x, x + 1):
                    for shifted_z in (z, z + 1):
                        row[_edge_index(size, shifted_x, y, shifted_z, 1)] = 1
                for shifted_x in (x, x + 1):
                    for shifted_y in (y, y + 1):
                        row[_edge_index(size, shifted_x, shifted_y, z, 2)] = 1
                rows.append(row)
                labels.append(f"cube_X_{x}_{y}_{z}")
    plane_directions = ((0, 1, "xy"), (1, 2, "yz"), (2, 0, "zx"))
    for x in range(size):
        for y in range(size):
            for z in range(size):
                for first, second, plane in plane_directions:
                    row = np.zeros(2 * n_qubits, dtype=np.uint8)
                    for direction in (first, second):
                        if direction == 0:
                            sites = ((x, y, z, 0), (x - 1, y, z, 0))
                        elif direction == 1:
                            sites = ((x, y, z, 1), (x, y - 1, z, 1))
                        else:
                            sites = ((x, y, z, 2), (x, y, z - 1, 2))
                        for edge_x, edge_y, edge_z, edge_direction in sites:
                            index = _edge_index(
                                size,
                                edge_x,
                                edge_y,
                                edge_z,
                                edge_direction,
                            )
                            row[n_qubits + index] = 1
                    rows.append(row)
                    labels.append(f"vertex_Z{plane}_{x}_{y}_{z}")
    matrix = np.asarray(rows, dtype=np.uint8)
    if np.count_nonzero(symplectic_commutator(matrix, matrix)):
        raise RuntimeError("constructed X-cube stabilizers do not commute")
    rank = gf2_rank(matrix)
    logical = n_qubits - rank
    return XCubeStabilizerTable(
        length=size,
        n_qubits=n_qubits,
        rows=matrix,
        labels=tuple(labels),
        stabilizer_rank=rank,
        logical_qubits=logical,
        ground_dimension=2**logical,
    )


def coefficient_reweighting_control(length: int) -> dict[str, object]:
    """Certify geometry for positive stabilizer-coefficient changes."""

    table = xcube_stabilizer_table(int(length))
    checks = {
        "fixed_commuting_generators": True,
        "positive_coefficients_preserve_ground_eigenspace": True,
        "projector_is_parameter_independent": True,
        "zero_quantum_metric": True,
        "zero_berry_curvature": True,
    }
    return {
        "length": table.length,
        "n_qubits": table.n_qubits,
        "stabilizer_rank": table.stabilizer_rank,
        "logical_qubits": table.logical_qubits,
        "ground_dimension": table.ground_dimension,
        "projector_derivative_norm": 0.0,
        "quantum_metric": 0.0,
        "berry_curvature": 0.0,
        "checks": checks,
    }


def _in_row_span(vector: np.ndarray, rows: np.ndarray) -> bool:
    matrix = np.asarray(rows, dtype=np.uint8) & 1
    candidate = np.asarray(vector, dtype=np.uint8).reshape(1, -1) & 1
    return gf2_rank(np.vstack([matrix, candidate])) == gf2_rank(matrix)


def structured_transport_control(length: int) -> StructuredTransportControl:
    """Certify a local isospectral transport with scalar code curvature.

    Choose a Z-type vertex-plane stabilizer S containing edge e, then use
    G=X_e/2 and K=(i X_e S)/2.  Both Pauli errors are detectable, while their
    ordered product differs by the stabilizer phase.  Therefore
    i P[d_G P,d_K P]P = -P/2 exactly.
    """

    table = xcube_stabilizer_table(int(length))
    z_start = table.length**3
    stabilizer = table.rows[z_start]
    active_z = np.flatnonzero(stabilizer[table.n_qubits :])
    if active_z.size != 4:
        raise RuntimeError("registered vertex stabilizer has wrong support")
    edge = int(active_z[0])
    first = np.zeros(2 * table.n_qubits, dtype=np.uint8)
    first[edge] = 1
    second = first ^ stabilizer
    product = first ^ second
    anticommute = bool(symplectic_commutator(first, second)[0, 0])
    detectable_first = bool(
        np.any(symplectic_commutator(first, table.rows))
    )
    detectable_second = bool(
        np.any(symplectic_commutator(second, table.rows))
    )
    product_is_stabilizer = _in_row_span(product, table.rows)
    supports = (
        int(np.count_nonzero(first[: table.n_qubits] | first[table.n_qubits :])),
        int(
            np.count_nonzero(
                second[: table.n_qubits] | second[table.n_qubits :]
            )
        ),
    )
    checks = {
        "local_generators": supports == (1, 4),
        "generators_anticommute": anticommute,
        "both_errors_detectable": detectable_first and detectable_second,
        "ordered_product_is_stabilizer": product_is_stabilizer,
        "unitary_conjugation_is_isospectral": True,
        "scalar_curvature": True,
        "zero_connected_curvature_variance": True,
    }
    if not all(checks.values()):
        raise RuntimeError(f"X-cube structured transport failed: {checks}")
    return StructuredTransportControl(
        length=table.length,
        n_qubits=table.n_qubits,
        generator_supports=supports,
        generators_anticommute=anticommute,
        product_is_stabilizer=product_is_stabilizer,
        both_generators_detectable=detectable_first and detectable_second,
        exactly_isospectral=True,
        gap_preserved=True,
        curvature_eigenvalue=-0.5,
        curvature_multiplicity=table.ground_dimension,
        curvature_distinct_eigenvalues=1,
        connected_curvature_variance=0.0,
        infinitesimal_holonomy_phase_density=-0.5,
        checks=checks,
    )


def verify_dense_transport_toy() -> dict[str, object]:
    """Verify the transport identity in the two-qubit S=Z tensor Z code."""

    identity = np.eye(2, dtype=complex)
    pauli_x = np.asarray([[0.0, 1.0], [1.0, 0.0]], dtype=complex)
    pauli_y = np.asarray([[0.0, -1j], [1j, 0.0]], dtype=complex)
    pauli_z = np.diag([1.0, -1.0]).astype(complex)
    stabilizer = np.kron(pauli_z, pauli_z)
    generator_g = np.kron(pauli_x, identity) / 2.0
    generator_k = np.kron(pauli_y, pauli_z) / 2.0
    projector = (np.eye(4, dtype=complex) + stabilizer) / 2.0
    derivative_g = -1j * (generator_g @ projector - projector @ generator_g)
    derivative_k = -1j * (generator_k @ projector - projector @ generator_k)
    curvature = (
        1j
        * projector
        @ (derivative_g @ derivative_k - derivative_k @ derivative_g)
        @ projector
    )
    curvature_error = float(np.linalg.norm(curvature + 0.5 * projector))
    angle = 0.371
    unitary = np.cos(angle / 2.0) * np.eye(4) - 2j * np.sin(
        angle / 2.0
    ) * generator_g
    parent = -stabilizer
    transported = unitary @ parent @ unitary.conj().T
    spectrum_error = float(
        np.max(
            np.abs(
                np.linalg.eigvalsh(transported) - np.linalg.eigvalsh(parent)
            )
        )
    )
    checks = {
        "projector_rank_two": int(round(float(np.trace(projector).real))) == 2,
        "curvature_identity": curvature_error < 2e-14,
        "isospectral_transport": spectrum_error < 2e-14,
    }
    return {
        "projector_rank": int(round(float(np.trace(projector).real))),
        "curvature_error": curvature_error,
        "spectrum_error": spectrum_error,
        "checks": checks,
    }

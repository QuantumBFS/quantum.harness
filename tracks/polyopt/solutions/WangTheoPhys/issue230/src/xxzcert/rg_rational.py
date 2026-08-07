"""Exact rational dual witnesses for the compressed RG-LTI relaxation."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import ceil

import numpy as np
from numpy.typing import NDArray

from .rational import RationalMatrix, exact_positive_definite_ldl, xxz_matrix_fraction
from .rg_dual_barrier import (
    build_rg_dual_barrier_model,
    qualify_rg_candidate,
    rg_dual_slacks,
    solve_rg_dual_barrier,
)
from .rg_relaxation import RGRelaxationCandidate, solve_rg_lti
from .rg_u1_conic import solve_rg_u1_conic
from .rg_symmetry import ChargeBasis, mps_rg_charge_bases

ObjectMatrix = NDArray[np.object_]


def _zeros(rows: int, cols: int) -> ObjectMatrix:
    result = np.empty((rows, cols), dtype=object)
    result.fill(Fraction(0))
    return result


def _identity(size: int) -> ObjectMatrix:
    result = _zeros(size, size)
    for index in range(size):
        result[index, index] = Fraction(1)
    return result


def _transpose(matrix: ObjectMatrix) -> ObjectMatrix:
    return matrix.T.copy()


def _as_rational_matrix(matrix: ObjectMatrix) -> RationalMatrix:
    return [[Fraction(value) for value in row] for row in matrix.tolist()]


def _floating_minimum(matrix: ObjectMatrix) -> float:
    floating = np.array(matrix.tolist(), dtype=float)
    symmetric = (floating + floating.T) / 2
    return float(np.linalg.eigvalsh(symmetric)[0])


def _kron(left: ObjectMatrix, right: ObjectMatrix) -> ObjectMatrix:
    return np.kron(left, right)


def _sandwich(map_matrix: ObjectMatrix, dual: ObjectMatrix) -> ObjectMatrix:
    return _transpose(map_matrix) @ dual @ map_matrix


def _fraction_tensor(
    numerators: tuple[int, ...], denominator: int, bond: int
) -> ObjectMatrix:
    values = [Fraction(value, denominator) for value in numerators]
    return np.array(values, dtype=object).reshape(bond, 2, bond)


def _exact_flow_maps(tensor: ObjectMatrix) -> tuple[ObjectMatrix, ObjectMatrix, ObjectMatrix]:
    bond, physical, _ = tensor.shape
    compressed = bond * bond
    w2 = _zeros(compressed, physical * physical)
    for first in range(physical):
        for second in range(physical):
            product = tensor[:, first, :] @ tensor[:, second, :]
            w2[:, first * physical + second] = product.reshape(-1)
    left = _zeros(compressed, physical * compressed)
    right = _zeros(compressed, compressed * physical)
    for output_left in range(bond):
        for output_right in range(bond):
            output = output_left * bond + output_right
            for spin in range(physical):
                for middle_left in range(bond):
                    middle = middle_left * bond + output_right
                    left[output, spin * compressed + middle] = tensor[
                        output_left, spin, middle_left
                    ]
                for middle_right in range(bond):
                    middle = output_left * bond + middle_right
                    right[output, middle * physical + spin] = tensor[
                        middle_right, spin, output_right
                    ]
    return w2, left, right


def _objective_operator(delta: Fraction) -> ObjectMatrix:
    local = np.array(xxz_matrix_fraction(delta, 2), dtype=object)
    return _kron(local, _identity(2))


@dataclass(frozen=True)
class RGDualWitness:
    depth: int
    bond_dimension: int
    tensor_denominator: int
    tensor_numerators: tuple[int, ...]
    dual_denominator: int
    y_numerator: int
    matrix_numerators: tuple[tuple[int, ...], ...]

    @property
    def energy_density_lower(self) -> Fraction:
        return -Fraction(self.y_numerator, self.dual_denominator)

    def tensor(self) -> ObjectMatrix:
        return _fraction_tensor(
            self.tensor_numerators,
            self.tensor_denominator,
            self.bond_dimension,
        )

    def matrices(self) -> list[ObjectMatrix]:
        dimension = 2 * self.bond_dimension * self.bond_dimension
        expected = 3 + 2 * (self.depth - 4)
        if len(self.matrix_numerators) != expected:
            raise ValueError("RG dual matrix count mismatch")
        matrices: list[ObjectMatrix] = []
        for index, payload in enumerate(self.matrix_numerators):
            size = 4 if index == 0 else dimension
            if len(payload) != size * size:
                raise ValueError("RG dual matrix dimension mismatch")
            matrices.append(
                np.array(
                    [
                        Fraction(value, self.dual_denominator)
                        for value in payload
                    ],
                    dtype=object,
                ).reshape(size, size)
            )
        return matrices


def reconstruct_rg_dual_slacks(
    delta: Fraction, witness: RGDualWitness
) -> tuple[ObjectMatrix, ...]:
    """Reconstruct every dual PSD slack using exact arithmetic."""
    tensor = witness.tensor()
    w2, left, right = _exact_flow_maps(tensor)
    physical = 2
    first_map = _kron(w2, _identity(physical))
    second_map = _kron(_identity(physical), w2)
    left_map = _kron(left, _identity(physical))
    right_map = _kron(_identity(physical), right)
    matrices = witness.matrices()
    lti_dual, first_dual, second_dual, *transition_flat = matrices
    transitions = [
        (transition_flat[index], transition_flat[index + 1])
        for index in range(0, len(transition_flat), 2)
    ]
    y = Fraction(witness.y_numerator, witness.dual_denominator)
    rho_slack = (
        _objective_operator(delta)
        + y * _identity(8)
        + _kron(_identity(physical), lti_dual)
        - _kron(lti_dual, _identity(physical))
        + _sandwich(first_map, first_dual)
        + _sandwich(second_map, second_dual)
    )
    omega_slacks: list[ObjectMatrix] = []
    count = witness.depth - 3
    for index in range(count):
        if index == 0:
            incoming_left, incoming_right = first_dual, second_dual
        else:
            incoming_left, incoming_right = transitions[index - 1]
        slack = -_kron(_identity(physical), incoming_left) - _kron(
            incoming_right, _identity(physical)
        )
        if index < count - 1:
            outgoing_left, outgoing_right = transitions[index]
            slack = (
                slack
                + _sandwich(left_map, outgoing_left)
                + _sandwich(right_map, outgoing_right)
            )
        omega_slacks.append(slack)
    return (rho_slack, *omega_slacks)


def _witness_slack_charge_bases(
    witness: RGDualWitness,
) -> tuple[ChargeBasis, ...] | None:
    try:
        bases = mps_rg_charge_bases(
            np.asarray(witness.tensor().tolist(), dtype=np.complex128),
            tolerance=1e-14,
        )
    except ValueError:
        return None
    physical = (1, -1)
    rho = ChargeBasis.from_labels(
        tuple(
            first + second + third
            for first in physical
            for second in physical
            for third in physical
        )
    )
    return (rho,) + (bases.omega,) * (witness.depth - 3)


def _exact_positive_in_charge_blocks(
    slack: ObjectMatrix,
    basis: ChargeBasis,
) -> bool:
    for row, row_charge in enumerate(basis.labels):
        for column, column_charge in enumerate(basis.labels):
            if row_charge != column_charge and slack[row, column] != 0:
                return False
    for indices in basis.indices:
        block = slack[np.ix_(indices, indices)]
        if not exact_positive_definite_ldl(
            _as_rational_matrix(block)
        )[0]:
            return False
    return True


def verify_rg_dual_witness(delta: Fraction, witness: RGDualWitness) -> bool:
    """Check map compatibility and strict dual feasibility exactly."""
    tensor = witness.tensor()
    w2, left, right = _exact_flow_maps(tensor)
    compatibility_left = left @ _kron(_identity(2), w2)
    compatibility_right = right @ _kron(w2, _identity(2))
    if not np.array_equal(compatibility_left, compatibility_right):
        return False
    slacks = reconstruct_rg_dual_slacks(delta, witness)
    bases = _witness_slack_charge_bases(witness)
    if bases is None:
        return all(
            exact_positive_definite_ldl(_as_rational_matrix(slack))[0]
            for slack in slacks
        )
    return all(
        _exact_positive_in_charge_blocks(slack, basis)
        for slack, basis in zip(slacks, bases, strict=True)
    )


def _candidate_witness(
    tensor_numerators: tuple[int, ...],
    tensor_scale: int,
    bond_dimension: int,
    depth: int,
    dual_scale: int,
    candidate: RGRelaxationCandidate,
) -> RGDualWitness:
    matrices: list[ObjectMatrix] = []
    for raw in candidate.equality_duals[1:]:
        array = np.asarray(raw)
        if np.max(np.abs(array.imag)) > 1e-7:
            raise ValueError("complex RG dual is not supported")
        symmetric = (array.real + array.real.T) / 2
        matrices.append(
            np.array(
                [
                    Fraction(int(round(float(value) * dual_scale)), dual_scale)
                    for value in symmetric.reshape(-1)
                ],
                dtype=object,
            ).reshape(symmetric.shape)
        )
    y = Fraction(
        int(round(float(candidate.equality_duals[0]) * dual_scale)),
        dual_scale,
    )
    denominator = 2 * dual_scale

    def make_current() -> RGDualWitness:
        return RGDualWitness(
            depth=depth,
            bond_dimension=bond_dimension,
            tensor_denominator=tensor_scale,
            tensor_numerators=tensor_numerators,
            dual_denominator=denominator,
            y_numerator=int(y * denominator),
            matrix_numerators=tuple(
                tuple(int(Fraction(value) * denominator) for value in matrix.reshape(-1))
                for matrix in matrices
            ),
        )

    initial_witness = make_current()
    charge_bases = _witness_slack_charge_bases(initial_witness)

    def positive(slack: ObjectMatrix, slack_index: int) -> bool:
        if charge_bases is None:
            return exact_positive_definite_ldl(
                _as_rational_matrix(slack)
            )[0]
        return _exact_positive_in_charge_blocks(
            slack, charge_bases[slack_index]
        )

    # First repair every level with floating reconstructions of the *rounded*
    # tensor and dual.  A generous positive margin makes the following exact
    # reconstruction normally a one-shot verification instead of rebuilding
    # all rational slacks once per scale.
    floating_tensor = np.asarray(
        make_current().tensor().tolist(), dtype=np.complex128
    )
    floating_model = build_rg_dual_barrier_model(
        1.0, floating_tensor, depth, use_symmetry=False
    )

    def floating_slacks() -> tuple[NDArray[np.float64], ...]:
        floating_matrices = tuple(
            np.asarray(matrix.tolist(), dtype=float)
            for matrix in matrices
        )
        parameters = floating_model.pack(
            float(y), floating_matrices
        )
        return rg_dual_slacks(floating_model, parameters)

    repair_margin = 1e-6
    for omega_index in range(depth - 4, -1, -1):
        minimum = float(
            np.linalg.eigvalsh(floating_slacks()[1 + omega_index])[0]
        )
        if minimum < repair_margin:
            steps = max(
                1,
                ceil(
                    (repair_margin - minimum)
                    * denominator
                    / 2
                ),
            )
            incoming_offset = (
                1 if omega_index == 0 else 3 + 2 * (omega_index - 1)
            )
            for matrix_index in (
                incoming_offset,
                incoming_offset + 1,
            ):
                for diagonal in range(
                    matrices[matrix_index].shape[0]
                ):
                    matrices[matrix_index][diagonal, diagonal] -= Fraction(
                        steps, denominator
                    )
    rho_minimum = float(np.linalg.eigvalsh(floating_slacks()[0])[0])
    if rho_minimum < repair_margin:
        y += Fraction(
            max(
                1,
                ceil(
                    (repair_margin - rho_minimum) * denominator
                ),
            ),
            denominator,
        )
    pre_repaired = make_current()
    exact_slacks = reconstruct_rg_dual_slacks(
        Fraction(1), pre_repaired
    )
    if all(
        positive(slack, index)
        for index, slack in enumerate(exact_slacks)
    ):
        return pre_repaired

    # Repair from the deepest compressed state backwards. Subtracting k/q
    # from both incoming multipliers adds 2k/q times the identity to that
    # omega slack. Its effect on the previous scale is repaired next.
    for omega_index in range(depth - 4, -1, -1):
        while True:
            slacks = reconstruct_rg_dual_slacks(Fraction(1), make_current())
            slack = slacks[1 + omega_index]
            if positive(slack, 1 + omega_index):
                break
            minimum = _floating_minimum(slack)
            steps = max(1, ceil((-minimum + 1e-10) * denominator / 2))
            incoming_offset = 1 if omega_index == 0 else 3 + 2 * (omega_index - 1)
            for matrix_index in (incoming_offset, incoming_offset + 1):
                for diagonal in range(matrices[matrix_index].shape[0]):
                    matrices[matrix_index][diagonal, diagonal] -= Fraction(
                        steps, denominator
                    )

    # The omega repairs propagate into rho3. Increasing y only shifts rho3
    # and lowers the certified objective, so it is the final safe repair.
    while True:
        witness = make_current()
        rho_slack = reconstruct_rg_dual_slacks(Fraction(1), witness)[0]
        if positive(rho_slack, 0):
            break
        minimum = _floating_minimum(rho_slack)
        steps = max(1, ceil((-minimum + 1e-10) * denominator))
        y += Fraction(steps, denominator)
    return make_current()


def make_rg_dual_witness(
    delta: Fraction,
    tensor: NDArray[np.complex128],
    depth: int,
    *,
    tensor_scale: int = 10**4,
    dual_scale: int = 10**7,
) -> tuple[RGDualWitness, RGRelaxationCandidate]:
    """Freeze an MPS map, solve its RG SDP, and exactly repair the dual."""
    if delta != 1:
        raise NotImplementedError("initial exact RG repair supports XXX only")
    if (
        tensor.ndim != 3
        or tensor.shape[1] != 2
        or tensor.shape[0] != tensor.shape[2]
    ):
        raise ValueError("RG tensor must have shape (D,2,D)")
    bond = tensor.shape[0]
    if np.max(np.abs(np.asarray(tensor).imag)) > 1e-10:
        raise ValueError("only real RG tensors are supported")
    numerators = tuple(
        int(round(float(value) * tensor_scale))
        for value in np.asarray(tensor).real.reshape(-1)
    )
    frozen = (
        np.array(numerators, dtype=float).reshape(bond, 2, bond)
        / tensor_scale
    ).astype(np.complex128)
    candidate = solve_rg_lti(
        float(delta),
        frozen,
        depth,
        solver="CVXOPT",
        normalize_maps=False,
    )
    witness = _candidate_witness(
        numerators,
        tensor_scale,
        bond,
        depth,
        dual_scale,
        candidate,
    )
    if not verify_rg_dual_witness(delta, witness):
        raise ArithmeticError("failed to construct exact RG dual witness")
    return witness, candidate


def make_rg_dual_barrier_witness(
    delta: Fraction,
    tensor: NDArray[np.complex128],
    depth: int,
    *,
    tensor_scale: int = 10**4,
    dual_scale: int = 10**7,
    barrier_parameters: tuple[float, ...] = (
        1e-1,
        3e-2,
        1e-2,
        3e-3,
        1e-3,
        3e-4,
        1e-4,
        3e-5,
        1e-5,
    ),
    max_iterations: int = 80,
    use_symmetry: bool = False,
    cg_max_iterations: int = 60,
    cg_relative_tolerance: float = 1e-3,
    initial_equality_duals: (
        tuple[NDArray[np.complex128] | float, ...] | None
    ) = None,
) -> tuple[RGDualWitness, RGRelaxationCandidate]:
    """Freeze a tensor, solve the matrix-free dual, and repair it exactly."""
    if delta != 1:
        raise NotImplementedError("initial exact RG repair supports XXX only")
    array = np.asarray(tensor)
    if (
        array.ndim != 3
        or array.shape[1] != 2
        or array.shape[0] != array.shape[2]
    ):
        raise ValueError("RG tensor must have shape (D,2,D)")
    if np.max(np.abs(array.imag)) > 1e-10:
        raise ValueError("only real RG tensors are supported")
    bond = array.shape[0]
    numerators = tuple(
        int(round(float(value) * tensor_scale))
        for value in array.real.reshape(-1)
    )
    frozen = (
        np.array(numerators, dtype=float).reshape(bond, 2, bond)
        / tensor_scale
    ).astype(np.complex128)
    candidate = solve_rg_dual_barrier(
        float(delta),
        frozen,
        depth,
        barrier_parameters=barrier_parameters,
        max_iterations=max_iterations,
        use_symmetry=use_symmetry,
        cg_max_iterations=cg_max_iterations,
        cg_relative_tolerance=cg_relative_tolerance,
        initial_equality_duals=initial_equality_duals,
    )
    qualify_rg_candidate(candidate)
    witness = _candidate_witness(
        numerators,
        tensor_scale,
        bond,
        depth,
        dual_scale,
        candidate,
    )
    if not verify_rg_dual_witness(delta, witness):
        raise ArithmeticError(
            "failed to construct exact matrix-free RG dual witness"
        )
    return witness, candidate


def make_rg_u1_conic_witness(
    delta: Fraction,
    tensor: NDArray[np.complex128],
    depth: int,
    *,
    tensor_scale: int = 10**4,
    dual_scale: int = 10**7,
    solver: str = "CLARABEL",
    slack_margin: float = 0.0,
) -> tuple[RGDualWitness, RGRelaxationCandidate]:
    """Solve the U(1)-blocked conic dual and repair it exactly."""
    if delta != 1:
        raise NotImplementedError("initial exact RG repair supports XXX only")
    array = np.asarray(tensor)
    if (
        array.ndim != 3
        or array.shape[1] != 2
        or array.shape[0] != array.shape[2]
    ):
        raise ValueError("RG tensor must have shape (D,2,D)")
    if np.max(np.abs(array.imag)) > 1e-10:
        raise ValueError("only real RG tensors are supported")
    bond = array.shape[0]
    numerators = tuple(
        int(round(float(value) * tensor_scale))
        for value in array.real.reshape(-1)
    )
    frozen = (
        np.array(numerators, dtype=float).reshape(bond, 2, bond)
        / tensor_scale
    ).astype(np.complex128)
    candidate = solve_rg_u1_conic(
        float(delta),
        frozen,
        depth,
        solver=solver,
        slack_margin=slack_margin,
    )
    witness = _candidate_witness(
        numerators,
        tensor_scale,
        bond,
        depth,
        dual_scale,
        candidate,
    )
    if not verify_rg_dual_witness(delta, witness):
        raise ArithmeticError(
            "failed to construct exact U(1)-blocked RG dual witness"
        )
    return witness, candidate

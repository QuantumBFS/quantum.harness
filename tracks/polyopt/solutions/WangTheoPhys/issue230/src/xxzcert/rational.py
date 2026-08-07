"""Exact rational witnesses for Anderson lower and block-product upper bounds."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR
from fractions import Fraction
from math import lcm

import numpy as np
from flint import arb, arb_mat, ctx, fmpq

from .model import finite_xxz

RationalMatrix = list[list[Fraction]]


def xxz_matrix_fraction(delta: Fraction, sites: int) -> RationalMatrix:
    """Construct an open XXZ Hamiltonian exactly in the computational basis."""
    if sites < 2:
        raise ValueError("sites must be at least 2")
    dim = 1 << sites
    matrix = [[Fraction(0) for _ in range(dim)] for _ in range(dim)]
    for basis in range(dim):
        for left in range(sites - 1):
            right = left + 1
            bit_l = (basis >> (sites - 1 - left)) & 1
            bit_r = (basis >> (sites - 1 - right)) & 1
            matrix[basis][basis] += (
                delta / 4 if bit_l == bit_r else -delta / 4
            )
            if bit_l != bit_r:
                flipped = basis ^ (1 << (sites - 1 - left))
                flipped ^= 1 << (sites - 1 - right)
                matrix[basis][flipped] += Fraction(1, 2)
    return matrix


def xxz_sector_matrix_fraction(
    delta: Fraction, sites: int, ones: int
) -> RationalMatrix:
    """Exact open XXZ Hamiltonian in a fixed-magnetization sector."""
    if ones < 0 or ones > sites:
        raise ValueError("ones must lie between zero and sites")
    basis = [index for index in range(1 << sites) if index.bit_count() == ones]
    positions = {index: position for position, index in enumerate(basis)}
    matrix = [
        [Fraction(0) for _ in range(len(basis))] for _ in range(len(basis))
    ]
    for row, state in enumerate(basis):
        for left in range(sites - 1):
            right = left + 1
            bit_l = (state >> (sites - 1 - left)) & 1
            bit_r = (state >> (sites - 1 - right)) & 1
            matrix[row][row] += delta / 4 if bit_l == bit_r else -delta / 4
            if bit_l != bit_r:
                flipped = state ^ (1 << (sites - 1 - left))
                flipped ^= 1 << (sites - 1 - right)
                matrix[row][positions[flipped]] += Fraction(1, 2)
    return matrix


def exact_positive_definite_ldl(matrix: RationalMatrix) -> tuple[bool, list[Fraction]]:
    """Exact no-pivot LDL^T test for a symmetric rational matrix."""
    n = len(matrix)
    if any(len(row) != n for row in matrix):
        raise ValueError("matrix must be square")
    lower = [[Fraction(0) for _ in range(n)] for _ in range(n)]
    diagonal = [Fraction(0) for _ in range(n)]
    for i in range(n):
        lower[i][i] = Fraction(1)
        pivot = matrix[i][i] - sum(
            lower[i][k] * lower[i][k] * diagonal[k] for k in range(i)
        )
        diagonal[i] = pivot
        if pivot <= 0:
            return False, diagonal
        for j in range(i + 1, n):
            numerator = matrix[j][i] - sum(
                lower[j][k] * lower[i][k] * diagonal[k] for k in range(i)
            )
            lower[j][i] = numerator / pivot
    return True, diagonal


def rigorous_positive_definite_arb(
    matrix: RationalMatrix, precisions: tuple[int, ...] = (128, 256, 512)
) -> bool:
    """Certify positivity using rigorous Arb eigenvalue enclosures.

    The matrix entries are injected as exact ``fmpq`` values. Returning true
    requires every computed real eigenvalue interval to lie strictly above
    zero; failures to isolate eigenvalues are retried at higher precision.
    """
    size = len(matrix)
    if any(len(row) != size for row in matrix):
        raise ValueError("matrix must be square")
    for precision in precisions:
        try:
            with ctx.workprec(precision):
                enclosed = arb_mat(
                    [
                        [
                            arb(fmpq(value.numerator, value.denominator))
                            for value in row
                        ]
                        for row in matrix
                    ]
                )
                eigenvalues = enclosed.eig(multiple=True)
                return all(value.real > 0 and value.imag.contains(0) for value in eigenvalues)
        except ValueError:
            continue
    return False


def rigorous_positive_definite_arb_ldl(
    matrix: RationalMatrix, precisions: tuple[int, ...] = (128, 256, 512)
) -> bool:
    """Rigorous interval LDL test with exact-rational Arb inputs."""
    size = len(matrix)
    if any(len(row) != size for row in matrix):
        raise ValueError("matrix must be square")
    for precision in precisions:
        with ctx.workprec(precision):
            lower = [[arb(0) for _ in range(size)] for _ in range(size)]
            diagonal = [arb(0) for _ in range(size)]
            failed = False
            for i in range(size):
                lower[i][i] = arb(1)
                exact_entry = matrix[i][i]
                pivot = arb(fmpq(exact_entry.numerator, exact_entry.denominator))
                for k in range(i):
                    pivot -= lower[i][k] * lower[i][k] * diagonal[k]
                if not pivot > 0:
                    failed = True
                    break
                diagonal[i] = pivot
                for j in range(i + 1, size):
                    exact_entry = matrix[j][i]
                    numerator = arb(
                        fmpq(exact_entry.numerator, exact_entry.denominator)
                    )
                    for k in range(i):
                        numerator -= lower[j][k] * lower[i][k] * diagonal[k]
                    lower[j][i] = numerator / pivot
            if not failed:
                return True
    return False


def rigorous_positive_definite_congruence(
    matrix: RationalMatrix,
    *,
    preconditioner_scale: int = 10**10,
    precisions: tuple[int, ...] = (128, 256, 512),
) -> bool:
    """Certify SPD by an exact-rational congruence and Arb Gershgorin.

    A floating Cholesky factor is used only to propose a rational
    preconditioner ``B``. The proof itself encloses ``B.T * A * B`` with Arb
    and requires strict row diagonal dominance with positive diagonal.
    """
    size = len(matrix)
    if any(len(row) != size for row in matrix):
        raise ValueError("matrix must be square")
    floating = np.array(matrix, dtype=float)
    floating = (floating + floating.T) / 2
    try:
        cholesky = np.linalg.cholesky(floating)
        inverse_transpose = np.linalg.inv(cholesky.T)
    except np.linalg.LinAlgError:
        return False
    numerators = np.rint(inverse_transpose * preconditioner_scale).astype(
        object
    )
    for precision in precisions:
        with ctx.workprec(precision):
            exact_a = arb_mat(
                [
                    [
                        arb(fmpq(value.numerator, value.denominator))
                        for value in row
                    ]
                    for row in matrix
                ]
            )
            exact_b = arb_mat(
                [
                    [
                        arb(fmpq(int(numerators[row, column]), preconditioner_scale))
                        for column in range(size)
                    ]
                    for row in range(size)
                ]
            )
            transformed = exact_b.transpose() * exact_a * exact_b
            proved = True
            for row in range(size):
                radius = arb(0)
                for column in range(size):
                    if column != row:
                        radius += abs(transformed[row, column])
                if not transformed[row, row] - radius > 0:
                    proved = False
                    break
            if proved:
                return True
    return False


@dataclass(frozen=True)
class AndersonWitness:
    sites: int
    eigenvalue_lower: Fraction

    @property
    def energy_density_lower(self) -> Fraction:
        return self.eigenvalue_lower / (self.sites - 1)


@dataclass(frozen=True)
class LTIDualWitness:
    sites: int
    denominator: int
    y_numerator: int
    matrix_numerators: tuple[int, ...]

    @property
    def y(self) -> Fraction:
        return Fraction(self.y_numerator, self.denominator)

    @property
    def energy_density_lower(self) -> Fraction:
        return -self.y

    def matrix(self) -> RationalMatrix:
        dim = 1 << (self.sites - 1)
        if len(self.matrix_numerators) != dim * dim:
            raise ValueError("dual matrix payload has incorrect length")
        return [
            [
                Fraction(self.matrix_numerators[row * dim + col], self.denominator)
                for col in range(dim)
            ]
            for row in range(dim)
        ]


def make_anderson_witness(
    delta: Fraction, sites: int, decimal_places: int = 10
) -> AndersonWitness:
    """Find and exactly verify a rational number below the cluster spectrum."""
    if decimal_places < 4:
        raise ValueError("decimal_places must be at least 4")
    floating = finite_xxz(float(delta), sites, periodic=False).real
    estimate = Decimal(str(float(np.linalg.eigvalsh(floating)[0])))
    scale = Decimal(10) ** decimal_places
    lower_decimal = (estimate * scale).to_integral_value(rounding=ROUND_FLOOR) / scale
    lower_decimal -= Decimal(1) / scale
    candidate = Fraction(lower_decimal)
    witness = AndersonWitness(sites=sites, eigenvalue_lower=candidate)
    if not verify_anderson_witness(delta, witness):
        raise ArithmeticError("failed to construct a positive-definite witness")
    return witness


def verify_anderson_witness(delta: Fraction, witness: AndersonWitness) -> bool:
    # XXZ conserves the number of down spins. Exact blockwise LDL is
    # equivalent to checking the full matrix and scales much better.
    for ones in range(witness.sites + 1):
        matrix = xxz_sector_matrix_fraction(delta, witness.sites, ones)
        shifted = [
            [
                value - witness.eigenvalue_lower if row == col else value
                for col, value in enumerate(values)
            ]
            for row, values in enumerate(matrix)
        ]
        positive, _ = exact_positive_definite_ldl(shifted)
        if not positive:
            return False
    return True


def lti_dual_slack_fraction(
    delta: Fraction, sites: int, y: Fraction, dual: RationalMatrix
) -> RationalMatrix:
    """Reconstruct C+yI+I⊗Y-Y⊗I exactly."""
    dim = 1 << sites
    dual_dim = 1 << (sites - 1)
    if len(dual) != dual_dim or any(len(row) != dual_dim for row in dual):
        raise ValueError("dual matrix dimension mismatch")
    local = xxz_matrix_fraction(delta, 2)
    rest_dim = 1 << (sites - 2)
    slack = [[Fraction(0) for _ in range(dim)] for _ in range(dim)]
    for row in range(dim):
        local_row, rest_row = divmod(row, rest_dim)
        left_bit, right_row = divmod(row, dual_dim)
        left_row, right_bit = divmod(row, 2)
        for col in range(dim):
            local_col, rest_col = divmod(col, rest_dim)
            if rest_row == rest_col:
                slack[row][col] += local[local_row][local_col]
            if row == col:
                slack[row][col] += y
            left_bit_col, right_col = divmod(col, dual_dim)
            if left_bit == left_bit_col:
                slack[row][col] += dual[right_row][right_col]
            left_col, right_bit_col = divmod(col, 2)
            if right_bit == right_bit_col:
                slack[row][col] -= dual[left_row][left_col]
    return slack


def verify_lti_dual_witness(delta: Fraction, witness: LTIDualWitness) -> bool:
    slack = lti_dual_slack_fraction(
        delta, witness.sites, witness.y, witness.matrix()
    )
    positive, _ = exact_positive_definite_ldl(slack)
    return positive


def make_lti_dual_witness(
    delta: Fraction,
    sites: int,
    dual_trace: float,
    dual_matrix: np.ndarray | None,
    scale: int = 10**8,
) -> LTIDualWitness:
    """Rationalize and exactly repair a numerical LTI dual solution."""
    if sites < 2:
        raise ValueError("sites must be at least 2")
    dual_dim = 1 << (sites - 1)
    if sites == 2:
        symmetric = np.zeros((dual_dim, dual_dim), dtype=float)
    else:
        if dual_matrix is None or dual_matrix.shape != (dual_dim, dual_dim):
            raise ValueError("missing or malformed dual matrix")
        if np.max(np.abs(np.asarray(dual_matrix).imag)) > 1e-8:
            raise ValueError("complex dual witness is not supported")
        real = np.asarray(dual_matrix).real
        symmetric = (real + real.T) / 2
    numerators = tuple(
        int(round(float(value) * scale)) for value in symmetric.reshape(-1)
    )
    rational_dual = [
        [
            Fraction(numerators[row * dual_dim + col], scale)
            for col in range(dual_dim)
        ]
        for row in range(dual_dim)
    ]
    base_y = Fraction(int(round(float(dual_trace) * scale)), scale)
    slack = lti_dual_slack_fraction(delta, sites, base_y, rational_dual)
    floating = np.array(
        [[float(value) for value in row] for row in slack], dtype=float
    )
    minimum = float(np.linalg.eigvalsh((floating + floating.T) / 2)[0])
    shift_steps = max(1, int(np.ceil(max(0.0, -minimum) * scale)) + 2)
    while True:
        repaired_y = base_y + Fraction(shift_steps, scale)
        witness = LTIDualWitness(
            sites=sites,
            denominator=scale,
            y_numerator=repaired_y.numerator * (scale // repaired_y.denominator),
            matrix_numerators=numerators,
        )
        if verify_lti_dual_witness(delta, witness):
            return witness
        shift_steps *= 2


def rationalize_state(state: np.ndarray, scale: int = 10**8) -> tuple[int, ...]:
    """Freeze a real floating state as a nonzero integer vector."""
    vector = np.asarray(state).reshape(-1)
    if np.max(np.abs(vector.imag)) > 1e-10:
        raise ValueError("only real state witnesses are supported")
    integers = tuple(int(round(float(value.real) * scale)) for value in vector)
    if not any(integers):
        raise ValueError("rationalized state is zero")
    return integers


def rationalize_sparse_state(
    state: np.ndarray, scale: int = 10**8
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Freeze a real state as sorted sparse integer amplitudes."""
    dense = rationalize_state(state, scale)
    indices = tuple(index for index, value in enumerate(dense) if value)
    values = tuple(dense[index] for index in indices)
    return indices, values


def _quadratic_form(matrix: RationalMatrix, vector: tuple[int, ...]) -> Fraction:
    return sum(
        Fraction(vector[i]) * matrix[i][j] * Fraction(vector[j])
        for i in range(len(vector))
        for j in range(len(vector))
        if matrix[i][j]
    )


def _exact_open_xxz_energy(
    delta: Fraction, vector: tuple[int, ...], sites: int
) -> Fraction:
    """Exact sparse quadratic form v^T H_open v."""
    total = Fraction(0)
    for state, amplitude in enumerate(vector):
        if amplitude == 0:
            continue
        diagonal = Fraction(0)
        for left in range(sites - 1):
            right = left + 1
            bit_l = (state >> (sites - 1 - left)) & 1
            bit_r = (state >> (sites - 1 - right)) & 1
            diagonal += delta / 4 if bit_l == bit_r else -delta / 4
            if bit_l != bit_r:
                flipped = state ^ (1 << (sites - 1 - left))
                flipped ^= 1 << (sites - 1 - right)
                total += Fraction(amplitude * vector[flipped], 2)
        total += diagonal * amplitude * amplitude
    return total


def _endpoint_rdm(
    vector: tuple[int, ...], sites: int, endpoint: str
) -> list[list[Fraction]]:
    rho = [[Fraction(0), Fraction(0)], [Fraction(0), Fraction(0)]]
    if endpoint not in {"first", "last"}:
        raise ValueError("endpoint must be first or last")
    position = sites - 1 if endpoint == "first" else 0
    mask = 1 << position
    for rest in range(1 << (sites - 1)):
        low_bits = rest & (mask - 1)
        high_bits = rest >> position
        index0 = (high_bits << (position + 1)) | low_bits
        index1 = index0 | mask
        rho[0][0] += vector[index0] * vector[index0]
        rho[0][1] += vector[index0] * vector[index1]
        rho[1][0] += vector[index1] * vector[index0]
        rho[1][1] += vector[index1] * vector[index1]
    return rho


def exact_block_product_energy(
    delta: Fraction, vector: tuple[int, ...]
) -> Fraction:
    """Exact thermodynamic energy of a repeated rational block state."""
    dim = len(vector)
    sites = dim.bit_length() - 1
    if dim != 1 << sites or sites < 2:
        raise ValueError("vector length must be 2**sites with sites >= 2")
    norm = sum(Fraction(value * value) for value in vector)
    if norm == 0:
        raise ValueError("state witness is zero")
    internal = _exact_open_xxz_energy(delta, vector, sites) / norm
    first = _endpoint_rdm(vector, sites, "first")
    last = _endpoint_rdm(vector, sites, "last")
    local = xxz_matrix_fraction(delta, 2)
    boundary_numerator = Fraction(0)
    for a in range(2):
        for b in range(2):
            row = 2 * a + b  # last site, then first site
            for c in range(2):
                for d in range(2):
                    col = 2 * c + d
                    boundary_numerator += (
                        local[row][col] * last[c][a] * first[d][b]
                    )
    boundary = boundary_numerator / (norm * norm)
    return (internal + boundary) / sites


def exact_sparse_block_product_energy(
    delta: Fraction,
    sites: int,
    indices: tuple[int, ...],
    values: tuple[int, ...],
) -> Fraction:
    """Exact repeated-block energy for a sparse integer state vector."""
    if sites < 2 or len(indices) != len(values) or not indices:
        raise ValueError("malformed sparse state witness")
    if tuple(sorted(indices)) != indices or len(set(indices)) != len(indices):
        raise ValueError("sparse indices must be unique and sorted")
    if indices[0] < 0 or indices[-1] >= 1 << sites:
        raise ValueError("sparse state index out of range")
    amplitudes = dict(zip(indices, values, strict=True))
    if any(value == 0 for value in values):
        raise ValueError("sparse state must not store zero amplitudes")
    norm = sum(Fraction(value * value) for value in values)
    internal = Fraction(0)
    for state, amplitude in amplitudes.items():
        diagonal = Fraction(0)
        for left in range(sites - 1):
            bit_l = (state >> (sites - 1 - left)) & 1
            bit_r = (state >> (sites - 2 - left)) & 1
            diagonal += delta / 4 if bit_l == bit_r else -delta / 4
            if bit_l != bit_r:
                flipped = state ^ (1 << (sites - 1 - left))
                flipped ^= 1 << (sites - 2 - left)
                internal += Fraction(
                    amplitude * amplitudes.get(flipped, 0), 2
                )
        internal += diagonal * amplitude * amplitude
    internal /= norm
    first = [[Fraction(0), Fraction(0)], [Fraction(0), Fraction(0)]]
    last = [[Fraction(0), Fraction(0)], [Fraction(0), Fraction(0)]]
    for rest in range(1 << (sites - 1)):
        first0, first1 = rest, (1 << (sites - 1)) | rest
        a0, a1 = amplitudes.get(first0, 0), amplitudes.get(first1, 0)
        first[0][0] += a0 * a0
        first[0][1] += a0 * a1
        first[1][0] += a1 * a0
        first[1][1] += a1 * a1
        last0, last1 = rest << 1, (rest << 1) | 1
        b0, b1 = amplitudes.get(last0, 0), amplitudes.get(last1, 0)
        last[0][0] += b0 * b0
        last[0][1] += b0 * b1
        last[1][0] += b1 * b0
        last[1][1] += b1 * b1
    local = xxz_matrix_fraction(delta, 2)
    boundary_numerator = Fraction(0)
    for a in range(2):
        for b in range(2):
            row = 2 * a + b
            for c in range(2):
                for d in range(2):
                    col = 2 * c + d
                    boundary_numerator += (
                        local[row][col] * last[c][a] * first[d][b]
                    )
    boundary = boundary_numerator / (norm * norm)
    return (internal + boundary) / sites


def exact_mps_block_product_energy(
    delta: Fraction,
    sites: int,
    bond_dimension: int,
    tensor_values: tuple[int, ...],
    left_boundary: tuple[int, ...],
    right_boundary: tuple[int, ...],
) -> Fraction:
    """Exact repeated-block energy of an integer OBC MPS."""
    if sites < 2 or bond_dimension < 1:
        raise ValueError("invalid MPS block dimensions")
    if len(tensor_values) != 2 * bond_dimension * bond_dimension:
        raise ValueError("MPS tensor payload dimension mismatch")
    if len(left_boundary) != bond_dimension or len(right_boundary) != bond_dimension:
        raise ValueError("MPS boundary dimension mismatch")
    tensors = np.array(tensor_values, dtype=object).reshape(
        bond_dimension, 2, bond_dimension
    )
    physical_matrices = [tensors[:, spin, :] for spin in range(2)]
    local = xxz_matrix_fraction(delta, 2)
    local_denominator = lcm(
        *(
            coefficient.denominator
            for row in local
            for coefficient in row
        )
    )
    local_integers = [
        [
            int(coefficient * local_denominator)
            for coefficient in row
        ]
        for row in local
    ]
    left_vector = np.array(left_boundary, dtype=object)
    right_vector = np.array(right_boundary, dtype=object)
    left_initial = np.outer(left_vector, left_vector)
    right_initial = np.outer(right_vector, right_vector)

    def propagate_right(environment):
        return sum(
            (
                matrix @ environment @ matrix.T
                for matrix in physical_matrices
            ),
            start=np.zeros(
                (bond_dimension, bond_dimension), dtype=object
            ),
        )

    def propagate_left(environment):
        return sum(
            (
                matrix.T @ environment @ matrix
                for matrix in physical_matrices
            ),
            start=np.zeros(
                (bond_dimension, bond_dimension), dtype=object
            ),
        )

    products = [
        [
            physical_matrices[first] @ physical_matrices[second]
            for second in range(2)
        ]
        for first in range(2)
    ]

    def insert_bond(environment):
        result = np.full(
            (bond_dimension, bond_dimension),
            0,
            dtype=object,
        )
        for first in range(2):
            for second in range(2):
                ket = products[first][second]
                row = 2 * first + second
                for first_prime in range(2):
                    for second_prime in range(2):
                        coefficient = local_integers[
                            row
                        ][2 * first_prime + second_prime]
                        if coefficient:
                            bra = products[first_prime][second_prime]
                            result += (
                                coefficient
                                * (ket @ environment @ bra.T)
                            )
        return result

    right_two_before = right_initial
    right_power = propagate_right(right_initial)
    internal_environment = np.full(
        (bond_dimension, bond_dimension),
        0,
        dtype=object,
    )
    for _ in range(2, sites + 1):
        internal_environment = (
            propagate_right(internal_environment)
            + insert_bond(right_two_before)
        )
        right_two_before, right_power = (
            right_power,
            propagate_right(right_power),
        )
    norm = sum(
        left_initial[row, column] * right_power[row, column]
        for row in range(bond_dimension)
        for column in range(bond_dimension)
    )
    if norm <= 0:
        raise ValueError("MPS block has zero norm")
    internal_numerator = sum(
        left_initial[index] * internal_environment[index]
        for index in np.ndindex(left_initial.shape)
    )
    internal = Fraction(internal_numerator, local_denominator)
    first = [[Fraction(0), Fraction(0)] for _ in range(2)]
    last = [[Fraction(0), Fraction(0)] for _ in range(2)]
    transfer_before_last = left_initial
    for _ in range(sites - 1):
        transfer_before_last = propagate_left(transfer_before_last)
    for ket in range(2):
        for bra in range(2):
            first_contracted = (
                physical_matrices[ket]
                @ right_two_before
                @ physical_matrices[bra].T
            )
            last_contracted = (
                physical_matrices[ket]
                @ right_initial
                @ physical_matrices[bra].T
            )
            first[ket][bra] = Fraction(
                sum(
                    left_initial[index] * first_contracted[index]
                    for index in np.ndindex(left_initial.shape)
                )
            )
            last[ket][bra] = Fraction(
                sum(
                    transfer_before_last[index]
                    * last_contracted[index]
                    for index in np.ndindex(transfer_before_last.shape)
                )
            )
    boundary_numerator = Fraction(0)
    for a in range(2):
        for b in range(2):
            row = 2 * a + b
            for c in range(2):
                for d in range(2):
                    boundary_numerator += Fraction(
                        local_integers[row][2 * c + d]
                        * last[c][a]
                        * first[d][b],
                        local_denominator,
                    )
    return (
        internal / norm + boundary_numerator / (norm * norm)
    ) / sites

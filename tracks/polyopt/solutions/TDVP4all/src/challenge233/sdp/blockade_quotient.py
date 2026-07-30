"""Exact quotient of Pauli tests by their action on blockaded inputs."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from challenge233.sdp.algebra import (
    GaussianRational,
    NEG_I,
    NEG_ONE,
    ONE,
    POS_I,
    PauliWord,
    add_polynomials,
    adjoint_polynomial,
    multiply_polynomials,
    polynomial_from_word,
    scale_polynomial,
)
from challenge233.sdp.conjugation_reduction import word_y_parity
from challenge233.sdp.constrained_trace import (
    constrained_polynomial_trace,
    periodic_blockade_dimension,
)
from challenge233.sdp.exact_linalg import (
    ExactColumnBasis,
    gaussian_column_basis,
    verify_column_reconstruction,
)
from challenge233.sdp.kyfan import (
    LinearEquality,
    _InvariantMomentFunctional,
)
from challenge233.sdp.kyfan_sparse import KyFanStructure


@dataclass(frozen=True)
class BlockadeQuotient:
    selected_indices: tuple[int, ...]
    reconstruction: tuple[
        tuple[tuple[int, GaussianRational], ...],
        ...,
    ]
    kernel: tuple[
        tuple[tuple[int, GaussianRational], ...],
        ...,
    ]
    legal_inputs: tuple[int, ...]
    output_count: int
    action_rank: int
    scope: str
    window_sites: tuple[int, ...]

    def __post_init__(self) -> None:
        selected = tuple(int(index) for index in self.selected_indices)
        legal_inputs = tuple(int(state) for state in self.legal_inputs)
        output_count = int(self.output_count)
        action_rank = int(self.action_rank)
        window_sites = tuple(int(site) for site in self.window_sites)
        if selected != tuple(sorted(set(selected))):
            raise ValueError(
                "selected quotient indices must be unique and sorted"
            )
        if legal_inputs != tuple(sorted(set(legal_inputs))):
            raise ValueError(
                "quotient legal inputs must be unique and sorted"
            )
        if output_count <= 0:
            raise ValueError("quotient output count must be positive")
        if action_rank != len(selected):
            raise ValueError(
                "quotient action rank must equal selected count"
            )
        if self.scope not in {"global", "local"}:
            raise ValueError("quotient scope must be global or local")
        object.__setattr__(self, "selected_indices", selected)
        object.__setattr__(
            self,
            "reconstruction",
            tuple(tuple(row) for row in self.reconstruction),
        )
        object.__setattr__(
            self,
            "kernel",
            tuple(tuple(row) for row in self.kernel),
        )
        object.__setattr__(self, "legal_inputs", legal_inputs)
        object.__setattr__(self, "output_count", output_count)
        object.__setattr__(self, "action_rank", action_rank)
        object.__setattr__(self, "window_sites", window_sites)


def _local_action(label: str, bit: int):
    if label == "X":
        return 1 - bit, ONE
    if label == "Z":
        return bit, ONE if bit else NEG_ONE
    if label == "Y":
        return 1 - bit, POS_I if bit else NEG_I
    raise ValueError("literal action only accepts X, Y, Z")


def literal_pauli_action(
    word: PauliWord,
    input_state: int,
    sites,
) -> tuple[int, GaussianRational]:
    """Apply one Pauli word to a bit state on ordered physical sites."""
    if not isinstance(word, PauliWord):
        raise TypeError("literal action requires a PauliWord")
    sites = tuple(int(site) for site in sites)
    if len(set(sites)) != len(sites) or any(
        site < 0 for site in sites
    ):
        raise ValueError(
            "literal action sites must be unique and nonnegative"
        )
    input_state = int(input_state)
    if not 0 <= input_state < (1 << len(sites)):
        raise ValueError("literal action input state is out of range")
    positions = {
        site: position for position, site in enumerate(sites)
    }
    if any(site not in positions for site, _ in word.factors):
        raise ValueError(
            "Pauli word lies outside the declared sites"
        )
    output_state = input_state
    phase = ONE
    for site, label in word.factors:
        position = positions[site]
        bit = (output_state >> position) & 1
        output_bit, local_phase = _local_action(label, bit)
        if output_bit != bit:
            output_state ^= 1 << position
        phase = phase * local_phase
    return output_state, phase


def _periodic_legal(state: int, size: int) -> bool:
    return all(
        not (
            ((state >> site) & 1)
            and ((state >> ((site + 1) % size)) & 1)
        )
        for site in range(size)
    )


def _open_legal(state: int, length: int) -> bool:
    return all(
        not (
            ((state >> position) & 1)
            and ((state >> (position + 1)) & 1)
        )
        for position in range(length - 1)
    )


def _domain(size: int, window_sites):
    if window_sites is None:
        sites = tuple(range(size))
        return (
            "global",
            sites,
            tuple(
                state
                for state in range(1 << size)
                if _periodic_legal(state, size)
            ),
            1 << size,
        )
    requested = tuple(int(site) for site in window_sites)
    no_collision = (
        len(set(requested)) == len(requested)
        and all(0 <= site < size for site in requested)
    )
    unwrapped = (
        bool(requested)
        and requested
        == tuple(
            range(requested[0], requested[0] + len(requested))
        )
        and requested[-1] < size
    )
    if (
        len(requested) < size
        and no_collision
        and unwrapped
    ):
        length = len(requested)
        return (
            "local",
            requested,
            tuple(
                state
                for state in range(1 << length)
                if _open_legal(state, length)
            ),
            1 << length,
        )
    sites = tuple(range(size))
    return (
        "global",
        sites,
        tuple(
            state
            for state in range(1 << size)
            if _periodic_legal(state, size)
        ),
        1 << size,
    )


def _action_columns(basis, sites, legal_inputs):
    input_count = len(legal_inputs)
    columns = []
    for word in basis:
        column = {}
        for input_position, input_state in enumerate(legal_inputs):
            output_state, phase = literal_pauli_action(
                word,
                input_state,
                sites,
            )
            coordinate = output_state * input_count + input_position
            column[coordinate] = phase
        columns.append(column)
    return tuple(columns)


def _validate_size_basis(size, basis):
    size = int(size)
    if size < 1:
        raise ValueError("quotient size must be positive")
    basis = tuple(basis)
    if not basis:
        raise ValueError("quotient basis must be non-empty")
    if any(not isinstance(word, PauliWord) for word in basis):
        raise TypeError("quotient basis must contain PauliWord values")
    if len(set(basis)) != len(basis):
        raise ValueError("quotient basis words must be unique")
    return size, basis


def build_blockade_quotient(
    size: int,
    basis,
    window_sites=None,
) -> BlockadeQuotient:
    size, basis = _validate_size_basis(size, basis)
    scope, sites, legal_inputs, output_count = _domain(
        size,
        window_sites,
    )
    columns = _action_columns(basis, sites, legal_inputs)
    exact = gaussian_column_basis(columns)
    return BlockadeQuotient(
        selected_indices=exact.selected,
        reconstruction=exact.reconstruction,
        kernel=exact.kernel,
        legal_inputs=legal_inputs,
        output_count=output_count,
        action_rank=len(exact.selected),
        scope=scope,
        window_sites=sites,
    )


def verify_blockade_quotient(
    size: int,
    basis,
    quotient: BlockadeQuotient,
    window_sites=None,
) -> dict:
    """Independently rebuild the literal action and exact quotient."""
    size, basis = _validate_size_basis(size, basis)
    if not isinstance(quotient, BlockadeQuotient):
        raise TypeError("quotient must be a BlockadeQuotient")
    requested_window = (
        quotient.window_sites
        if window_sites is None and quotient.scope == "local"
        else window_sites
    )
    scope, sites, legal_inputs, output_count = _domain(
        size,
        requested_window,
    )
    if quotient.scope != scope or quotient.window_sites != sites:
        raise ValueError("quotient scope or window mismatch")
    if quotient.legal_inputs != legal_inputs:
        raise ValueError("quotient legal-input domain mismatch")
    if quotient.output_count != output_count:
        raise ValueError("quotient output domain mismatch")
    columns = _action_columns(basis, sites, legal_inputs)
    expected = gaussian_column_basis(columns)
    if quotient.selected_indices != expected.selected:
        raise ValueError("quotient selected-column inventory mismatch")
    if quotient.reconstruction != expected.reconstruction:
        raise ValueError("quotient reconstruction mismatch")
    if quotient.kernel != expected.kernel:
        raise ValueError("quotient kernel mismatch")
    exact = ExactColumnBasis(
        selected=quotient.selected_indices,
        reconstruction=quotient.reconstruction,
        kernel=quotient.kernel,
        pivots=expected.pivots,
    )
    verify_column_reconstruction(columns, exact)
    if quotient.action_rank != len(expected.selected):
        raise ValueError("quotient action rank mismatch")
    return {
        "status": "verified",
        "scope": scope,
        "action_rank": quotient.action_rank,
        "input_count": len(legal_inputs),
        "output_count": output_count,
    }


def _kernel_polynomial(basis, relation):
    return add_polynomials(
        *(
            scale_polynomial(
                coefficient,
                polynomial_from_word(basis[index]),
            )
            for index, coefficient in relation
        )
    )


def kernel_localizer_rows(
    structure: KyFanStructure,
    quotient: BlockadeQuotient,
) -> tuple[LinearEquality, ...]:
    """Expand every action-kernel relation as retained left-ideal rows."""
    if not isinstance(structure, KyFanStructure):
        raise TypeError("structure must be a KyFanStructure")
    verify_blockade_quotient(
        structure.size,
        structure.moment_basis,
        quotient,
        (
            quotient.window_sites
            if quotient.scope == "local"
            else None
        ),
    )
    functional = _InvariantMomentFunctional(
        structure.size,
        structure.variables,
    )
    rows = []
    for kernel_index, relation in enumerate(quotient.kernel):
        kernel = _kernel_polynomial(
            structure.moment_basis,
            relation,
        )
        kernel_provenance = tuple(
            (
                index,
                {
                    "real": (
                        f"{coefficient.real.numerator}/"
                        f"{coefficient.real.denominator}"
                    ),
                    "imag": (
                        f"{coefficient.imag.numerator}/"
                        f"{coefficient.imag.denominator}"
                    ),
                },
            )
            for index, coefficient in relation
        )
        for left_position, left_index in enumerate(
            quotient.selected_indices
        ):
            left = adjoint_polynomial(
                polynomial_from_word(
                    structure.moment_basis[left_index]
                )
            )
            value = functional.polynomial(
                multiply_polynomials(left, kernel)
            )
            prefix = (
                "blockade-right-ideal-localizer"
                f"-kernel-{kernel_index}"
                f"-left-{left_position}"
            )
            provenance = {
                "localizer_kind": "blockade-right-ideal",
                "kernel_index": kernel_index,
                "left_selected_position": left_position,
                "left_basis_index": left_index,
                "kernel_relation": kernel_provenance,
            }
            if not value.real.is_zero:
                rows.append(
                    LinearEquality(
                        identifier=f"{prefix}-real",
                        form=value.real,
                        provenance={
                            **provenance,
                            "component": "real",
                        },
                    )
                )
            if not value.imag.is_zero:
                rows.append(
                    LinearEquality(
                        identifier=f"{prefix}-imag",
                        form=value.imag,
                        provenance={
                            **provenance,
                            "component": "imag",
                        },
                    )
                )
    return tuple(rows)


def _gauge_phase(left: PauliWord, right: PauliWord):
    values = (ONE, POS_I, NEG_ONE, NEG_I)
    return (
        values[-word_y_parity(left) % 4]
        * values[word_y_parity(right) % 4]
    )


def slater_gram(
    structure: KyFanStructure,
    quotient: BlockadeQuotient,
) -> tuple[tuple[Fraction, ...], ...]:
    """Return the normalized exact Gram on selected quotient columns."""
    if not isinstance(structure, KyFanStructure):
        raise TypeError("structure must be a KyFanStructure")
    verify_blockade_quotient(
        structure.size,
        structure.moment_basis,
        quotient,
        (
            quotient.window_sites
            if quotient.scope == "local"
            else None
        ),
    )
    selected = tuple(
        structure.moment_basis[index]
        for index in quotient.selected_indices
    )
    normalization = Fraction(
        1,
        periodic_blockade_dimension(structure.size),
    )
    matrix = []
    for left in selected:
        row = []
        for right in selected:
            product = multiply_polynomials(
                adjoint_polynomial(polynomial_from_word(left)),
                polynomial_from_word(right),
            )
            trace = constrained_polynomial_trace(
                structure.size,
                product,
            )
            gauged = _gauge_phase(left, right) * trace
            if gauged.imag:
                raise ValueError(
                    "phase-gauged Slater Gram is not real"
                )
            row.append(normalization * gauged.real)
        matrix.append(tuple(row))
    return tuple(matrix)


def exact_ldlt_pivots(matrix) -> tuple[Fraction, ...]:
    matrix = tuple(
        tuple(Fraction(value) for value in row)
        for row in matrix
    )
    dimension = len(matrix)
    if any(len(row) != dimension for row in matrix):
        raise ValueError("Slater Gram must be square")
    if any(
        matrix[row][column] != matrix[column][row]
        for row in range(dimension)
        for column in range(dimension)
    ):
        raise ValueError("Slater Gram must be symmetric")
    lower = [
        [
            Fraction(int(row == column))
            for column in range(dimension)
        ]
        for row in range(dimension)
    ]
    diagonal = []
    for column in range(dimension):
        pivot = matrix[column][column] - sum(
            lower[column][prior]
            * lower[column][prior]
            * diagonal[prior]
            for prior in range(column)
        )
        if pivot <= 0:
            raise ValueError(
                "Slater Gram is not positive definite"
            )
        diagonal.append(pivot)
        for row in range(column + 1, dimension):
            numerator = matrix[row][column] - sum(
                lower[row][prior]
                * lower[column][prior]
                * diagonal[prior]
                for prior in range(column)
            )
            lower[row][column] = numerator / pivot
    reconstructed = tuple(
        tuple(
            sum(
                lower[row][index]
                * diagonal[index]
                * lower[column][index]
                for index in range(dimension)
            )
            for column in range(dimension)
        )
        for row in range(dimension)
    )
    if reconstructed != matrix:
        raise ArithmeticError("exact LDL reconstruction failed")
    return tuple(diagonal)

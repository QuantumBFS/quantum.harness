"""Exact lifting helpers for presolved Ky Fan dual certificates."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping

from challenge233.sdp.algebra import (
    GaussianRational,
    NEG_I,
    NEG_ONE,
    ONE,
    POS_I,
    PauliWord,
)
from challenge233.sdp.blockade_quotient import literal_pauli_action
from challenge233.sdp.dual_certificate import (
    DyadicFactor,
    _validate_factor,
    positive_dyadic_factor,
)
from challenge233.sdp.kyfan import (
    MagnitudeWitness,
    MomentVariable,
    RationalLinearForm,
)
from challenge233.sdp.kyfan_presolve import KyFanSolverReduction
from challenge233.sdp.kyfan_sparse import KyFanStructure
from challenge233.sdp.symmetry import (
    DihedralElement,
    act_on_site,
    representation_permutation,
)


@dataclass(frozen=True)
class WeightedFactorOrbit:
    """One exact dyadic Gram template averaged over a spatial group."""

    identifier: str
    weight: Fraction
    factor: DyadicFactor
    group_images: tuple[DihedralElement, ...]
    phase_exponents: tuple[int, ...]
    source_block: str
    irrep_label: str
    irrep_degree: int

    def __post_init__(self) -> None:
        identifier = str(self.identifier)
        source_block = str(self.source_block)
        irrep_label = str(self.irrep_label)
        images = tuple(self.group_images)
        phases = tuple(int(value) % 4 for value in self.phase_exponents)
        degree = int(self.irrep_degree)
        if not identifier or not source_block or not irrep_label:
            raise ValueError("factor-orbit identifiers must be nonempty")
        _validate_factor(self.factor)
        if not images or len(set(images)) != len(images):
            raise ValueError("factor-orbit group images must be unique")
        if any(
            not isinstance(element, DihedralElement)
            for element in images
        ):
            raise TypeError(
                "factor-orbit images must be DihedralElement values"
            )
        if len(phases) != self.factor.rows:
            raise ValueError(
                "factor-orbit phases must match the lifted factor rows"
            )
        if degree <= 0:
            raise ValueError("factor-orbit irrep degree must be positive")
        expected_weight = Fraction(1, len(images))
        if Fraction(self.weight) != expected_weight:
            raise ValueError(
                "factor-orbit weight must average all group images"
            )
        object.__setattr__(self, "identifier", identifier)
        object.__setattr__(self, "weight", expected_weight)
        object.__setattr__(self, "group_images", images)
        object.__setattr__(self, "phase_exponents", phases)
        object.__setattr__(self, "source_block", source_block)
        object.__setattr__(self, "irrep_label", irrep_label)
        object.__setattr__(self, "irrep_degree", degree)


@dataclass(frozen=True)
class ExactLiftedIdentity:
    """Original-coordinate exact identity with two sound corrections."""

    a: Fraction
    residuals: tuple[Fraction, ...]
    rho_mom: Fraction
    rho_op: Fraction
    rho: Fraction
    residual_route: str
    a_cert: Fraction

    def __post_init__(self) -> None:
        a = Fraction(self.a)
        residuals = tuple(Fraction(value) for value in self.residuals)
        rho_mom = Fraction(self.rho_mom)
        rho_op = Fraction(self.rho_op)
        rho = Fraction(self.rho)
        if rho_mom < 0 or rho_op < 0:
            raise ValueError("residual corrections must be nonnegative")
        expected_rho = min(rho_mom, rho_op)
        expected_route = (
            "pseudo-moment"
            if rho_mom <= rho_op
            else "physical-operator"
        )
        if rho != expected_rho or self.residual_route != expected_route:
            raise ValueError("residual correction route is inconsistent")
        if Fraction(self.a_cert) != a - rho:
            raise ValueError("certified objective is inconsistent")
        object.__setattr__(self, "a", a)
        object.__setattr__(self, "residuals", residuals)
        object.__setattr__(self, "rho_mom", rho_mom)
        object.__setattr__(self, "rho_op", rho_op)
        object.__setattr__(self, "rho", rho)
        object.__setattr__(self, "a_cert", a - rho)


def build_weighted_factor_orbit(
    identifier,
    factor,
    group_images,
    phase_exponents,
    source_block,
    irrep_label,
    irrep_degree,
) -> WeightedFactorOrbit:
    """Build one degree-labelled exact group average."""
    images = tuple(group_images)
    if not images:
        raise ValueError("factor-orbit group images must be nonempty")
    return WeightedFactorOrbit(
        identifier=identifier,
        weight=Fraction(1, len(images)),
        factor=factor,
        group_images=images,
        phase_exponents=tuple(phase_exponents),
        source_block=source_block,
        irrep_label=irrep_label,
        irrep_degree=irrep_degree,
    )


def _dyadic_exponent(denominator: int) -> int:
    if denominator <= 0 or denominator & (denominator - 1):
        raise ValueError(
            "spatial lift produced a non-dyadic factor coefficient"
        )
    return denominator.bit_length() - 1


def _lift_factor(transform, factor: DyadicFactor) -> DyadicFactor:
    """Apply one exact sparse spatial embedding to a dyadic factor."""
    _validate_factor(factor)
    if transform.columns != factor.rows:
        raise ValueError(
            "spatial transform does not match reduced factor rows"
        )
    columns = factor.columns
    values = [
        [Fraction(0) for _ in range(columns)]
        for _ in range(transform.rows)
    ]
    for row, source, coefficient in transform.entries:
        for column, numerator in enumerate(factor.numerators[source]):
            values[row][column] += coefficient * numerator
    extra_bits = max(
        (
            _dyadic_exponent(value.denominator)
            for row in values
            for value in row
        ),
        default=0,
    )
    used_bits = factor.used_bits + extra_bits
    requested_bits = max(
        factor.requested_bits,
        used_bits,
    )
    if requested_bits > 60:
        raise OverflowError(
            "lifted dyadic factor requires more than 60 bits"
        )
    scale = 1 << extra_bits
    numerators = tuple(
        tuple(int(value * scale) for value in row)
        for row in values
    )
    maximum = max(
        (
            abs(value)
            for row in numerators
            for value in row
        ),
        default=0,
    )
    overflow_bound = columns * maximum * maximum
    int64_safe = (
        overflow_bound < 1 << 62
        and all(
            -(1 << 63) <= value < (1 << 63)
            for row in numerators
            for value in row
        )
    )
    return DyadicFactor(
        rows=transform.rows,
        columns=columns,
        requested_bits=requested_bits,
        used_bits=used_bits,
        numerators=numerators,
        storage="int64" if int64_safe else "decimal-json",
        overflow_bound=overflow_bound,
    )


def lift_reduced_duals(
    structure,
    reduction,
    solver_result,
    factor_bits,
) -> tuple[WeightedFactorOrbit, ...]:
    """Round and lift every reduced numerical PSD dual exactly."""
    if not isinstance(structure, KyFanStructure):
        raise TypeError("structure must be a KyFanStructure")
    if not isinstance(reduction, KyFanSolverReduction):
        raise TypeError("reduction must be a KyFanSolverReduction")
    if reduction.structure_sha256 != structure.logical_fingerprint():
        # The artifact SHA and logical fingerprint use the same canonical
        # signature for in-memory structures.
        from challenge233.sdp.kyfan_v2_artifact import (
            logical_structure_sha256,
        )

        if reduction.structure_sha256 != logical_structure_sha256(
            structure
        ):
            raise ValueError(
                "solver reduction does not bind the logical structure"
            )
    if not isinstance(solver_result, Mapping):
        raise TypeError("solver_result must be a mapping")
    raw_duals = tuple(solver_result.get("psd_duals", ()))
    by_identifier = {}
    for metadata in raw_duals:
        if not isinstance(metadata, Mapping):
            raise TypeError("solver PSD dual metadata must be a mapping")
        identifier = str(metadata.get("block", ""))
        if not identifier or identifier in by_identifier:
            raise ValueError(
                "solver PSD dual identifiers must be nonempty and unique"
            )
        by_identifier[identifier] = metadata
    expected = {
        block.identifier for block in reduction.psd_blocks
    }
    if set(by_identifier) != expected:
        raise ValueError(
            "solver PSD dual inventory does not match reduced blocks"
        )
    spatial_by_identifier = {
        block.identifier: block for block in reduction.spatial
    }
    lifted = []
    for block in reduction.psd_blocks:
        metadata = by_identifier[block.identifier]
        spatial = spatial_by_identifier.get(block.spatial_block)
        if spatial is None:
            raise ValueError("reduced block names an unknown spatial slice")
        for field, actual, expected_value in (
            ("dimension", metadata.get("dimension"), block.dimension),
            (
                "source effect",
                metadata.get("source_effect"),
                block.source_block,
            ),
            (
                "spatial block",
                metadata.get("spatial_block"),
                block.spatial_block,
            ),
            (
                "irrep label",
                metadata.get("irrep_label"),
                spatial.irrep_label,
            ),
            (
                "irrep degree",
                metadata.get("irrep_degree"),
                spatial.irrep_degree,
            ),
        ):
            if actual != expected_value:
                raise ValueError(
                    f"solver PSD dual {field} metadata mismatch"
                )
        if "matrix" not in metadata:
            raise ValueError(
                "solver PSD dual matrix must be loaded before lifting"
            )
        reduced_factor = positive_dyadic_factor(
            metadata["matrix"],
            factor_bits,
        )
        if reduced_factor.rows != block.dimension:
            raise ValueError(
                "solver PSD dual matrix dimension mismatch"
            )
        full_factor = _lift_factor(
            spatial.transform,
            reduced_factor,
        )
        lifted.append(
            build_weighted_factor_orbit(
                identifier=block.identifier,
                factor=full_factor,
                group_images=spatial.internal_group,
                phase_exponents=reduction.conjugation.phases,
                source_block=block.source_block,
                irrep_label=spatial.irrep_label,
                irrep_degree=spatial.irrep_degree,
            )
        )
    return tuple(lifted)


def _phase(exponent: int) -> GaussianRational:
    return (ONE, POS_I, NEG_ONE, NEG_I)[int(exponent) % 4]


def _permuted_gram_entry(
    factor: DyadicFactor,
    inverse_permutation,
    row: int,
    column: int,
) -> Fraction:
    left = factor.numerators[inverse_permutation[row]]
    right = factor.numerators[inverse_permutation[column]]
    numerator = sum(
        left[index] * right[index]
        for index in range(factor.columns)
    )
    return Fraction(
        numerator,
        1 << (2 * factor.used_bits),
    )


def exact_lifted_psd_contribution(
    structure,
    factor_orbits,
) -> tuple[Fraction, tuple[Fraction, ...]]:
    """Pair exact group-averaged lifted Grams with logical sparse blocks."""
    if not isinstance(structure, KyFanStructure):
        raise TypeError("structure must be a KyFanStructure")
    factor_orbits = tuple(factor_orbits)
    if any(
        not isinstance(item, WeightedFactorOrbit)
        for item in factor_orbits
    ):
        raise TypeError(
            "factor_orbits must contain WeightedFactorOrbit values"
        )
    source_blocks = {
        block.identifier: block for block in structure.psd_blocks
    }
    variable_count = len(structure.variables)
    expected_phases = tuple(
        sum(label == "Y" for _, label in word.factors) % 2
        for word in structure.moment_basis
    )
    odd_variables = {
        variable.index
        for variable in structure.variables
        if sum(
            label == "Y"
            for _, label in variable.representative.factors
        )
        % 2
    }
    constant = Fraction(0)
    coefficients = [Fraction(0)] * variable_count
    for item in factor_orbits:
        if item.factor.rows != len(structure.moment_basis):
            raise ValueError(
                "lifted factor row count does not match logical basis"
            )
        if item.phase_exponents != expected_phases:
            raise ValueError(
                "lifted factor conjugation phases are inconsistent"
            )
        source = source_blocks.get(item.source_block)
        if source is None:
            raise ValueError(
                "lifted factor names an unknown logical PSD block"
            )
        inverse_permutations = []
        for element in item.group_images:
            permutation = representation_permutation(
                element,
                structure.moment_basis,
                structure.size,
            )
            inverse = [None] * len(permutation)
            for original, image in enumerate(permutation):
                inverse[image] = original
            inverse_permutations.append(tuple(inverse))
        for entry in source.upper_entries:
            gram = item.weight * sum(
                (
                    _permuted_gram_entry(
                        item.factor,
                        inverse,
                        entry.row,
                        entry.column,
                    )
                    for inverse in inverse_permutations
                ),
                Fraction(0),
            )
            if not gram:
                continue
            if entry.row != entry.column:
                gram *= 2
            gauged = entry.form.scale(
                _phase(
                    item.phase_exponents[entry.column]
                    - item.phase_exponents[entry.row]
                )
            )
            if gauged.imag.constant:
                raise ArithmeticError(
                    "inverse phase lift produced an imaginary constant"
                )
            if any(
                variable not in odd_variables and coefficient
                for variable, coefficient in gauged.imag.terms
            ):
                raise ArithmeticError(
                    "inverse phase lift produced an imaginary even moment"
                )
            constant += gram * gauged.real.constant
            for variable, coefficient in gauged.real.terms:
                coefficients[variable] += gram * coefficient
    return constant, tuple(coefficients)


def _exact_coefficient_vector(form, count: int):
    if not isinstance(form, RationalLinearForm):
        raise TypeError("bound instance objective must be an exact form")
    values = [Fraction(0)] * count
    for variable, coefficient in form.terms:
        if not 0 <= variable < count:
            raise ValueError("objective variable index is out of range")
        values[variable] += coefficient
    return tuple(values)


def _solve_exact_square(matrix, right_hand_side):
    matrix = [
        [Fraction(value) for value in row]
        + [Fraction(right_hand_side[index])]
        for index, row in enumerate(matrix)
    ]
    dimension = len(matrix)
    if any(len(row) != dimension + 1 for row in matrix):
        raise ValueError("equality pivot system must be square")
    for column in range(dimension):
        pivot = next(
            (
                row
                for row in range(column, dimension)
                if matrix[row][column]
            ),
            None,
        )
        if pivot is None:
            raise ArithmeticError(
                "equality pivot system is singular"
            )
        matrix[column], matrix[pivot] = (
            matrix[pivot],
            matrix[column],
        )
        inverse = Fraction(1) / matrix[column][column]
        matrix[column] = [
            inverse * value for value in matrix[column]
        ]
        for row in range(dimension):
            if row == column or not matrix[row][column]:
                continue
            factor = matrix[row][column]
            matrix[row] = [
                left - factor * right
                for left, right in zip(
                    matrix[row],
                    matrix[column],
                )
            ]
    return tuple(row[-1] for row in matrix)


def reconstruct_equality_multipliers(
    structure,
    reduction,
    psd_coefficients,
) -> dict[str, Fraction]:
    """Choose exact kept-row multipliers cancelling every pivot coordinate.

    ``structure`` is the bound instance (or compatible object) carrying the
    exact detuning-specific ``objective``.  The shared logical structure is
    deliberately insufficient here because its objective is an overlay.
    """
    if not isinstance(reduction, KyFanSolverReduction):
        raise TypeError("reduction must be a KyFanSolverReduction")
    objective_form = getattr(structure, "objective", None)
    if objective_form is None:
        raise TypeError(
            "equality reconstruction requires a bound exact objective"
        )
    variable_count = reduction.statistics["original_variable_count"]
    objective = _exact_coefficient_vector(
        objective_form,
        variable_count,
    )
    psd = _residual_vector(psd_coefficients, variable_count)
    target = tuple(
        objective[index] - psd[index]
        for index in range(variable_count)
    )
    kept = tuple(reduction.kept_equalities)
    pivots = tuple(reduction.equality.pivot_columns)
    if len(kept) != len(pivots):
        raise ArithmeticError(
            "kept equality and pivot inventories are inconsistent"
        )
    coefficient_maps = tuple(
        dict(row.form.terms) for row in kept
    )
    # A_pivot^T mu = target_pivot.
    pivot_system = tuple(
        tuple(
            coefficients.get(pivot, Fraction(0))
            for coefficients in coefficient_maps
        )
        for pivot in pivots
    )
    multipliers = _solve_exact_square(
        pivot_system,
        tuple(target[pivot] for pivot in pivots),
    )
    reconstructed = {
        str(identifier): Fraction(0)
        for identifier in reduction.equality.statistics[
            "all_identifiers"
        ]
    }
    for row, multiplier in zip(kept, multipliers):
        if row.identifier not in reconstructed:
            raise ValueError(
                "kept equality is missing from full inventory"
            )
        reconstructed[row.identifier] = multiplier
    for pivot in pivots:
        cancellation = target[pivot] - sum(
            reconstructed[row.identifier]
            * dict(row.form.terms).get(pivot, Fraction(0))
            for row in kept
        )
        if cancellation:
            raise ArithmeticError(
                "equality pivot cancellation failed"
            )
    return reconstructed


def _residual_vector(residuals, variable_count: int):
    if not isinstance(residuals, Mapping):
        raise TypeError("residuals must be an index-to-Fraction mapping")
    expected = set(range(variable_count))
    if set(residuals) != expected:
        raise ValueError(
            "residual inventory must contain every variable exactly once"
        )
    values = []
    for index in range(variable_count):
        value = residuals[index]
        if isinstance(value, (bool, float)):
            raise TypeError("residual coefficients must be exact")
        values.append(Fraction(value))
    return tuple(values)


def moment_residual_correction(
    residuals,
    witnesses,
) -> Fraction:
    """Bound an identity residual using checked pseudo-moment witnesses."""
    witnesses = tuple(witnesses)
    if any(
        not isinstance(witness, MagnitudeWitness)
        for witness in witnesses
    ):
        raise TypeError("witnesses must contain MagnitudeWitness values")
    by_variable = {}
    for witness in witnesses:
        if witness.variable in by_variable:
            raise ValueError("duplicate magnitude witness")
        bound = Fraction(witness.bound)
        if bound < 0:
            raise ValueError("magnitude witness bound must be nonnegative")
        by_variable[witness.variable] = bound
    values = _residual_vector(residuals, len(witnesses))
    if set(by_variable) != set(range(len(witnesses))):
        raise ValueError("missing magnitude witness")
    return sum(
        by_variable[index] * abs(value)
        for index, value in enumerate(values)
    )


def _validate_physical_inputs(size, variables, residuals):
    if isinstance(size, bool) or not isinstance(size, int) or size < 3:
        raise ValueError("physical size must be an integer at least 3")
    variables = tuple(variables)
    if any(
        not isinstance(variable, MomentVariable)
        for variable in variables
    ):
        raise TypeError("variables must contain MomentVariable values")
    if tuple(variable.index for variable in variables) != tuple(
        range(len(variables))
    ):
        raise ValueError("moment variable indices must be contiguous")
    for variable in variables:
        if (
            not variable.orbit
            or len(set(variable.orbit)) != len(variable.orbit)
            or variable.representative not in variable.orbit
            or any(
                not isinstance(word, PauliWord)
                for word in variable.orbit
            )
        ):
            raise ValueError("moment variable orbit is malformed")
        if any(
            site >= size
            for word in variable.orbit
            for site, _ in word.factors
        ):
            raise ValueError("moment variable lies outside physical size")
    return variables, _residual_vector(residuals, len(variables))


def _periodic_legal(state: int, size: int) -> bool:
    return all(
        not (
            ((state >> site) & 1)
            and ((state >> ((site + 1) % size)) & 1)
        )
        for site in range(size)
    )


def _legal_states(size: int):
    return tuple(
        state
        for state in range(1 << size)
        if _periodic_legal(state, size)
    )


def _act_on_state(element: DihedralElement, state: int, size: int) -> int:
    output = 0
    for site in range(size):
        if (state >> site) & 1:
            output |= 1 << act_on_site(element, site, size)
    return output


def _canonical_input_states(size: int, legal_states):
    unseen = set(legal_states)
    representatives = []
    from challenge233.sdp.symmetry import dihedral_elements

    group = dihedral_elements(size)
    while unseen:
        representative = min(unseen)
        orbit = {
            _act_on_state(element, representative, size)
            for element in group
        }
        if not orbit <= set(legal_states):
            raise ArithmeticError(
                "dihedral action did not preserve blockade legality"
            )
        representatives.append(representative)
        unseen.difference_update(orbit)
    return tuple(representatives)


def _row_sum_bound(
    size: int,
    variables,
    values,
    input_states,
) -> Fraction:
    legal = set(_legal_states(size))
    sites = tuple(range(size))
    maximum = Fraction(0)
    for input_state in input_states:
        row = {}
        for variable, residual in zip(variables, values):
            if not residual:
                continue
            coefficient = residual / len(variable.orbit)
            for word in variable.orbit:
                output_state, phase = literal_pauli_action(
                    word,
                    input_state,
                    sites,
                )
                if output_state not in legal:
                    continue
                row[output_state] = (
                    row.get(output_state, GaussianRational())
                    + GaussianRational(
                        coefficient * phase.real,
                        coefficient * phase.imag,
                    )
                )
        # The rational complex l1 row norm bounds the spectral norm.  In
        # the invariant Hermitian residuals used here every surviving entry
        # is axis-aligned, so it also equals the ordinary absolute row sum.
        row_sum = sum(
            abs(value.real) + abs(value.imag)
            for value in row.values()
        )
        maximum = max(maximum, row_sum)
    return 2 * maximum


def physical_residual_correction(
    size,
    variables,
    residuals,
) -> Fraction:
    """Bound the physical residual from one representative per D_N orbit."""
    variables, values = _validate_physical_inputs(
        size,
        variables,
        residuals,
    )
    legal = _legal_states(size)
    representatives = _canonical_input_states(size, legal)
    return _row_sum_bound(
        size,
        variables,
        values,
        representatives,
    )


def literal_dense_residual_norm_bound(
    size,
    variables,
    residuals,
) -> Fraction:
    """Small-system oracle evaluating the same bound on every legal row."""
    variables, values = _validate_physical_inputs(
        size,
        variables,
        residuals,
    )
    return _row_sum_bound(
        size,
        variables,
        values,
        _legal_states(size),
    )

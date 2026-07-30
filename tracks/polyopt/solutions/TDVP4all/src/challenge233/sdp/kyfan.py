"""Exact-rational Ky Fan effect-moment problem assembly."""

from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from functools import lru_cache

from challenge233.sdp.algebra import (
    GaussianRational,
    PauliPolynomial,
    PauliWord,
    canonicalize_word,
)
from challenge233.sdp.constrained_trace import (
    constrained_polynomial_trace,
    periodic_blockade_dimension,
)
from challenge233.sdp.constraints import pxp_hamiltonian_polynomial
from challenge233.sdp.hierarchy import (
    HierarchyLevel,
    clique_orbit,
    global_pauli_basis,
    local_pauli_basis,
    safe_localizer_basis,
)
from challenge233.sdp.localizers import (
    SafeWord,
    build_safe_sandwich_localizers,
    build_support_localizers,
)
from challenge233.sdp.symmetry import (
    DihedralElement,
    act_on_site,
    act_on_word,
    dihedral_elements,
    word_orbit,
)


@dataclass(frozen=True)
class RationalLinearForm:
    constant: Fraction = Fraction(0)
    terms: tuple = ()

    def __post_init__(self) -> None:
        combined = {}
        for variable, coefficient in self.terms:
            variable = int(variable)
            coefficient = Fraction(coefficient)
            combined[variable] = (
                combined.get(variable, Fraction(0))
                + coefficient
            )
        object.__setattr__(self, "constant", Fraction(self.constant))
        object.__setattr__(
            self,
            "terms",
            tuple(
                (variable, coefficient)
                for variable, coefficient in sorted(combined.items())
                if coefficient
            ),
        )

    @property
    def is_zero(self) -> bool:
        return self.constant == 0 and not self.terms

    def __add__(self, other):
        if not isinstance(other, RationalLinearForm):
            return NotImplemented
        return RationalLinearForm(
            self.constant + other.constant,
            self.terms + other.terms,
        )

    def __neg__(self):
        return self.scale(Fraction(-1))

    def __sub__(self, other):
        if not isinstance(other, RationalLinearForm):
            return NotImplemented
        return self + (-other)

    def scale(self, coefficient) -> "RationalLinearForm":
        coefficient = Fraction(coefficient)
        return RationalLinearForm(
            coefficient * self.constant,
            tuple(
                (variable, coefficient * value)
                for variable, value in self.terms
            ),
        )


@dataclass(frozen=True)
class ComplexLinearForm:
    real: RationalLinearForm = RationalLinearForm()
    imag: RationalLinearForm = RationalLinearForm()

    def __post_init__(self) -> None:
        if not isinstance(self.real, RationalLinearForm):
            raise TypeError("real part must be a RationalLinearForm")
        if not isinstance(self.imag, RationalLinearForm):
            raise TypeError("imaginary part must be a RationalLinearForm")

    @classmethod
    def constant(cls, value: GaussianRational) -> "ComplexLinearForm":
        if not isinstance(value, GaussianRational):
            raise TypeError("complex constant must be GaussianRational")
        return cls(
            RationalLinearForm(value.real),
            RationalLinearForm(value.imag),
        )

    @property
    def is_zero(self) -> bool:
        return self.real.is_zero and self.imag.is_zero

    def __add__(self, other):
        if not isinstance(other, ComplexLinearForm):
            return NotImplemented
        return ComplexLinearForm(
            self.real + other.real,
            self.imag + other.imag,
        )

    def __neg__(self):
        return ComplexLinearForm(-self.real, -self.imag)

    def __sub__(self, other):
        if not isinstance(other, ComplexLinearForm):
            return NotImplemented
        return self + (-other)

    def scale(
        self,
        coefficient: GaussianRational,
    ) -> "ComplexLinearForm":
        if not isinstance(coefficient, GaussianRational):
            raise TypeError("complex scale must be GaussianRational")
        return ComplexLinearForm(
            self.real.scale(coefficient.real)
            - self.imag.scale(coefficient.imag),
            self.real.scale(coefficient.imag)
            + self.imag.scale(coefficient.real),
        )

    def conjugate(self) -> "ComplexLinearForm":
        return ComplexLinearForm(self.real, -self.imag)


@dataclass(frozen=True)
class LinearEquality:
    identifier: str
    form: RationalLinearForm
    provenance: dict


@dataclass(frozen=True)
class ComplexPSDBlock:
    identifier: str
    dimension: int
    entries: tuple
    provenance: dict


@dataclass(frozen=True)
class RealPSDBlock:
    identifier: str
    dimension: int
    entries: tuple
    provenance: dict

    def __post_init__(self) -> None:
        dimension = int(self.dimension)
        object.__setattr__(self, "dimension", dimension)
        if len(self.entries) != dimension:
            raise ValueError("PSD block row count does not match dimension")
        if any(len(row) != dimension for row in self.entries):
            raise ValueError(
                "PSD block column count does not match dimension"
            )
        if any(
            not isinstance(entry, RationalLinearForm)
            for row in self.entries
            for entry in row
        ):
            raise TypeError("real PSD entries must be RationalLinearForm")
        for row in range(dimension):
            for column in range(row):
                if self.entries[row][column] != self.entries[column][row]:
                    raise ValueError("real PSD block must be symmetric")


@dataclass(frozen=True)
class MomentVariable:
    index: int
    representative: PauliWord
    orbit: tuple


@dataclass(frozen=True)
class MagnitudeWitness:
    variable: int
    block: str
    row: int
    column: int
    phase: GaussianRational
    bound: Fraction


@dataclass(frozen=True)
class CliqueImage:
    shift: int
    reflected: bool
    sites: tuple
    representative_blocks: tuple
    row_permutation: tuple
    localizer_sites: tuple


@dataclass(frozen=True)
class KyFanProblem:
    size: int
    detuning: Fraction
    hierarchy: str
    localizer_mode: str
    moment_basis: tuple
    safe_basis: tuple
    variables: tuple
    objective: RationalLinearForm
    equalities: tuple
    psd_blocks: tuple
    unrealified_psd_blocks: tuple
    magnitude_witnesses: tuple
    clique_orbits: tuple
    clique_images: tuple
    localizer_sites: tuple
    provenance: dict
    statistics: dict


def _fraction_coefficient(value) -> GaussianRational:
    return GaussianRational(Fraction(value), Fraction(0))


def _validate_complex_hermitian(matrix) -> tuple:
    matrix = tuple(tuple(row) for row in matrix)
    dimension = len(matrix)
    if any(len(row) != dimension for row in matrix):
        raise ValueError("complex matrix must be square")
    if any(
        not isinstance(entry, ComplexLinearForm)
        for row in matrix
        for entry in row
    ):
        raise TypeError("complex matrix entries must be ComplexLinearForm")
    for row in range(dimension):
        for column in range(dimension):
            if matrix[row][column] != matrix[column][row].conjugate():
                raise ValueError("complex matrix must be Hermitian")
    return matrix


def realify_hermitian_matrix(matrix) -> tuple:
    """Apply the exact realification ``[[Re,-Im],[Im,Re]]``."""
    matrix = _validate_complex_hermitian(matrix)
    dimension = len(matrix)
    return tuple(
        tuple(
            (
                matrix[row][column].real
                if row < dimension and column < dimension
                else -matrix[row][column - dimension].imag
                if row < dimension
                else matrix[row - dimension][column].imag
                if column < dimension
                else matrix[row - dimension][column - dimension].real
            )
            for column in range(2 * dimension)
        )
        for row in range(2 * dimension)
    )


@lru_cache(maxsize=None)
def _moment_product(
    left: PauliWord,
    right: PauliWord,
) -> PauliPolynomial:
    canonical = canonicalize_word(left.factors + right.factors)
    return PauliPolynomial(
        ((canonical.word, canonical.coefficient),)
    )


@lru_cache(maxsize=200_000)
def _cached_word_orbit(
    size: int,
    word: PauliWord,
) -> tuple[PauliWord, ...]:
    return word_orbit(word, size)


def _orbit_representative(size: int, word: PauliWord) -> PauliWord:
    return _cached_word_orbit(size, word)[0]


def _build_variable_registry(
    size: int,
    polynomials,
) -> tuple[MomentVariable, ...]:
    representatives = set()
    for polynomial in polynomials:
        if not isinstance(polynomial, PauliPolynomial):
            raise TypeError("registry inputs must be PauliPolynomial values")
        for word, _ in polynomial.terms:
            if any(not 0 <= site < size for site, _ in word.factors):
                raise ValueError(
                    "moment word site must lie in range(size)"
                )
            if word.factors:
                representatives.add(_orbit_representative(size, word))
    return tuple(
        MomentVariable(
            index=index,
            representative=representative,
            orbit=_cached_word_orbit(size, representative),
        )
        for index, representative in enumerate(sorted(representatives))
    )


class _InvariantMomentFunctional:
    def __init__(self, size: int, variables) -> None:
        self.size = size
        self.indices = {
            variable.representative: variable.index
            for variable in variables
        }
        self._word_forms = {}

    def word(self, word: PauliWord) -> ComplexLinearForm:
        if word in self._word_forms:
            return self._word_forms[word]
        if not word.factors:
            result = ComplexLinearForm(
                RationalLinearForm(Fraction(2)),
                RationalLinearForm(),
            )
        else:
            representative = _orbit_representative(self.size, word)
            try:
                index = self.indices[representative]
            except KeyError as error:
                raise ValueError(
                    "moment polynomial was not registered"
                ) from error
            result = ComplexLinearForm(
                RationalLinearForm(
                    Fraction(0),
                    ((index, Fraction(1)),),
                ),
                RationalLinearForm(),
            )
        self._word_forms[word] = result
        return result

    def polynomial(
        self,
        polynomial: PauliPolynomial,
    ) -> ComplexLinearForm:
        result = ComplexLinearForm()
        for word, coefficient in polynomial.terms:
            result = result + self.word(word).scale(coefficient)
        return result


def _normalized_moment_matrices(
    size: int,
    products,
    functional: _InvariantMomentFunctional,
) -> tuple[tuple, tuple]:
    kappa = periodic_blockade_dimension(size)
    complement_scale = Fraction(1, kappa - 2)
    gamma_scale = _fraction_coefficient(Fraction(1, 2))
    negative_complement_scale = _fraction_coefficient(
        -complement_scale
    )
    positive_complement_scale = _fraction_coefficient(
        complement_scale
    )
    gamma = []
    complement = []
    for product_row in products:
        gamma_row = []
        complement_row = []
        for polynomial in product_row:
            ell = functional.polynomial(polynomial)
            tau = ComplexLinearForm.constant(
                constrained_polynomial_trace(size, polynomial)
            )
            gamma_row.append(ell.scale(gamma_scale))
            complement_row.append(
                tau.scale(positive_complement_scale)
                + ell.scale(negative_complement_scale)
            )
        gamma.append(tuple(gamma_row))
        complement.append(tuple(complement_row))
    return (
        _validate_complex_hermitian(tuple(gamma)),
        _validate_complex_hermitian(tuple(complement)),
    )


def _make_real_block(
    identifier: str,
    complex_matrix,
    provenance: dict,
) -> tuple[ComplexPSDBlock, RealPSDBlock]:
    complex_matrix = _validate_complex_hermitian(complex_matrix)
    complex_block = ComplexPSDBlock(
        identifier=identifier,
        dimension=len(complex_matrix),
        entries=complex_matrix,
        provenance=dict(provenance),
    )
    entries = realify_hermitian_matrix(complex_matrix)
    real_block = RealPSDBlock(
        identifier=identifier,
        dimension=len(entries),
        entries=entries,
        provenance={
            **provenance,
            "complex_dimension": len(complex_matrix),
            "realification": "[[Re,-Im],[Im,Re]]",
        },
    )
    return complex_block, real_block


def build_magnitude_witnesses(
    variables,
    gamma_block: RealPSDBlock,
) -> tuple[MagnitudeWitness, ...]:
    """Find a unit-diagonal gamma minor proving each ``|x_w| <= 2``."""
    if not isinstance(gamma_block, RealPSDBlock):
        raise TypeError("gamma_block must be a RealPSDBlock")
    unit = RationalLinearForm(Fraction(1))
    coordinates = {}
    for row in range(gamma_block.dimension):
        if gamma_block.entries[row][row] != unit:
            continue
        for column in range(gamma_block.dimension):
            if row == column:
                continue
            if gamma_block.entries[column][column] != unit:
                continue
            entry = gamma_block.entries[row][column]
            if entry.constant != 0 or len(entry.terms) != 1:
                continue
            variable, coefficient = entry.terms[0]
            if abs(coefficient) != Fraction(1, 2):
                continue
            coordinates.setdefault(
                variable,
                (
                    row,
                    column,
                    GaussianRational(2 * coefficient, Fraction(0)),
                ),
            )

    witnesses = []
    for variable in variables:
        if variable.index not in coordinates:
            raise ValueError(
                "moment variable has no PSD magnitude witness"
            )
        row, column, phase = coordinates[variable.index]
        witnesses.append(
            MagnitudeWitness(
                variable=variable.index,
                block=gamma_block.identifier,
                row=row,
                column=column,
                phase=phase,
                bound=Fraction(2),
            )
        )
    return tuple(witnesses)


def _localizer_equalities(
    functional: _InvariantMomentFunctional,
    support_rows,
    sandwich_rows,
) -> tuple[LinearEquality, ...]:
    equalities = []
    for row in support_rows:
        value = functional.polynomial(row.polynomial)
        provenance = {
            "localizer_kind": f"{row.side}-support",
            "site": row.site,
            "test_index": row.test_index,
        }
        prefix = (
            f"support-site-{row.site}-{row.side}"
            f"-test-{row.test_index}"
        )
        if not value.real.is_zero:
            equalities.append(
                LinearEquality(
                    f"{prefix}-real",
                    value.real,
                    {**provenance, "component": "real"},
                )
            )
        if not value.imag.is_zero:
            equalities.append(
                LinearEquality(
                    f"{prefix}-imag",
                    value.imag,
                    {**provenance, "component": "imag"},
                )
            )
    for row in sandwich_rows:
        value = functional.polynomial(row.polynomial)
        provenance = {
            "localizer_kind": "safe-sandwich",
            "site": row.site,
            "row": row.row,
            "column": row.column,
        }
        prefix = (
            f"safe-sandwich-site-{row.site}"
            f"-row-{row.row}-column-{row.column}"
        )
        if not value.real.is_zero:
            equalities.append(
                LinearEquality(
                    f"{prefix}-real",
                    value.real,
                    {**provenance, "component": "real"},
                )
            )
        if not value.imag.is_zero:
            equalities.append(
                LinearEquality(
                    f"{prefix}-imag",
                    value.imag,
                    {**provenance, "component": "imag"},
                )
            )
    identifiers = [row.identifier for row in equalities]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("localizer equality identifiers are not unique")
    return tuple(equalities)


def _affine_nonzeros(form: RationalLinearForm) -> int:
    return int(form.constant != 0) + len(form.terms)


def _assemble_problem(
    *,
    size: int,
    detuning: Fraction,
    hierarchy: str,
    moment_basis: tuple,
    safe_basis: tuple[SafeWord, ...],
    localizer_sites: tuple[int, ...],
    clique_orbits: tuple,
    clique_images: tuple,
    localizer_mode: str,
) -> KyFanProblem:
    if localizer_mode not in {"sound", "none"}:
        raise ValueError("localizer_mode must be 'sound' or 'none'")
    products = tuple(
        tuple(
            _moment_product(left, right)
            for right in moment_basis
        )
        for left in moment_basis
    )
    objective_polynomial = pxp_hamiltonian_polynomial(size, detuning)
    support_rows = build_support_localizers(
        size,
        moment_basis,
        localizer_sites,
    )
    sandwich_rows = build_safe_sandwich_localizers(
        size,
        safe_basis,
        localizer_sites,
    )
    registry_polynomials = [
        polynomial
        for row in products
        for polynomial in row
    ]
    registry_polynomials.append(objective_polynomial)
    registry_polynomials.extend(
        row.polynomial for row in support_rows
    )
    registry_polynomials.extend(
        row.polynomial for row in sandwich_rows
    )
    variables = _build_variable_registry(size, registry_polynomials)
    functional = _InvariantMomentFunctional(size, variables)

    gamma_matrix, complement_matrix = _normalized_moment_matrices(
        size,
        products,
        functional,
    )
    gamma_complex, gamma_real = _make_real_block(
        "gamma",
        gamma_matrix,
        {
            "normalization": "Tr(Gamma)=2",
            "scale": "1/2",
        },
    )
    complement_complex, complement_real = _make_real_block(
        "blockade-complement",
        complement_matrix,
        {
            "normalization": "Tr(Pi_K-Gamma)=kappa_N-2",
            "scale": (
                f"1/{periodic_blockade_dimension(size) - 2}"
            ),
        },
    )
    witnesses = build_magnitude_witnesses(
        variables,
        gamma_real,
    )

    objective = functional.polynomial(objective_polynomial)
    if not objective.imag.is_zero:
        raise ValueError("Ky Fan objective has a nonzero imaginary part")

    normalization = LinearEquality(
        identifier="trace-gamma-equals-2",
        form=RationalLinearForm(),
        provenance={
            "normalization": "ell(I)=2",
            "implementation": "identity moment eliminated exactly",
        },
    )
    sound_equalities = _localizer_equalities(
        functional,
        support_rows,
        sandwich_rows,
    )
    equalities = (
        (normalization, *sound_equalities)
        if localizer_mode == "sound"
        else (normalization,)
    )
    psd_blocks = (gamma_real, complement_real)
    unrealified = (gamma_complex, complement_complex)
    affine_nonzero_count = (
        _affine_nonzeros(objective.real)
        + sum(_affine_nonzeros(row.form) for row in equalities)
        + sum(
            _affine_nonzeros(entry)
            for block in psd_blocks
            for row in block.entries
            for entry in row
        )
    )
    statistics = {
        "moment_word_count": len(moment_basis),
        "moment_variable_count": len(variables),
        "equality_count": len(equalities),
        "support_localizer_count": (
            len(support_rows) if localizer_mode == "sound" else 0
        ),
        "safe_sandwich_count": (
            len(sandwich_rows) if localizer_mode == "sound" else 0
        ),
        "psd_block_dimensions": [
            block.dimension for block in psd_blocks
        ],
        "largest_real_psd_dimension": max(
            block.dimension for block in psd_blocks
        ),
        "affine_nonzero_count": affine_nonzero_count,
        "bounded_variable_count": len(witnesses),
        "dense_psd_payload_bytes": sum(
            8 * block.dimension**2 for block in psd_blocks
        ),
    }
    if (
        statistics["bounded_variable_count"]
        != statistics["moment_variable_count"]
    ):
        raise ValueError("not every moment variable is bounded")

    return KyFanProblem(
        size=size,
        detuning=detuning,
        hierarchy=hierarchy,
        localizer_mode=localizer_mode,
        moment_basis=moment_basis,
        safe_basis=safe_basis,
        variables=variables,
        objective=objective.real,
        equalities=tuple(equalities),
        psd_blocks=psd_blocks,
        unrealified_psd_blocks=unrealified,
        magnitude_witnesses=witnesses,
        clique_orbits=clique_orbits,
        clique_images=clique_images,
        localizer_sites=localizer_sites,
        provenance={
            "boundary": "periodic",
            "local_state_convention": "0=down, 1=up",
            "symmetry": "D_N group-averaged effect, all physical sectors",
            "localizer_mode": localizer_mode,
            "identity_moment": "ell(I)=2 eliminated exactly",
        },
        statistics=statistics,
    )


def _validate_problem_inputs(
    size: int,
    detuning: Fraction,
) -> tuple[int, Fraction]:
    size = int(size)
    if size < 4:
        raise ValueError("Ky Fan problem size must be at least 4")
    if not isinstance(detuning, Fraction):
        raise TypeError("detuning must be a Fraction")
    return size, detuning


def _blockade_site_image(
    element: DihedralElement,
    site: int,
    size: int,
) -> int:
    if element.reflected:
        return (element.shift - site - 1) % size
    return (element.shift + site) % size


def _representative_localizer_sites(
    size: int,
    start: int,
    range_sites: int,
) -> tuple[int, ...]:
    window = _window_sites(size, start, range_sites)
    window_set = set(window)
    internal = {
        site
        for site in range(size)
        if site in window_set and (site + 1) % size in window_set
    }
    stabilizer = tuple(
        element
        for element in dihedral_elements(size)
        if {
            act_on_site(element, site, size)
            for site in window
        }
        == window_set
    )
    unassigned = set(internal)
    representatives = []
    while unassigned:
        representative = min(unassigned)
        orbit = {
            _blockade_site_image(element, representative, size)
            for element in stabilizer
        } & internal
        representatives.append(representative)
        unassigned.difference_update(orbit)
    return tuple(representatives)


@lru_cache(maxsize=None)
def build_clique_images(
    size: int,
    start: int,
    level: HierarchyLevel,
) -> tuple[CliqueImage, ...]:
    """Export all D_N images and their exact complex-row permutations."""
    size = int(size)
    if size < 4:
        raise ValueError("Ky Fan problem size must be at least 4")
    if not isinstance(level, HierarchyLevel):
        raise TypeError("level must be a HierarchyLevel")
    start = int(start) % size
    basis = local_pauli_basis(size, start, level)
    window = _window_sites(size, start, level.range_sites)
    localizer_representatives = _representative_localizer_sites(
        size,
        start,
        level.range_sites,
    )
    images = []
    for element in dihedral_elements(size):
        transformed = tuple(
            act_on_word(element, word, size)
            for word in basis
        )
        image_basis = tuple(sorted(transformed))
        image_index = {
            word: index
            for index, word in enumerate(image_basis)
        }
        images.append(
            CliqueImage(
                shift=element.shift,
                reflected=element.reflected,
                sites=tuple(
                    sorted(
                        act_on_site(element, site, size)
                        for site in window
                    )
                ),
                representative_blocks=(
                    "gamma",
                    "blockade-complement",
                ),
                row_permutation=tuple(
                    image_index[word]
                    for word in transformed
                ),
                localizer_sites=tuple(
                    sorted(
                        {
                            _blockade_site_image(
                                element,
                                site,
                                size,
                            )
                            for site in localizer_representatives
                        }
                    )
                ),
            )
        )
    return tuple(images)


def _without_localizers(problem: KyFanProblem) -> KyFanProblem:
    normalization = tuple(
        row
        for row in problem.equalities
        if "localizer_kind" not in row.provenance
    )
    statistics = dict(problem.statistics)
    statistics.update(
        {
            "equality_count": len(normalization),
            "support_localizer_count": 0,
            "safe_sandwich_count": 0,
            "affine_nonzero_count": (
                _affine_nonzeros(problem.objective)
                + sum(
                    _affine_nonzeros(row.form)
                    for row in normalization
                )
                + sum(
                    _affine_nonzeros(entry)
                    for block in problem.psd_blocks
                    for row in block.entries
                    for entry in row
                )
            ),
        }
    )
    return replace(
        problem,
        localizer_mode="none",
        equalities=normalization,
        provenance={
            **problem.provenance,
            "localizer_mode": "none",
        },
        statistics=statistics,
    )


@lru_cache(maxsize=None)
def build_global_kyfan_problem(
    size: int,
    detuning: Fraction,
    max_weight: int,
    localizer_mode: str = "sound",
) -> KyFanProblem:
    """Build a full finite-N Pauli-basis Ky Fan moment problem."""
    size, detuning = _validate_problem_inputs(size, detuning)
    if localizer_mode == "none":
        return _without_localizers(
            build_global_kyfan_problem(
                size,
                detuning,
                max_weight,
                "sound",
            )
        )
    if localizer_mode != "sound":
        raise ValueError("localizer_mode must be 'sound' or 'none'")
    max_weight = int(max_weight)
    moment_basis = global_pauli_basis(size, max_weight)
    safe_level = HierarchyLevel(
        name=f"global-d{max_weight}-safe",
        range_sites=size,
        moment_weight=max_weight,
        safe_depth=1,
    )
    safe_basis = safe_localizer_basis(size, 0, safe_level)
    return _assemble_problem(
        size=size,
        detuning=detuning,
        hierarchy=f"global-d{max_weight}",
        moment_basis=moment_basis,
        safe_basis=safe_basis,
        localizer_sites=tuple(range(size)),
        clique_orbits=(clique_orbit(size, 0, size),),
        clique_images=build_clique_images(
            size,
            0,
            safe_level,
        ),
        localizer_mode=localizer_mode,
    )


def _window_sites(
    size: int,
    start: int,
    range_sites: int,
) -> tuple[int, ...]:
    width = min(size, range_sites)
    return tuple((start + offset) % size for offset in range(width))


@lru_cache(maxsize=None)
def build_local_kyfan_problem(
    size: int,
    detuning: Fraction,
    level: HierarchyLevel,
    localizer_mode: str = "sound",
) -> KyFanProblem:
    """Build one representative local-clique Ky Fan relaxation."""
    size, detuning = _validate_problem_inputs(size, detuning)
    if not isinstance(level, HierarchyLevel):
        raise TypeError("level must be a HierarchyLevel")
    if localizer_mode == "none":
        return _without_localizers(
            build_local_kyfan_problem(
                size,
                detuning,
                level,
                "sound",
            )
        )
    if localizer_mode != "sound":
        raise ValueError("localizer_mode must be 'sound' or 'none'")
    moment_basis = local_pauli_basis(size, 0, level)
    safe_basis = safe_localizer_basis(size, 0, level)
    localizer_sites = _representative_localizer_sites(
        size,
        0,
        level.range_sites,
    )
    return _assemble_problem(
        size=size,
        detuning=detuning,
        hierarchy=level.name,
        moment_basis=moment_basis,
        safe_basis=safe_basis,
        localizer_sites=localizer_sites,
        clique_orbits=(
            clique_orbit(size, 0, level.range_sites),
        ),
        clique_images=build_clique_images(size, 0, level),
        localizer_mode=localizer_mode,
    )

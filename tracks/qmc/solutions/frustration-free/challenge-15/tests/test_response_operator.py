from dataclasses import FrozenInstanceError, replace
from types import MappingProxyType

import numpy as np
import pytest
from scipy import sparse
from sympy import Rational
from sympy.physics.wigner import clebsch_gordan

import challenge15
from challenge15.chiral_source import (
    lhyr_pair_reduced_source,
    pair_source_tensor,
    planar_coulomb_reduced_amplitudes,
)
from challenge15.fermions import (
    DeterminantBasis,
    apply_annihilation,
    apply_creation,
)
from challenge15.response_operator import (
    ResponseFamily,
    adjoint_residual,
    build_response_family,
    monopole_reversal_matrix,
    monopole_reversal_residual,
    tensor_commutator_residuals,
)
from challenge15.spec import SphereSpec
from challenge15.two_body import assemble_two_body


def test_response_operator_stable_root_exports_preserve_identity():
    assert challenge15.ResponseFamily is ResponseFamily
    assert challenge15.build_response_family is build_response_family


def _brute_force_two_body(domain, codomain, tensor):
    count = domain.spec.orbital_count
    result = np.zeros(
        (codomain.dimension, domain.dimension),
        dtype=np.result_type(tensor.dtype, np.float64),
    )
    for column, state in enumerate(domain.states):
        for a in range(count):
            for b in range(count):
                for c in range(count):
                    for d in range(count):
                        coefficient = 0.5 * tensor[a, b, c, d]
                        if coefficient == 0.0:
                            continue
                        after_c = apply_annihilation(state, c)
                        if after_c is None:
                            continue
                        after_d = apply_annihilation(after_c.state, d)
                        if after_d is None:
                            continue
                        after_b = apply_creation(after_d.state, b)
                        if after_b is None:
                            continue
                        after_a = apply_creation(after_b.state, a)
                        if after_a is None:
                            continue
                        row = codomain.state_index.get(after_a.state)
                        if row is None:
                            continue
                        result[row, column] += (
                            coefficient
                            * after_c.sign
                            * after_d.sign
                            * after_b.sign
                            * after_a.sign
                        )
    return result


@pytest.mark.parametrize("particles", [2, 3])
@pytest.mark.parametrize("component_m", [-2, -1, 0, 1, 2])
def test_rectangular_two_body_assembler_matches_brute_force(
    particles, component_m
):
    spec = SphereSpec(particles)
    domain = DeterminantBasis.with_two_m(spec, 0)
    codomain = DeterminantBasis.with_two_m(spec, 2 * component_m)
    tensor = pair_source_tensor(
        lhyr_pair_reduced_source(spec, "-"), component_m
    )

    actual = assemble_two_body(domain, codomain, tensor)
    expected = _brute_force_two_body(domain, codomain, tensor)

    assert actual.format == "csr"
    assert actual.shape == (codomain.dimension, domain.dimension)
    np.testing.assert_allclose(actual.toarray(), expected, rtol=0.0, atol=1e-14)


def test_rectangular_assembler_validates_specs_shape_and_sector_shift():
    spec = SphereSpec(2)
    other_spec = SphereSpec(3)
    domain = DeterminantBasis.with_two_m(spec, 0)
    codomain = DeterminantBasis.with_two_m(spec, 2)
    tensor = pair_source_tensor(lhyr_pair_reduced_source(spec, "-"), 1)

    with pytest.raises(ValueError, match="SphereSpec"):
        assemble_two_body(
            domain,
            DeterminantBasis.with_two_m(other_spec, 2),
            tensor,
        )
    with pytest.raises(ValueError, match="shape"):
        assemble_two_body(domain, codomain, tensor[..., 0])
    with pytest.raises(ValueError, match="sector"):
        assemble_two_body(
            domain,
            DeterminantBasis.with_two_m(spec, 4),
            tensor,
        )


def test_response_family_builds_all_sealed_rectangular_components():
    spec = SphereSpec(3)
    family = build_response_family(spec, "-", orientation=-1)

    assert family.spec == spec
    assert family.orientation == -1
    assert family.helicity == "-"
    assert isinstance(family.components, MappingProxyType)
    assert set(family.components) == set(range(-2, 3))
    domain = DeterminantBasis.with_two_m(spec, 0)
    for component_m, matrix in family.components.items():
        codomain = DeterminantBasis.with_two_m(spec, 2 * component_m)
        expected = assemble_two_body(
            domain,
            codomain,
            pair_source_tensor(
                lhyr_pair_reduced_source(spec, "-", orientation=-1),
                component_m,
            ),
        )
        assert matrix.format == "csr"
        assert matrix.shape == (codomain.dimension, domain.dimension)
        assert (matrix != expected).nnz == 0

    with pytest.raises(TypeError):
        family.components[0] = sparse.csr_matrix((1, 1))
    with pytest.raises(FrozenInstanceError):
        family.helicity = "+"


@pytest.mark.parametrize(
    "keys",
    [
        [-2, -1, 0, 1],
        [-2, -1, 0, 1, 2, 3],
    ],
)
def test_response_family_rejects_missing_or_extra_components(keys):
    spec = SphereSpec(2)
    components = {key: sparse.csr_matrix((1, 1)) for key in keys}
    with pytest.raises(ValueError, match="components"):
        ResponseFamily(spec, 1, "-", components)


@pytest.mark.parametrize("invalid_key", [False, 0.0])
def test_response_family_rejects_non_integer_component_keys(invalid_key):
    spec = SphereSpec(2)
    components = {}
    for component_m in range(-2, 3):
        codomain = DeterminantBasis.with_two_m(spec, 2 * component_m)
        components[component_m] = sparse.csr_matrix(
            (
                codomain.dimension,
                DeterminantBasis.with_two_m(spec, 0).dimension,
            )
        )
    components[invalid_key] = components.pop(0)

    with pytest.raises(ValueError, match="components"):
        ResponseFamily(spec, 1, "-", components)


@pytest.mark.parametrize("particles", [2, 3, 4])
@pytest.mark.parametrize("helicity", ["+", "-"])
def test_rank_two_tensor_commutators_cover_all_five_components(
    particles, helicity
):
    residuals = tensor_commutator_residuals(
        build_response_family(SphereSpec(particles), helicity)
    )

    expected_keys = {
        f"{generator}[{component_m}]"
        for generator in ("lz", "lplus", "lminus")
        for component_m in range(-2, 3)
    }
    assert set(residuals) == expected_keys
    assert max(residuals.values()) <= 1e-10


@pytest.mark.parametrize("particles", [2, 3, 4])
def test_plus_minus_families_obey_spherical_adjoint(particles):
    spec = SphereSpec(particles)
    plus = build_response_family(spec, "+")
    minus = build_response_family(spec, "-")

    assert adjoint_residual(plus, minus) <= 1e-12


def _expected_monopole_reversal(spec, two_m):
    domain = DeterminantBasis.with_two_m(spec, two_m)
    codomain = DeterminantBasis.with_two_m(spec, -two_m)
    rows = []
    columns = []
    data = []
    for column, state in enumerate(domain.states):
        occupied = [
            orbital
            for orbital in range(spec.orbital_count)
            if state & (1 << orbital)
        ]
        reversed_occupied = [spec.two_q - orbital for orbital in occupied]
        reversed_state = sum(1 << orbital for orbital in reversed_occupied)
        orbital_phase = np.prod(
            [
                (-1) ** ((spec.two_q - spec.two_m_values[orbital]) // 2)
                for orbital in occupied
            ]
        )
        permutation_sign = (-1) ** (
            spec.particles * (spec.particles - 1) // 2
        )
        rows.append(codomain.state_index[reversed_state])
        columns.append(column)
        data.append(orbital_phase * permutation_sign)
    return sparse.csr_matrix(
        (data, (rows, columns)),
        shape=(codomain.dimension, domain.dimension),
    )


def _independent_positive_orientation_tensors(spec):
    pair_coefficients = {}

    def pair_state(total_j, total_m):
        key = (total_j, total_m)
        if key not in pair_coefficients:
            coefficients = np.zeros(
                (spec.orbital_count, spec.orbital_count),
                dtype=np.complex128,
            )
            for a, two_ma in enumerate(spec.two_m_values):
                for b, two_mb in enumerate(spec.two_m_values):
                    coefficients[a, b] = complex(
                        clebsch_gordan(
                            Rational(spec.two_q, 2),
                            Rational(spec.two_q, 2),
                            total_j,
                            Rational(two_ma, 2),
                            Rational(two_mb, 2),
                            total_m,
                        )
                    )
            pair_coefficients[key] = coefficients
        return pair_coefficients[key]

    minus = {}
    for component_m in range(-2, 3):
        tensor = np.zeros(
            (spec.orbital_count,) * 4,
            dtype=np.complex128,
        )
        for relative_m, amplitude in planar_coulomb_reduced_amplitudes(
            spec.two_q
        ):
            j_bra = spec.two_q - relative_m
            j_ket = j_bra - 2
            for m_ket in range(-j_ket, j_ket + 1):
                m_bra = m_ket + component_m
                if abs(m_bra) > j_bra:
                    continue
                rank_coefficient = complex(
                    clebsch_gordan(
                        j_ket,
                        2,
                        j_bra,
                        m_ket,
                        component_m,
                        m_bra,
                    )
                )
                tensor += amplitude * rank_coefficient * np.einsum(
                    "ab,cd->abcd",
                    pair_state(j_bra, m_bra),
                    pair_state(j_ket, m_ket),
                )
        tensor = 0.5 * (tensor - tensor.swapaxes(2, 3))
        tensor = 0.5 * (tensor - tensor.swapaxes(0, 1))
        minus[component_m] = tensor
    plus = {
        component_m: (-1) ** component_m
        * minus[-component_m].conj().transpose(2, 3, 0, 1)
        for component_m in range(-2, 3)
    }
    return {"+": plus, "-": minus}


def _independent_negative_orientation_tensor(
    spec,
    positive_tensors,
    helicity,
    component_m,
):
    opposite = "-" if helicity == "+" else "+"
    positive = positive_tensors[opposite][-component_m]
    orbital_phases = np.asarray(
        [
            (-1) ** ((spec.two_q - two_m) // 2)
            for two_m in spec.two_m_values
        ]
    )
    target_phases = orbital_phases[::-1]
    return (
        (-1) ** component_m
        * positive.conj()[::-1, ::-1, ::-1, ::-1]
        * np.einsum(
            "a,b,c,d->abcd",
            target_phases,
            target_phases,
            target_phases,
            target_phases,
        )
    )


def _synthetic_complex_reversal_families(*, conjugate, corrupt_component=None):
    spec = SphereSpec(3)
    domain = DeterminantBasis.with_two_m(spec, 0)
    positive_components = {}
    reversed_components = {}
    reversal_zero = _expected_monopole_reversal(spec, 0)
    for component_m in range(-2, 3):
        codomain = DeterminantBasis.with_two_m(spec, 2 * component_m)
        values = np.arange(
            codomain.dimension * domain.dimension,
            dtype=np.float64,
        ).reshape(codomain.dimension, domain.dimension)
        operator = sparse.csr_matrix(
            (1.0 + 0.2j * (component_m + 3)) * (values + 1.0)
        )
        positive_components[component_m] = operator
        transformed = (
            _expected_monopole_reversal(spec, 2 * component_m)
            @ (operator.conjugate() if conjugate else operator)
            @ reversal_zero.conj().T
        )
        reversed_components[-component_m] = (-1) ** component_m * transformed
    if corrupt_component is not None:
        reversed_components[corrupt_component] = (
            1j * reversed_components[corrupt_component]
        )
    return (
        ResponseFamily(spec, 1, "-", positive_components),
        ResponseFamily(spec, -1, "+", reversed_components),
    )


@pytest.mark.parametrize("particles", [2, 3, 4])
@pytest.mark.parametrize("two_m", [-4, -2, 0, 2, 4])
def test_monopole_reversal_lifts_orbital_phases_to_fixed_m_sectors(
    particles, two_m
):
    spec = SphereSpec(particles)

    actual = monopole_reversal_matrix(spec, two_m)
    expected = _expected_monopole_reversal(spec, two_m)

    assert actual.format == "csr"
    assert actual.shape == expected.shape
    assert (actual != expected).nnz == 0


def test_monopole_reversal_is_antiunitary_for_complex_families():
    positive, antiunitary_reversed = _synthetic_complex_reversal_families(
        conjugate=True
    )
    _, incorrectly_linear = _synthetic_complex_reversal_families(
        conjugate=False
    )

    assert (
        monopole_reversal_residual(positive, antiunitary_reversed) <= 1e-12
    )
    assert monopole_reversal_residual(positive, incorrectly_linear) > 1e-3


@pytest.mark.parametrize("component_m", [-2, -1, 0, 1, 2])
def test_negative_orientation_construction_conjugates_complex_coefficients(
    component_m,
):
    spec = SphereSpec(3)
    positive = lhyr_pair_reduced_source(spec, "-", orientation=1)
    complex_values = {
        channel: value * (1.0 + 0.25j * (index + 1))
        for index, (channel, value) in enumerate(positive.values.items())
    }
    positive = replace(positive, values=complex_values)
    negative = replace(positive, orientation=-1)
    positive_tensor = pair_source_tensor(positive, component_m)
    target_phases = np.asarray(
        [
            (-1) ** ((spec.two_q + two_m) // 2)
            for two_m in spec.two_m_values
        ]
    )
    expected = positive_tensor.transpose(2, 3, 0, 1)[
        ::-1, ::-1, ::-1, ::-1
    ] * np.einsum(
        "a,b,c,d->abcd",
        target_phases,
        target_phases,
        target_phases,
        target_phases,
    )

    np.testing.assert_allclose(
        pair_source_tensor(negative, component_m),
        expected,
        rtol=0.0,
        atol=1e-14,
    )


def test_monopole_reversal_detects_one_component_phase_corruption():
    positive, corrupted = _synthetic_complex_reversal_families(
        conjugate=True,
        corrupt_component=0,
    )

    assert monopole_reversal_residual(positive, corrupted) > 1e-3


@pytest.mark.parametrize("particles", [2, 3])
@pytest.mark.parametrize("helicity", ["+", "-"])
def test_negative_orientation_matches_independent_cg_car_oracle(
    particles, helicity
):
    spec = SphereSpec(particles)
    positive_tensors = _independent_positive_orientation_tensors(spec)
    actual = build_response_family(spec, helicity, orientation=-1)
    domain = DeterminantBasis.with_two_m(spec, 0)

    for component_m in range(-2, 3):
        codomain = DeterminantBasis.with_two_m(spec, 2 * component_m)
        expected_tensor = _independent_negative_orientation_tensor(
            spec,
            positive_tensors,
            helicity,
            component_m,
        )
        expected = _brute_force_two_body(
            domain,
            codomain,
            expected_tensor,
        )
        np.testing.assert_allclose(
            actual.components[component_m].toarray(),
            expected,
            rtol=0.0,
            atol=1e-13,
        )


@pytest.mark.parametrize("particles", [2, 3, 4])
@pytest.mark.parametrize("helicity", ["+", "-"])
def test_monopole_reversal_interchanges_full_response_families(
    particles, helicity
):
    spec = SphereSpec(particles)
    positive = build_response_family(spec, helicity, orientation=1)
    reversed_family = build_response_family(
        spec,
        "+" if helicity == "-" else "-",
        orientation=-1,
    )

    assert monopole_reversal_residual(positive, reversed_family) <= 1e-12

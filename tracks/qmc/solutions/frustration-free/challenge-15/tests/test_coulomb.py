import json
from itertools import combinations
from math import comb
from pathlib import Path

import numpy as np
import pytest
from scipy import sparse

from challenge15.angular import angular_operators
from challenge15.coulomb import (
    _full_product_pair_integral,
    _legal_transition_capacity,
    _raw_density_coulomb_tensor,
    density_multipole_integrals,
    many_body_coulomb,
    orbital_coulomb_tensor,
    pair_pseudopotentials,
    pseudopotential_coulomb_tensor,
)
from challenge15.fermions import (
    DeterminantBasis,
    apply_annihilation,
    apply_creation,
)
from challenge15.spec import SphereSpec


@pytest.mark.parametrize("particles", [2, 3, 4])
def test_independent_coulomb_builders_agree(particles):
    spec = SphereSpec(particles)
    direct = orbital_coulomb_tensor(spec)
    reduced = pseudopotential_coulomb_tensor(spec, pair_pseudopotentials(spec))
    np.testing.assert_allclose(direct, reduced, rtol=0.0, atol=1e-11)


def test_pair_route_does_not_call_density_route(monkeypatch):
    import challenge15.coulomb as coulomb

    def forbidden(*_args, **_kwargs):
        raise AssertionError("pair-channel route called the density route")

    monkeypatch.setattr(coulomb, "density_multipole_integrals", forbidden)
    monkeypatch.setattr(coulomb, "orbital_coulomb_tensor", forbidden)
    assert pair_pseudopotentials(SphereSpec(2))


def test_two_electron_levels_are_pair_angular_momentum_multiplets():
    spec = SphereSpec(2)
    values = pair_pseudopotentials(spec)
    assert set(values) == {
        j for j in range(0, spec.two_q + 1) if (spec.two_q - j) % 2 == 1
    }
    assert all(np.isfinite(list(values.values())))


@pytest.mark.parametrize("particles", [2, 3])
def test_density_monopole_is_identity_and_selection_rule_is_exact(particles):
    spec = SphereSpec(particles)
    multipoles = density_multipole_integrals(spec)
    np.testing.assert_allclose(
        multipoles[(0, 0)],
        np.eye(spec.orbital_count) / np.sqrt(4.0 * np.pi),
        rtol=0.0,
        atol=1e-14,
    )
    for (rank, q), matrix in multipoles.items():
        for row, two_m in enumerate(spec.two_m_values):
            for column, two_mp in enumerate(spec.two_m_values):
                if two_m - two_mp != 2 * q:
                    assert matrix[row, column] == 0.0


@pytest.mark.parametrize("particles", [2, 3])
def test_tensor_conventions_and_exchange_symmetries(particles):
    spec = SphereSpec(particles)
    tensor = orbital_coulomb_tensor(spec)
    np.testing.assert_allclose(tensor, tensor.transpose(1, 0, 2, 3) * -1.0, atol=1e-13)
    np.testing.assert_allclose(tensor, tensor.transpose(0, 1, 3, 2) * -1.0, atol=1e-13)
    np.testing.assert_allclose(tensor, tensor.transpose(2, 3, 0, 1).conj(), atol=1e-13)
    for a, ma in enumerate(spec.two_m_values):
        for b, mb in enumerate(spec.two_m_values):
            for c, mc in enumerate(spec.two_m_values):
                for d, md in enumerate(spec.two_m_values):
                    if ma + mb != mc + md:
                        assert tensor[a, b, c, d] == 0.0


@pytest.mark.parametrize("particles", [2, 3, 4])
def test_raw_tensor_trace_contains_exact_inverse_radius_factor(particles):
    spec = SphereSpec(particles)
    raw = _raw_density_coulomb_tensor(particles)
    distinguishable_trace = sum(
        raw[a, b, a, b]
        for a in range(spec.orbital_count)
        for b in range(spec.orbital_count)
    )
    np.testing.assert_allclose(
        distinguishable_trace / spec.orbital_count**2,
        1.0 / np.sqrt(spec.q),
        rtol=0.0,
        atol=2e-14,
    )


def test_n2_many_body_matrix_has_channel_eigenvalues_and_half_factor():
    spec = SphereSpec(2)
    basis = DeterminantBasis.full(spec)
    values = pair_pseudopotentials(spec)
    tensor = pseudopotential_coulomb_tensor(spec, values)
    matrix = many_body_coulomb(basis, tensor)
    assert matrix.format == "csr"
    expected = np.concatenate(
        [np.full(2 * j + 1, value, dtype=np.float64) for j, value in values.items()]
    )
    np.testing.assert_allclose(
        np.linalg.eigvalsh(matrix.toarray()),
        np.sort(expected),
        rtol=0.0,
        atol=2e-12,
    )


def test_n2_many_body_matrix_matches_independent_four_index_operator_loop():
    spec = SphereSpec(2)
    basis = DeterminantBasis.full(spec)
    tensor = orbital_coulomb_tensor(spec)
    assembled = many_body_coulomb(basis, tensor).toarray()
    brute_force = np.zeros_like(assembled)

    for column, state in enumerate(basis.states):
        for a in range(spec.orbital_count):
            for b in range(spec.orbital_count):
                for c in range(spec.orbital_count):
                    for d in range(spec.orbital_count):
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
                        row = basis.state_index.get(after_a.state)
                        if row is None:
                            continue
                        brute_force[row, column] += (
                            coefficient
                            * after_c.sign
                            * after_d.sign
                            * after_b.sign
                            * after_a.sign
                        )

    np.testing.assert_allclose(assembled, brute_force, rtol=0.0, atol=1e-14)


def _legacy_pair_substitution_matrix(basis, tensor):
    count = basis.spec.orbital_count
    grouped_pairs = {}
    for a, b in combinations(range(count), 2):
        pair_two_m = basis.spec.two_m_values[a] + basis.spec.two_m_values[b]
        grouped_pairs.setdefault(pair_two_m, []).append(
            (a, b, (1 << a) | (1 << b))
        )

    rows = []
    columns = []
    data = []
    for column, state in enumerate(basis.states):
        occupied = tuple(index for index in range(count) if state & (1 << index))
        for c, d in combinations(occupied, 2):
            after_c = apply_annihilation(state, c)
            assert after_c is not None
            after_d = apply_annihilation(after_c.state, d)
            assert after_d is not None
            source_two_m = basis.spec.two_m_values[c] + basis.spec.two_m_values[d]
            for a, b, pair_mask in grouped_pairs[source_two_m]:
                if after_d.state & pair_mask:
                    continue
                element = 2.0 * tensor[a, b, c, d]
                if element == 0.0:
                    continue
                after_b = apply_creation(after_d.state, b)
                assert after_b is not None
                after_a = apply_creation(after_b.state, a)
                assert after_a is not None
                row = basis.state_index.get(after_a.state)
                if row is None:
                    continue
                rows.append(row)
                columns.append(column)
                data.append(
                    element
                    * after_c.sign
                    * after_d.sign
                    * after_b.sign
                    * after_a.sign
                )
    matrix = sparse.csr_matrix(
        (np.asarray(data), (np.asarray(rows), np.asarray(columns))),
        shape=(basis.dimension, basis.dimension),
    )
    matrix.sum_duplicates()
    matrix.eliminate_zeros()
    return matrix


@pytest.mark.parametrize("particles", [2, 3])
def test_many_body_coulomb_is_bitwise_legacy_pair_assembly(particles):
    spec = SphereSpec(particles)
    basis = DeterminantBasis.full(spec)
    tensor = orbital_coulomb_tensor(spec)
    actual = many_body_coulomb(basis, tensor)
    expected = _legacy_pair_substitution_matrix(basis, tensor)

    assert np.array_equal(actual.indptr, expected.indptr)
    assert np.array_equal(actual.indices, expected.indices)
    assert np.array_equal(actual.data, expected.data)


def test_n8_capacity_counts_only_m_preserving_target_pairs():
    spec = SphereSpec(8)
    basis = DeterminantBasis.full(spec)
    legal_capacity = _legal_transition_capacity(basis)
    former_all_pairs_capacity = (
        basis.dimension
        * comb(spec.particles, 2)
        * comb(spec.orbital_count - spec.particles + 2, 2)
    )
    bytes_per_entry = (
        2 * np.dtype(np.int64).itemsize + np.dtype(np.float64).itemsize
    )

    assert legal_capacity == 35_500_080
    assert legal_capacity * bytes_per_entry < 1 * 2**30
    assert former_all_pairs_capacity * bytes_per_entry > 24 * 2**30
    assert former_all_pairs_capacity > 30 * legal_capacity


def test_many_body_coulomb_commutes_with_l2():
    spec = SphereSpec(3)
    basis = DeterminantBasis.full(spec)
    matrix = many_body_coulomb(basis, orbital_coulomb_tensor(spec))
    lz, lp, lm = angular_operators(basis)
    l2 = lm @ lp + lz @ (lz + sparse.identity(basis.dimension, format="csr"))
    commutator = matrix @ l2 - l2 @ matrix
    scale = max(np.linalg.norm(matrix.toarray()) * np.linalg.norm(l2.toarray()), 1.0)
    assert np.linalg.norm(commutator.toarray()) / scale < 1e-10


def test_pair_pseudopotential_fixture():
    fixture_path = Path(__file__).with_name("fixtures") / "coulomb_n2.json"
    fixture = json.loads(fixture_path.read_text())
    spec = SphereSpec(2)
    assert fixture["two_q"] == spec.two_q
    values = pair_pseudopotentials(spec)
    assert fixture["allowed_j"] == list(values)
    np.testing.assert_allclose(
        [values[j] for j in values],
        fixture["v_j_over_ec"],
        rtol=0.0,
        atol=5e-14,
    )


def test_low_q_full_product_quadrature_is_m_independent():
    spec = SphereSpec(2)
    expected = pair_pseudopotentials(spec)
    for total_j, value in expected.items():
        by_m = [
            _full_product_pair_integral(
                spec,
                total_j,
                total_m,
                polar_order=32,
                azimuth_order=128,
            )
            for total_m in range(-total_j, total_j + 1)
        ]
        assert max(by_m) - min(by_m) < 2e-6
        np.testing.assert_allclose(by_m, value, rtol=0.0, atol=5e-6)

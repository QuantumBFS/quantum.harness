from __future__ import annotations

import jax
import numpy as np
import pytest
from scipy.linalg import expm
from scipy.special import eval_legendre

import challenge15.carriers as carriers_module
import challenge15.oracle as oracle_module
from challenge15.fermions import DeterminantBasis
from challenge15.model import ModelConfig, ProjectedPfaffianNQS
from challenge15.monopole import raw_north_lll_polynomials
from challenge15.oracle import solve_target_sectors
from challenge15.pfaffian import bordered_pfaffian, pfaffian
from challenge15.spec import SphereSpec


@pytest.fixture(scope="module")
def trained_n4():
    spec = SphereSpec(4)
    config = ModelConfig(rank=3, hidden_width=10, depth=1, token_width=5)
    model = ProjectedPfaffianNQS(config)
    spinors = np.asarray(
        [
            [1.0, 0.2j],
            [0.7, 0.3 - 0.1j],
            [0.4 + 0.2j, 0.8],
            [0.1 - 0.3j, 0.9],
        ],
        dtype=np.complex128,
    )
    return model.init(jax.random.key(801), spec, spinors, target_l=0)


@pytest.fixture(scope="module")
def oracle_n4():
    return solve_target_sectors(SphereSpec(4))


@pytest.fixture(scope="module")
def metrics_n4(trained_n4, oracle_n4):
    return oracle_module.evaluate_exact_nqs(SphereSpec(4), trained_n4, oracle_n4)


def _random_spinors(particles: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    spinors = rng.normal(size=(particles, 2)) + 1j * rng.normal(
        size=(particles, 2)
    )
    return spinors / np.linalg.norm(spinors, axis=1, keepdims=True)


def _determinant_row(spec: SphereSpec, spinors: np.ndarray) -> np.ndarray:
    basis = DeterminantBasis.with_two_m(spec, 0)
    orbitals = np.asarray(raw_north_lll_polynomials(spinors, spec))
    return np.asarray(
        [
            np.linalg.det(
                orbitals[
                    :,
                    [
                        orbital
                        for orbital in range(spec.orbital_count)
                        if state & (1 << orbital)
                    ],
                ]
            )
            for state in basis.states
        ],
        dtype=np.complex128,
    )


def _phase_aligned_distance(reference: np.ndarray, candidate: np.ndarray) -> float:
    first = np.asarray(reference, dtype=np.complex128)
    second = np.asarray(candidate, dtype=np.complex128)
    first /= np.linalg.norm(first)
    second /= np.linalg.norm(second)
    overlap = np.vdot(first, second)
    if overlap:
        second *= np.exp(-1j * np.angle(overlap))
    return float(np.linalg.norm(first - second))


def _model_carriers(model, variables, spec, target_l):
    weights, borders = model.apply(
        variables,
        spec,
        target_l,
        method=model._reduced_carriers,
    )
    gate_components = np.asarray(variables["params"]["carrier_gates"])
    gates = gate_components[:, 0] + 1j * gate_components[:, 1]
    return np.asarray(weights), np.asarray(borders), gates


def test_exact_metrics_distinguish_energy_overlap_and_true_variance(
    metrics_n4,
):
    metrics = metrics_n4

    assert metrics.norm_l0 > 0
    assert metrics.norm_l2 > 0
    assert 0 <= metrics.overlap_l0 <= 1
    assert 0 <= metrics.overlap_l2 <= 1
    assert metrics.h_variance_l0 >= 0
    assert metrics.h_variance_l2 >= 0
    assert metrics.bare_potential_sampling_variance is None
    assert metrics.energy_l0 != pytest.approx(metrics.overlap_l0)
    assert metrics.h_variance_l0 != pytest.approx(metrics.l2_variance_l0)


def test_exact_metrics_use_stored_eigensystem_without_hidden_eigensolve(
    monkeypatch, trained_n4, oracle_n4
):
    def forbidden_eigh(*_args, **_kwargs):
        raise AssertionError("evaluate_exact_nqs must not diagonalize")

    monkeypatch.setattr(oracle_module.np.linalg, "eigh", forbidden_eigh)
    metrics = oracle_module.evaluate_exact_nqs(SphereSpec(4), trained_n4, oracle_n4)

    for target_l, energy, variance, overlap in (
        (0, metrics.energy_l0, metrics.h_variance_l0, metrics.overlap_l0),
        (2, metrics.energy_l2, metrics.h_variance_l2, metrics.overlap_l2),
    ):
        sector = oracle_n4.exact_sector(target_l)
        state = metrics.normalized_sector_coefficients(target_l)
        image = sector.hamiltonian @ state
        expected_energy = float(np.vdot(state, image).real)
        expected_variance = float(
            np.vdot(image - expected_energy * state, image - expected_energy * state).real
        )
        expected_overlap = float(abs(np.vdot(sector.eigenvectors[:, 0], state)) ** 2)
        assert energy == pytest.approx(expected_energy, abs=2e-13)
        assert variance == pytest.approx(expected_variance, abs=2e-13)
        assert overlap == pytest.approx(expected_overlap, abs=2e-13)


def test_projected_span_rank_and_quadrature_stability_are_auditable(
    metrics_n4, oracle_n4
):
    metrics = metrics_n4

    for target_l in (0, 2):
        singular_values = metrics.projected_carrier_relative_singular_values(target_l)
        assert singular_values.ndim == 1
        assert np.all(singular_values[:-1] >= singular_values[1:])
        if singular_values.size:
            assert singular_values[0] == pytest.approx(1.0)
        expected_rank = int(np.count_nonzero(singular_values > 1e-10))
        assert metrics.projected_span_rank(target_l) == expected_rank
        assert metrics.projected_span_complete(target_l) is (
            expected_rank == oracle_n4.exact_sector(target_l).isometry.shape[1]
        )

    assert metrics.quadrature_coefficient_relative_change_l0 <= 1e-11
    assert metrics.quadrature_coefficient_relative_change_l2 <= 1e-11
    assert metrics.quadrature_energy_relative_change_l0 <= 1e-11
    assert metrics.quadrature_energy_relative_change_l2 <= 1e-11
    assert metrics.quadrature_coefficient_relative_change_l0 >= 0
    assert metrics.quadrature_coefficient_relative_change_l2 >= 0
    for minimal, doubled in (
        metrics.quadrature_orders_l0,
        metrics.quadrature_orders_l2,
    ):
        assert doubled == (2 * minimal[0], 2 * minimal[1])


@pytest.mark.parametrize("particles", [2, 3])
def test_exact_coefficients_match_direct_pointwise_model_projection(
    particles,
):
    spec = SphereSpec(particles)
    basis = DeterminantBasis.with_two_m(spec, 0)
    model = ProjectedPfaffianNQS(
        ModelConfig(rank=2, hidden_width=9, depth=1, token_width=4)
    )
    initial = _random_spinors(particles, 900 + particles)
    variables = model.init(jax.random.key(910 + particles), spec, initial, target_l=0)
    oracle = solve_target_sectors(spec)
    metrics = oracle_module.evaluate_exact_nqs(spec, variables, oracle, block_size=3)

    rows = []
    points = []
    for index in range(4 * basis.dimension):
        point = _random_spinors(particles, 1000 + 20 * particles + index)
        candidate_rows = np.asarray(rows + [_determinant_row(spec, point)])
        if np.linalg.matrix_rank(candidate_rows, tol=1e-11) > len(rows):
            rows.append(candidate_rows[-1])
            points.append(point)
        if len(rows) == basis.dimension:
            break
    evaluation = np.asarray(rows)
    assert evaluation.shape == (basis.dimension, basis.dimension)
    assert np.linalg.matrix_rank(evaluation, tol=1e-11) == basis.dimension

    for target_l in (0, 2):
        sector = oracle.exact_sector(target_l)
        coefficients = (
            sector.isometry @ metrics.normalized_sector_coefficients(target_l)
        )
        reconstructed = evaluation @ coefficients
        direct = np.asarray(
            [
                model.apply(variables, spec, point, target_l=target_l)
                for point in points
            ]
        )
        assert _phase_aligned_distance(reconstructed, direct) < 2e-10


def test_projected_carrier_gram_is_independently_reconstructed(
    trained_n4, oracle_n4, metrics_n4
):
    spec = SphereSpec(4)
    model = ProjectedPfaffianNQS(
        ModelConfig(rank=3, hidden_width=10, depth=1, token_width=5)
    )
    metrics = metrics_n4
    for target_l in (0, 2):
        weights, borders, _ = _model_carriers(
            model, trained_n4, spec, target_l
        )
        raw_columns = np.asarray(
            carriers_module.carrier_determinant_coefficients(
                spec, weights, border_weight=borders, block_size=4
            )
        ).T
        projected_columns = (
            oracle_n4.exact_sector(target_l).isometry.conj().T @ raw_columns
        )
        gram = projected_columns.conj().T @ projected_columns
        singular_values = np.linalg.svd(gram, compute_uv=False)
        relative = singular_values / singular_values[0]
        production = (
            metrics.carrier_gram_singular_values_l0
            if target_l == 0
            else metrics.carrier_gram_singular_values_l2
        )
        np.testing.assert_allclose(production, singular_values, rtol=2e-11, atol=2e-13)
        np.testing.assert_allclose(
            metrics.projected_carrier_relative_singular_values(target_l),
            relative,
            rtol=2e-11,
            atol=2e-13,
        )
        assert metrics.projected_span_rank(target_l) == int(
            np.count_nonzero(relative > 1e-10)
        )


def test_independent_quadrature_oracle_detects_perturbed_rotation(
    trained_n4, metrics_n4, oracle_n4
):
    spec = SphereSpec(4)
    target_l = 2
    model = ProjectedPfaffianNQS(
        ModelConfig(rank=3, hidden_width=10, depth=1, token_width=5)
    )
    weights, borders, gates = _model_carriers(
        model, trained_n4, spec, target_l
    )
    minimal_beta = (spec.l_max + target_l + 2) // 2
    minimal = _independent_quadrature_coefficients(
        spec, weights, borders, gates, target_l, minimal_beta
    )
    doubled = _independent_quadrature_coefficients(
        spec, weights, borders, gates, target_l, 2 * minimal_beta
    )
    stable_change = _phase_aligned_distance(minimal, doubled)
    sector = oracle_n4.exact_sector(target_l)
    exact = sector.isometry @ metrics_n4.normalized_sector_coefficients(target_l)
    assert _phase_aligned_distance(exact, minimal) < 2e-10
    assert stable_change == pytest.approx(
        metrics_n4.quadrature_coefficient_relative_change_l2,
        abs=3e-12,
    )
    assert stable_change <= 1e-11
    minimal_energy = _sector_energy(sector, minimal)
    doubled_energy = _sector_energy(sector, doubled)
    independent_energy_change = abs(doubled_energy - minimal_energy) / max(
        abs(minimal_energy), 1.0
    )
    assert independent_energy_change == pytest.approx(
        metrics_n4.quadrature_energy_relative_change_l2,
        abs=3e-12,
    )

    perturbed = _independent_quadrature_coefficients(
        spec,
        weights,
        borders,
        gates,
        target_l,
        minimal_beta,
        perturb_rotation=True,
    )
    assert _phase_aligned_distance(minimal, perturbed) > 1e-11


def test_quadrature_blocks_are_fixed_width_padded_and_masked():
    spec = SphereSpec(4)
    blocks = tuple(
        oracle_module._iter_padded_quadrature_blocks(
            spec, n_beta=5, block_size=3
        )
    )

    assert len(blocks) == 2
    assert all(block.indices.shape == (3,) for block in blocks)
    assert all(block.nodes.shape == (3,) for block in blocks)
    assert all(block.weights.shape == (3,) for block in blocks)
    assert all(
        block.rotations.shape == (3, spec.orbital_count, spec.orbital_count)
        for block in blocks
    )
    assert all(block.valid.shape == (3,) for block in blocks)
    assert [index for block in blocks for index in block.indices[block.valid]] == [
        0,
        1,
        2,
        3,
        4,
    ]
    np.testing.assert_array_equal(blocks[-1].valid, [True, True, False])
    assert blocks[-1].weights[-1] == 0.0


def test_n8_quadrature_path_is_block_bounded_without_square_allocation(
    monkeypatch,
):
    spec = SphereSpec(8)
    basis = DeterminantBasis.with_two_m(spec, 0)
    determinant_block = 257
    carrier_block = 2
    quadrature_block = 3
    seen_determinant_widths = []
    seen_carrier_widths = []
    seen_quadrature_shapes = []
    original_allocators = {
        name: getattr(oracle_module.np, name)
        for name in ("empty", "full", "ones", "zeros")
    }
    original_quadrature_blocks = oracle_module._iter_padded_quadrature_blocks

    def guarded_allocator(name):
        def allocate(shape, *args, **kwargs):
            if shape == (basis.dimension, basis.dimension):
                raise AssertionError("full determinant-space square allocation")
            return original_allocators[name](shape, *args, **kwargs)

        return allocate

    def observed_quadrature_blocks(_spec, n_beta, block_size):
        for block in original_quadrature_blocks(_spec, n_beta, block_size):
            seen_quadrature_shapes.append(
                (
                    block.nodes.shape,
                    block.rotations.shape,
                    block.valid.shape,
                )
            )
            yield block

    def fake_coefficients(
        _spec,
        pair_matrices,
        _border_vectors,
        states,
    ):
        width = len(states)
        seen_determinant_widths.append(width)
        seen_carrier_widths.append(pair_matrices.shape[0])
        values = np.zeros(
            (pair_matrices.shape[0], width), dtype=np.complex128
        )
        values[:, 0] = 1.0
        return values

    for name in original_allocators:
        monkeypatch.setattr(
            oracle_module.np, name, guarded_allocator(name)
        )
    monkeypatch.setattr(
        oracle_module,
        "_numpy_pfaffian_coefficients",
        fake_coefficients,
    )
    monkeypatch.setattr(
        oracle_module,
        "_iter_padded_quadrature_blocks",
        observed_quadrature_blocks,
    )
    channel_count = sum(two_m > 0 for two_m in spec.two_m_values)
    result = oracle_module._quadrature_projected_coefficients(
        spec,
        np.ones((1, channel_count), dtype=np.complex128),
        np.ones(1, dtype=np.complex128),
        np.ones(1, dtype=np.complex128),
        target_l=0,
        n_alpha=3,
        n_beta=5,
        determinant_block=determinant_block,
        carrier_block=carrier_block,
        quadrature_block=quadrature_block,
    )
    assert result.shape == (basis.dimension,)
    assert seen_determinant_widths
    assert max(seen_determinant_widths) <= determinant_block
    assert set(seen_carrier_widths) == {carrier_block}
    assert sum(seen_determinant_widths) == 5 * basis.dimension
    assert seen_quadrature_shapes
    assert all(
        node_shape == (quadrature_block,)
        and rotation_shape
        == (quadrature_block, spec.orbital_count, spec.orbital_count)
        and valid_shape == (quadrature_block,)
        for node_shape, rotation_shape, valid_shape in seen_quadrature_shapes
    )


def test_mocked_n8_complete_acceptance_path_avoids_determinant_square(
    monkeypatch,
):
    spec = SphereSpec(8)
    basis = DeterminantBasis.with_two_m(spec, 0)
    dimension = basis.dimension
    rank = 2
    determinant_block = 257
    isometry = np.zeros((dimension, 1), dtype=np.complex128)
    isometry[0, 0] = 1.0

    def sector(target_l, energy):
        return oracle_module.ExactSectorEigensystem(
            angular_momentum=target_l,
            isometry=isometry,
            hamiltonian=np.asarray([[energy]], dtype=np.complex128),
            l2_operator=np.asarray(
                [[target_l * (target_l + 1)]], dtype=np.complex128
            ),
            eigenvalues=np.asarray([energy], dtype=np.float64),
            eigenvectors=np.asarray([[1.0]], dtype=np.complex128),
        )

    oracle = oracle_module.OracleResult(
        solver_mode="mocked-n8-shape",
        spec=spec,
        sectors=(),
        energy_l0=1.0,
        energy_l2=2.0,
        gap=1.0,
        residual_l0=0.0,
        residual_l2=0.0,
        mean_l2_l0=0.0,
        mean_l2_l2=6.0,
        l2_variance_l0=0.0,
        l2_variance_l2=0.0,
        l2_target_deviation_squared_l0=0.0,
        l2_target_deviation_squared_l2=0.0,
        absolute_excitation_energy=None,
        absolute_excitation_gap=None,
        absolute_excitation_l=None,
        m_zero_dimension=dimension,
        pair_channels=(),
        array_hash_items=(),
        source_hash_items=(),
        package_version_items=(),
        git_revision="mocked",
        exact_sectors=(sector(0, 1.0), sector(2, 2.0)),
        sparse_symmetry_diagnostics=(),
        low_energy_states=(),
        dense_diagnostics=None,
        m_zero_hamiltonian=None,
        m_zero_l2=None,
    )
    channel_count = sum(two_m > 0 for two_m in spec.two_m_values)
    gates = np.asarray([1.0, 0.5], dtype=np.complex128)
    pair_weights = np.ones(
        (rank, channel_count), dtype=np.complex128
    )
    borders = np.ones(rank, dtype=np.complex128)
    seen_widths = []
    seen_gram_shapes = []
    original_allocators = {
        name: getattr(oracle_module.np, name)
        for name in ("empty", "full", "ones", "zeros")
    }
    original_svd = oracle_module.np.linalg.svd

    def guarded_allocator(name):
        def allocate(shape, *args, **kwargs):
            if shape == (dimension, dimension):
                raise AssertionError("full determinant-space square allocation")
            return original_allocators[name](shape, *args, **kwargs)

        return allocate

    def fake_model_carriers(_spec, _parameters):
        return gates, {
            0: (pair_weights, borders),
            2: (pair_weights, borders),
        }

    def fake_coefficients(_spec, pair_matrices, _border_vectors, states):
        seen_widths.append(len(states))
        return np.ones(
            (pair_matrices.shape[0], len(states)), dtype=np.complex128
        )

    def fake_quadrature(*_args, **_kwargs):
        coefficients = np.zeros(dimension, dtype=np.complex128)
        coefficients[0] = 1.0
        return coefficients

    def observed_svd(matrix, *args, **kwargs):
        seen_gram_shapes.append(matrix.shape)
        return original_svd(matrix, *args, **kwargs)

    for name in original_allocators:
        monkeypatch.setattr(
            oracle_module.np, name, guarded_allocator(name)
        )
    monkeypatch.setattr(
        oracle_module, "_model_reduced_carriers", fake_model_carriers
    )
    monkeypatch.setattr(
        oracle_module, "_numpy_pfaffian_coefficients", fake_coefficients
    )
    monkeypatch.setattr(
        oracle_module, "_quadrature_projected_coefficients", fake_quadrature
    )
    monkeypatch.setattr(oracle_module.np.linalg, "svd", observed_svd)

    metrics = oracle_module.evaluate_exact_nqs(
        spec,
        {"params": {}},
        oracle,
        determinant_block=determinant_block,
        carrier_block=rank,
        quadrature_block=3,
    )

    assert metrics.projected_span_dimension_l0 == 1
    assert metrics.projected_span_dimension_l2 == 1
    assert seen_widths
    assert max(seen_widths) <= determinant_block
    assert sum(seen_widths) == 2 * dimension
    assert seen_gram_shapes == [(rank, rank), (rank, rank)]


def test_carrier_coefficients_stream_in_bounded_determinant_blocks():
    spec = SphereSpec(4)
    basis = DeterminantBasis.with_two_m(spec, 0)
    channel_count = sum(two_m > 0 for two_m in spec.two_m_values)
    weights = np.ones((2, channel_count), dtype=np.complex128)
    blocks = list(
        carriers_module.iter_carrier_determinant_coefficient_blocks(
            spec,
            weights,
            border_weight=np.ones(2),
            states=basis.states,
            block_size=5,
        )
    )

    assert sum(block.shape[1] for block in blocks) == basis.dimension
    assert all(block.shape[0] == 2 for block in blocks)
    assert all(block.shape[1] <= 5 for block in blocks)


def _independent_quadrature_coefficients(
    spec,
    weights,
    borders,
    gates,
    target_l,
    n_beta,
    *,
    perturb_rotation=False,
):
    basis = DeterminantBasis.with_two_m(spec, 0)
    nodes, quadrature_weights = np.polynomial.legendre.leggauss(n_beta)
    result = np.zeros(basis.dimension, dtype=np.complex128)
    jy = _single_particle_jy(spec)
    orbital_pairs = [
        np.asarray(carriers_module._orbital_pair_matrix(spec, carrier))
        for carrier in weights
    ]
    zero_orbital = (
        spec.two_m_values.index(0) if spec.particles % 2 else None
    )
    border_vectors = []
    for border in borders:
        vector = np.zeros(spec.orbital_count, dtype=np.complex128)
        if zero_orbital is not None:
            vector[zero_orbital] = border
        border_vectors.append(vector)

    for node_index, (node, weight) in enumerate(
        zip(nodes, quadrature_weights, strict=True)
    ):
        beta = np.arccos(node)
        rotation = expm(-1j * beta * jy)
        if perturb_rotation and node_index == 0:
            rotation = rotation.copy()
            rotation[0, 0] += 0.05
        kernel = (2 * target_l + 1) / 2 * weight * eval_legendre(target_l, node)
        for carrier_index, pair_matrix in enumerate(orbital_pairs):
            rotated_pair = rotation @ pair_matrix @ rotation.T
            rotated_border = rotation @ border_vectors[carrier_index]
            for determinant_index, state in enumerate(basis.states):
                occupied = [
                    orbital
                    for orbital in range(spec.orbital_count)
                    if state & (1 << orbital)
                ]
                restricted = rotated_pair[np.ix_(occupied, occupied)]
                if spec.particles % 2:
                    coefficient = bordered_pfaffian(
                        restricted, rotated_border[occupied]
                    )
                else:
                    coefficient = pfaffian(restricted)
                result[determinant_index] += (
                    kernel * gates[carrier_index] * complex(coefficient)
                )
    result /= np.linalg.norm(result)
    return result


def _single_particle_jy(spec):
    dimension = spec.orbital_count
    raising = np.zeros((dimension, dimension), dtype=np.complex128)
    for column, two_m in enumerate(spec.two_m_values[:-1]):
        m = two_m / 2
        raising[column + 1, column] = np.sqrt(
            spec.q * (spec.q + 1) - m * (m + 1)
        )
    return (raising - raising.conj().T) / (2j)


def _sector_energy(sector, coefficients):
    projected = sector.isometry.conj().T @ coefficients
    projected /= np.linalg.norm(projected)
    return float(np.vdot(projected, sector.hamiltonian @ projected).real)

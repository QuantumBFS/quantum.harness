from math import sqrt

import jax.numpy as jnp
import numpy as np
import pytest
from scipy.linalg import expm

import challenge15
from challenge15.angular import _ladder_matrix, angular_operators, target_irrep_isometry
from challenge15.fermions import DeterminantBasis
from challenge15.monopole import raw_north_lll_polynomials
from challenge15.projector import ProjectionGrid, project_m0, project_multiplet
from challenge15.spec import SphereSpec


def test_projector_interfaces_are_publicly_exported():
    assert challenge15.ProjectionGrid is ProjectionGrid
    assert challenge15.project_m0 is project_m0
    assert challenge15.project_multiplet is project_multiplet


def _random_spinors(particles: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    spinors = rng.normal(size=(particles, 2)) + 1j * rng.normal(size=(particles, 2))
    return spinors / np.linalg.norm(spinors, axis=-1, keepdims=True)


def _determinant_amplitude(spec: SphereSpec, basis: DeterminantBasis, coefficients):
    occupied = tuple(
        tuple(
            orbital
            for orbital in range(spec.orbital_count)
            if state & (1 << orbital)
        )
        for state in basis.states
    )
    coefficients_array = jnp.asarray(coefficients, dtype=jnp.complex128)

    def evaluate(spinors):
        orbitals = raw_north_lll_polynomials(spinors, spec)
        determinants = jnp.stack(
            [jnp.linalg.det(orbitals[:, jnp.asarray(indices)]) for indices in occupied]
        )
        return jnp.dot(coefficients_array, determinants)

    return evaluate


def _evaluate_coefficients(
    spinors: np.ndarray,
    spec: SphereSpec,
    basis: DeterminantBasis,
    coefficients: np.ndarray,
) -> complex:
    return complex(_determinant_amplitude(spec, basis, coefficients)(spinors))


def _determinant_evaluation_matrix(
    spinor_points: tuple[np.ndarray, ...],
    spec: SphereSpec,
    basis: DeterminantBasis,
) -> np.ndarray:
    occupied = tuple(
        tuple(
            orbital
            for orbital in range(spec.orbital_count)
            if state & (1 << orbital)
        )
        for state in basis.states
    )
    rows = []
    for spinors in spinor_points:
        orbitals = np.asarray(raw_north_lll_polynomials(spinors, spec))
        rows.append(
            [np.linalg.det(orbitals[:, np.asarray(indices)]) for indices in occupied]
        )
    return np.asarray(rows, dtype=np.complex128)


@pytest.mark.parametrize("particles,target_l", [(4, 0), (4, 2), (6, 0), (6, 2)])
def test_grid_satisfies_exact_bandlimit(particles, target_l):
    spec = SphereSpec(particles)
    grid = ProjectionGrid.exact(spec, target_l)
    assert grid.n_alpha >= 2 * spec.l_max + 1
    assert 2 * grid.n_beta - 1 >= spec.l_max + target_l
    assert grid.alpha_nodes.dtype == np.float64
    assert grid.beta_nodes.dtype == np.float64
    assert grid.alpha_weights.dtype == np.complex128
    assert grid.beta_weights.dtype == np.complex128
    assert abs(grid.alpha_weights.sum() - 2 * np.pi) < 1e-13
    assert abs(grid.beta_weights.sum() - 2.0) < 1e-13
    assert not grid.alpha_nodes.flags.writeable
    assert not grid.alpha_weights.flags.writeable
    assert not grid.beta_nodes.flags.writeable
    assert not grid.beta_weights.flags.writeable
    with pytest.raises(ValueError):
        grid.alpha_nodes[0] = 0.1
    with pytest.raises(ValueError):
        grid.alpha_nodes.setflags(write=True)


@pytest.mark.parametrize("target_l", [0, 2])
def test_beta_rule_is_an_exact_legendre_projector(target_l):
    spec = SphereSpec(6)
    grid = ProjectionGrid.exact(spec, target_l)
    p_target = np.polynomial.legendre.Legendre.basis(target_l)(grid.beta_nodes)
    for source_l in range(spec.l_max + 1):
        p_source = np.polynomial.legendre.Legendre.basis(source_l)(grid.beta_nodes)
        projected = (2 * target_l + 1) / 2 * np.sum(
            grid.beta_weights * p_target * p_source
        )
        np.testing.assert_allclose(
            projected, float(source_l == target_l), atol=2e-12
        )


def test_periodic_rule_has_every_required_fourier_orthogonality():
    spec = SphereSpec(6)
    grid = ProjectionGrid.exact(spec, 2)
    for mode in range(-2 * spec.l_max, 2 * spec.l_max + 1):
        value = np.sum(grid.alpha_weights * np.exp(1j * mode * grid.alpha_nodes))
        expected = 2 * np.pi if mode == 0 else 0.0
        np.testing.assert_allclose(value, expected, atol=2e-12, rtol=0.0)


def _canonical_custom_grid(
    spec: SphereSpec,
    target_l: int,
    *,
    extra_alpha: int = 2,
    extra_beta: int = 2,
) -> ProjectionGrid:
    n_alpha = 2 * spec.l_max + 1 + extra_alpha
    n_beta = (spec.l_max + target_l + 2) // 2 + extra_beta
    alpha_nodes = np.arange(n_alpha, dtype=np.float64) * (2 * np.pi / n_alpha)
    alpha_weights = np.full(n_alpha, 2 * np.pi / n_alpha, dtype=np.complex128)
    beta_nodes, beta_weights = np.polynomial.legendre.leggauss(n_beta)
    beta_nodes = np.asarray(beta_nodes, dtype=np.float64)
    beta_weights = np.asarray(beta_weights, dtype=np.complex128)
    for array in (alpha_nodes, alpha_weights, beta_nodes, beta_weights):
        array.setflags(write=False)
    return ProjectionGrid(
        alpha_nodes=alpha_nodes,
        alpha_weights=alpha_weights,
        beta_nodes=beta_nodes,
        beta_weights=beta_weights,
        target_l=target_l,
        l_max=spec.l_max,
    )


def _grid_arguments(grid: ProjectionGrid) -> dict[str, object]:
    return {
        "alpha_nodes": grid.alpha_nodes.copy(),
        "alpha_weights": grid.alpha_weights.copy(),
        "beta_nodes": grid.beta_nodes.copy(),
        "beta_weights": grid.beta_weights.copy(),
        "target_l": grid.target_l,
        "l_max": grid.l_max,
    }


def _freeze_grid_arguments(arguments: dict[str, object]) -> None:
    for name in ("alpha_nodes", "alpha_weights", "beta_nodes", "beta_weights"):
        arguments[name].setflags(write=False)


def test_larger_canonical_grid_matches_minimal_projection():
    spec = SphereSpec(2)
    basis = DeterminantBasis.with_two_m(spec, 0)
    coefficients = np.array([0.3 + 0.8j, -0.5 + 0.1j])
    amplitude = _determinant_amplitude(spec, basis, coefficients)
    spinors = _random_spinors(spec.particles, 77)
    larger = _canonical_custom_grid(spec, 2)
    minimal_value = project_m0(amplitude, spinors, spec, 2, block_size=5)
    larger_value = project_m0(
        amplitude, spinors, spec, 2, grid=larger, block_size=5
    )
    np.testing.assert_allclose(larger_value, minimal_value, atol=2e-12, rtol=2e-12)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda args: args.update(alpha_nodes=args["alpha_nodes"][:-1]), "matching"),
        (
            lambda args: args.update(alpha_nodes=args["alpha_nodes"].astype(np.float32)),
            "float64",
        ),
        (
            lambda args: args.update(alpha_weights=args["alpha_weights"].astype(np.complex64)),
            "complex128",
        ),
        (
            lambda args: args["alpha_nodes"].__setitem__(0, np.nan),
            "finite",
        ),
        (
            lambda args: args["alpha_nodes"].__setitem__(1, args["alpha_nodes"][0]),
            "equispaced",
        ),
        (
            lambda args: args["alpha_weights"].__setitem__(0, 0.0),
            "periodic",
        ),
        (
            lambda args: args["beta_nodes"].__setitem__(0, args["beta_nodes"][0] + 1e-4),
            "Gauss-Legendre",
        ),
        (
            lambda args: args["beta_weights"].__setitem__(0, args["beta_weights"][0] + 1e-4),
            "Gauss-Legendre",
        ),
    ],
)
def test_projection_grid_rejects_malformed_exact_rules(mutation, message):
    canonical = _canonical_custom_grid(SphereSpec(2), 2)
    arguments = _grid_arguments(canonical)
    mutation(arguments)
    _freeze_grid_arguments(arguments)
    with pytest.raises(ValueError, match=message):
        ProjectionGrid(**arguments)


def test_projection_grid_rejects_mutable_arrays():
    canonical = _canonical_custom_grid(SphereSpec(2), 2)
    arguments = _grid_arguments(canonical)
    with pytest.raises(ValueError, match="immutable"):
        ProjectionGrid(**arguments)


def test_block_iterator_is_lazy_and_peak_storage_is_block_bounded():
    block_size = 17
    peak_bytes = []
    total_nodes = []
    for particles in (2, 6):
        grid = ProjectionGrid.exact(SphereSpec(particles), 2)
        consumed = 0
        maximum_bytes = 0
        maximum_live_size = 0
        for block in grid.iter_blocks(block_size=block_size):
            consumed += block.size
            maximum_live_size = max(maximum_live_size, block.size)
            maximum_bytes = max(
                maximum_bytes,
                sum(
                    array.nbytes
                    for array in (
                        block.alpha_indices,
                        block.beta_indices,
                        block.alpha_nodes,
                        block.beta_nodes,
                        block.weights,
                    )
                ),
            )
        assert consumed == grid.n_alpha * grid.n_beta
        assert maximum_live_size <= block_size
        assert maximum_bytes <= block_size * (8 + 8 + 8 + 8 + 16)
        peak_bytes.append(maximum_bytes)
        total_nodes.append(grid.n_alpha * grid.n_beta)
        assert not hasattr(grid, "rotations")
    assert total_nodes[1] > 10 * total_nodes[0]
    assert peak_bytes[1] == peak_bytes[0]


@pytest.mark.parametrize("particles,target_l", [(2, 0), (2, 2), (3, 2), (4, 0), (4, 2)])
def test_coordinate_projector_matches_occupation_projector(particles, target_l):
    spec = SphereSpec(particles)
    basis = DeterminantBasis.with_two_m(spec, 0)
    rng = np.random.default_rng(100 * particles + target_l)
    coefficients = rng.normal(size=basis.dimension) + 1j * rng.normal(
        size=basis.dimension
    )
    isometry = target_irrep_isometry(basis, target_l)
    expected_coefficients = isometry @ (isometry.conj().T @ coefficients)
    spinors = _random_spinors(particles, 200 * particles + target_l)

    projected = project_m0(
        _determinant_amplitude(spec, basis, coefficients),
        spinors,
        spec,
        target_l,
        block_size=13,
    )
    expected = _evaluate_coefficients(spinors, spec, basis, expected_coefficients)
    np.testing.assert_allclose(projected, expected, rtol=1e-10, atol=2e-12)


def test_pure_wrong_irrep_is_annihilated():
    spec = SphereSpec(2)
    basis = DeterminantBasis.with_two_m(spec, 0)
    wrong_irrep = target_irrep_isometry(basis, 2)[:, 0]
    spinors = _random_spinors(spec.particles, 303)
    projected = project_m0(
        _determinant_amplitude(spec, basis, wrong_irrep),
        spinors,
        spec,
        target_l=0,
        block_size=5,
    )
    assert abs(projected) < 1e-11


def _ladder_multiplet(
    spec: SphereSpec, m_zero_coefficients: np.ndarray, target_l: int
) -> dict[int, tuple[DeterminantBasis, np.ndarray]]:
    basis_zero = DeterminantBasis.with_two_m(spec, 0)
    result = {0: (basis_zero, np.asarray(m_zero_coefficients))}

    basis = basis_zero
    vector = np.asarray(m_zero_coefficients)
    for m in range(0, target_l):
        next_basis = DeterminantBasis.with_two_m(spec, 2 * (m + 1))
        factor = sqrt(target_l * (target_l + 1) - m * (m + 1))
        vector = np.asarray(_ladder_matrix(basis, next_basis, 1) @ vector) / factor
        result[m + 1] = (next_basis, vector)
        basis = next_basis

    basis = basis_zero
    vector = np.asarray(m_zero_coefficients)
    for m in range(0, -target_l, -1):
        next_basis = DeterminantBasis.with_two_m(spec, 2 * (m - 1))
        factor = sqrt(target_l * (target_l + 1) - m * (m - 1))
        vector = np.asarray(_ladder_matrix(basis, next_basis, -1) @ vector) / factor
        result[m - 1] = (next_basis, vector)
        basis = next_basis
    return result


def test_direct_multiplet_matches_ladders_with_equal_norms():
    spec = SphereSpec(3)
    basis = DeterminantBasis.with_two_m(spec, 0)
    rng = np.random.default_rng(404)
    coefficients = rng.normal(size=basis.dimension) + 1j * rng.normal(
        size=basis.dimension
    )
    isometry = target_irrep_isometry(basis, 2)
    projected_zero = isometry @ (isometry.conj().T @ coefficients)
    ladder = _ladder_multiplet(spec, projected_zero, 2)
    point_count = 2 * max(sector_basis.dimension for sector_basis, _ in ladder.values())
    spinor_points = tuple(
        _random_spinors(spec.particles, 405 + point)
        for point in range(point_count)
    )
    direct_at_points = [
        project_multiplet(
            _determinant_amplitude(spec, basis, coefficients),
            spinors,
            spec,
            target_l=2,
            block_size=11,
        )
        for spinors in spinor_points
    ]

    assert tuple(direct_at_points[0]) == (-2, -1, 0, 1, 2)
    for m in range(-2, 3):
        sector_basis, sector_coefficients = ladder[m]
        evaluation = _determinant_evaluation_matrix(
            spinor_points, spec, sector_basis
        )
        assert np.linalg.matrix_rank(evaluation, tol=1e-11) == sector_basis.dimension
        direct_values = np.asarray(
            [point_values[m] for point_values in direct_at_points],
            dtype=np.complex128,
        )
        reconstructed, _, rank, _ = np.linalg.lstsq(
            evaluation, direct_values, rcond=1e-12
        )
        assert rank == sector_basis.dimension
        np.testing.assert_allclose(
            reconstructed, sector_coefficients, rtol=2e-10, atol=2e-11
        )
        np.testing.assert_allclose(
            direct_values,
            evaluation @ sector_coefficients,
            rtol=1e-10,
            atol=2e-12,
        )
    norms = [np.linalg.norm(ladder[m][1]) for m in range(-2, 3)]
    np.testing.assert_allclose(norms, norms[0], rtol=2e-12, atol=2e-12)


def test_multiplet_obeys_random_finite_rotation_covariance():
    spec = SphereSpec(2)
    basis = DeterminantBasis.with_two_m(spec, 0)
    coefficients = np.array([0.7 - 0.2j, -0.4 + 0.9j])
    amplitude = _determinant_amplitude(spec, basis, coefficients)
    spinors = _random_spinors(spec.particles, 505)
    axis = np.array([0.3, -0.4, 0.5])
    axis /= np.linalg.norm(axis)
    angle = 0.73
    pauli = np.array(
        [
            [[0, 1], [1, 0]],
            [[0, -1j], [1j, 0]],
            [[1, 0], [0, -1]],
        ],
        dtype=np.complex128,
    )
    rotation = expm(-0.5j * angle * np.einsum("a,aij->ij", axis, pauli))
    rotated_spinors = np.einsum("ab,ib->ia", rotation.conj().T, spinors)

    values = project_multiplet(amplitude, spinors, spec, 2, block_size=7)
    rotated_values = project_multiplet(
        amplitude, rotated_spinors, spec, 2, block_size=7
    )
    m_values = np.arange(-2, 3)
    jz = np.diag(m_values)
    jp = np.zeros((5, 5), dtype=np.complex128)
    for column, m in enumerate(m_values[:-1]):
        jp[column + 1, column] = sqrt(6 - m * (m + 1))
    jx = (jp + jp.conj().T) / 2
    jy = (jp - jp.conj().T) / (2j)
    representation = expm(
        -1j * angle * (axis[0] * jx + axis[1] * jy + axis[2] * jz)
    )
    expected = representation.conj().T @ np.array(tuple(values.values()))
    np.testing.assert_allclose(
        np.array(tuple(rotated_values.values())),
        expected,
        rtol=2e-10,
        atol=2e-11,
    )


@pytest.mark.parametrize("block_size", [0, -1, True])
def test_projection_rejects_invalid_block_sizes(block_size):
    spec = SphereSpec(2)
    with pytest.raises(ValueError, match="block_size"):
        project_m0(lambda spinors: jnp.sum(spinors), np.ones((2, 2)), spec, 0, block_size=block_size)

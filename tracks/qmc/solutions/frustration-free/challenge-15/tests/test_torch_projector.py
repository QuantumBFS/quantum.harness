from __future__ import annotations

from math import sqrt
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest
from scipy.linalg import expm

torch = pytest.importorskip("torch")

from challenge15.carriers import carrier_amplitudes as jax_carrier_amplitudes
from challenge15.fermions import DeterminantBasis
from challenge15.projection_data import ProjectionGrid, StaticProjectionBlocks
from challenge15.projector import (
    project_m0 as jax_project_m0,
)
from challenge15.projector import (
    project_multiplet as jax_project_multiplet,
)
from challenge15.spec import SphereSpec
from challenge15.torch_carriers import (
    carrier_amplitudes,
    raw_north_lll_polynomials,
)
from challenge15.torch_projector import (
    project_carrier_block,
    project_m0,
    project_multiplet,
)

jax.config.update("jax_enable_x64", True)

RTOL = 2e-10
ATOL = 2e-11
MODULE_PATH = Path(__file__).parents[1] / "src" / "challenge15" / "torch_projector.py"
FROZEN_M0 = {
    (2, 0): -0.000375859214018865 - 0.00014094720525707237j,
    (2, 2): -0.02486770787834968 - 0.024759592317936084j,
    (3, 0): -2.8332122896344305e-09 - 1.170748891441472e-11j,
    (3, 2): -5.494990785110461e-07 - 2.2887394916842391e-07j,
    (4, 0): 2.7883795228019533e-18 + 1.270495157833267e-17j,
    (4, 2): 1.2332159738926293e-15 + 5.524085454745951e-15j,
}
FROZEN_N2_MULTIPLET = {
    -2: -0.02434827947609123 - 0.028091304088664323j,
    -1: -0.03172882822789727 - 0.03395325079882604j,
    0: -0.02486770787834968 - 0.024759592317936084j,
    1: -0.012759538467864715 - 0.011855200161935362j,
    2: -0.003941338579425158 - 0.003425576652632271j,
}


def _parity_case(
    particles: int,
) -> tuple[np.ndarray, np.ndarray, np.complex128]:
    spec = SphereSpec(particles)
    base = np.arange(1, 2 * particles + 1, dtype=np.float64).reshape(particles, 2)
    spinors = np.asarray(base + 1j * (base[::-1] * 0.125 - 0.3), dtype=np.complex128)
    spinors /= np.linalg.norm(spinors, axis=-1, keepdims=True)
    channel_count = sum(two_m > 0 for two_m in spec.two_m_values)
    channels = np.arange(1, channel_count + 1)
    weights = np.asarray(
        channels * (0.3 + 0.2j) + np.arange(channel_count)[::-1] * (-0.1 + 0.05j),
        dtype=np.complex128,
    )
    return spinors, weights, np.complex128(-0.7 + 0.4j)


def _random_case(
    particles: int, seed: int
) -> tuple[np.ndarray, np.ndarray, np.complex128]:
    spec = SphereSpec(particles)
    rng = np.random.default_rng(seed)
    spinors = np.asarray(
        rng.normal(size=(particles, 2)) + 1j * rng.normal(size=(particles, 2)),
        dtype=np.complex128,
    )
    channel_count = sum(two_m > 0 for two_m in spec.two_m_values)
    weights = np.asarray(
        rng.normal(size=channel_count) + 1j * rng.normal(size=channel_count),
        dtype=np.complex128,
    )
    border = np.complex128(rng.normal() + 1j * rng.normal())
    return spinors, weights, border


def _torch_amplitude(spec, weights, border):
    weights_tensor = torch.as_tensor(weights, dtype=torch.complex128)
    border_tensor = torch.as_tensor(border, dtype=torch.complex128)

    def evaluate(spinors):
        return carrier_amplitudes(
            spinors,
            spec,
            weights_tensor.to(spinors.device),
            border_tensor.to(spinors.device),
        )

    return evaluate


def _jax_amplitude(spec, weights, border):
    weights_array = jnp.asarray(weights, dtype=jnp.complex128)

    def evaluate(spinors):
        return jax_carrier_amplitudes(spinors, spec, weights_array, border)

    return evaluate


def _larger_grid(spec: SphereSpec, target_l: int) -> ProjectionGrid:
    n_alpha = 2 * spec.l_max + 3
    n_beta = (spec.l_max + target_l + 2) // 2 + 2
    alpha_nodes = np.arange(n_alpha, dtype=np.float64) * (2 * np.pi / n_alpha)
    alpha_weights = np.full(n_alpha, 2 * np.pi / n_alpha, dtype=np.complex128)
    beta_nodes, beta_weights = np.polynomial.legendre.leggauss(n_beta)
    arrays = (
        alpha_nodes,
        alpha_weights,
        np.asarray(beta_nodes, dtype=np.float64),
        np.asarray(beta_weights, dtype=np.complex128),
    )
    for value in arrays:
        value.setflags(write=False)
    return ProjectionGrid(*arrays, target_l=target_l, l_max=spec.l_max)


@pytest.mark.parametrize("particles", [2, 3, 4])
@pytest.mark.parametrize("target_l", [0, 2])
def test_exact_grid_matches_frozen_and_independent_jax_values(particles, target_l):
    spec = SphereSpec(particles)
    spinors, weights, border = _parity_case(particles)
    actual = project_m0(
        _torch_amplitude(spec, weights, border),
        torch.tensor(spinors),
        spec,
        target_l,
        block_size=7,
    )
    expected = jax_project_m0(
        _jax_amplitude(spec, weights, border),
        jnp.asarray(spinors),
        spec,
        target_l,
        block_size=7,
    )
    assert actual.dtype == torch.complex128
    assert actual.device == torch.tensor(spinors).device
    np.testing.assert_allclose(actual.detach().numpy(), expected, rtol=RTOL, atol=ATOL)
    np.testing.assert_allclose(
        actual.detach().numpy(), FROZEN_M0[particles, target_l], rtol=RTOL, atol=ATOL
    )


@pytest.mark.parametrize("particles", [2, 3, 4])
@pytest.mark.parametrize("target_l", [0, 2])
def test_larger_exact_grid_and_block_layouts_preserve_projection(particles, target_l):
    spec = SphereSpec(particles)
    spinors, weights, border = _random_case(particles, 1000 + 10 * particles + target_l)
    amplitude = _torch_amplitude(spec, weights, border)
    values = [
        project_m0(
            amplitude,
            torch.tensor(spinors),
            spec,
            target_l,
            grid=grid,
            block_size=block_size,
        )
        for grid in (ProjectionGrid.exact(spec, target_l), _larger_grid(spec, target_l))
        for block_size in (1, 7, 64)
    ]
    for value in values[1:]:
        torch.testing.assert_close(value, values[0], rtol=RTOL, atol=ATOL)


def test_full_multiplet_matches_frozen_and_independent_jax_values():
    spec = SphereSpec(2)
    spinors, weights, border = _parity_case(2)
    actual = project_multiplet(
        _torch_amplitude(spec, weights, border),
        torch.tensor(spinors),
        spec,
        2,
        block_size=7,
    )
    expected = jax_project_multiplet(
        _jax_amplitude(spec, weights, border),
        jnp.asarray(spinors),
        spec,
        2,
        block_size=7,
    )
    assert tuple(actual) == (-2, -1, 0, 1, 2)
    for m in actual:
        np.testing.assert_allclose(
            actual[m].detach().numpy(), expected[m], rtol=RTOL, atol=ATOL
        )
        np.testing.assert_allclose(
            actual[m].detach().numpy(), FROZEN_N2_MULTIPLET[m], rtol=RTOL, atol=ATOL
        )


def test_wrong_irrep_is_annihilated_exactly_within_quadrature_tolerance():
    spec = SphereSpec(2)
    spinors, _, _ = _random_case(2, 1202)

    def scalar_amplitude(value):
        return torch.ones((), dtype=torch.complex128, device=value.device)

    projected = project_multiplet(
        scalar_amplitude, torch.tensor(spinors), spec, 2, block_size=7
    )
    for value in projected.values():
        assert abs(value.item()) < 2e-11


def test_multiplet_obeys_finite_su2_rotation_covariance():
    spec = SphereSpec(2)
    spinors, weights, border = _random_case(2, 1302)
    amplitude = _torch_amplitude(spec, weights, border)
    axis = np.asarray([0.3, -0.4, 0.5], dtype=np.float64)
    axis /= np.linalg.norm(axis)
    angle = 0.73
    pauli = np.asarray(
        [[[0, 1], [1, 0]], [[0, -1j], [1j, 0]], [[1, 0], [0, -1]]],
        dtype=np.complex128,
    )
    rotation = expm(-0.5j * angle * np.einsum("a,aij->ij", axis, pauli))
    rotated_spinors = np.einsum("ab,ib->ia", rotation.conj().T, spinors)
    values = project_multiplet(amplitude, torch.tensor(spinors), spec, 2, block_size=7)
    rotated = project_multiplet(
        amplitude, torch.tensor(rotated_spinors), spec, 2, block_size=7
    )
    m_values = np.arange(-2, 3)
    jz = np.diag(m_values)
    jp = np.zeros((5, 5), dtype=np.complex128)
    for column, m in enumerate(m_values[:-1]):
        jp[column + 1, column] = sqrt(6 - m * (m + 1))
    jx = (jp + jp.conj().T) / 2
    jy = (jp - jp.conj().T) / (2j)
    representation = expm(-1j * angle * (axis[0] * jx + axis[1] * jy + axis[2] * jz))
    expected = representation.conj().T @ np.asarray(tuple(values.values()))
    np.testing.assert_allclose(
        np.asarray([value.detach().numpy() for value in rotated.values()]),
        expected,
        rtol=RTOL,
        atol=ATOL,
    )


def test_reconstructed_multiplet_components_have_equal_hilbert_norms():
    spec = SphereSpec(3)
    source_basis = DeterminantBasis.with_two_m(spec, 0)
    rng = np.random.default_rng(1353)
    coefficients = np.asarray(
        rng.normal(size=source_basis.dimension)
        + 1j * rng.normal(size=source_basis.dimension),
        dtype=np.complex128,
    )
    occupied = tuple(
        tuple(
            orbital for orbital in range(spec.orbital_count) if state & (1 << orbital)
        )
        for state in source_basis.states
    )
    coefficient_tensor = torch.tensor(coefficients)

    def amplitude(spinors):
        orbitals = raw_north_lll_polynomials(spinors, spec)
        determinants = torch.stack(
            [
                torch.linalg.det(
                    orbitals.index_select(
                        1, torch.tensor(indices, device=spinors.device)
                    )
                )
                for indices in occupied
            ]
        )
        return torch.dot(coefficient_tensor.to(spinors.device), determinants)

    sector_bases = {m: DeterminantBasis.with_two_m(spec, 2 * m) for m in range(-2, 3)}
    point_count = 2 * max(basis.dimension for basis in sector_bases.values())
    points = tuple(
        _random_case(spec.particles, 1360 + index)[0] for index in range(point_count)
    )
    projected = [
        project_multiplet(amplitude, torch.tensor(point), spec, 2, block_size=7)
        for point in points
    ]
    norms = []
    for m, basis in sector_bases.items():
        sector_occupied = tuple(
            tuple(
                orbital
                for orbital in range(spec.orbital_count)
                if state & (1 << orbital)
            )
            for state in basis.states
        )
        evaluation = []
        for point in points:
            orbitals = raw_north_lll_polynomials(torch.tensor(point), spec)
            evaluation.append(
                [
                    torch.linalg.det(orbitals[:, indices]).detach().numpy()
                    for indices in sector_occupied
                ]
            )
        matrix = np.asarray(evaluation, dtype=np.complex128)
        values = np.asarray(
            [components[m].detach().numpy() for components in projected]
        )
        reconstructed, _, rank, _ = np.linalg.lstsq(matrix, values, rcond=1e-12)
        assert rank == basis.dimension
        norms.append(np.linalg.norm(reconstructed))
    np.testing.assert_allclose(norms, norms[0], rtol=2e-10, atol=2e-11)


def test_carrier_block_supports_walkers_carriers_zero_masks_and_layouts():
    spec = SphereSpec(3)
    first_spinors, first_weights, first_border = _random_case(3, 1403)
    second_spinors, _, _ = _random_case(3, 1404)
    walkers = torch.tensor(np.stack((first_spinors, second_spinors)))
    weights = torch.tensor(
        np.stack((first_weights, 0.25j * first_weights, np.zeros_like(first_weights)))
    )
    borders = torch.tensor([first_border, -0.3 + 0.2j, 0.0])
    outputs = [
        project_carrier_block(
            walkers,
            spec,
            weights,
            borders,
            target_l=2,
            quadrature_block=block,
        )
        for block in (1, 7, 64)
    ]
    assert outputs[0].shape == (2, 3)
    assert outputs[0].dtype == torch.complex128
    torch.testing.assert_close(outputs[0][:, 2], torch.zeros(2, dtype=torch.complex128))
    for output in outputs[1:]:
        torch.testing.assert_close(output, outputs[0], rtol=RTOL, atol=ATOL)
    expected = torch.stack(
        [
            torch.stack(
                [
                    project_m0(
                        _torch_amplitude(spec, weight, border),
                        walker,
                        spec,
                        2,
                        block_size=7,
                    )
                    for weight, border in zip(weights, borders, strict=True)
                ]
            )
            for walker in walkers
        ]
    )
    torch.testing.assert_close(outputs[1], expected, rtol=RTOL, atol=ATOL)


class _PoisonedGrid:
    def __init__(self, base: ProjectionGrid):
        self.target_l = base.target_l
        self.l_max = base.l_max
        self.n_alpha = base.n_alpha
        self.n_beta = base.n_beta
        self._base = base

    def static_blocks(self, block_size: int) -> StaticProjectionBlocks:
        blocks = self._base.static_blocks(block_size)
        alpha = blocks.alpha_nodes.copy()
        beta = blocks.beta_nodes.copy()
        weights = blocks.weights.copy()
        invalid = ~blocks.node_valid
        alpha[invalid] = np.nan
        beta[invalid] = np.nan
        weights[invalid] = np.nan + 1j * np.nan
        return StaticProjectionBlocks(
            alpha, beta, weights, blocks.node_valid, blocks.tree_valid
        )


def test_padded_nan_and_garbage_nodes_are_masked_before_arithmetic():
    spec = SphereSpec(2)
    spinors, weights, border = _random_case(2, 1502)
    grid = ProjectionGrid.exact(spec, 2)
    clean = project_m0(
        _torch_amplitude(spec, weights, border),
        torch.tensor(spinors),
        spec,
        2,
        grid=grid,
        block_size=7,
    )
    poisoned = project_m0(
        _torch_amplitude(spec, weights, border),
        torch.tensor(spinors),
        spec,
        2,
        grid=_PoisonedGrid(grid),
        block_size=7,
    )
    assert torch.isfinite(poisoned)
    torch.testing.assert_close(poisoned, clean, rtol=0.0, atol=0.0)


def test_noncontiguous_inputs_and_reverse_mode_and_jvp_are_supported():
    spec = SphereSpec(2)
    spinors, weights, border = _random_case(2, 1602)
    storage = torch.empty((2, 4), dtype=torch.complex128)
    storage[:, ::2] = torch.tensor(spinors)
    noncontiguous = storage[:, ::2].requires_grad_()
    assert not noncontiguous.is_contiguous()
    amplitude = _torch_amplitude(spec, weights, border)
    value = project_m0(amplitude, noncontiguous, spec, 2, block_size=7)
    gradient = torch.autograd.grad(value.real, noncontiguous)[0]
    assert gradient.shape == noncontiguous.shape
    assert torch.all(torch.isfinite(gradient))
    tangent = torch.full_like(noncontiguous, 0.03 - 0.02j)
    _, derivative = torch.func.jvp(
        lambda x: project_m0(amplitude, x, spec, 2, block_size=7),
        (noncontiguous.detach(),),
        (tangent,),
    )
    epsilon = 1e-5
    finite_difference = (
        project_m0(
            amplitude,
            noncontiguous.detach() + epsilon * tangent,
            spec,
            2,
            block_size=7,
        )
        - project_m0(
            amplitude,
            noncontiguous.detach() - epsilon * tangent,
            spec,
            2,
            block_size=7,
        )
    ) / (2 * epsilon)
    torch.testing.assert_close(derivative, finite_difference, rtol=2e-7, atol=2e-8)


@pytest.mark.parametrize("target_l", [-1, 4, True, 1.0])
def test_invalid_target_l_is_rejected(target_l):
    spec = SphereSpec(2)
    spinors, weights, border = _random_case(2, 1702)
    with pytest.raises(ValueError, match="target_l"):
        project_m0(
            _torch_amplitude(spec, weights, border),
            torch.tensor(spinors),
            spec,
            target_l,
        )


def test_multiplet_validates_target_before_constructing_component_range():
    spec = SphereSpec(2)
    spinors, weights, border = _random_case(2, 1752)
    with pytest.raises(ValueError, match="target_l"):
        project_multiplet(
            _torch_amplitude(spec, weights, border),
            torch.tensor(spinors),
            spec,
            1.5,
        )


@pytest.mark.parametrize("block_size", [0, -1, True, 1.5])
def test_invalid_block_size_is_rejected(block_size):
    spec = SphereSpec(2)
    spinors, weights, border = _random_case(2, 1802)
    with pytest.raises(ValueError, match="block_size"):
        project_m0(
            _torch_amplitude(spec, weights, border),
            torch.tensor(spinors),
            spec,
            0,
            block_size=block_size,
        )


def test_mismatched_grid_is_rejected():
    spec = SphereSpec(2)
    spinors, weights, border = _random_case(2, 1902)
    grid = ProjectionGrid.exact(spec, 2)
    with pytest.raises(ValueError, match="grid"):
        project_m0(
            _torch_amplitude(spec, weights, border),
            torch.tensor(spinors),
            spec,
            0,
            grid=grid,
        )


@pytest.mark.parametrize(
    ("spinors", "message"),
    [
        (np.ones((2, 2), dtype=np.complex128), "torch.Tensor"),
        (torch.ones((2, 2), dtype=torch.complex64), "complex128"),
        (torch.ones((2, 3), dtype=torch.complex128), "shape"),
        (torch.ones((1, 2, 2), dtype=torch.complex128), "shape"),
    ],
)
def test_invalid_spinor_type_dtype_and_shape_are_rejected(spinors, message):
    spec = SphereSpec(2)
    _, weights, border = _random_case(2, 2002)
    with pytest.raises((TypeError, ValueError), match=message):
        project_m0(_torch_amplitude(spec, weights, border), spinors, spec, 0)


def test_amplitude_wrong_dtype_shape_and_device_are_rejected():
    spec = SphereSpec(2)
    spinors, _, _ = _random_case(2, 2102)
    tensor = torch.tensor(spinors)
    with pytest.raises(TypeError, match="complex128"):
        project_m0(lambda value: value.real.sum(), tensor, spec, 0)
    with pytest.raises(ValueError, match="scalar"):
        project_m0(lambda value: value[:, 0], tensor, spec, 0)
    if torch.cuda.is_available():
        with pytest.raises(ValueError, match="same device"):
            project_m0(
                lambda value: torch.ones((), dtype=torch.complex128),
                tensor.to("cuda"),
                spec,
                0,
            )


def test_carrier_block_rejects_invalid_shapes_dtypes_devices_and_blocks():
    spec = SphereSpec(3)
    spinors, weights, border = _random_case(3, 2203)
    walkers = torch.tensor(spinors)[None]
    bank = torch.tensor(weights)[None]
    with pytest.raises(ValueError, match="walkers"):
        project_carrier_block(
            walkers[0],
            spec,
            bank,
            torch.tensor([border]),
            target_l=0,
            quadrature_block=7,
        )
    with pytest.raises(ValueError, match="carrier"):
        project_carrier_block(
            walkers,
            spec,
            bank[0],
            torch.tensor([border]),
            target_l=0,
            quadrature_block=7,
        )
    with pytest.raises(TypeError, match="float64 or complex128"):
        project_carrier_block(
            walkers,
            spec,
            bank.to(torch.complex64),
            torch.tensor([border]),
            target_l=0,
            quadrature_block=7,
        )
    with pytest.raises(ValueError, match="quadrature_block"):
        project_carrier_block(
            walkers,
            spec,
            bank,
            torch.tensor([border]),
            target_l=0,
            quadrature_block=0,
        )
    if torch.cuda.is_available():
        with pytest.raises(ValueError, match="same device"):
            project_carrier_block(
                walkers.to("cuda"),
                spec,
                bank,
                torch.tensor([border]),
                target_l=0,
                quadrature_block=7,
            )


def test_production_module_has_no_jax_import_or_cpu_fallback():
    source = MODULE_PATH.read_text()
    assert "import jax" not in source
    assert "from jax" not in source
    assert ".cpu(" not in source
    assert ".numpy(" not in source

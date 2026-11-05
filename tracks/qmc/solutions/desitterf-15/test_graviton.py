"""Regression checks for flux, Coulomb normalization, and exact symmetries."""

import numpy as np
import pytest
from scipy.linalg import expm

import sphere


def test_pair_singlet_coulomb_normalization():
    # The J=0 pair has relative density proportional to t**(2Q),
    # t = sin(gamma/2)**2. Integrating 1/(2 R sqrt(t)) gives this value.
    for flux in (1, 3, 5):
        expected = (flux + 1) / ((2 * flux + 1) * np.sqrt(flux / 2))
        assert sphere.coulomb_pseudopotentials(flux)[0] == pytest.approx(expected)


def test_two_particle_spectrum_and_rotation_commutator():
    model = sphere.Sphere(2)
    basis = model.basis(0)
    hamiltonian = model.hamiltonian(0)
    raising = model.raising(0)
    l_squared = raising.T @ raising
    np.testing.assert_allclose(hamiltonian, hamiltonian.T, atol=1e-14)
    np.testing.assert_allclose(hamiltonian @ l_squared, l_squared @ hamiltonian, atol=1e-13)
    np.testing.assert_allclose(np.linalg.eigvalsh(l_squared), [0, 6], atol=1e-13)
    np.testing.assert_allclose(
        np.linalg.eigvalsh(hamiltonian),
        np.sort(model.pseudopotentials[[0, 2]]),
        atol=1e-13,
    )
    assert len(basis) == 2


def test_laughlin_parent_has_unique_singlet_zero_mode():
    model = sphere.Sphere(4)
    parent = np.zeros(model.flux + 1)
    parent[model.flux - 1] = 1
    spectrum = np.linalg.eigvalsh(model.hamiltonian(0, parent))
    assert abs(spectrum[0]) < 1e-13
    assert spectrum[1] > 0.01
    basis, tower = model.tower(0)
    assert tower[0].shape[1] == 2
    np.testing.assert_allclose(model.raising(0) @ tower[0], 0, atol=1e-13)


def test_rotated_sample_and_particle_exchange():
    model = sphere.Sphere(4)
    bases, tower = model.tower(2)
    coefficients = np.arange(1, tower[2].shape[1] + 1, dtype=float)
    coefficients /= np.linalg.norm(coefficients)
    rng = np.random.default_rng(37)
    spinors = rng.normal(size=(4, 2)) + 1j * rng.normal(size=(4, 2))
    spinors /= np.linalg.norm(spinors, axis=1)[:, None]
    amplitudes = model.wavefunction(spinors, bases, tower, coefficients)
    exchanged = model.wavefunction(spinors[[1, 0, 2, 3]], bases, tower, coefficients)
    np.testing.assert_allclose(exchanged, -amplitudes, atol=1e-14)
    axis = np.array([0.3, -0.5, 0.7])
    axis /= np.linalg.norm(axis)
    pauli = np.array([[[0, 1], [1, 0]], [[0, -1j], [1j, 0]], [[1, 0], [0, -1]]])
    rotation = expm(-0.5j * 0.71 * np.einsum('a,aij->ij', axis, pauli))
    rotated = model.wavefunction(spinors @ rotation.T, bases, tower, coefficients)
    generators = sphere.angular_momentum(2)
    wigner = expm(-1j * 0.71 * sum(a * j for a, j in zip(axis, generators)))
    np.testing.assert_allclose(rotated, wigner @ amplitudes, atol=1e-13)


def test_lowering_does_not_amplify_high_angular_momentum_roundoff():
    model = sphere.Sphere(6)
    _, tower = model.tower(2)
    for magnetic, columns in tower.items():
        raising = model.raising(magnetic)
        casimir = raising.T @ raising + magnetic * (magnetic + 1) * np.eye(len(columns))
        assert np.linalg.norm(casimir @ columns - 6 * columns) < 1e-11
        np.testing.assert_allclose(columns.T @ columns, np.eye(columns.shape[1]), atol=1e-12)


@pytest.mark.parametrize('electrons', [0, 1, 2.5, 8])
def test_rejects_sizes_outside_documented_small_system_range(electrons):
    with pytest.raises(ValueError):
        sphere.Sphere(electrons)


def test_shared_network_gradient_matches_finite_differences():
    import nqs

    network = nqs.Network([2, 3], width=5, seed=13)
    sectors = [
        nqs.Sector(np.eye(2), np.array([[0.3, 0.1], [0.1, 0.8]])),
        nqs.Sector(np.eye(3), np.diag([0.1, 0.9, 1.5])),
    ]
    _, gradients = nqs.energy_gradient(network, sectors)
    for parameter, gradient in zip(network.parameters, gradients):
        for index in np.ndindex(parameter.shape):
            original = parameter[index]
            parameter[index] = original + 1e-6
            plus, _ = nqs.energy_gradient(network, sectors)
            parameter[index] = original - 1e-6
            minus, _ = nqs.energy_gradient(network, sectors)
            parameter[index] = original
            assert gradient[index] == pytest.approx((np.mean(plus) - np.mean(minus)) / 2e-6, abs=2e-8)


def test_vmc_gradient_includes_directions_through_exact_discrete_nodes():
    import nqs

    network = nqs.Network([2], width=2, seed=0)
    for parameter in network.parameters:
        parameter.fill(0)
    network.parameters[-1][0] = 1
    sector = nqs.Sector(np.eye(2), np.array([[0., 1.], [1., 0.]]))
    _, gradients = nqs.energy_gradient(network, [sector], np.random.default_rng(4), samples=128)
    np.testing.assert_allclose(gradients[-1], [0, 2], atol=1e-14)


def test_vmc_training_finds_both_toy_ground_states():
    import nqs

    sectors = [
        nqs.Sector(np.eye(2), np.array([[0.2, 0.1], [0.1, 0.5]])),
        nqs.Sector(np.eye(3), np.diag([0.7, 1.1, 1.5])),
    ]
    network, _ = nqs.train(sectors, seed=11, steps=4000, samples=4096, progress=False)
    for state, sector in zip(network.states(), sectors):
        assert state @ sector.action @ state == pytest.approx(
            np.linalg.eigvalsh(sector.action)[0], abs=1e-6
        )


def test_iid_energy_standard_error_and_zero_variance():
    import nqs

    hamiltonian = np.array([[0.2, 0.1], [0.1, 0.5]])
    _, eigenvectors = np.linalg.eigh(hamiltonian)
    result = nqs.measure(eigenvectors[:, 0], hamiltonian, samples=20000, seed=17)
    assert result['standard_error'] < 1e-15
    state = np.array([np.sqrt(0.3), np.sqrt(0.7)])
    result = nqs.measure(state, hamiltonian, samples=200000, seed=17)
    assert result['standard_error'] > 0
    assert abs(result['mean'] - state @ hamiltonian @ state) < 5 * result['standard_error']
    assert result['standard_error'] == pytest.approx(
        np.sqrt(result['local_energy_variance'] / 200000)
    )


def test_command_line_produces_a_complete_small_system_run(tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import sys

    script = Path(__file__).with_name('run.py')
    subprocess.run(
        [sys.executable, str(script), '--electrons', '2', '--seeds', '3',
         '--steps', '10', '--samples', '128', '--measurements', '1000',
         '--output', str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads((tmp_path / 'summary.json').read_text())
    result = data['systems'][0]
    assert result['electrons'] == 2
    assert result['flux'] == 3
    assert result['gap']['exact_variational'] > 0
    assert len(result['multiplet']) == 5
    assert max(abs(row['l_squared'] - 6) for row in result['multiplet']) < 1e-12
    assert result['symmetry']['rotation_relative_error'] < 1e-11
    assert (tmp_path / 'gap.png').is_file()
    assert (tmp_path / 'N2_seed3.npz').is_file()

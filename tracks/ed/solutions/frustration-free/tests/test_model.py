from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
from scipy.sparse import diags, load_npz
from scipy.sparse.linalg import ArpackNoConvergence

from src.diagonalization import EDEngine, diagonalize_full
from src.model import ModelParameters, RiceMeleHubbardModel


REFERENCE_EIGENSYSTEM = (
    Path(__file__).resolve().parents[1]
    / "results"
    / "reference"
    / "rice_mele_L6_Nup3_Ndown3_t1p0_delta0p5_Delta0p3_theta6p283185307179586.npz"
)
REFERENCE_HAMILTONIAN = (
    Path(__file__).resolve().parents[1]
    / "results"
    / "reference"
    / "hamiltonian_production_L6_t1p0_delta0p5_Delta0p3_theta2pi.npz"
)


def make_model(**overrides) -> RiceMeleHubbardModel:
    values = {
        "L": 4,
        "t": 1.0,
        "delta0": 0.9,
        "Delta0": 3.0,
        "U": 0.0,
        "N_up": 2,
        "N_down": 2,
    }
    values.update(overrides)
    return RiceMeleHubbardModel(ModelParameters(**values))


def test_l6_half_filled_basis_has_dimension_400():
    model = RiceMeleHubbardModel(ModelParameters(L=6))

    assert model.parameters.N_up == 3
    assert model.parameters.N_down == 3
    assert model.basis.Ns == 400


@pytest.mark.parametrize(
    "overrides",
    [
        {"L": 5},
        {"L": 4, "N_up": 5},
        {"L": 4, "U": float("nan")},
        {"L": 4, "delta0": "0.9"},
        {"L": 4, "Delta_center": float("nan")},
    ],
)
def test_model_parameters_reject_invalid_values(overrides):
    with pytest.raises((TypeError, ValueError)):
        ModelParameters(**overrides)


def test_hamiltonian_is_hermitian_and_twist_periodic():
    model = make_model(U=1.7)
    h_zero = model.hamiltonian(phi=0.37, theta=0.0).toarray()
    h_twopi = model.hamiltonian(phi=0.37, theta=2.0 * np.pi).toarray()

    assert model.hermiticity_error(phi=0.37, theta=0.91) < 1e-12
    np.testing.assert_allclose(h_zero, h_twopi, atol=1e-12, rtol=0.0)


def test_offset_path_changes_only_the_instantaneous_pump_coefficients():
    centered = make_model()
    offset = make_model(delta_center=0.2, Delta_center=-0.4)
    phi = 0.73

    assert offset.delta(phi) == pytest.approx(centered.delta(phi) + 0.2)
    assert offset.Delta(phi) == pytest.approx(centered.Delta(phi) - 0.4)
    np.testing.assert_allclose(
        centered.hamiltonian(phi, 0.31).toarray(),
        centered.hamiltonian_from_terms(
            delta=centered.delta(phi),
            Delta=centered.Delta(phi),
            theta=0.31,
        ).toarray(),
        atol=1e-14,
        rtol=0.0,
    )


def test_instantaneous_builder_preserves_production_boundary_phase():
    model = make_model(U=1.4)
    matrix = model.hamiltonian_from_terms(
        delta=0.37,
        Delta=-0.22,
        theta=0.73,
    ).toarray()

    expected = 0.46945987347726836 - 0.42012787005232965j
    assert matrix[0, 4] == pytest.approx(expected, abs=1e-14)
    assert matrix[4, 0] == pytest.approx(expected.conjugate(), abs=1e-14)
    np.testing.assert_allclose(
        np.diag(matrix)[:6].real,
        [2.8, 0.96, 1.4, 1.4, 1.84, 0.0],
        atol=1e-14,
        rtol=0.0,
    )


def test_current_operator_is_hamiltonian_twist_derivative():
    model = make_model(U=2.0)
    phi = 0.41
    epsilon = 1e-7
    finite_difference = (
        model.hamiltonian(phi, epsilon).toarray()
        - model.hamiltonian(phi, -epsilon).toarray()
    ) / (2.0 * epsilon)
    current = model.current(phi, theta=0.0).toarray()

    np.testing.assert_allclose(current, finite_difference, atol=2e-9, rtol=0.0)
    np.testing.assert_allclose(current, current.conj().T, atol=1e-12, rtol=0.0)


def test_l6_theta_twopi_full_spectrum_matches_pre_refactor_reference():
    model = RiceMeleHubbardModel(ModelParameters(L=6, delta0=0.5, Delta0=0.3))
    hamiltonian = model.hamiltonian_from_terms(
        delta=0.5,
        Delta=0.3,
        theta=2.0 * np.pi,
    )
    result = diagonalize_full(hamiltonian)
    with np.load(REFERENCE_EIGENSYSTEM) as reference:
        expected_eigenvalues = reference["eigenvalues"]
    expected_hamiltonian = load_npz(REFERENCE_HAMILTONIAN).toarray()

    assert result.eigenvalues.shape == (400,)
    assert result.eigenvectors.shape == (400, 400)
    np.testing.assert_allclose(
        result.eigenvalues,
        expected_eigenvalues,
        atol=1e-10,
        rtol=0.0,
    )
    np.testing.assert_allclose(
        hamiltonian.toarray(),
        expected_hamiltonian,
        atol=1e-10,
        rtol=0.0,
    )
    assert np.max(result.residuals) < 1e-10
    assert result.orthogonality_error < 1e-10


def test_low_energy_engine_checks_both_residuals_and_reuses_periodic_vertex():
    engine = EDEngine(make_model())

    origin = engine.vertex(Fraction(0), Fraction(0))
    periodic = engine.vertex(Fraction(1), Fraction(-1))

    assert periodic is origin
    assert engine.diagonalization_count == 1
    assert origin.ground_state_residual < 1e-8
    assert origin.first_excited_residual < 1e-8
    assert origin.residual == max(
        origin.ground_state_residual,
        origin.first_excited_residual,
    )


class _FakeBasis:
    Ns = 2048


class _FakeHamiltonian:
    def __init__(self, *, fail_first: bool = False, mixed_ground: bool = False):
        diagonal = np.arange(_FakeBasis.Ns, dtype=np.float64) - 32.0
        self.matrix = diags(diagonal, format="csr", dtype=np.complex128)
        self.fail_first = fail_first
        self.mixed_ground = mixed_ground
        self.calls: list[dict] = []

    def tocsr(self):
        return self.matrix

    def eigsh(self, **kwargs):
        self.calls.append(kwargs)
        exact = np.zeros((_FakeBasis.Ns, 2), dtype=np.complex128)
        exact[0, 0] = 1.0
        exact[1, 1] = 1.0
        if self.fail_first and len(self.calls) == 1:
            raise ArpackNoConvergence(
                "first Krylov space did not converge",
                np.array([-32.0]),
                exact[:, :1],
            )
        if self.mixed_ground:
            epsilon = 1.0e-8
            exact[0, 0] = np.sqrt(1.0 - epsilon**2)
            exact[2, 0] = epsilon
        return np.array([-32.0, -31.0]), exact


class _FakeSparseModel:
    def __init__(self, hamiltonian):
        self.basis = _FakeBasis()
        self._hamiltonian = hamiltonian

    def validate_basis(self):
        return None

    def hamiltonian(self, phi, theta):
        return self._hamiltonian


def test_low_energy_engine_retries_arpack_with_a_larger_krylov_space():
    hamiltonian = _FakeHamiltonian(fail_first=True)
    engine = EDEngine(_FakeSparseModel(hamiltonian))

    result = engine.vertex(Fraction(0), Fraction(0))

    assert result.energies == pytest.approx((-32.0, -31.0))
    assert len(hamiltonian.calls) == 2
    assert hamiltonian.calls[1]["ncv"] > hamiltonian.calls[0]["ncv"]


def test_low_energy_engine_scales_residual_tolerance_with_energy():
    hamiltonian = _FakeHamiltonian(mixed_ground=True)
    engine = EDEngine(_FakeSparseModel(hamiltonian))

    result = engine.vertex(Fraction(0), Fraction(0))

    assert 1.0e-8 < result.ground_state_residual < 1.0e-7
    assert result.first_excited_residual == pytest.approx(0.0, abs=1.0e-14)


def test_nested_gap_grids_reuse_fraction_vertices_and_preserve_gap_reference():
    engine = EDEngine(make_model())

    coarse, fine = engine.scan_nested_gaps((3, 6))

    assert coarse.new_diagonalizations == 9
    assert fine.new_diagonalizations == 27
    assert fine.total_diagonalizations == 36
    assert fine.minimum_gap == pytest.approx(3.6, abs=1e-10)
    assert fine.maximum_residual < 1e-8


def test_gap_grids_must_be_nested_integer_multiples():
    engine = EDEngine(make_model())

    with pytest.raises(ValueError, match="integer multiple"):
        engine.scan_nested_gaps((3, 5))

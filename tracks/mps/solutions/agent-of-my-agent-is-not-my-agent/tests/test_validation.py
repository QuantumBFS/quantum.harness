from __future__ import annotations

import numpy as np
from tenpy.networks.mps import MPS
from tenpy.networks.site import SpinHalfSite

from lrtfim.couplings import periodic_coupling
from lrtfim.dmrg_workflow import default_dmrg_options
from lrtfim.exponential_fit import ExponentialFit
from lrtfim.validation import (
    dense_mpo_hamiltonian,
    exact_pair_hamiltonian,
    scalar_errors,
    translation_averaged_zz_mps,
    translation_averaged_zz_statevector,
    validate_cell,
)
from lrtfim.dmrg_workflow import build_mpo_model
from lrtfim.mpo import build_periodized_mpo


def _many_body_operator(
    local_operators: dict[int, np.ndarray],
    length: int,
) -> np.ndarray:
    identity = np.eye(2)
    result = local_operators.get(0, identity)
    for site in range(1, length):
        result = np.kron(result, local_operators.get(site, identity))
    return result


def test_exact_pair_hamiltonian_uses_periodic_hurwitz_couplings() -> None:
    length = 4
    sigma = 1.75
    gamma = 0.37
    x = np.array([[0.0, 1.0], [1.0, 0.0]])
    z = np.diag([1.0, -1.0])
    expected = np.zeros((2**length, 2**length))
    for i in range(length):
        expected -= gamma * _many_body_operator({i: x}, length)
        for j in range(i + 1, length):
            coupling = periodic_coupling(j - i, length, sigma)
            expected -= coupling * _many_body_operator({i: z, j: z}, length)

    actual = exact_pair_hamiltonian(length, sigma, gamma)
    np.testing.assert_allclose(actual, expected, atol=1.0e-13)


def test_dense_mpo_expansion_overrides_tenpy_default_size_guard() -> None:
    length = 11  # 4,194,304 matrix entries exceed TeNPy's 2e6 default.
    mpo = build_periodized_mpo(
        length,
        lambdas=np.array([0.5]),
        coefficients=np.array([1.0]),
        gamma=0.0,
    )
    dense = dense_mpo_hamiltonian(build_mpo_model(mpo))
    assert dense.shape == (2**length, 2**length)
    np.testing.assert_allclose(dense, dense.T, atol=1.0e-14)


def test_translation_averaged_correlations_include_wrapped_pairs() -> None:
    # |up, up, down, down>: C(1)=0 and C(2)=-1 on the periodic ring.
    vector = np.zeros(16)
    vector[0b0011] = 1.0
    expected = np.array([0.0, -1.0])
    np.testing.assert_allclose(
        translation_averaged_zz_statevector(vector, 4),
        expected,
        atol=1.0e-14,
    )

    site = SpinHalfSite(conserve=None)
    psi = MPS.from_product_state(
        [site] * 4,
        ["up", "up", "down", "down"],
        bc="finite",
    )
    np.testing.assert_allclose(
        translation_averaged_zz_mps(psi),
        expected,
        atol=1.0e-14,
    )


def test_scalar_errors_report_absolute_relative_and_zero_policy() -> None:
    assert scalar_errors(-10.0, -9.5) == {
        "absolute": 0.5,
        "relative": 0.05,
    }
    assert scalar_errors(0.0, 1.0) == {
        "absolute": 1.0,
        "relative": None,
    }


def test_validate_cell_separates_mpo_and_mps_errors() -> None:
    fit = ExponentialFit(
        sigma=1.75,
        r_fit=32,
        lambdas=np.array([0.72, 0.31]),
        coefficients=np.array([0.4, 0.08]),
        max_relative_error=0.0,
        rms_relative_error=0.0,
    )
    options = default_dmrg_options(chi_max=16)
    options.update({"min_sweeps": 4, "max_sweeps": 12})
    record = validate_cell(
        length=4,
        sigma=1.75,
        gamma=1.2,
        fit=fit,
        dmrg_options=options,
    )

    assert set(record["layers"]) == {
        "exact_pair_ed",
        "compact_mpo_ed",
        "compact_mpo_dmrg",
    }
    assert set(record["comparisons"]) == {
        "mpo_representation",
        "mps_optimization",
    }
    for comparison in record["comparisons"].values():
        for name in ("ground_energy", "excited_energy", "gap"):
            assert set(comparison[name]) == {"absolute", "relative"}
        assert comparison["correlation_max_absolute"] >= 0.0
    assert record["hamiltonian"]["relative_frobenius_error"] >= 0.0
    assert len(record["coupling_profile"]) == 3
    assert len(record["layers"]["exact_pair_ed"]["correlations"]) == 2
    diagnostics = record["layers"]["compact_mpo_dmrg"]["diagnostics"]
    assert diagnostics["overlap"] < 1.0e-10
    assert record["layers"]["compact_mpo_dmrg"]["gap"] > 0.0

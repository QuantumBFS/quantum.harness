"""
Tests for symmetries of the neural quantum state ansatz.

Verifies:
1. SO(3) rotation invariance of |Psi|²
2. Fermionic antisymmetry under particle exchange
3. Laughlin wavefunction correctness (m=3)
4. Chord distance SO(3) invariance
"""

import torch
import math
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.haldane_sphere import HaldaneSphere, chord_distance_matrix, spinor_coordinates
from src.laughlin_wf import lauglin_jastrow, lauglin_wf_amplitude
from src.ansatz import FullWavefunction, EquivariantNN

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
dtype_real = torch.float64


def test_chord_distance_invariance():
    """Chord distance matrix should be SO(3) invariant."""
    N = 6
    sphere = HaldaneSphere(N)

    theta, phi, xyz = sphere.sample_initial(1, seed=42)

    d_orig = chord_distance_matrix(xyz)

    # Random rotation
    from scipy.spatial.transform import Rotation as R
    r = R.random()
    rot = torch.tensor(r.as_matrix(), device=device, dtype=dtype_real)
    xyz_rot = torch.matmul(xyz, rot.T)

    d_rot = chord_distance_matrix(xyz_rot)

    diff = (d_orig - d_rot).abs().max().item()
    assert diff < 1e-10, f"Chord distance not invariant: max diff = {diff}"
    print(f"  ✓ SO(3) invariance of chord distances: max diff = {diff:.2e}")


def test_laughlin_antisymmetry():
    """Laughlin Jastrow should be antisymmetric under particle exchange."""
    N = 4
    sphere = HaldaneSphere(N)
    theta, phi, _ = sphere.sample_initial(1, seed=42)

    log_psi = lauglin_jastrow(theta, phi, m=3)

    # Swap two particles
    theta_swap = theta.clone()
    phi_swap = phi.clone()
    theta_swap[:, [0, 1]] = theta_swap[:, [1, 0]]
    phi_swap[:, [0, 1]] = phi_swap[:, [1, 0]]

    log_psi_swap = lauglin_jastrow(theta_swap, phi_swap, m=3)

    # For a single swap (odd parity), ψ → -ψ
    # So log(ψ_swap) = log(ψ) + iπ
    # Compare amplitudes rather than complex logarithms because the latter are
    # defined only modulo 2πi.
    psi = torch.exp(log_psi)
    psi_swap = torch.exp(log_psi_swap)
    relative_error = (
        (psi_swap + psi).abs() / psi.abs().clamp_min(1e-30)
    ).max().item()
    assert relative_error < 1e-10, (
        f"Antisymmetry violated: relative error = {relative_error}"
    )
    print(
        "  ✓ Laughlin antisymmetry under swap: "
        f"relative error = {relative_error:.2e}"
    )


def test_laughlin_probability_invariance():
    """|Psi|^2 from Laughlin Jastrow should be permutation invariant."""
    N = 4
    sphere = HaldaneSphere(N)
    theta, phi, _ = sphere.sample_initial(1, seed=42)

    log_psi_orig = lauglin_jastrow(theta, phi, m=3)
    prob_orig = torch.exp(2 * log_psi_orig.real)

    # Random permutation
    perm = torch.randperm(N)
    theta_perm = theta[:, perm]
    phi_perm = phi[:, perm]

    log_psi_perm = lauglin_jastrow(theta_perm, phi_perm, m=3)
    prob_perm = torch.exp(2 * log_psi_perm.real)

    diff = (prob_orig - prob_perm).abs().max().item()
    assert diff < 1e-10, f"|Psi|^2 not permutation invariant: diff = {diff}"
    print(f"  ✓ Laughlin |Psi|² permutation invariance: max diff = {diff:.2e}")


def test_nn_so3_equivariance():
    """NN correction should be SO(3) equivariant."""
    N = 6
    sphere = HaldaneSphere(N)
    _, _, xyz = sphere.sample_initial(1, seed=42)

    nn = EquivariantNN(N, hidden_dim=32).to(device)
    nn.eval()

    log_ampl_orig, phase_orig = nn(xyz)

    # Random rotation
    from scipy.spatial.transform import Rotation as R
    for _ in range(5):
        r = R.random()
        rot = torch.tensor(r.as_matrix(), device=device, dtype=dtype_real)
        xyz_rot = torch.matmul(xyz, rot.T)

        log_ampl_rot, phase_rot = nn(xyz_rot)

        diff_ampl = (log_ampl_orig - log_ampl_rot).abs().max().item()
        diff_phase = (phase_orig - phase_rot).abs().max().item()
        assert diff_ampl < 1e-10, f"Amplitude changed under rotation: {diff_ampl}"
        assert diff_phase < 1e-10, f"Phase changed under rotation: {diff_phase}"

    print(f"  ✓ NN SO(3) equivariance: amplitude invariant, phase invariant")


def test_full_wavefunction():
    """Full wavefunction should produce finite outputs."""
    N = 6
    sphere = HaldaneSphere(N)
    theta, phi, xyz = sphere.sample_initial(4, seed=42)

    wf = FullWavefunction(N, hidden_dim=32, n_layers=2)
    wf.eval()

    log_psi = wf(theta, phi, xyz)

    assert not torch.isnan(log_psi).any(), "NaN in wavefunction output"
    assert not torch.isinf(log_psi).any(), "Inf in wavefunction output"
    assert log_psi.shape == (4,), f"Wrong shape: {log_psi.shape}"

    print(f"  ✓ Full wavefunction output: shape {log_psi.shape}, finite ✓")
    print(f"    log|Psi| range: [{log_psi.real.min().item():.2f}, "
          f"{log_psi.real.max().item():.2f}]")


def run_all_tests():
    """Run all symmetry tests."""
    print("=" * 60)
    print("  Symmetry & Correctness Tests")
    print("=" * 60)

    tests = [
        ("Chord distance SO(3) invariance", test_chord_distance_invariance),
        ("Laughlin antisymmetry", test_laughlin_antisymmetry),
        ("Laughlin |Psi|² invariance", test_laughlin_probability_invariance),
        ("NN SO(3) equivariance", test_nn_so3_equivariance),
        ("Full wavefunction", test_full_wavefunction),
    ]

    n_pass = 0
    n_fail = 0

    for name, test_fn in tests:
        print(f"\n  [{name}]")
        try:
            test_fn()
            n_pass += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            n_fail += 1

    print(f"\n{'=' * 60}")
    print(f"  Results: {n_pass} passed, {n_fail} failed")
    print(f"{'=' * 60}")
    return n_fail == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

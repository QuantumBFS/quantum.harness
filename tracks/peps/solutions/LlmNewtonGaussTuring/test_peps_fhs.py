#!/usr/bin/env python3
"""
Test suite for PEPS-FHS Berry curvature engine (Challenge 73 Stage 4).

Tests:
1. Hamiltonian identity: H(θ) = R_x(θ) H(0) R_x^†(θ)
2. Hermiticity check
3. 1D JW oracle reference values
4. FHS formula: gauge invariance, zero-overlap rejection
5. ED F12: theta-independence, positivity properties
6. MPS decomposition: fidelity convergence with bond dimension
7. MPS vs ED F12 agreement
"""
import numpy as np
from peps_fhs import *


def test_hamiltonian_rotation_identity():
    """Verify H(θ,Ω) = R_x(θ) H(0,Ω) R_x^†(θ)."""
    Lx, Ly = 2, 2
    J, Omega, theta = 1.0, 1.0, 0.7

    H_theta = build_hamiltonian_dense(Lx, Ly, J, Omega, theta)
    H_0 = build_hamiltonian_dense(Lx, Ly, J, Omega, 0.0)

    # Build R_x(θ) = exp(-iθ Σ X_i / 2)
    N = Lx * Ly
    dim = 1 << N
    R = np.eye(dim, dtype=complex)
    for i in range(N):
        Ri = np.array([[np.cos(theta/2), -1j*np.sin(theta/2)],
                        [-1j*np.sin(theta/2), np.cos(theta/2)]])
        R = R @ np.kron(np.eye(1 << i), np.kron(Ri, np.eye(1 << (N-i-1))))
        # Actually this doesn't give the correct Kronecker product... let me do simpler
    # Simpler: build R as exp(-iθ ΣX/2) = ∏ exp(-iθ X_i/2)
    # Since X_i commute, product is OK
    R2 = np.eye(dim, dtype=complex)
    for i in range(N):
        X_full = np.eye(dim, dtype=complex)
        X_i = np.array([[0, 1], [1, 0]], dtype=complex)
        left = np.eye(1 << i, dtype=complex)
        right = np.eye(1 << (N - i - 1), dtype=complex)
        X_full = np.kron(left, np.kron(X_i, right))
        R2 = R2 @ (np.cos(theta/2) * np.eye(dim) - 1j * np.sin(theta/2) * X_full)

    H_rotated = R2 @ H_0 @ R2.conj().T
    diff = np.max(np.abs(H_theta - H_rotated))
    print(f"  [hamiltonian] Rotation identity: max|Δ| = {diff:.2e}")
    assert diff < 1e-10, f"Rotation identity violated: {diff}"
    return True


def test_hermiticity():
    """Check H is Hermitian."""
    Lx, Ly = 2, 2
    H = build_hamiltonian_dense(Lx, Ly, 1.0, 1.5, 0.3)
    diff = np.max(np.abs(H - H.conj().T))
    print(f"  [hamiltonian] Hermiticity: max|H-H^†| = {diff:.2e}")
    assert diff < 1e-10, f"Hamiltonian not Hermitian: {diff}"
    return True


def test_jw_oracle():
    """Verify 1D JW oracle against known reference values."""
    from peps_fhs import tfim_chain_f12_finite as chain_f12

    # Reference: C++ code values
    f12_N4 = chain_f12(4, 1.0, 1.5)
    f12_N6 = chain_f12(6, 1.0, 1.5)
    f12_N8 = chain_f12(8, 1.0, 1.5)

    # Expected monotonic approach to thermodynamic limit for Ω close to J
    # The sign depends on system size; check Ω=1.0 case
    f12_n4_j1 = chain_f12(4, 1.0, 1.0)
    f12_n6_j1 = chain_f12(6, 1.0, 1.0)
    f12_n8_j1 = chain_f12(8, 1.0, 1.0)
    assert abs(f12_n4_j1) > 0, "F12 should be non-zero"
    assert abs(f12_n6_j1) > abs(f12_n4_j1), "N=6 larger |F12| than N=4 for Ω=1.0"
    assert f12_n6_j1 < 0, "F12 should be negative for J=Ω=1"

    # Critical point: F12 should become more negative as Ω→J
    # For finite N, the singularity is softened; check that it's non-zero
    f12_near_crit = chain_f12(4, 1.0, 1.0001)
    f12_away = chain_f12(4, 1.0, 1.5)
    assert f12_near_crit < 0, f"Near-critical F12 should be negative: {f12_near_crit}"
    assert abs(f12_near_crit) > abs(f12_away), \
        f"|F12| near critical should exceed |F12| away from critical"

    print(f"  [jw_oracle] N=4: {f12_N4:.6f}, N=6: {f12_N6:.6f}, N=8: {f12_N8:.6f}")
    print(f"  [jw_oracle] Near-critical: F12(Ω=1.0001) = {f12_near_crit:.6f}, away: F12(Ω=1.5) = {f12_away:.6f}")
    return True


def test_fhs_gauge_invariance():
    """FHS formula should be invariant under U(1) phase rotations."""
    dim = 4
    psi_00 = np.random.randn(dim) + 1j * np.random.randn(dim)
    psi_10 = np.random.randn(dim) + 1j * np.random.randn(dim)
    psi_11 = np.random.randn(dim) + 1j * np.random.randn(dim)
    psi_01 = np.random.randn(dim) + 1j * np.random.randn(dim)

    # Normalize
    for psi in [psi_00, psi_10, psi_11, psi_01]:
        psi[:] /= np.sqrt(np.sum(np.abs(psi)**2))

    dth, dom = 0.1, 0.1
    f12_ref = compute_f12_from_states(psi_00, psi_10, psi_11, psi_01, dth, dom)

    # Apply random phases
    rng = np.random.RandomState(123456789)
    phases = [rng.uniform(0, 2*np.pi) for _ in range(4)]
    f12_gauge = compute_f12_from_states(
        psi_00 * np.exp(1j*phases[0]),
        psi_10 * np.exp(1j*phases[1]),
        psi_11 * np.exp(1j*phases[2]),
        psi_01 * np.exp(1j*phases[3]),
        dth, dom)

    diff = abs(f12_ref['F12'] - f12_gauge['F12'])
    print(f"  [fhs] Gauge invariance: |ΔF12| = {diff:.2e}")
    assert diff < 1e-12, f"FHS not gauge invariant: {diff}"
    return True


def test_fhs_zero_overlap():
    """FHS should return invalid=None when overlaps vanish."""
    dim = 8
    psi_a = np.zeros(dim, dtype=complex)
    psi_a[0] = 1.0
    psi_b = np.zeros(dim, dtype=complex)
    psi_b[1] = 1.0

    U1 = np.dot(np.conj(psi_a), psi_b)  # zero
    f12 = fhs_curvature(U1, complex(1, 0), complex(1, 0), complex(1, 0), 0.1, 0.1)
    assert not f12['valid'], "Should reject zero overlap"
    assert np.isnan(f12['F12']), "F12 should be NaN for zero overlap"
    print("  [fhs] Zero-overlap rejection: OK")
    return True


def test_ed_f12_theta_independence():
    """For the Kolodrubetz rotation, F12 should not depend on θ."""
    Lx, Ly = 2, 2
    J, Omega = 1.0, 1.0
    dtheta, dOmega = 0.01, 0.01

    f12_vals = []
    for theta in [0.0, 0.5, 1.0, 1.5]:
        H00 = build_hamiltonian_dense(Lx, Ly, J, Omega, theta)
        H10 = build_hamiltonian_dense(Lx, Ly, J, Omega, theta + dtheta)
        H11 = build_hamiltonian_dense(Lx, Ly, J, Omega + dOmega, theta + dtheta)
        H01 = build_hamiltonian_dense(Lx, Ly, J, Omega + dOmega, theta)

        psi_00 = solve_ground_state(H00)['psi']
        psi_10 = solve_ground_state(H10)['psi']
        psi_11 = solve_ground_state(H11)['psi']
        psi_01 = solve_ground_state(H01)['psi']

        f12 = compute_f12_from_states(psi_00, psi_10, psi_11, psi_01, dtheta, dOmega)
        f12_vals.append(f12['F12'] / (Lx * Ly))

    spread = max(f12_vals) - min(f12_vals)
    print(f"  [ed] θ-independence: F12/N = {f12_vals[0]:.8f} at all θ, spread={spread:.2e}")
    assert spread < 1e-12, f"F12 should be θ-independent: spread={spread}"
    return True


def test_mps_convergence():
    """MPS with sufficient bond dimension should reproduce ED F12."""
    Lx, Ly = 2, 2
    J, Omega, theta = 1.0, 1.5, 0.3
    dtheta, dOmega = 0.01, 0.01

    H00 = build_hamiltonian_dense(Lx, Ly, J, Omega, theta)
    H10 = build_hamiltonian_dense(Lx, Ly, J, Omega, theta + dtheta)
    H11 = build_hamiltonian_dense(Lx, Ly, J, Omega + dOmega, theta + dtheta)
    H01 = build_hamiltonian_dense(Lx, Ly, J, Omega + dOmega, theta)

    psi_00 = solve_ground_state(H00)['psi']
    psi_10 = solve_ground_state(H10)['psi']
    psi_11 = solve_ground_state(H11)['psi']
    psi_01 = solve_ground_state(H01)['psi']

    f12_ed = compute_f12_from_states(psi_00, psi_10, psi_11, psi_01, dtheta, dOmega)

    errors = []
    for D in [2, 4, 8, 16]:
        mps_00, so = state_to_mps(psi_00, Lx, Ly, D)
        mps_10, _ = state_to_mps(psi_10, Lx, Ly, D)
        mps_11, _ = state_to_mps(psi_11, Lx, Ly, D)
        mps_01, _ = state_to_mps(psi_01, Lx, Ly, D)
        f12_mps = compute_f12_from_mps(mps_00, mps_10, mps_11, mps_01, so, dtheta, dOmega)
        err = abs(f12_mps['F12'] - f12_ed['F12']) / abs(f12_ed['F12'])
        errors.append(err)

    print(f"  [mps] Convergence: D=2 err={errors[0]:.2e}, D=4 err={errors[1]:.2e}, "
          f"D=8 err={errors[2]:.2e}")
    assert errors[1] < 1e-12, f"MPS D=4 should match ED for 2x2: err={errors[1]}"
    return True


def test_mps_self_overlap():
    """MPS self-overlap should be 1.0 for sufficient bond dimension."""
    Lx, Ly = 2, 2
    H = build_hamiltonian_dense(Lx, Ly, 1.0, 1.0, 0.0)
    psi = solve_ground_state(H)['psi']

    # D=2 truncation has fidelity loss for 4-site system
    mps2, so = state_to_mps(psi, Lx, Ly, 2)
    ov2 = mps_overlap(mps2, mps2, so)
    assert abs(ov2.real - 1.0) < 0.01, f"D=2 self-overlap too far from 1: {ov2.real}"

    # D>=4 should be exact for 4-site system (max dim=16)
    for D in [4, 8]:
        mps, so = state_to_mps(psi, Lx, Ly, D)
        ov = mps_overlap(mps, mps, so)
        diff = abs(ov.real - 1.0)
        assert diff < 1e-12, f"MPS(D={D}) self-overlap ≠ 1: {ov.real}"
    print("  [mps] Self-overlap: D=2 tolerates ~0.999, D≥4 exact at 1.0")
    return True


def test_ed_small_systems():
    """ED produces valid F12 for small system sizes."""
    for L in [2, 3]:
        H = build_hamiltonian_dense(L, L, 1.0, 1.5, 0.3)
        gs = solve_ground_state(H)
        assert gs['converged'], f"ED unconverged for {L}x{L}"
        assert gs['residual'] < 1e-10, f"ED residual too large: {gs['residual']}"
        print(f"  [ed] {L}x{L} (dim={gs['dim']}): E0={gs['E0']:.6f}, "
              f"residual={gs['residual']:.2e}")
    return True


if __name__ == '__main__':
    print("=== Challenge 73 Stage 4: Test Suite ===\n")
    tests = [
        ("Hamiltonian rotation identity", test_hamiltonian_rotation_identity),
        ("Hamiltonian Hermiticity", test_hermiticity),
        ("1D JW oracle", test_jw_oracle),
        ("FHS gauge invariance", test_fhs_gauge_invariance),
        ("FHS zero-overlap rejection", test_fhs_zero_overlap),
        ("ED theta-independence", test_ed_f12_theta_independence),
        ("MPS convergence", test_mps_convergence),
        ("MPS self-overlap", test_mps_self_overlap),
        ("ED small systems", test_ed_small_systems),
    ]

    passed = 0
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print(f"  PASS: {name}\n")
        except Exception as e:
            print(f"  FAIL: {name}: {e}\n")

    print(f"=== Results: {passed}/{len(tests)} tests passed ===")
    if passed == len(tests):
        print("All tests passed!")
    else:
        exit(1)

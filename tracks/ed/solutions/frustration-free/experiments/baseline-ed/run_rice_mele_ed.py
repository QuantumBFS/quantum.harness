from __future__ import annotations

import json
from math import comb
from pathlib import Path

import numpy as np
from quspin.basis import spinful_fermion_basis_1d
from quspin.operators import hamiltonian


SUPPORTED_LENGTHS = {6, 8}


def build_rice_mele_hamiltonian(
    L: int,
    delta: float,
    Delta: float,
    theta: float,
    t: float = 1.0,
):
    """Build the half-filled, zero-magnetization spinful Rice-Mele Hamiltonian."""
    if L not in SUPPORTED_LENGTHS:
        raise ValueError(f"L must be one of {sorted(SUPPORTED_LENGTHS)}, got {L}")

    particles_per_spin = L // 2
    basis = spinful_fermion_basis_1d(L, Nf=(particles_per_spin, particles_per_spin))

    up_hopping = []
    down_hopping = []
    for j in range(L - 1):
        coefficient = -(t + (-1) ** (j + 1) * delta)
        up_hopping.extend([[coefficient, j, j + 1], [coefficient, j + 1, j]])
        down_hopping.extend([[coefficient, j, j + 1], [coefficient, j + 1, j]])

    boundary_coefficient = -(t + (-1) ** L * delta)
    forward_boundary = boundary_coefficient * np.exp(1j * theta)
    backward_boundary = boundary_coefficient * np.exp(-1j * theta)
    up_hopping.extend([[forward_boundary, L - 1, 0], [backward_boundary, 0, L - 1]])
    down_hopping.extend([[forward_boundary, L - 1, 0], [backward_boundary, 0, L - 1]])

    onsite = [[Delta * (-1) ** (j + 1), j] for j in range(L)]
    static = [
        ["+-|", up_hopping],
        ["|+-", down_hopping],
        ["n|", onsite],
        ["|n", onsite],
    ]
    return basis, hamiltonian(static, [], basis=basis, dtype=np.complex128)


def diagonalize_rice_mele(
    L: int = 6,
    delta: float = 0.5,
    Delta: float = 0.3,
    theta: float = 2.0 * np.pi,
    t: float = 1.0,
):
    """Return the complete eigensystem and numerical diagnostics."""
    basis, H = build_rice_mele_hamiltonian(L, delta, Delta, theta, t)
    energies, vectors = H.eigh()
    matrix = H.toarray()
    hermiticity_error = float(np.max(np.abs(matrix - matrix.conj().T)))
    expected_dimension = comb(L, L // 2) ** 2
    diagnostics = {
        "basis_dimension": basis.Ns,
        "expected_basis_dimension": expected_dimension,
        "hermiticity_error": hermiticity_error,
        "parameters": {"L": L, "delta": delta, "Delta": Delta, "theta": theta, "t": t},
    }
    if basis.Ns != expected_dimension or hermiticity_error >= 1e-12:
        raise RuntimeError("Rice-Mele Hamiltonian diagnostic failed")
    return energies, vectors, diagnostics


def write_artifacts(
    output_dir: Path,
    L: int = 6,
    delta: float = 0.5,
    Delta: float = 0.3,
    theta: float = 2.0 * np.pi,
    t: float = 1.0,
) -> dict[str, str]:
    """Persist the complete eigensystem and diagnostics for one fixed parameter point."""
    output_dir.mkdir(parents=True, exist_ok=True)
    energies, vectors, diagnostics = diagonalize_rice_mele(L, delta, Delta, theta, t)
    np.save(output_dir / "rice_mele_eigenvalues.npy", energies)
    np.save(output_dir / "rice_mele_eigenvectors.npy", vectors)

    manifest = {
        "parameters": diagnostics["parameters"],
        "diagnostics": {
            "basis_dimension": diagnostics["basis_dimension"],
            "expected_basis_dimension": diagnostics["expected_basis_dimension"],
            "hermiticity_error": diagnostics["hermiticity_error"],
            "eigenvalue_shape": list(energies.shape),
            "eigenvector_shape": list(vectors.shape),
            "lowest_eigenvalues": energies[:8].tolist(),
        },
        "artifacts": ["rice_mele_eigenvalues.npy", "rice_mele_eigenvectors.npy"],
    }
    (output_dir / "rice_mele_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return {
        "eigenvalues": "rice_mele_eigenvalues.npy",
        "eigenvectors": "rice_mele_eigenvectors.npy",
        "manifest": "rice_mele_manifest.json",
    }


if __name__ == "__main__":
    output_dir = Path(__file__).resolve().parents[2] / "results" / "baseline-ed"
    files = write_artifacts(output_dir)
    energies, _, diagnostics = diagonalize_rice_mele()
    _, H_zero = build_rice_mele_hamiltonian(6, 0.5, 0.3, 0.0)
    _, H_two_pi = build_rice_mele_hamiltonian(6, 0.5, 0.3, 2.0 * np.pi)
    energies_zero, _, _ = diagonalize_rice_mele(theta=0.0)
    matrix_periodicity_error = float(np.max(np.abs(H_zero.toarray() - H_two_pi.toarray())))
    spectrum_periodicity_error = float(np.max(np.abs(energies_zero - energies)))

    print(f"Hilbert space dimension: {diagnostics['basis_dimension']}")
    print("Lowest eigenvalues:", energies[:8])
    print(f"Hermiticity error: {diagnostics['hermiticity_error']:.3e}")
    print(f"theta=0 vs 2pi matrix error: {matrix_periodicity_error:.3e}")
    print(f"theta=0 vs 2pi spectrum error: {spectrum_periodicity_error:.3e}")
    print("Saved:", ", ".join(files.values()))

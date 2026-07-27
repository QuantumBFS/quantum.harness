"""
Lennard-Jones cluster energy and forces in reduced units (epsilon=sigma=1).

Rung 0 of the "How low can you go?" challenge (#117).
Reference: Wales & Doye, J. Phys. Chem. A 101, 5111 (1997).
"""

import numpy as np


def load_xyz(path: str) -> np.ndarray:
    """Load coordinates from the Cambridge Cluster Database plain-text format."""
    coords = []
    with open(path) as f:
        for line in f:
            parts = line.split()
            if len(parts) == 3:
                coords.append([float(x) for x in parts])
    return np.array(coords)


def lj_energy(coords: np.ndarray) -> float:
    """
    Total Lennard-Jones potential energy in reduced units.

    E = 4 * sum_{i<j} [(1/r_ij)^12 - (1/r_ij)^6]

    No cutoff, no shift — the exact definition used by the Cambridge database.
    """
    N = coords.shape[0]
    energy = 0.0
    for i in range(N):
        for j in range(i + 1, N):
            r = np.linalg.norm(coords[i] - coords[j])
            r6 = r ** 6
            r12 = r6 * r6
            energy += 4.0 * (1.0 / r12 - 1.0 / r6)
    return energy


def lj_energy_fast(coords: np.ndarray) -> float:
    """Vectorized LJ energy for speed on larger clusters."""
    N = coords.shape[0]
    # pairwise displacement tensor: (N, N, 3)
    diff = coords[:, None, :] - coords[None, :, :]
    # pairwise distances: (N, N)
    r2 = np.sum(diff ** 2, axis=-1)
    # zero the diagonal (self-interaction)
    np.fill_diagonal(r2, np.inf)
    r6 = r2 ** 3
    r12 = r6 * r6
    # sum over upper triangle (i < j) via mask
    mask = np.triu(np.ones((N, N), dtype=bool), k=1)
    inv_r6 = 1.0 / r6[mask]
    inv_r12 = 1.0 / r12[mask]
    return 4.0 * np.sum(inv_r12 - inv_r6)


def lj_forces(coords: np.ndarray) -> np.ndarray:
    """
    Analytic forces on each atom.

    F_i = -dE/dr_i = 24 * sum_{j!=i} (2/r_ij^14 - 1/r_ij^8) * (r_i - r_j)
    """
    N = coords.shape[0]
    diff = coords[:, None, :] - coords[None, :, :]  # (N, N, 3)
    r2 = np.sum(diff ** 2, axis=-1)  # (N, N)
    np.fill_diagonal(r2, 1.0)  # avoid division by zero
    r8 = r2 ** 4
    r14 = r2 ** 7
    coeff = 24.0 * (2.0 / r14 - 1.0 / r8)  # (N, N)
    np.fill_diagonal(coeff, 0.0)
    forces = np.sum(coeff[:, :, None] * diff, axis=1)  # (N, 3)
    return forces


if __name__ == "__main__":
    import sys

    coord_file = sys.argv[1] if len(sys.argv) > 1 else None
    if coord_file is None:
        print("Usage: python lj_energy.py <coords_file> [E_ref]")
        sys.exit(1)

    coords = load_xyz(coord_file)
    N = coords.shape[0]

    # compute energy both ways and cross-check
    e_loop = lj_energy(coords)
    e_vec = lj_energy_fast(coords)

    print(f"N = {N}")
    print(f"E (loop)   = {e_loop:.12f}")
    print(f"E (vector) = {e_vec:.12f}")
    print(f"Agreement  = {abs(e_loop - e_vec):.2e}")

    # check against reference if provided
    e_ref = float(sys.argv[2]) if len(sys.argv) > 2 else None
    if e_ref is not None:
        delta = abs(e_vec - e_ref)
        status = "PASS" if delta < 1e-6 else "FAIL"
        print(f"E_ref      = {e_ref:.12f}")
        print(f"|E - E_ref| = {delta:.2e}  [{status}]")

    # force sanity: at a minimum, |F| should be very small
    f = lj_forces(coords)
    max_force = np.max(np.linalg.norm(f, axis=1))
    print(f"max |F|    = {max_force:.2e}")

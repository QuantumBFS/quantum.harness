"""Transverse-field Ising model (TFIM): Pauli operators, bond list, Z2 symmetry.

H = -J sum_<ij> sigma^z_i sigma^z_j - h sum_i sigma^x_i ,  J = 1.

Sites are indexed row-major i = y*Lx + x on an Lx x Ly square lattice with
open boundary conditions (see core.lattice).
"""
import numpy as np

# Pauli matrices, float64 (real). sigma^z is diagonal; sigma^x is off-diagonal.
SZ = np.diag([1.0, -1.0]).astype(np.float64)
SX = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.float64)


def tfim_bonds(Lx, Ly):
    """List of nearest-neighbour site pairs (i, j), open BC, row-major index.

    Horizontals: Ly*(Lx-1); verticals: (Ly-1)*Lx.
    """
    bonds = []
    for y in range(Ly):
        for x in range(Lx):
            i = y * Lx + x
            if x + 1 < Lx:
                bonds.append((i, i + 1))      # right neighbour
            if y + 1 < Ly:
                bonds.append((i, i + Lx))     # down neighbour
    return bonds


def z2_flip_invariant(bonds):
    """TFIM is invariant under the global Z2 spin flip sigma^z -> -sigma^z:
    every bond term sigma^z_i sigma^z_j is even, and sigma^x is invariant.
    Trivially True for the TFIM; kept as an explicit symmetry assertion hook.
    """
    return True

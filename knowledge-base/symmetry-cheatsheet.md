# Symmetry Cheat-Sheet

Conserved quantities and lattice generators for common QMB problems. Skills cite this card to set up sectors, verify symmetry, and validate calculations.

## Spin Hamiltonians

### Isotropic Heisenberg

- `S^z_total = Σ_i S^z_i` is conserved (U(1)).
- `S²_total = (Σ_i S_i)²` is conserved (SU(2)).
- For finite-N AFM: ground state is total spin `S_total = 0` (singlet) on bipartite lattices; on frustrated lattices `S_total = 0` is still expected but not guaranteed.

### XXZ

- `S^z_total` conserved (U(1) in spin space).
- Full SU(2) only at `Δ = 1`.

### XY (S^x, S^y only) / Hard-core boson

- `S^z_total` conserved (or particle number in boson language).

### External field `-h Σ S^z_i`

- Breaks SU(2) → U(1). `S^z_total` still conserved.
- Breaks `Z_2` (`S^z → -S^z`) symmetry.

## Fermion Hamiltonians

### Hubbard / t-V

- `N↑`, `N↓` separately conserved (U(1) × U(1)). For Hubbard, use this to fix the sector (e.g., `N↑ = N↓ = N/2` for half-filling).
- `S^z_total = (N↑ - N↓)/2` conserved.
- For `H_{Hubbard}` with no Zeeman field: full SU(2) spin rotation symmetry in addition to charge U(1).

### t-J

- Same `N↑`, `N↓`, `S^z_total` conservation as Hubbard.
- Plus the no-double-occupancy constraint (Hilbert-space restriction, not a symmetry).

### Anderson impurity

- Total `N` and `S^z` conserved (impurity + bath).
- For symmetric Anderson (`ε_d = -U/2`): particle-hole symmetry.

## Lattice symmetries

### Chain (1D)

- Translation: cyclic group `Z_N` (PBC) or none (OBC).
- Reflection (parity): `Z_2`.
- Inversion ≡ reflection in 1D.

### Square lattice

- Translations: `Z_{L_x} × Z_{L_y}` (PBC).
- Point group: `D_4` (4-fold rotation + reflection) for square clusters.
- Sublattice (bipartite): `A`/`B` decomposition for AFM; useful for QMC sign-problem.

### Triangular lattice

- Translations: `Z_{L_x} × Z_{L_y}` (PBC, with appropriate twist for non-orthogonal lattice vectors).
- Point group: `D_6` (6-fold rotation + reflection).
- Frustrated: not bipartite; sublattice decomposition is 3-coloring (A/B/C).

### Kagome lattice

- 3-site unit cell.
- Translations + 6-fold rotation + reflection.
- Frustrated: each triangle has 3 spins; corner-sharing triangles.

### Pyrochlore lattice

- 4-site unit cell (corner-sharing tetrahedra in 3D).
- Cubic symmetry, large degenerate manifold.

## Using symmetries in calculations

### ED

Block-diagonalize by quantum numbers. For Heisenberg: fix `S^z_total` (and `S²_total` if SU(2)-symmetric, though that's harder). For Hubbard: fix `(N↑, N↓)`. Block sizes shrink dramatically; e.g., `S^z = 0` sector of N=20 spin-1/2 is `C(20,10) = 184756`, vs full `2^20 = 1M`.

### DMRG

Quantum-number conservation is enabled in ITensors via `siteinds("S=1/2"; conserve_qns=true)` for U(1) `S^z`, or `("Electron"; conserve_qns=true)` for charge + spin. Initial state must be in the target sector (e.g., a Néel product state for `S^z = 0`).

### QMC

Sublattice / bipartite structure is essential for sign-problem-free QMC. Frustrated lattices typically have a sign problem; constrained-path methods or stochastic series expansion variants may work.

## Validation pattern

Always check for sectors:
1. Did the code conserve the symmetry it should? (e.g., `S^z` should not drift.)
2. Is the ground state in the expected sector? (e.g., Heisenberg AFM: total `S^z = 0`.)
3. Does breaking the symmetry (small field, sublattice flip) move the energy in the expected direction?

These are nearly free sanity checks and catch the most common setup errors.

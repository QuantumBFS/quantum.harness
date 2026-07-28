# Challenge 81 Implementation Plan

## 1. Lock the Julia runtime

- Add a dedicated `julia/Project.toml` with exact compatible package bounds.
- Instantiate it to produce `julia/Manifest.toml`.
- Run a clean import smoke test and record Julia/package versions.

## 2. Prove the purification construction

- First add Julia tests for the normalized local identity pair and an exactly
  solvable interacting impurity at finite beta.
- Implement the physical/ancilla MPS construction and imaginary-time gate.
- Verify impurity occupancy and double occupancy against the analytic trace.

## 3. Fit and serialize the bath

- First test quadrature symmetry, positivity, total spectral weight, and
  deterministic JSON output.
- Implement semicircular Gauss-Chebyshev discretization.
- Emit finite bath parameters and broadened hybridization on a common grid.

## 4. Build the independent ED oracle

- First test fermionic anticommutation, Hermiticity, particle-hole symmetry,
  atomic/noninteracting limits, and Green-function endpoint identity.
- Implement the complete finite-bath Hamiltonian in the full Fock space.
- Compute exact thermal \(n_d\), double occupancy, and \(G(\tau)\).
- Publish a machine-readable oracle artifact for the same bath used by MPS.

## 5. Configure TRIQS/CT-HYB separately

- Inspect host/compiler/MPI/HDF5 prerequisites without modifying the Julia or
  Python solver environments.
- Create a pinned environment/build recipe and smoke test.
- Keep CT-HYB output and provenance separate, then compare on the same
  \(\tau\)-grid and parameter convention.

## 6. Acceptance

- Run focused tests, then the complete solution test suite.
- Require the finite-bath MPS/ED maximum observable error to be at most
  \(10^{-6}\) before scaling beta, bath size, or bond dimension.

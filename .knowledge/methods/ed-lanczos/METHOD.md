<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ./ref.bib. -->

# Exact Diagonalization — Iterative Lanczos (ED Lanczos)

Krylov-subspace iteration (Lanczos / Arnoldi / shift-invert) to compute a few extremal or interior eigenpairs of a sparse Hamiltonian, matrix-free.

## Method card

### What it is

ED Lanczos builds an orthonormal Krylov basis `{|v₀⟩, H|v₀⟩, H²|v₀⟩, …}` from a random starting vector and extracts the extreme (lowest/highest) or interior eigenvalues and eigenvectors via a tridiagonal eigenvalue problem. Because only a few Lanczos vectors are kept at any time, the memory requirement is `O(D_blk)` (a few full vectors) rather than the `O(D_blk²)` of full diagonalization, allowing access to system sizes up to `N≈48–50` at the supercomputer frontier. Matrix-vector products `H|v⟩` exploit the sparsity of the Hamiltonian (`N_nnz ≈ N · D_blk` for short-range models). Dynamical correlation functions `S(q,ω)` are obtained via the continued-fraction (Haydock) method without storing all eigenvectors. Shift-invert Lanczos targets interior eigenstates.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Ground-state energy · ground-state wavefunction · few excited states & gaps · dynamical `S(q,ω)` (continued-fraction) · real-time dynamics (Krylov exponentiation) · entanglement entropy · order parameters | Level statistics and full thermodynamics require the full spectrum (ED full). |
| M2 regime | T=0 (a few low eigenstates); real-time dynamics on finite clusters | Finite-T via FTLM/TPQ (separate method) uses the same matrix-free machinery. |
| M3 accuracy class | Numerically exact, deterministic | The Lanczos recursion converges to machine precision for the targeted eigenpairs; no stochastic error. |
| M4 dimension fit (A1) | Any dimension / geometry | Same as ED full: geometry only affects `N_nnz` and the sparsity pattern, not the algorithm's applicability. |
| M5 statistics & local dim (A3) | Spin / hard-core boson / soft-core boson / fermion / any | `D_H = d^N`; large `d` shrinks reachable `N`, same as ED full, but Lanczos reaches about 2× larger `N` than full diag. |
| M6 entanglement regime (B5) | Volume-law tolerated | No entanglement restriction; the ground-state wavefunction is stored as a full vector of length `D_blk`. |
| M7 sign-problem dependence (C12) | Sign-immune | Not a Monte Carlo method; no sign problem. |
| M8 symmetry exploitation (C9/C10) | U(1)/SU(2)/Z₂/parity block-diagonalize `H`; translation (k) and point-group reduce `D_blk` by `≈N` and `\|G\|` | The decisive cost lever: symmetry reduction is the primary route to larger system sizes. With full symmetry, `N≈48–50` is accessible (Wietek–Läuchli 2018). |
| M9 time complexity | `O(n_iter · N_nnz)` where `N_nnz ≈ N · D_blk` for short-range (A4) Hamiltonians | `n_iter` ≈ tens for gapped (B6) systems; hundreds for critical or near-degenerate systems; much higher for shift-invert (interior states). |
| M10 memory | `O(D_blk)` | Stores only a few Lanczos vectors of length `D_blk`; the key advantage over ED full. |
| M11 control knob | `n_iter` (number of Lanczos steps) — controls convergence of the targeted eigenpairs | Convergence criterion: residual norm `‖H|ψ⟩ − E|ψ⟩‖ < ε`. For the GS, convergence is typically fast (tens of iterations); for excited states or `S(q,ω)`, more iterations needed. |
| M12 scale frontier | ~40 sites routine with full symmetry; **48–50 sites at the supercomputer frontier** (Wietek–Läuchli 2018, arXiv:1804.05028, sublattice-coding with translation + point group + parity) | Frontier requires distributed-memory storage of `D_blk`-length vectors across many nodes. |
| M13 primary approximation / bias | None — numerically exact for the targeted eigenpairs | The finite cluster approximation (open/PBC) is external; bulk extrapolation requires finite-size scaling. |
| M14 hard blocker / failure mode | `d^N` wall (same as ED full, but shifted to larger `N`): `D_blk` vector storage requires distributed memory beyond ~40 sites; near-degenerate or critical systems (B6) require many iterations (`n_iter → ∞` at a quantum critical point) | Long-range interactions (A4) raise `N_nnz` and slow matrix-vector products. |

### Cost & scaling

- Time: `O(n_iter · N_nnz)` with `N_nnz ≈ N · D_blk` for short-range models; `n_iter` ~ tens (gapped) to hundreds (critical)
- Memory: `O(D_blk)` — stores only a few Krylov vectors (the key advantage over ED full)
- Control knob: `n_iter` (Lanczos iterations) — controls eigenpair convergence to machine precision
- Scale frontier: ~40 sites routine; **48–50 sites** at the supercomputer frontier with full symmetry reduction

### Accuracy & guarantees

- Class: numerically exact, deterministic (for the targeted eigenpairs)
- Primary approximation & its control: finite cluster; bulk physics requires finite-size scaling
- Error scaling: residual norm `‖H|ψ⟩ − E|ψ⟩‖` decreases exponentially with `n_iter`; machine precision typically reached in < 500 iterations for the GS

### Tasks it computes

- Ground-state energy and wavefunction (the primary use case)
- Few lowest excited states (targeting different symmetry sectors separately, or via block Lanczos / shift-invert)
- Spectral gap (from the first excited state in the same sector)
- Dynamical structure factor `S(q,ω)` and spectral functions `A(ω)` via the Lanczos continued-fraction (Haydock) method — extra Krylov runs per `q` point
- Real-time evolution of finite-cluster states via Krylov exponentiation `e^{−iHt}|ψ⟩`
- Entanglement entropy and spectrum from the GS wavefunction

### Recommended for (models / regimes)

- **Primary GS solver for small-to-medium clusters:** all lattice models up to `N≈40`; the benchmark oracle for DMRG, QMC, VMC at these sizes
- **Dynamical properties `S(q,ω)` on small clusters:** frustrated magnets (B8, C12 sign-ful) where QMC cannot reach real-frequency data without analytic continuation
- **Finite-cluster Krylov dynamics:** quench dynamics, spectral weight computation on clusters where TEBD would be overkill
- **Interior excited states (shift-invert):** eigenstate thermalization hypothesis (ETH) studies in specific energy windows
- Per `method-property-map.md` (ED profile): applicable when `D_H ≲ 10⁷–10⁸` after symmetry reduction; preferred over ED full whenever the full spectrum is not required

### Key reference

[@sandvik_2010_computational] — covers the Lanczos algorithm, symmetry reduction, continued-fraction computation of `S(q,ω)`, and benchmarks for Heisenberg chains and ladders.
Rendered: `../../literature/ed/1101.3281_computational-studies-of-quantum-spin-systems.md` _(reused)_.

[@gagliano_1987_dynamical] — original demonstration of the Lanczos continued-fraction method for computing dynamical properties `S(q,ω)` at T=0; the standard reference for dynamical Lanczos.
Rendered: `../../literature/ed/10-1103-physrevlett-59-2999.md` _(reused)_.

### Benchmarks

- ED Lanczos frontier: **48–50 sites** (spin-½ kagome/triangular with full symmetry, sublattice coding) [Wietek–Läuchli, arXiv:1804.05028; verified in `method-survey.md` §1.2].
- GS energy convergence: residual `< 10⁻¹²` in < 200 Lanczos steps for gapped 1D Heisenberg (`N=36`) [@sandvik_2010_computational].
- `S(q,ω)` via continued-fraction: `n_CF ≈ 200` Lanczos steps per `q` point for Heisenberg chain `N=24` [@gagliano_1987_dynamical].
- `n_iter` ~ 50 (gapped) vs ~ 500 (critical, near-degenerate) — `B6` dependence verified in `method-survey.md` §1.2.

## How it is used / Operational

**Owning skill:** `/method-ed` (primary), with tool skills `/using-xdiag` and `/using-quspin`.

**Default workflow:**
1. Apply symmetry reduction (U(1) Sᶻ or N_e, translation `k`, point group, parity) to select the target block.
2. Implement the sparse matrix-vector product `H|v⟩` (xdiag's `apply_H`, QuSpin's `H.matvec`).
3. Run Lanczos iterations until the residual norm `< ε` (e.g., `1e-12`); extract the targeted eigenpairs.
4. For `S(q,ω)`: run additional Krylov runs from `|q, σ⟩ = S^z_q |GS⟩` using the continued-fraction method.
5. For real-time dynamics: use Krylov exponentiation (`scipy.sparse.linalg.expm_multiply` or xdiag's Krylov time stepper).

**Verification pointers:**
- GS energy must agree with ED full (if feasible) to machine precision.
- For `S(q,ω)`, verify sum rules: `∑_q ∫ S(q,ω) dω = ⟨S²⟩` (total spin sum rule).
- For dynamics, energy conservation: `⟨E(t)⟩` should be constant to `< 10⁻¹⁰` relative.

**Cross-links:**
- Survey: `method-survey.md` §1.2 (Exact diagonalization — iterative)
- Model↔method gate: `method-property-map.md` (ED profile)
- Complementary methods: ED full (full spectrum, smaller `N`), FTLM/TPQ (finite-T, same memory footprint), KPM (spectral densities without eigenstates)

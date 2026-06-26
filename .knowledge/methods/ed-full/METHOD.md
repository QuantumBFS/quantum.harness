<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Exact Diagonalization — Full (ED full)

Full diagonalization of the finite Hamiltonian matrix; returns the complete spectrum and all eigenvectors.

## Method card

### What it is

ED full constructs the Hamiltonian matrix in a symmetry-reduced block (using U(1), translation, point-group, and spin-inversion quantum numbers) and performs a dense eigendecomposition via LAPACK routines (`dsyevd`/`zheevd`). The result is all eigenvalues and eigenvectors within the block, giving numerically-exact access to the full spectrum, level statistics (ETH, quantum chaos), and all thermodynamic quantities via canonical/grand-canonical sums. It is the universal oracle against which all approximate methods are calibrated, but is limited to small system sizes by the `d^N` Hilbert-space wall.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Full spectrum · all eigenvectors · level statistics · ETH diagnostics · thermodynamics · entanglement spectrum · order parameters · exact finite-cluster dynamics | Only method that natively returns the full spectrum; thermodynamics via exact canonical sum. |
| M2 regime | T=0 and finite-T (all temperatures from a single diagonalization) | Full spectrum covers all regimes at once. |
| M3 accuracy class | Numerically exact, deterministic | Errors are only floating-point rounding; no statistical error, no truncation bias. |
| M4 dimension fit (A1) | Any dimension / geometry | Applicable to any lattice; total site count `N` is the only limit, not geometry. |
| M5 statistics & local dim (A3) | Spin / hard-core boson / soft-core boson / fermion / any | Local dim `d` enters as `D_H = d^N`; large `d` (Hubbard `d=4`, soft-core bosons) drastically shrinks reachable `N`. |
| M6 entanglement regime (B5) | Volume-law tolerated | No entanglement restriction; full Hilbert-space representation requires `O(D_blk²)` memory. |
| M7 sign-problem dependence (C12) | Sign-immune | Not a Monte Carlo method; no sign problem. |
| M8 symmetry exploitation (C9/C10) | U(1)/SU(2)/Z₂/parity block-diagonalize `H`; translation (k) and point-group reduce `D_blk` by `≈N` and `\|G\|` respectively | Decisive cost lever: `D_blk = D_H / (reduction factor)`. With full symmetry (Sᶻ + momentum + point group + parity), a spin-½ chain of `N≈20` is trivial dense; dense ED reaches ~28–30 sites maximum (see M12). The ~40-site and 48–50-site numbers belong to iterative (Lanczos) ED — see ed-lanczos card. |
| M9 time complexity | `O(D_blk³)` | Dense eigensolve (LAPACK `dsyevd`); dominant cost for useful system sizes. |
| M10 memory | `O(D_blk²)` | Must store the full dense matrix and all eigenvectors; the first wall hit in practice. |
| M11 control knob | None (exact) — the only knob is which symmetry sectors to diagonalize | No convergence parameter: result is exact within machine precision. |
| M12 scale frontier | ~20 sites trivial dense; **~28–30 sites maximum for dense ED** with full symmetry (N=28 full-symmetry D_blk~1.8×10⁵ → ~250–520 GB (real vs complex double); N=32 → ~44 TB, infeasible) | Dense `O(D_blk²)` memory is the binding wall. Iterative (Lanczos) ED reaches ~40 sites routine and 48–50 at the supercomputer frontier (Wietek–Läuchli 2018, arXiv:1804.05028) — see ed-lanczos card. |
| M13 primary approximation / bias | None — numerically exact | Only approximation is the finite cluster (open/periodic BC); bulk extrapolation requires finite-size scaling. |
| M14 hard blocker / failure mode | Hilbert-space `d^N` wall: dense `O(D_blk²)` memory walls by `N ≈ 30` (spin-½) or `N ≈ 16` (Hubbard `d=4`) | No workaround within ED full; switch to ED Lanczos for larger `N` or for a few eigenstates. |

### Cost & scaling

- Time: `O(D_blk³)` — LAPACK dense eigensolve
- Memory: `O(D_blk²)` — stores the full matrix and all eigenvectors
- Control knob: none (exact); symmetry-sector choice determines `D_blk`
- Scale frontier: ~20 sites trivial dense; ~28–30 sites maximum for dense ED (O(D_blk²) memory wall; N=28 D_blk~1.8×10⁵ → ~250–520 GB (real vs complex double)); iterative/Lanczos ED reaches ~40 sites routine and 48–50 at the supercomputer frontier (Wietek–Läuchli 2018) — see ed-lanczos card

### Accuracy & guarantees

- Class: numerically exact, deterministic
- Primary approximation & its control: finite cluster only; finite-size scaling to thermodynamic limit is external to the method
- Error scaling: floating-point rounding (`~10⁻¹⁵` relative) for the eigenvalues; no systematic bias

### Tasks it computes

- Full spectrum and all eigenvectors (the defining task of ED full)
- Level statistics (level-spacing ratio `r`, spectral form factor) for ETH and quantum chaos studies
- Thermodynamics at all temperatures: partition function `Z(T)`, internal energy, specific heat, susceptibility, free energy
- Entanglement entropy and entanglement spectrum (from the eigenvectors)
- Order parameters, correlation functions, structure factors
- Exact finite-cluster real-time dynamics via Krylov exponentiation (cheaper than full diag; see ED Lanczos)

### Recommended for (models / regimes)

- **Universal oracle / cross-check:** all models at small `N`; primary validation target for DMRG, QMC, VMC, iPEPS
- **Level statistics and ETH:** non-integrable models (Heisenberg, Hubbard, SYK) at sizes where the full spectrum fits
- **Thermodynamics at all temperatures:** small frustrated clusters (kagome, pyrochlore) where QMC has a sign problem (C12) and FTLM requires many random vectors
- **Topological models (B7):** ED on a torus gives ground-state degeneracy and TEE directly
- **Any model with small Hilbert space:** spin-½ chains up to `N≈20`, Hubbard up to `N≈12–16` sites
- Per `method-property-map.md` (ED profile): applicable when `D_H ≲ 10⁷–10⁸` after symmetry reduction

### Key reference

[@sandvik_2010_computational] — comprehensive tutorial covering the full diagonalization approach, symmetry reduction (momentum sectors, point group, spin inversion), thermodynamic observables via exact canonical sums, and benchmarks for Heisenberg and Hubbard models.
Rendered: `../../literature/ed/1101.3281_computational-studies-of-quantum-spin-systems.md` _(reused)_.

[@weisse_2008_exact] — authoritative chapter on exact diagonalization techniques including Lanczos; covers symmetry implementation, spectral functions, and finite-temperature methods.
Rendered: `../../literature/ed/10-1007-978-3-540-74686-7-18.md` _(reused)_.

### Benchmarks

- Dense ED frontier: **~28–30 sites** (spin-½ with full U(1) + translation + point-group symmetry); N=28 gives D_blk~1.8×10⁵ → ~250–520 GB (real vs complex double) for the dense matrix; N=32 → ~44 TB, infeasible.
- Iterative (Lanczos/Krylov) ED frontier: **48–50 sites** (spin-½ kagome/square lattice with sublattice coding, sparse matrix-vector products) [Wietek–Läuchli, arXiv:1804.05028; method-survey.md §1.1] — this belongs to ed-lanczos, not ed-full.
- Spin-½ chain `N=20`: Hilbert-space dim `D_H = 2^20 ≈ 10^6`; with U(1) largest block `C(20,10) ≈ 184,756`; dense diag trivial on a laptop [@sandvik_2010_computational].
- Hubbard `d=4`, `N=16`: `D_H = 4^16 ≈ 4×10^9` (full Fock space, all fillings; at half-filling `D_H = C(16,8)² ≈ 1.66×10^8`); requires full symmetry reduction to be tractable [method-survey.md §1.1].

## How it is used / Operational

**Owning skill:** `/method-ed` (primary), with tool skills `/using-xdiag` and `/using-quspin`.

**Default workflow:**
1. Identify the symmetry group (U(1) Sᶻ or N_e, translation k, point group, parity) via the model's C9/C10 axes.
2. Construct the Hamiltonian in the target symmetry block using xdiag or QuSpin.
3. Call the full diagonalization routine (e.g., `xdiag.eig_sym` or `scipy.linalg.eigh`).
4. Compute observables: thermodynamic sums, level statistics, entanglement entropy.

**Verification pointers:**
- Cross-check GS energy against ED Lanczos (which targets only the GS but should agree exactly).
- Validate level-spacing ratio `r = min(δ_n, δ_{n+1})/max(δ_n, δ_{n+1})`: GOE value ≈ 0.530, Poisson ≈ 0.386.
- For thermodynamics, verify high-T limit matches the exactly known entropy `S = N ln d`.

**Cross-links:**
- Survey: `method-survey.md` §1.1 (Exact diagonalization — full)
- Model↔method gate: `method-property-map.md` (ED profile)
- Complementary methods: ED Lanczos (fewer eigenstates, larger `N`), FTLM/TPQ (finite-T without full diag)

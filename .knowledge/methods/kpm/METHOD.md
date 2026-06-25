<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ./ref.bib. -->

# Kernel Polynomial Method (KPM / Chebyshev)

Expand spectral densities in Chebyshev polynomials of a sparse Hamiltonian; linear-in-`M` cost to compute density of states, spectral functions, and dynamical correlations.

## Method card

### What it is

KPM represents spectral quantities (density of states, dynamical structure factor `S(q,ω)`, optical conductivity, single-particle spectral function `A(ω)`) as a truncated Chebyshev-polynomial expansion. The expansion coefficients `μ_m = Tr[T_m(H)]` are estimated stochastically by averaging over `R` random vectors: `μ_m ≈ (1/R) Σ_r ⟨r|T_m(H)|r⟩`, where each `T_m(H)|r⟩` is computed by the three-term Chebyshev recursion using only sparse matrix-vector products. A Jackson kernel (or other kernel) is applied to the truncated series to control the Gibbs oscillations and give a controlled approximation of the spectral function at spectral resolution `≈ bandwidth/M`. The method never diagonalizes the Hamiltonian and requires no eigenvalues; it accesses the spectral density directly. Memory is `O(D_H)` for the state vectors — no eigenvalue storage.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Density of states (DOS) · spectral function `A(ω)` · dynamical structure factor `S(q,ω)` · optical / dynamical conductivity · finite-T traces via Chebyshev expansion of `e^{-βH}` | Does NOT provide individual eigenstates, the GS wavefunction, or entanglement data (these require Lanczos). |
| M2 regime | T=0 spectral densities · finite-T thermodynamic traces (stochastic Chebyshev) | Ground-state GS energy not native (no variational principle); spectral densities at all `ω`. |
| M3 accuracy class | Stochastic-trace + controlled-bias; deterministic per random vector, stochastic across `R` vectors | Bias: Gibbs ripples from truncating the Chebyshev series at order `M` — controlled by Jackson/Lorentz kernel; statistical error `∝ 1/√(R · D_H)` from the stochastic trace. Resolution `≈ bandwidth/M` improves with `M`. |
| M4 dimension fit (A1) | Any dimension / geometry — wins for large sparse Hamiltonians in any `d` | Sparsity (A4) is the key gate; short-range interactions → small `N_nnz` per site → cheap matrix-vector products. |
| M5 statistics & local dim (A3) | Spin / hard-core boson / soft-core boson / fermion / any | `D_H = d^N`; memory `O(D_H)` (stores one or a few state vectors of length `D_H`). |
| M6 entanglement regime (B5) | Volume-law tolerated | No entanglement restriction; KPM never constructs a wavefunction ansatz — it works with the full `D_H`-dimensional Hilbert space. |
| M7 sign-problem dependence (C12) | Sign-immune | Not a Monte Carlo method; random vectors sampled in Hilbert space, not field space. |
| M8 symmetry exploitation (C9/C10) | Block structure can reduce `D_H` (same as ED Lanczos); random vectors drawn within a symmetry sector for sector-resolved DOS/`S(q,ω)` | Symmetry is less critical than for ED (no need to diagonalize): KPM already reaches full `D_H` scale cheaply. |
| M9 time complexity | `O(M · R · N_nnz)` where `M` = #Chebyshev moments, `R` = #random vectors, `N_nnz` = #nonzeros in `H` | Linear in `M` and `R`; no `D_H³` or `D_H^2` factor. Scales to very large sparse Hamiltonians inaccessible to Lanczos. |
| M10 memory | `O(D_H)` — stores one or a few state vectors of length `D_H` | No matrix storage (matrix-free); no eigenvalue array; just the state vectors and the recursion coefficients. |
| M11 control knob | `M` (#Chebyshev moments) — controls spectral resolution `≈ bandwidth/M` and Gibbs-ripple suppression | Larger `M` → finer spectral resolution → higher cost (linearly). `R` controls statistical error `1/√(R · D_H)`. Both knobs are independent and can be tuned separately. |
| M12 scale frontier | Largest system sizes accessible among the exact methods: `D_H ≈ 10^{9}–10^{10}` feasible on a single workstation since only `O(D_H)` memory is needed for the vectors | Without the `O(D_H²)` or `O(D_H³)` wall, KPM reaches much larger `D_H` than ED full/Lanczos for the tasks it computes (spectral densities). |
| M13 primary approximation / bias | Truncated Chebyshev expansion at order `M` — spectral resolution limited to `≈ bandwidth/M`; Gibbs oscillations damped by kernel (controlled) | The kernel choice (Jackson, Lorentz) determines the trade-off between resolution and Gibbs suppression; this is a controlled, improvable approximation. |
| M14 hard blocker / failure mode | `O(D_H)` memory wall — must store state vectors of length `D_H`; not a route to individual eigenstates or the GS wavefunction; poor for sharp spectral features if `M` is limited | Long-range interactions (A4) raise `N_nnz` and slow the matrix-vector products; dense Hamiltonians break the sparse advantage. |

### Cost & scaling

- Time: `O(M · R · N_nnz)` — linear in `M` and `R`; `N_nnz ≈ N · D_H` for short-range models
- Memory: `O(D_H)` — only a few state vectors; no eigenvalue storage
- Control knob: `M` (#moments) → spectral resolution `≈ bandwidth/M`; `R` (#random vectors) → statistical error `1/√(R · D_H)`
- Scale frontier: `D_H ≈ 10^9–10^{10}` feasible (memory-limited only by the state vector size)

### Accuracy & guarantees

- Class: controlled-bias (improvable), stochastic
- Primary approximation & its control: Chebyshev truncation at order `M` with Jackson/Lorentz kernel; increasing `M` improves resolution
- Error scaling: spectral resolution `≈ bandwidth/M`; stochastic trace error `∝ 1/√(R · D_H)`; Gibbs oscillations exponentially suppressed by the kernel

### Tasks it computes

- Density of states (DOS): `ρ(ω) = (1/D_H) Tr[δ(ω − H)]` at resolution `≈ bandwidth/M`
- Dynamical structure factor `S(q,ω) = ∑_n |⟨n|S^z_q|GS⟩|² δ(ω − E_n + E_0)` (or its finite-T version)
- Optical / dynamical conductivity `σ(ω)`
- Single-particle spectral function `A(ω)` for fermionic systems
- Finite-T thermodynamic traces using the Chebyshev expansion of `e^{-βH}`

### Recommended for (models / regimes)

- **Large sparse Hamiltonians where only spectral densities are needed:** Anderson localization, random Hamiltonians, large Heisenberg clusters — situations where `D_H` is too large for Lanczos eigenstates but `O(D_H)` memory is feasible
- **DOS and optical conductivity surveys:** tight-binding / Hubbard models on large clusters where Lanczos continued-fraction would require many eigenstates
- **Disorder-averaged spectral functions:** quench-disorder studies where `R` random vectors serve dual purpose as disorder-average samples
- **Transport coefficients:** electrical/thermal conductivity via the Kubo formula on large clusters
- Per `method-property-map.md` (ED profile, extended): a matrix-free spectral-density method that extends the ED harness to larger `D_H` for spectral tasks

### Key reference

[@weisse_2006_kernel] — authoritative Reviews of Modern Physics paper by Weisse, Wellein, Alvermann, and Fehske; defines the Chebyshev expansion, kernel choices (Jackson, Lorentz, Dirichlet), stochastic-trace evaluation, and applications to DOS, dynamical conductivity, and spectral functions. The primary reference for all KPM implementations.
Rendered: `./cond-mat-0504627_the-kernel-polynomial-method.md` _(downloaded)_.

### Benchmarks

- Time cost: `O(M · R · N_nnz)` — verified scaling in [@weisse_2006_kernel] §III; resolution `≈ bandwidth/M` confirmed for the 1D Heisenberg chain DOS.
- Memory: `O(D_H)` — storing two state vectors of length `D_H`; verified in [method-survey.md §1.4].
- Stochastic-trace error: `∝ 1/√(R · D_H)` — for `D_H = 10^8` and `R = 10`, error `≈ 3×10^{-5}` per spectral bin [@weisse_2006_kernel §II.D].
- KPM vs Lanczos for DOS: KPM at `M = 2000` gives resolution `≈ bandwidth/2000`; Lanczos continued-fraction achieves similar resolution at comparable cost but requires a starting vector near the target state [@weisse_2006_kernel §IV].

## How it is used / Operational

**Owning skill:** `/method-ed` (primary), with tool skills `/using-xdiag` and `/using-quspin`.

**Default workflow:**
1. Rescale the Hamiltonian to `[-1, 1]`: `H̃ = (H − b) / a` where `a = (E_max − E_min)/2`, `b = (E_max + E_min)/2` (requires estimating the spectral bounds, e.g., via a few Lanczos steps).
2. Compute the Chebyshev moments `μ_m = (1/R) Σ_r ⟨r|T_m(H̃)|r⟩` for `m = 0, …, M−1` via the three-term recursion `|α_{m+1}⟩ = 2H̃|α_m⟩ − |α_{m−1}⟩`.
3. Apply the Jackson kernel (or Lorentz kernel) to the moment sequence to suppress Gibbs oscillations.
4. Evaluate the spectral density at target frequencies `ω` via the Chebyshev reconstruction formula.
5. For `S(q,ω)`: compute the cross-correlation `⟨r|T_m(H̃)|r'⟩` where `|r'⟩ = O_q|GS⟩` (requires one Lanczos step to find `|GS⟩`, or a random vector `|r⟩` for the stochastic-trace version).

**Verification pointers:**
- DOS integral: `∫ ρ(ω) dω = 1` (normalization) — check to `< 0.1%`.
- For `S(q,ω)`: verify the total spectral weight sum rule `∑_q ∫ S(q,ω) dω = ⟨S²⟩`.
- Convergence with `M`: plot a sharp feature (e.g., the Heisenberg chain two-spinon continuum edge) and verify width `∝ 1/M`.
- Compare to Lanczos continued-fraction at small `N` — should agree to `O(1/M)` resolution.

**Cross-links:**
- Survey: `method-survey.md` §1.4 (Kernel polynomial method)
- Model↔method gate: `method-property-map.md` (ED profile — spectral functions)
- Complementary methods: ED Lanczos (individual eigenstates, smaller `D_H`), FTLM/TPQ (thermodynamic averages), DQMC + analytic continuation (spectral functions at finite T for sign-free models)

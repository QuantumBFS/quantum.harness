<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ./ref.bib. -->

# Finite-Temperature Lanczos Method and Thermal Pure Quantum States (FTLM / TPQ)

Stochastic random-vector sampling for finite-temperature thermodynamics and dynamical functions, without full diagonalization; exploits quantum typicality.

## Method card

### What it is

FTLM (Jaklič–Prelovšek 1994) and TPQ (Sugiura–Shimizu 2012/2013) compute finite-temperature thermal averages by replacing the Boltzmann trace `Tr[e^{-βH} O] / Tr[e^{-βH}]` with an average over a small number of random starting vectors. For each random vector `|r⟩`, a short Lanczos run generates the Krylov basis from which the thermal expectation value is computed. The statistical error from using `R` random vectors scales as `1/√(R·D_H)` and shrinks automatically with system size due to quantum typicality — at large `D_H`, a single random vector gives exponentially good estimates. TPQ directly evolves `|r⟩` in imaginary time (`e^{-βH/2}|r⟩`) to obtain a thermal pure quantum state; FTLM uses the Lanczos basis for the same computation. Both methods share the `O(D_blk)` memory footprint of iterative ED and work with the same sparse matrix-vector product.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Finite-T thermodynamics (free energy, internal energy, specific heat `C_v`, susceptibility `χ`) · finite-T dynamical `S(q,ω)` (FTLM) · canonical and grand-canonical ensembles (canonical TPQ) | Does NOT natively give the full spectrum or level statistics (need ED full for those). |
| M2 regime | Finite-T (all temperatures including T→0 limit via large `β`) | T=0 ground-state properties accessible via large-`β` limit; in practice ED Lanczos is cheaper for T=0. |
| M3 accuracy class | Stochastic (statistical error `∝ 1/√(R·D_H)`); controlled-bias (improvable by increasing `R`) | Error shrinks with system size (typicality) — a key practical advantage at `N ≳ 20`. Deterministic per random vector; stochastic only across the average. |
| M4 dimension fit (A1) | Any dimension / geometry | Same as ED full/Lanczos: geometry enters only through `N_nnz` and the symmetry block structure. |
| M5 statistics & local dim (A3) | Spin / hard-core boson / soft-core boson / fermion / any | `D_H = d^N`; memory `O(D_blk)` means the accessible `N` matches ED Lanczos (not ED full). |
| M6 entanglement regime (B5) | Volume-law tolerated | Operates in the full Hilbert space; no entanglement restriction. |
| M7 sign-problem dependence (C12) | Sign-immune | Not a Monte Carlo method; random vectors in Hilbert space, not field-space sampling. |
| M8 symmetry exploitation (C9/C10) | U(1)/SU(2)/Z₂/parity block-diagonalize; translation and point-group reduce `D_blk` | Same symmetry reduction as ED Lanczos; random vectors drawn within the symmetry sector. |
| M9 time complexity | `O(R · n_iter · N_nnz)` where `R` = number of random vectors, `n_iter` = Lanczos steps per vector, `N_nnz ≈ N · D_blk` | At high `T`, `R` can be small (1–10); at low `T`, thermal fluctuations are larger and `R` must grow. |
| M10 memory | `O(D_blk)` | Stores only the current Lanczos basis vectors; same footprint as ED Lanczos. |
| M11 control knob | `R` (number of random vectors) — controls statistical error `1/√(R·D_H)` | At large `N`, even `R=1` can give < 1% error (typicality); at small `N`, need `R ≈ 10–100`. Standard canonical TPQ (Sugiura–Shimizu 2012/2013) applies `e^{-βH/2}|r⟩` via Krylov/Chebyshev — exact to machine precision with no Trotter error; `Δτ` is a knob only in Trotter-based TPQ implementations. |
| M12 scale frontier | Same as ED Lanczos: ~40 sites routine; frontier ~48–50 sites with full symmetry | Typicality means error improves with system size; FTLM/TPQ is most powerful for `N ≳ 20` where it beats ED full on memory while giving accurate finite-T results. |
| M13 primary approximation / bias | Stochastic trace approximation with `R` random vectors; error `∝ 1/√(R·D_H)` (controlled) | Finite cluster approximation for bulk thermodynamics; bulk limit requires finite-size scaling. |
| M14 hard blocker / failure mode | Very low `T` (large `β`): thermal fluctuations grow → `R` must increase to maintain accuracy; long imaginary-time Lanczos evolution becomes numerically delicate | `D_H` wall same as ED; sign-immune so no QMC sign problem. At very low `T`, ED Lanczos (T=0) or DMRG (finite-T purification) may be preferred. |

### Cost & scaling

- Time: `O(R · n_iter · N_nnz)` with `N_nnz ≈ N · D_blk` for short-range models
- Memory: `O(D_blk)` — same as ED Lanczos; no full matrix or all-eigenvector storage
- Control knob: `R` (random vectors) controlling statistical error `1/√(R · D_H)`; standard Krylov-TPQ has no `Δτ` (exact imaginary-time evolution); `Δτ` (error `O(Δτ²)`) applies only in Trotter-based TPQ implementations
- Scale frontier: ~40 sites routine; ~48–50 sites at the supercomputer frontier (same as ED Lanczos)

### Accuracy & guarantees

- Class: controlled-bias (improvable), stochastic
- Primary approximation & its control: trace replaced by `R`-sample average; error `1/√(R · D_H)` → use larger `R` or larger system (typicality)
- Error scaling: `∝ 1/√(R · D_H)`; at `N ≳ 20` and `R = 10`, errors are typically `< 0.1%` for thermodynamic observables

### Tasks it computes

- Finite-temperature free energy `F(T)`, internal energy `U(T)`, specific heat `C_v(T)`, magnetic susceptibility `χ(T)`
- Finite-T dynamical structure factor `S(q,ω,T)` via FTLM with additional Lanczos runs (extra cost)
- Canonical-ensemble thermal averages (canonical TPQ enforces exact particle number)
- Grand-canonical averages (FTLM with U(1) sectors summed)
- T=0 GS (via `β→∞` limit; in practice ED Lanczos is preferred for T=0)

### Recommended for (models / regimes)

- **Finite-T thermodynamics on frustrated or sign-ful clusters:** kagome Heisenberg, pyrochlore, J₁-J₂ square lattice, Kitaev honeycomb — where QMC has a sign problem (C12) and LTRG/XTRG is not yet implemented
- **Medium-sized clusters `N ≈ 20–40`:** where FTLM/TPQ beats ED full (memory `O(D_blk)` vs `O(D_blk²)`) while giving accurate finite-T results
- **Specific heat and susceptibility peaks:** identification of crossover temperatures, spin-gap detection, Schottky anomalies
- **Finite-T `S(q,ω)`:** dynamical neutron-scattering structure factor at finite `T` on finite clusters
- Per `method-property-map.md`: falls under the ED harness skill profile; preferred for D13 finite-T when QMC sign is present and LTRG/XTRG is unavailable

### Key reference

[@jaklic_1994_lanczos] — original FTLM paper by Jaklič and Prelovšek; establishes the random-vector Lanczos approach for finite-T thermodynamics and dynamical functions in correlated systems.
Rendered: `../../literature/ed/10-1103-physrevb-49-5065.md` _(reused)_.

[@sugiura_2012_thermal] — introduces the thermal pure quantum (TPQ) state concept; proves that a single random vector gives exponentially accurate thermal averages (typicality theorem).
Rendered: `../../literature/ed/10-1103-physrevlett-108-240401.md` _(reused)_.

[@sugiura_2013_canonical] — canonical TPQ extension enforcing exact particle-number conservation, enabling grand-canonical and canonical ensemble comparison.
Rendered: `../../literature/ed/10-1103-physrevlett-111-010401.md` _(reused)_.

### Benchmarks

- Statistical error `∝ 1/√(R · D_H)`: for `N=20` spin-½ (`D_H ≈ 10^6`), `R=10` gives error `≈ 3×10^{-4}` per observable [@sugiura_2012_thermal].
- FTLM specific heat for Heisenberg chain `N=28`: agrees with Bethe ansatz TBA to < 0.5% for `T ≥ J/10` with `R=20` [@jaklic_1994_lanczos].
- Cost per random vector: `n_iter ≈ 100–200` Lanczos steps for convergence at intermediate `T` [method-survey.md §1.3].

## How it is used / Operational

**Owning skill:** `/method-ed` (primary), with tool skills `/using-xdiag` and `/using-quspin`.

**Default workflow:**
1. Apply the same symmetry reduction as ED Lanczos (U(1) Sᶻ or N_e, translation, point group).
2. Draw `R` random normalized vectors `|r_i⟩` uniformly from the Hilbert space (or a symmetry sector).
3. For each `|r_i⟩`: run `n_iter` Lanczos steps to build a Krylov basis; diagonalize the tridiagonal matrix; compute the finite-T observable via the spectral decomposition in the Krylov basis.
4. Average over `R` random vectors; estimate the statistical error from the variance.
5. Sweep over `β` (temperature) without re-running: the Krylov basis stores the full temperature dependence.

**Verification pointers:**
- Compare to ED full at small `N` where both are feasible; should agree to machine precision (per-sample).
- High-T limit: `⟨E⟩ → 0` and `⟨E²⟩ → ‹Tr[H²]›/D_H` — analytically computable cross-check.
- Check typicality convergence: plot observable vs `R` and verify `1/√R` scaling.
- For canonical TPQ: verify that `⟨N⟩ = N_e` exactly (particle number conservation).

**Cross-links:**
- Survey: `method-survey.md` §1.3 (Finite-temperature Lanczos and TPQ)
- Model↔method gate: `method-property-map.md` (ED profile — finite-T)
- Complementary methods: ED full (full spectrum, small `N`), ED Lanczos (T=0 GS), LTRG/XTRG (finite-T without `d^N` wall, sign-free 2D), QMC SSE (finite-T, sign-free lattices at large `N`)

<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Functional Renormalization Group (fRG)

Derives exact flow equations for the one-particle-irreducible (1PI) effective action as a function of an infrared cutoff `Λ`, and truncates the vertex expansion at finite order to identify leading instabilities in correlated Fermi systems.

## Method card

### What it is

The functional renormalization group (fRG) is a field-theoretic implementation of Wilson's RG idea. An infrared momentum (or frequency) cutoff `Λ` is introduced to regularize the free propagator. Exact flow equations (Wetterich equation) govern how the 1PI vertices (self-energy, two-particle vertex, ...) evolve as `Λ` is lowered from `∞` (non-interacting) to `0` (full theory). In practice, the infinite hierarchy of flow equations is truncated at the two-particle vertex level (one-loop or Katanin-truncated), and the two-particle interaction vertex `Γ^(4)` (four external legs) is parameterized by `N_patch` momentum-space patches. When `Γ^(4)` diverges in a particular channel (magnetic / superconducting / charge), this signals a leading instability and defines a pseudo-critical scale `Λ_c`. The method detects phase boundaries and leading ordering tendencies but does not construct the ordered ground state.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Leading-instability phase diagrams (magnetic, superconducting, charge-density-wave) · susceptibilities · pseudo-critical scales `Λ_c` · renormalized quasiparticle properties | NOT ground-state energies of strongly-correlated phases; the divergence signals an instability, not the true ordered state. |
| M2 regime | T=0 and finite-T (cutoff flow equations work at both); real-frequency accessible via Keldysh fRG | Standard formulation at T=0 or T>0 in Matsubara; real-time dynamics via Keldysh formulation. |
| M3 accuracy class | Controlled approximation (truncation order is the knob); uncontrolled at strong coupling | Weak–intermediate coupling: one-loop + Katanin truncation is a controlled expansion; strong coupling truncation breaks down. |
| M4 dimension fit (A1) | Any dimension (1D, 2D, 3D) | Particularly powerful in 2D (competing instabilities in the Hubbard model); 1D reproduces bosonization results. |
| M5 statistics & local dim (A3) | Fermions (fermionic fRG); bosonic fRG also exists | Fermionic sign enters only via the choice of statistics in the propagators; no sign problem in the sense of QMC. |
| M6 entanglement regime (B5) | No entanglement restriction (field-theoretic, not wavefunction-based) | fRG is not a wavefunction method; entanglement is not a controlling parameter. |
| M7 sign-problem dependence (C12) | Sign-immune (not a Monte Carlo method) | Deterministic flow equations; no stochastic sampling. |
| M8 symmetry exploitation (C9/C10) | Symmetries (SU(2), time-reversal, lattice point group) reduce vertex parameterization cost; translation used to parameterize vertex in momentum space | Exploiting symmetry reduces the number of independent vertex components and accelerates the flow. |
| M9 time complexity | `~O(N_patch³)` for the two-particle vertex flow (three momentum sums); higher-order frequency dependence adds factors | `N_patch` is the number of momentum patches on the Fermi surface; frequency dependence multiplies cost by `N_ω³`. |
| M10 memory | `O(N_patch²)` to `O(N_patch³)` for storing the two-particle vertex (depending on channel decomposition) | Channel decomposition (particle-particle, particle-hole crossed/direct) allows efficient storage. |
| M11 control knob | Truncation order (one-loop → Katanin → multiloop → ...) — controls vertex approximation; `N_patch` — controls momentum resolution | Higher truncation order is closer to exact but exponentially more expensive; `N_patch` convergence required. |
| M12 scale frontier | Thermodynamic limit (field-theoretic, no finite-size constraint); limited by `N_patch` and truncation order | Patch numbers `N_patch ~ 16–96` are typical; multiloop fRG up to 3–5 loop orders is state of the art. |
| M13 primary approximation / bias | Truncation of the vertex hierarchy at finite order (one-loop / Katanin / multiloop) — the controlled approximation | One-loop truncation is uncontrolled at strong coupling; multiloop fRG converges the loop expansion. |
| M14 hard blocker / failure mode | **Strong coupling not controlled**: vertex flow diverges when the coupling is too large (beyond weak–intermediate); cannot describe Mott physics or strongly frustrated states | Two-particle interaction vertex divergence `Γ^(4) → ∞` is a signature of instability, not a numerical failure — but the truncation breaks down before the physical strong-coupling fixed point. |

### Cost & scaling

- Time: `~O(N_patch³)` for two-particle vertex flow (three momentum sums); multiplied by `N_ω³` with frequency dependence
- Memory: `O(N_patch²)`–`O(N_patch³)` for vertex storage (channel-decomposed)
- Control knob: truncation order (one-loop → multiloop) and `N_patch` (momentum resolution)
- Scale frontier: thermodynamic limit; `N_patch ~ 16–96` typical; multiloop 3–5 loop orders is frontier

### Accuracy & guarantees

- Class: controlled approximation (in truncation order and `N_patch`); deterministic
- Primary approximation & its control: vertex hierarchy truncation at finite loop order; converges for weak–intermediate coupling
- Error scaling: one-loop error `O(g²)` at coupling `g`; multiloop improves systematically

### Tasks it computes

- Leading-instability identification: which channel (magnetic, SC, CDW) diverges first as `Λ→0`
- Phase diagrams in parameter space (e.g. `U`-`t'` plane for Hubbard model)
- Susceptibility enhancement and pseudo-critical scales `Λ_c`
- Renormalized quasiparticle effective mass and scattering rates (from self-energy flow)
- Competition between orders (e.g. AF vs d-SC in cuprates)

### Recommended for (models / regimes)

- **2D Hubbard model at weak–intermediate coupling** — detecting AF, SC, CDW instabilities and their competition
- **Kohn-Luttinger superconductivity** and unconventional pairing symmetry identification
- **Competing order parameter scenarios** where mean-field is biased toward a single channel
- **1D correlated systems** where fRG reproduces bosonization / Luttinger liquid results
- Per `method-property-map.md`: complement to MF (`/method-mf`) at weak coupling; sign-immune alternative to sign-ful QMC in frustrated 2D systems

### Key reference

[@metzner_2011_functional] — comprehensive review of fermionic fRG: flow equations, truncation schemes, vertex parameterizations, and applications to Hubbard-model instabilities.
Rendered: `./1105.5289_functional-renormalization-group-approach-to-correlated-ferm.md` _(downloaded)_.

### Benchmarks

- Hubbard model `U/t = 2`, square lattice: fRG pseudo-critical scale `Λ_c` consistent with RPA at weak coupling; leading instability AF at half-filling, d-SC away from half-filling [@metzner_2011_functional].
- `N_patch` convergence: local observables converge at `N_patch ~ 32–64` for 2D Hubbard [method-survey.md §6.4].
- Multiloop fRG vs one-loop: loop convergence demonstrated for 2D Hubbard at `U/t ≲ 3` [method-survey.md §6.4].

## How it is used / Operational

**Harness coverage:** fRG is a quantum-field-theoretic / perturbative RG method **outside the current harness skill set**. No dedicated `/method-frg` skill exists. It is not related to any of the core harness method skills (ED, MPS, PEPS, QMC, VMC, MF, LTRG, MCRG, QCS, PolyOpt).

**External tools:** mfrg (multiloop fRG), fRG codes from Salmhofer group (Tübingen), katanin-corrected codes; typically implemented in Fortran/C++ or Julia.

**Standard workflow:**
1. Parameterize the two-particle interaction vertex `Γ^(4)(k₁, k₂, k₃)` on `N_patch` Fermi-surface patches.
2. Set up the flow equations (one-loop / Katanin / multiloop) for self-energy and vertex.
3. Integrate the ODE system from `Λ=∞` to `Λ→0` (or until divergence).
4. Identify the leading channel from which susceptibility channel diverges first.
5. Record the pseudo-critical scale `Λ_c` and instability symmetry.

**Verification pointers:**
- Check `N_patch` convergence of `Λ_c` and instability symmetry.
- Compare one-loop vs Katanin-corrected flow (should agree at weak coupling).
- At half-filling Hubbard: leading instability should be AF for any `U > 0` on the square lattice.

**Cross-links:**
- Survey: `method-survey.md` §6.4 (fRG)
- Model↔method gate: `method-property-map.md`
- Complementary: `/method-mf` (mean-field instability analysis — cruder); DMFT (§6.1, wave-F card — local but captures strong coupling); coupled-cluster (§6.5, wave-F card — energetics at weak–moderate coupling)

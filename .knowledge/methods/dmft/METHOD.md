<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ./ref.bib. -->

# Dynamical Mean-Field Theory (DMFT)

Maps the lattice problem to a self-consistent quantum impurity model; yields the exact local self-energy in the limit of infinite coordination number (`Z→∞`).

## Method card

### What it is

DMFT (Metzner–Vollhardt 1989; Georges–Kotliar 1992) replaces the lattice with a single site (or cluster) embedded in a self-consistent Weiss field (the "effective bath"). The local Green's function and self-energy are computed by solving the resulting Anderson impurity model (AIM) with a high-level impurity solver (CT-QMC, ED-bath, NRG, or DMRG). The self-energy is fed back to the lattice Dyson equation, and the loop is iterated until convergence. Single-site DMFT is exact as the coordination number `Z→∞` (Metzner–Vollhardt theorem); cluster extensions (CDMFT, DCA, EDMFT with `N_c` cluster sites) restore short-range spatial correlations at exponentially growing cost.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Single-particle spectral function `A(ω)` / self-energy `Σ(ω)` / DOS · Mott transition & phase diagram · finite-T thermodynamics | Two-particle responses (susceptibilities, optical conductivity) require vertex functions → substantially more expensive; momentum resolution needs cluster extensions. |
| M2 regime | Finite-T natural; T=0 accessible; real-frequency via analytic continuation (MaxEnt/Padé) | Imaginary-axis QMC solver gives `G(iω_n)`; real-frequency requires analytic continuation with associated uncertainty. NRG solver gives real-frequency directly. |
| M3 accuracy class | Controlled (exact at `Z→∞`); uncontrolled at finite dimension | Cluster DMFT (`N_c` sites) is systematically improvable in `N_c` but at exponential cost. Sign from CT-QMC introduces stochastic error for multi-orbital/cluster cases. |
| M4 dimension fit (A1) | Exact as coordination `Z→∞` / infinite dimension (Metzner–Vollhardt); finite-D neglects spatial correlations beyond the cluster | Single-site DMFT best for 3D / high-coordination; short-range correlations restored by clusters (`N_c`); cluster cost grows **exponentially with `N_c`**. |
| M5 statistics & local dim (A3) | Fermions (multi-orbital supported); local Hilbert dim grows with #orbitals | CT-QMC sign worsens with #orbitals and cluster size; off-diagonal hybridization triggers sign problem. |
| M6 entanglement regime (B5) | No explicit entanglement gate (impurity picture) | The bath is integrated out; entanglement of impurity + bath is handled by the solver; no bond-dimension wall in principle. |
| M7 sign-problem dependence (C12) | Sign-problem enters through the CT-QMC impurity solver | CT-HYB/CT-INT sign worsens with multi-orbital / off-diagonal hybridization / cluster size. ED-bath and NRG solvers are sign-immune. |
| M8 symmetry exploitation (C9/C10) | Spin, orbital, and point-group symmetries reduce the impurity problem; translation exploited in DCA (momentum-space clusters) | Symmetry reduces bath/cluster dimension and cuts impurity-solver cost. |
| M9 time complexity | Self-consistency loop × impurity-solver cost: CT-QMC ~polynomial in `β` (with sign worsening for multi-orbital/cluster); ED-bath exponential in #bath sites; NRG `O(N_kept³)` per iteration | Cluster DMFT cost grows **exponentially with `N_c`**. |
| M10 memory | Impurity solver memory (CT-QMC: bath Green's function matrices; ED: `d^{N_bath}` Hilbert space) | Scales with #orbitals × cluster size; memory is rarely the primary wall compared to sign/cost. |
| M11 control knob | Cluster size `N_c` (spatial resolution); bath size (ED solver); `N_kept` (NRG solver); `β` and #MC steps (CT-QMC statistical error) | Larger `N_c` → exponentially harder; `β` convergence at low T for CT-QMC. |
| M12 scale frontier | Single-site DMFT: thermodynamic limit by construction; cluster DMFT: `N_c` ~ 4–16 routine, larger with DMRG solver | Infinite-lattice is treated at the single-site level; finite `N_c` for cluster variants. |
| M13 primary approximation / bias | Neglect of spatial correlations (single-site); cluster truncation (cluster DMFT) | Controlled in `N_c`; exact at `Z→∞` for single-site. |
| M14 hard blocker / failure mode | Strong sign problem for multi-orbital / off-diagonal hybridization / large clusters (CT-QMC); spatial correlations beyond `N_c` (momentum differentiation, pseudo-gap precursors) | 1D strongly-correlated: spatial fluctuations dominate and single-site DMFT is qualitatively wrong. |

### Cost & scaling

- Time: self-consistency loop × impurity-solver cost; CT-QMC ~polynomial in `β`; ED-bath exponential in #bath sites; cluster DMFT cost grows **exponentially with `N_c`**
- Memory: impurity Green's function matrices (~`N_orb² × N_τ`); ED-bath `O(d^{N_bath})`
- Control knob: `N_c` (cluster size, spatial resolution); `β` and MC steps (CT-QMC); bath size (ED solver)
- Scale frontier: single-site — thermodynamic limit; cluster DMFT `N_c` ~ 4–16 routine

### Accuracy & guarantees

- Class: controlled (exact at `Z→∞`); uncontrolled at finite dimension (single-site)
- Primary approximation & its control: neglect of spatial correlations for single-site; cluster `N_c` is the convergence knob
- Error scaling: systematic in `1/N_c` for cluster DMFT; statistical `∝1/√N_{MC}` for CT-QMC

### Tasks it computes

- Single-particle spectral function `A(ω)` and self-energy `Σ(ω)` at real or imaginary frequency
- Local density of states (DOS) and Fermi-liquid / non-Fermi-liquid crossover
- Mott metal-insulator transition, phase diagram as function of `U`, `T`, doping
- Finite-T thermodynamics (entropy, specific heat, compressibility)
- Susceptibilities and optical conductivity (via two-particle vertex — extra cost)

### Recommended for (models / regimes)

- **Correlated fermions in 3D / high-coordination lattices** (Hubbard, multi-orbital Hubbard, Hund's metals) where spatial correlations are secondary
- **Mott physics and finite-T phase diagrams** — the method of choice
- **Real-frequency spectral functions** when NRG is used as the impurity solver
- **Multi-orbital / realistic correlated materials** via DFT+DMFT
- Per `method-property-map.md`: preferred over MF (A1~3D, B7 strong correlation); complement with cluster DMFT for spatial correlations, DCA for `k`-resolved physics

### Key reference

[@georges_1996_dynamical] — the authoritative DMFT review covering the `Z→∞` limit, impurity solvers, the Mott transition, and benchmarks for the Hubbard model.
Rendered: `../../literature/dmft/10-1103-revmodphys-68-13.md` _(reused: `../../literature/dmft/10-1103-revmodphys-68-13.md`)_.

### Benchmarks

- Mott transition in the half-filled Hubbard model: `U_c2 ≈ 2.9 D` (Bethe lattice, half-bandwidth D=1, T=0; equivalently U_c2/t ≈ 5.8 since D=2t) [@georges_1996_dynamical].
- CT-QMC solver sign: sign ~1 for single-band, degrades exponentially with #orbitals and cluster size [method-survey.md §6.1].
- Cluster DMFT `N_c` convergence: local observables converge ~`1/N_c`; momentum-space quantities require larger `N_c` [method-survey.md §6.1].

## How it is used / Operational

**Harness coverage:** DMFT is referenced in the method zoo for completeness; it is **not a standalone harness `/method-*` skill**. The closest pointer is `/method-mf` (mean-field family), but DMFT is distinct and not directly covered. The impurity solvers that DMFT calls are related to `/method-ed` (ED-bath solver) and NRG (§6.3), but no dedicated `/method-dmft` skill exists in the current harness.

**Standard workflow (external tools: w2dynamics, TRIQS, DCore, solid_dmft):**
1. Define the impurity model (Weiss field / hybridization function `Δ(iω_n)`).
2. Run impurity solver (CT-QMC for finite-T; ED-bath for small bath; NRG for real-frequency).
3. Extract self-energy `Σ(iω_n)` from Dyson equation.
4. Update Weiss field via lattice Dyson equation; iterate until convergence.
5. Perform analytic continuation (MaxEnt) for real-frequency spectra if using imaginary-axis solver.

**Cross-links:**
- Survey: `method-survey.md` §6.1 (DMFT and cluster extensions)
- Model↔method gate: `method-property-map.md`
- Complementary: DMET (§6.2, wave-F card), NRG as impurity solver (§6.3, wave-F card), MF (`/method-mf`)

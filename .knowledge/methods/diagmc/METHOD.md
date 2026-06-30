<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Diagrammatic Monte Carlo (DiagMC)

Stochastic summation of Feynman-diagram series directly in the thermodynamic limit — no finite-size error.

## Method card

### What it is

DiagMC stochastically generates and evaluates Feynman diagrams for the many-body Green's function or self-energy `Σ(k,ω)` up to a maximum order `n_max`. Instead of discretizing space (no lattice of `N` sites), the algorithm directly samples the continuous-variable integrand (momenta, imaginary times, interaction lines) that appears in the Dyson series. Each diagram is a term in the perturbative expansion; the Monte Carlo process selects diagrams with probability proportional to their modulus, computing their contribution with the correct sign. Convergence is controlled by `n_max` and by the resummation method (Padé, bold-line summation, conformal maps). The key differentiator: because there is no spatial lattice, results are at the thermodynamic limit by construction — no finite-size scaling extrapolation is needed.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Self-energy `Σ(k,ω)` · one-particle Green's function `G(k,ω)` · vertex functions · thermodynamics (free energy, density, compressibility) · polaron binding energy and dispersion | All computed directly in the thermodynamic limit; finite-size effects absent. |
| M2 regime | Finite-T (Matsubara formalism) or T=0 (real-frequency); polaron ground state | Both regimes accessible; imaginary-frequency results require analytic continuation for spectra. |
| M3 accuracy class | Controlled-bias (series truncation at order `n_max`); stochastic | Statistical error `∝1/√N_s`; systematic error from diagram-series truncation and resummation scheme; uncontrolled if the series diverges or the sign problem (diagram-sign) is severe. |
| M4 dimension fit (A1) | **Thermodynamic limit directly (no finite-size error)** — the key differentiator | Works in any dimension; no finite-size scaling needed; directly accesses the TDL. |
| M5 statistics & local dim (A3) | Bosons and fermions in the diagrammatic language; local dim `d` does not appear (momentum-space formulation) | Polaron problems (single fermion in a bosonic bath) are the canonical application; fermionic sign enters via diagram signs. |
| M6 entanglement regime (B5) | Not a wavefunction method — no entanglement restriction | Diagrammatic expansion does not represent a wavefunction; entanglement concept does not apply. |
| M7 sign-problem dependence (C12) | Diagram-sign + series-convergence are the limiters; weak–intermediate coupling regime | At strong coupling, the diagram series may diverge or require resummation; the sign problem manifests as cancellations between diagrams of opposite sign. |
| M8 symmetry exploitation (C9/C10) | Momentum conservation and translational invariance are explicit in the momentum-space formulation; spin SU(2) used to relate spin channels | Symmetry reduces the diagram phase space and variance; used to relate diagram classes. |
| M9 time complexity | Cost grows with maximum diagram order `n_max`; convergence/resummation of the series is the bottleneck, not lattice size | No `N³` matrix cost; the bottleneck is high-order diagram evaluation and the exponential growth of diagram topologies with order. |
| M10 memory | `O(n_max)` per configuration — stores the current diagram topology and variables | Extremely modest compared to wavefunction-based methods; no Hilbert-space dimension enters. |
| M11 control knob | `n_max` (maximum diagram order) → series truncation error; resummation method (Padé, bold-line, conformal) → systematic convergence of resummed series | Check convergence as `n_max` increases; residual error is scheme-dependent. |
| M12 scale frontier | **Thermodynamic limit by construction** — no system-size extrapolation needed | The unique frontier: `N=∞` at the cost of a perturbative expansion. Applies to homogeneous (translationally invariant) systems. |
| M13 primary approximation / bias | Series truncation at order `n_max` and resummation scheme bias; diagram-sign problem at strong coupling | Controlled at weak–intermediate coupling; uncontrolled when the series radius of convergence is exceeded. |
| M14 hard blocker / failure mode | Strong coupling: diagram series diverges or has zero radius of convergence; sign problem from diagram cancellations; inhomogeneous / disordered systems break translation invariance (no momentum basis) | Lattice models at strong `U/t` and frustrated systems are beyond the weak–intermediate coupling reach. |

### Cost & scaling

- Time: cost grows with `n_max`; diagram topology enumeration grows factorially with order; each diagram evaluated via Monte Carlo quadrature
- Memory: `O(n_max)` per configuration — negligible
- Control knob: `n_max` (truncation order → series error); resummation method → systematic bias
- Scale frontier: thermodynamic limit `N=∞` by construction; `n_max~8`–`14` typical for polaron problems

### Accuracy & guarantees

- Class: controlled-bias (series truncation), stochastic
- Primary approximation & its control: series truncation at `n_max` + resummation; improved by higher-order and better resummation (Padé, conformal Borel)
- Error scaling: statistical `∝1/√N_s`; systematic decreases with `n_max` until convergence (or divergence at strong coupling)

### Tasks it computes

- Single-particle Green's function `G(k,τ)` / `G(k,iω_n)` → spectral function `A(k,ω)` via analytic continuation
- Self-energy `Σ(k,ω)` for quasiparticle properties (effective mass, quasiparticle weight `Z`)
- Two-particle vertex functions (susceptibilities) for collective modes
- Thermodynamics in the TDL: pressure, density, compressibility
- Polaron binding energy, effective mass, and dispersion curve (the founding application)

### Recommended for (models / regimes)

- **Polaron and impurity problems:** single fermion or boson in a bosonic/fermionic bath — the founding and best-established application
- **Homogeneous correlated systems at weak–intermediate coupling:** Hubbard model at moderate `U/t`, Bose gas near unitarity — direct TDL results without finite-size extrapolation
- **When thermodynamic-limit results are required without finite-size corrections:** avoids the `N→∞` extrapolation cost that burdens all lattice methods
- **Cross-check for DQMC/AFQMC:** DiagMC self-energy at TDL vs DQMC finite-size-extrapolated self-energy
- Per `method-property-map.md`: the only method that directly accesses `N=∞`; blocked at strong coupling (B7) and by inhomogeneity (disorder, interfaces)

### Key reference

[@prokofev_1998_polaron] — founding DiagMC paper: stochastic summation of polaron Green function diagrams, first demonstration that continuous-variable diagrammatic MC gives exact polaron properties in the TDL.
Rendered: `./cond-mat__9804097_polaron-problem-by-diagrammatic-quantum-monte-carlo.md` _(downloaded)_.

### Benchmarks

- Fröhlich polaron: DiagMC ground-state energy and effective mass from weak coupling (`α→0`) through intermediate coupling (`α≈6`) — matches Feynman variational bound at weak coupling and improves beyond it [@prokofev_1998_polaron].
- Effective mass `m*/m` at `α=3`: DiagMC `1.87(2)` vs Feynman variational `1.89` — consistent at the few-percent level for the founding calculation [@prokofev_1998_polaron].

## How it is used / Operational

**Owning skill:** `/method-qmc`. No dedicated harness tool skill exists for DiagMC — codes include the Prokof'ev–Svistunov group's private implementations, and community codes such as `diagramMC` (Mishchenko group); use them directly.

**Default workflow:**
1. Define the propagator lines and interaction vertices for the target model in momentum-frequency space.
2. Implement the diagram generation: sampling topology updates (add/remove/reconnect a vertex pair) and continuous-variable updates (momenta, imaginary times).
3. Run until `G(k,τ)` / `Σ(k,iω_n)` converges in `n_max`; repeat at several values of `n_max` (e.g. `n_max=4, 6, 8, 10`).
4. Resum the series: Padé approximant in `n_max`, bold-diagrammatic partial resummation (Dyson equation), or conformal Borel transform.
5. Extract spectral function `A(k,ω)` via analytic continuation (MaxEnt/Nevanlinna).
6. Report convergence: plot `E(n_max)` or `Σ(n_max)` to show the series converges.

**Verification pointers:**
- Weak-coupling limit: compare to known perturbative result (second-order self-energy).
- Non-interacting limit `U→0` or `α→0`: recover exact `G_0(k,ω)`.
- Polaron effective mass: cross-check against Feynman path-integral variational bound (DiagMC must be ≤ Feynman at converged `n_max`).

**Cross-links:**
- Survey: `method-survey.md` §4.6 (Diagrammatic Monte Carlo)
- Model↔method gate: `method-property-map.md` (DiagMC profile)
- Complementary methods: DQMC (finite-T lattice fermions — compare TDL-extrapolated DQMC to DiagMC); AFQMC-CPMC (GS lattice fermions); bold-DiagMC and self-consistent Dyson resummation as variants

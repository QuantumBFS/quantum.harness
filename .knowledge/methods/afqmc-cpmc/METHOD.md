<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Auxiliary-Field QMC Ground State / Constrained-Path / Phaseless (AFQMC-CPMC)

Ground-state imaginary-time projection in auxiliary-field space; the sign/phase problem is controlled by a trial-state constraint (constrained-path for real wave functions, phaseless for complex).

## Method card

### What it is

AFQMC projects the ground state by iterating `|Ψ⟩ ← e^{−ΔτH}|Ψ⟩` in a space of auxiliary fields (`N_w` walkers, each a Slater determinant). After a Hubbard–Stratonovich transformation, each `e^{−Δτ·(one-body)}` propagator is a product of single-particle operators, so each walker remains a Slater determinant throughout. The sign (or phase) problem — walkers accumulating opposite-sign (or rotating) weights — is controlled by the **constrained-path approximation** (real-valued case) or **phaseless approximation** (complex case): walkers whose overlap with a trial state `|Ψ_T⟩` crosses zero (or whose phase departs) are killed. This introduces a bias set by the quality of `|Ψ_T⟩`, but makes the cost polynomial. CPMC-Lab (arXiv:1407.7967) is the reference open-source implementation.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | GS energy (benchmark-grade for many Hubbard regimes) · back-propagated observables (density, correlation functions) · imaginary-time correlations → spectral functions via analytic continuation | Best-in-class for GS energy of the 2D Hubbard model; back-propagated observables carry extra bias from the constraint. |
| M2 regime | T=0 (ground state) | DQMC is the finite-T sibling; AFQMC-CPMC targets the GS specifically. |
| M3 accuracy class | Controlled-bias — phaseless/constrained-path bias set by trial-state quality; stochastic | Statistical error `∝1/√(N_w·N_steps)`; systematic bias shrinks as `|Ψ_T⟩` → exact GS; free-projection (unbiased) is exponentially costly. |
| M4 dimension fit (A1) | Any dimension (1D, 2D, 3D) | Frequently applied to 2D Hubbard where it gives the best GS energies among polynomial-cost methods. |
| M5 statistics & local dim (A3) | Fermions (primary); also applied to real materials via plane-wave basis | Each walker is a Slater determinant; `N` orbitals (sites × spin); local dim `d=4` Hubbard. |
| M6 entanglement regime (B5) | Volume-law tolerated | Walker space imposes no entanglement restriction; the constraint bias is the limit, not entanglement. |
| M7 sign-problem dependence (C12) | Phaseless/constrained-path approximation removes the sign at the cost of a trial-state bias | Free-projection (unbiased) cost blows up `∝e^{2βNΔf}` with the sign; the constraint trades that for polynomial cost + controllable bias. |
| M8 symmetry exploitation (C9/C10) | Trial state `\|Ψ_T⟩` can be symmetry-projected (UHF, ROHF, GHF) to reduce bias; particle-number and spin conservation preserved in walker propagation | Better `\|Ψ_T⟩` (e.g. from DMRG or VMC) directly reduces the phaseless bias. |
| M9 time complexity | `O(N³)` per walker per step × `N_w` × `N_steps`; `O(N²)` per walker memory | `N` = number of orbitals/sites; `N³` from matrix products in Slater determinant updates; `N_w~100`–`1000` typical. |
| M10 memory | `O(N²)` per walker (Slater determinant stored as `N×N_e` matrix) | Total `O(N_w·N²)`; modest compared to exact-diagonalization storage. |
| M11 control knob | `N_w` (walkers) → statistical error `∝1/√N_w`; `Δτ` (projection step) → Trotter error; trial state `\|Ψ_T⟩` quality → phaseless bias | Improving `\|Ψ_T⟩` systematically reduces the bias; can use VMC-NQS or DMRG wavefunction as trial state. |
| M12 scale frontier | `N~100`–`500` sites routine; `N~1000` on HPC; thermodynamic-limit extrapolation via finite-size scaling | State-of-the-art for the 2D Hubbard model ground state at intermediate-to-strong coupling and away from half-filling. |
| M13 primary approximation / bias | Phaseless/constrained-path bias — set by overlap of walkers with `\|Ψ_T⟩`; controlled by improving the trial state | Bias is variational in the constrained-path case: the constrained-path energy is an upper bound, E_CP ≥ E_0 (Zhang–Krakauer 2003); the phaseless approximation is not strictly variational. |
| M14 hard blocker / failure mode | Poor trial state → large phaseless bias (e.g. strongly frustrated models where even HF is qualitatively wrong); back-propagated observables have extra bias; free-projection is exponentially costly | The constraint quality is the central limit; no sign-free condition exists for general fermion models. |

### Cost & scaling

- Time: `O(N³)` per walker per step × `N_w` × `N_steps`
- Memory: `O(N²)` per walker; total `O(N_w·N²)`
- Control knob: `N_w` (statistical error `∝1/√N_w`); trial state quality → phaseless bias; `Δτ` → Trotter error
- Scale frontier: `N~100`–`500` routine; `N~1000` HPC; finite-size scaling to thermodynamic limit

### Accuracy & guarantees

- Class: controlled-bias (phaseless/constrained-path), stochastic
- Primary approximation & its control: phaseless bias set by trial-state quality; reduced by improving `|Ψ_T⟩` (e.g. DMRG trial state)
- Error scaling: statistical `∝1/√(N_w·N_steps)`; systematic from phaseless approximation (non-zero for imperfect `|Ψ_T⟩`)

### Tasks it computes

- Ground-state energy (benchmark-grade for Hubbard model regimes at finite doping)
- Back-propagated observables: density, spin/charge correlations, momentum distributions
- Imaginary-time correlations `⟨A(τ)B(0)⟩` → spectral functions via analytic continuation
- Benchmark reference for 2D Hubbard model phase diagram (stripe order, SC susceptibility)

### Recommended for (models / regimes)

- **2D Hubbard model away from half-filling (D14 doped):** best-in-class GS energies where DQMC sign problem is severe; the method of choice for the doped Mott insulator
- **Strongly correlated fermion models where sign problem precludes DQMC:** AFQMC-CPMC with DMRG/VMC trial state narrows the phaseless bias substantially
- **Real materials (ab initio AFQMC):** plane-wave/localized orbital basis; benchmark quality for molecules and solids
- **Benchmarking VMC-NQS upper bounds:** AFQMC-CPMC GS energy cross-checks the VMC variational bound from below
- Per `method-property-map.md`: preferred over DQMC for GS at finite doping; complementary to DQMC's finite-T capabilities

### Key reference

[@zhang_2019_auxiliary] — comprehensive lecture-note review of the auxiliary-field QMC algorithm at zero and finite temperature; the standard pedagogical and technical reference.
Rendered: `../../literature/quantum-monte-carlo/zhang_2019_auxiliary-field-quantum-monte-carlo.md` _(reused)_.

[@nguyen_2014_cpmc] — CPMC-Lab: open-source MATLAB implementation; documents the constrained-path algorithm, back-propagation estimators, and benchmarks on the 2D Hubbard model.
Rendered: `../../literature/quantum-monte-carlo/1407.7967_cpmc-lab-a-matlab-package-for-constrained-path-monte-carlo-c.md` _(reused)_.

### Benchmarks

- 2D Hubbard model (`10×10`, `U/t=4`, `⟨n⟩=0.875`): AFQMC-CPMC energy `E/t = −0.5444(4)` — benchmark in the doped regime where DQMC is sign-ful [@zhang_2019_auxiliary].
- Phaseless bias test: with UHF trial state vs DMRG trial state, energy difference `< 0.1%` for `U/t≤8` on `4×4` lattice [@nguyen_2014_cpmc].

## How it is used / Operational

**Owning skill:** `/method-qmc`, with tool skill `/using-cpmc-lab`.

**Default workflow:**
1. Prepare a trial state `|Ψ_T⟩` (UHF, GHF, or DMRG/VMC wavefunction for better quality).
2. Initialize `N_w` walkers as copies of `|Ψ_T⟩`; set `Δτ` and projection time `τ_max`.
3. Propagate each walker: apply auxiliary-field propagator, compute importance-sampled weight, apply constrained-path (phaseless) kill/clone.
4. Accumulate energy and back-propagated observables; check walker population stability.
5. Extrapolate `Δτ→0`; vary trial state quality to bound the phaseless bias.
6. For spectral functions: compute imaginary-time correlations and apply analytic continuation.

**Verification pointers:**
- Compare against ED on small clusters (`4×4`, `6×6`) for energy and structure factor.
- Check that phaseless bias is small: vary `|Ψ_T⟩` from UHF → ROHF → DMRG and monitor energy change.
- Walker population statistics: effective number of walkers `N_eff = (Σw_i)²/Σw_i²` should remain `≥N_w/10`.

**Cross-links:**
- Survey: `method-survey.md` §4.5 (Auxiliary-field QMC ground state / AFQMC / CPMC)
- Model↔method gate: `method-property-map.md` (AFQMC-CPMC profile)
- Complementary methods: DQMC (finite-T sibling); VMC-NQS (upper bound — cross-check with AFQMC-CPMC); DMRG (1D exact, 2D cylinders — use as trial state source)

<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ./ref.bib. -->

# Metropolis Monte Carlo (Metropolis MC)

Importance-sampling of the classical Boltzmann distribution via local single-spin-flip updates to compute finite-temperature thermodynamics.

## Method card

### What it is

Metropolis MC (and the closely related Glauber / heat-bath dynamics) constructs a Markov chain over the classical phase space by proposing a random local change (single-spin flip) and accepting it with the Metropolis–Hastings probability `min(1, e^{−βΔE})`. The steady-state distribution is the Boltzmann weight `e^{−βH}/Z`, so time averages over the chain estimate thermal expectation values. Because each proposed update touches only one site (and its neighbors), each sweep costs `O(N)`. Near a continuous phase transition the autocorrelation time diverges as `τ_auto ~ ξ^z ~ L^z` — this "critical slowing down" is the central limitation.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Finite-T thermodynamics: energy, magnetization, magnetic susceptibility, specific heat, Binder cumulants, structure factors, correlation functions | NOT ground-state energy or quantum amplitudes; NOT critical exponents (use MCRG). |
| M2 regime | Finite temperature (thermal equilibrium) | Classical models only, or quantum models mapped sign-free to a classical representation (e.g. transfer-matrix / SSE at finite `β`). |
| M3 accuracy class | Numerically exact (within Boltzmann statistics), stochastic | Statistical error `∝ 1/√(N_s/τ_auto)`; systematic bias only from finite `τ_auto` (equilibration) and finite lattice. |
| M4 dimension fit (A1) | Any (1D / 2D / 3D / ∞-D) | Per-sweep cost `O(N)` is independent of geometry; suited to classical Ising, Heisenberg, XY, Potts models in any dimension. |
| M5 statistics & local dim (A3) | Classical spin models (Ising `d=2`, Potts `d=q`, continuous O(n) spins); sign-free quantum mappings | Not applicable to genuine quantum models with a sign problem. Local dim `d` only affects the update cost per site, not the algorithmic structure. |
| M6 entanglement regime (B5) | N/A — classical model; no entanglement restriction | For quantum models accessed via sign-free mappings, entanglement is implicit in the weight. |
| M7 sign-problem dependence (C12) | Requires sign-free (classical models or sign-free quantum mappings) | Not a quantum MC method per se. A genuine fermionic/frustrated quantum model is NOT accessible unless a sign-free classical representation exists. |
| M8 symmetry exploitation (C9/C10) | Global symmetry used to measure order parameters (e.g. `Z₂` for Ising, O(n) for Heisenberg); translation used for structure-factor measurement | Symmetry does not reduce per-sweep cost (unlike ED block-diagonalization), but allows optimized estimators. |
| M9 time complexity | `O(N)` per sweep; total `O(N · τ_auto · N_s)`; near `T_c`: `τ_auto ~ L^z` with `z = 2.1665(12)` (2D Ising, Glauber/Metropolis, Nightingale–Blöte 1996) | Critical slowing down `τ_auto ~ L^z` dominates at a continuous transition (B6). Larger lattice `L` is far more expensive at `T_c`. |
| M10 memory | `O(N)` — stores spin configuration + neighbor list | Minimal memory footprint; scales to thermodynamic-limit lattices (millions of sites). |
| M11 control knob | `N_s` (number of sweeps after equilibration) — statistical error `∝ 1/√(N_s/τ_auto)` | Increasing `N_s` systematically reduces statistical error; `τ_auto` must be measured to set `N_s` reliably. |
| M12 scale frontier | Millions of sites in practice (off-critical); thousands of sites near `T_c` (critical slowing down limits effective sample count) | The method scales to very large `L` away from criticality; near `T_c` the effective sample count is `N_s/τ_auto`. |
| M13 primary approximation / bias | None — sampling from the exact Boltzmann distribution (within statistical error and given exact weights) | Finite-size effects require finite-size scaling to extract thermodynamic-limit behavior. |
| M14 hard blocker / failure mode | Critical slowing down (`τ_auto ~ L^z`, `z = 2.1665(12)`) near a continuous transition; frustration/glassiness (B8) inflates `τ_auto` further, causing metastability; NOT applicable to sign-ful quantum models | Critical slowing down is partially defeated by cluster algorithms (§2.2 of `method-survey.md`). |

### Cost & scaling

- Time: `O(N)` per sweep; `O(N · τ_auto · N_s)` total; at criticality `τ_auto ~ L^z` with `z = 2.1665(12)` for 2D Ising
- Memory: `O(N)` — spin configuration and neighbor list only
- Control knob: `N_s` (sweeps) — controls statistical error as `1/√(N_s/τ_auto)`
- Scale frontier: millions of sites off-critical; thousands near `T_c` before critical slowing down dominates

### Accuracy & guarantees

- Class: numerically exact (Boltzmann statistics), stochastic
- Primary approximation & its control: none intrinsic — finite lattice bias removed by finite-size scaling; `τ_auto` measured by the integrated autocorrelation time of each observable
- Error scaling: statistical error `∝ 1/√(N_s/τ_auto)`; systematic bias from `τ_auto` → removed by ensuring `N_s ≫ τ_auto`

### Tasks it computes

- Internal energy `⟨E⟩` and specific heat `C = (⟨E²⟩ − ⟨E⟩²)/T²` (k_B = 1 units)
- Magnetization `⟨m⟩` and magnetic susceptibility `χ = N(⟨m²⟩ − ⟨m⟩²)/T`
- Binder cumulant `U_4 = 1 − ⟨m⁴⟩/(3⟨m²⟩²)` (for locating `T_c` via finite-size scaling)
- Structure factor `S(q)` and spatial correlation functions `C(r)`
- Free energy (via thermodynamic integration or parallel tempering)

### Recommended for (models / regimes)

- **Classical Ising / Heisenberg / XY / Potts** in any dimension at finite temperature, away from the critical point
- **Finite-size scaling studies** at or near `T_c` (combined with Binder cumulants), though cluster MC is preferred when `z` matters
- **Sign-free quantum models mapped to classical weights** (e.g. transverse-field Ising via Suzuki–Trotter at finite `β`)
- Per `method-property-map.md`: classical models (B8 unfrustrated) at finite `T`; not for critical-exponent extraction (use MCRG) or quantum sign-ful models (use MPS/PEPS/VMC)

### Key reference

[@sandvik_2010_computational] — comprehensive treatment of classical and quantum Monte Carlo for spin systems, including Metropolis/heat-bath algorithms, finite-size scaling with Binder cumulants, and structure-factor estimators.
Rendered: `../../literature/quantum-monte-carlo/1101.3281_computational-studies-of-quantum-spin-systems.md` _(reused)_.

### Benchmarks

- 2D Ising `T_c/J = 2/ln(1+√2) ≈ 2.2692` (exact Onsager): located to < 0.01% precision by Binder-cumulant crossing at `L ≈ 32–64` [@sandvik_2010_computational].
- Dynamical critical exponent (local Metropolis/Glauber): `z = 2.1665(12)` for 2D Ising [@nightingale_1996_dynamic] [verified in `method-survey.md` §2.1].
- 2D Ising critical specific heat: `C ~ L^{α/ν}` with `α = 0` (log divergence) captured correctly after `N_s ≫ τ_auto ~ L^{2.1665}` sweeps [@sandvik_2010_computational].

## How it is used / Operational

**Owning skill:** No dedicated classical-MC harness skill exists. Metropolis MC is typically run via custom code (Python/NumPy, C/Fortran, or Julia) or community packages such as ALPS. For frustrated-magnet regime classification and method selection see the guidance in `method-property-map.md` and, where relevant, the `frustration` skill. The `/method-qmc` skill covers *quantum* MC (SSE, AFQMC, DQMC) and is distinct.

**Default workflow:**
1. Initialize the spin configuration (random high-T or ordered low-T start).
2. Run equilibration sweeps (`N_eq ≥ 10 × τ_auto`); discard.
3. Collect `N_s` measurement sweeps; estimate `τ_auto` via the integrated autocorrelation function.
4. Compute observables and their statistical errors accounting for `τ_auto` (jackknife or binning analysis).
5. Repeat for multiple system sizes `L`; perform finite-size scaling (Binder cumulants for `T_c`, power-law fits for critical exponents — or hand off to MCRG for more precise exponents).

**Verification pointers:**
- For 2D Ising: verify `T_c ≈ 2.269 J/k_B` by Binder-cumulant crossing; energy and magnetization agree with exact Onsager/Yang solutions.
- Check `⟨E⟩` fluctuations satisfy `C = (⟨E²⟩ − ⟨E⟩²)/T²` (k_B = 1 units) self-consistently.
- Confirm `τ_auto` measured at `T_c` scales as `L^{2.1665}` (Metropolis), or use cluster MC if this is prohibitive.

**Cross-links:**
- Survey: `method-survey.md` §2.1 (Metropolis single-spin-flip)
- Model↔method gate: `method-property-map.md` (classical models, finite-T)
- Complementary methods: cluster-mc (defeats critical slowing down for unfrustrated models), MCRG (critical exponents), LTRG (quantum finite-T tensor networks)

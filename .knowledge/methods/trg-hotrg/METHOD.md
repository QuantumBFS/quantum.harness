<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ../ref.bib. -->

# Tensor Renormalization Group (TRG / HOTRG)

Real-space coarse-graining of 2D/3D tensor networks for classical partition functions and quantum path integrals; primary method for critical properties of classical lattice models.

## Method card

### What it is

TRG and HOTRG perform iterative coarse-graining of a tensor network — most naturally the partition function of a classical 2D or 3D statistical model written as a network of local tensors — by repeatedly contracting and truncating via singular-value decomposition (TRG, Levin–Nave) or higher-order SVD (HOTRG, Xie et al. 2012). At each step the network is halved in size; after many steps only the fixed-point tensor survives, encoding the thermodynamic free energy and the RG spectrum. The bond dimension χ controls how many states are retained after each truncation and sets both the accuracy and the cost. The same framework contracts 2D quantum-thermal (path-integral) and PEPS networks by treating the imaginary-time or layer index as an extra tensor leg.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | Free energy & partition function · critical temperature T_c · critical exponents & central charge (from transfer-matrix / RG-spectrum eigenvalues) · correlation length · thermodynamic observables; also contracts 2D quantum-thermal & PEPS networks | CFT data (scaling dimensions, central charge c) extracted from the fixed-point spectrum of the transfer matrix or RG superoperator. |
| M2 regime | Finite-T (classical equilibrium); T=0 quantum via path-integral / PEPS contraction | Imaginary-time direction mapped onto a spatial leg; real-time dynamics not natural in this framework. |
| M3 accuracy class | Controlled-bias (finite-χ truncation at each coarse-graining step), deterministic | Bias → 0 as χ → ∞; no stochastic error. TNR removes short-range correlations that contaminate the TRG fixed point. |
| M4 dimension fit (A1) | 2D (TRG / CTMRG); 2D & 3D (HOTRG) | TRG cost grows as O(χ⁶) per step (feasible in 2D); HOTRG cost O(χ^{4d−1}) (d = spatial dimension here, not local Hilbert dim) makes 3D practical at moderate χ but expensive. |
| M5 statistics & local dim (A3) | Classical spins / hard-core variables; quantum via path integral (bosons, spins); fermions need Grassmann tensor extensions | Local dimension d absorbed into the initial tensor; classical Ising/Potts are natural applications. Fermionic path integrals require careful sign handling via Grassmann tensors. |
| M6 entanglement regime (B5) | Area-law classical correlations; handles critical (log-growing) correlations at finite χ via RG fixed-point | Unlike MERA, TRG/HOTRG do not explicitly install disentanglers; TNR variant removes the short-range entanglement that spoils the TRG fixed point. |
| M7 sign-problem dependence (C12) | Sign-free (real Boltzmann weights for classical models) | Classical statistical models have non-negative Boltzmann weights; no sign problem. Quantum path integrals can carry a sign, but this is treated by explicit tensor structure rather than Monte Carlo sampling. |
| M8 symmetry exploitation (C9/C10) | Global symmetry (Z₂, U(1), etc.) enforced via symmetric tensors; translation exploited by the coarse-graining geometry | Symmetric tensor implementations reduce the effective bond dimension and improve convergence near criticality. |
| M9 time complexity | TRG O(χ⁶) per step (2D); HOTRG O(χ^{4d−1}) per step = O(χ⁷) in 2D, O(χ¹¹) in 3D | DO NOT confuse with ATRG O(χ^{2d+1}) — that is a different (cheaper) algorithm. TNR scales higher than HOTRG but yields clean scale invariance. |
| M10 memory | TRG O(χ⁴); HOTRG O(χ^{2d}) (d = spatial dimension here, not local Hilbert dim) = O(χ⁴) in 2D, O(χ⁶) in 3D | Stores one or two local tensors per coarse-graining step; environment tensors in CTMRG are O(χ³). |
| M11 control knob | Bond dimension χ (number of singular values retained after each truncation) | Increasing χ reduces the truncation bias; convergence monitored via free-energy density as a function of χ. |
| M12 scale frontier | Thermodynamic limit directly (coarse-graining runs to infinite volume); classical 2D models routine at χ ~ 20–60; 3D at χ ~ 10–20 | Iterative coarse-graining naturally accesses the infinite-volume fixed point without finite-size extrapolation. |
| M13 primary approximation / bias | Finite-χ truncation at each coarse-graining step (controlled); TRG additionally accumulates short-range correlation errors near criticality (partially fixed by TNR) | Truncation bias is the only source of error; systematically controlled by increasing χ. |
| M14 hard blocker / failure mode | 3D at large χ (O(χ¹¹) wall); sign-ful quantum path integrals; real-time dynamics; volume-law entanglement phases | Frustrated quantum models with a sign problem require Grassmann extensions and are not naturally sign-free. TRG fixed points near criticality need TNR/loop-TNR to remove short-range contamination. |

### Cost & scaling

- Time: TRG O(χ⁶) per step (2D); HOTRG O(χ^{4d−1}) = O(χ⁷) in 2D, O(χ¹¹) in 3D
- Memory: TRG O(χ⁴); HOTRG O(χ^{2d}) = O(χ⁴) in 2D, O(χ⁶) in 3D
- Control knob: bond dimension χ — controls truncation error at each coarse-graining step
- Scale frontier: thermodynamic limit directly; 2D classical models at χ ~ 20–60; 3D at χ ~ 10–20

### Accuracy & guarantees

- Class: controlled-bias, deterministic; controlled-bias estimate of the free energy (not a strict variational bound; bias → 0 as χ → ∞)
- Primary approximation & its control: finite-χ truncation accumulated over coarse-graining steps; bias → 0 as χ → ∞; near criticality, TNR removes additional short-range-correlation contamination present in TRG
- Error scaling: free-energy error ~ O(ε_trunc) per step; critical exponents converge as a power of χ with exponent that depends on the universality class

### Tasks it computes

- Free energy density and partition function as a function of temperature
- Critical temperature T_c (from singular behavior of the free energy or its derivatives)
- Critical exponents (ν, η, β, …) and central charge c via the transfer-matrix / RG-spectrum eigenvalue ratios
- Scaling dimensions of primary operators from the fixed-point spectrum
- Correlation length as a function of T
- Contraction of 2D PEPS networks (replaces CTMRG for certain geometries)
- Contraction of 2D quantum path-integral networks (imaginary-time formulation)

### Recommended for (models / regimes)

- **Primary method for 2D classical statistical models** (Ising, Potts, XY, …): free energy, T_c, and CFT data at the thermodynamic limit without finite-size extrapolation
- **3D classical models** (3D Ising, …): HOTRG is feasible at moderate χ; provides thermodynamic-limit estimates
- **Quantum models in 1+1D** (path integral → 2D tensor network): maps onto TRG/HOTRG after Suzuki–Trotter decomposition
- **PEPS contraction as an alternative to CTMRG**: useful when the geometry favors a coarse-graining sweep
- Per `method-property-map.md`: optimal when A1=2D/3D classical, B6=critical (CFT data needed), C12=sign-free; disfavored for real-time dynamics, fermionic sign-ful quantum problems, or volume-law phases

### Key reference

[@xie_2012_coarse] — introduces HOTRG, derives the O(χ^{4d−1}) cost scaling, and benchmarks critical exponents for 2D and 3D Ising models.
Rendered: `./1201.1144_coarse-graining-renormalization-by-higher-order-singular-val.md` _(downloaded)_.

Also cite: [@ors_2013_practical] — pedagogical introduction to TRG in the context of tensor network methods (MPS/PEPS/TRG).

### Benchmarks

- 2D classical Ising T_c: TRG/HOTRG recover T_c = 2J/ln(1+√2) ≈ 2.269 J to ≲0.01% at χ ~ 24 [survey §3.5; @xie_2012_coarse].
- 2D Ising central charge: c = 0.5 extracted from transfer-matrix RG spectrum at χ ~ 24 [@xie_2012_coarse].
- 3D Ising critical exponents (HOTRG χ=16): ν ≈ 0.630, η ≈ 0.036, consistent with conformal-bootstrap values [@xie_2012_coarse].

## How it is used / Operational

**Owning skill:** `/method-peps` (tensor-RG / classical-TN route); TRG/HOTRG is the classical-partition-function coarse-graining cousin of the PEPS contraction workflow.

**Default workflow:**
1. Write the classical partition function (or quantum path integral after Trotter decomposition) as a 2D/3D tensor network: one local tensor per site encoding the Boltzmann factor.
2. Choose χ (start with χ ~ 8–16 for a quick estimate).
3. Apply TRG (2D) or HOTRG (2D/3D) coarse-graining: at each step contract neighboring tensors and truncate the resulting bond to dimension χ via SVD / HOSVD.
4. Iterate until the network collapses to a single tensor; extract the free energy from its trace.
5. Repeat at multiple temperatures to locate T_c; extract critical exponents from the RG-spectrum eigenvalue ratios near T_c.
6. Increase χ and repeat to check convergence; plot observables vs 1/χ to estimate χ → ∞ limit.
7. For clean CFT data, consider TNR or loop-TNR in place of TRG.

**Verification pointers:**
- Cross-check T_c and critical exponents against exact results (2D Ising) or high-precision Monte Carlo (3D Ising, Potts).
- Verify central charge c from the degeneracy pattern of the fixed-point spectrum.
- Compare free-energy density vs exact transfer-matrix result for small χ to calibrate truncation error.

**Cross-links:**
- Survey: `method-survey.md` §3.5 (Tensor RG for classical / partition functions)
- Model↔method gate: `method-property-map.md` (TRG/HOTRG profile)
- Complementary methods: MCRG (§ Wave B — independent RG flow from MC configurations), MERA (§3.4 — quantum critical GS with disentanglers), CTMRG (environment method for 2D PEPS contraction), PEPS/iPEPS (§3.2 — 2D quantum variational method)

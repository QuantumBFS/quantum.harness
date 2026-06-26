<!-- Method-card template. Axis definitions: ../method-property-checklist.md (M1–M14).
     Inverse model→method map: ../method-property-map.md. Cost derivations & citations:
     ../method-survey.md. Cite keys resolve in ./ref.bib. -->

# Density-Matrix Renormalization Group (DMRG / MPS)

Variational optimization over matrix product states (MPS); the method of choice for 1D and quasi-1D ground states.

## Method card

### What it is

DMRG represents the many-body ground state as a matrix product state — a chain of rank-3 tensors with bond dimension χ — and optimizes it by sweeping left-to-right and right-to-left, solving a local eigenvalue problem at each bond ("two-site" or "single-site" update). The bond dimension χ controls accuracy: area-law ground states need small constant χ; 1D-critical states need χ growing polynomially with system size; 2D cylinders need χ ~ e^{cW} where W is the cylinder width. The modern formulation (Schollwöck 2010) unifies finite-system DMRG, iDMRG, and VUMPS under the MPS language and incorporates U(1)/SU(2) block-sparse tensors for a large (often ≳10×) constant-factor speedup at fixed accuracy.

### Properties (M1–M14)

| Axis | Value | Note |
|---|---|---|
| M1 tasks / outputs | GS energy & observables · gap & few excited states (targeted DMRG) · correlation length (transfer-matrix spectrum) · entanglement entropy & spectrum (free from MPS) · order parameters · S(q,ω) (post-process via DMRG + correction-vector or TDVP) | Finite-T and real-time are separate algorithms (§5 of survey); dynamical spectra require additional passes. |
| M2 regime | T=0 ground state (primary); thermodynamic limit via iDMRG/VUMPS | Finite-T via purification/METTS (separate algorithm using same MPS machinery). |
| M3 accuracy class | Controlled-bias (truncation error ε_trunc is the systematic knob), deterministic | Variational upper bound on energy at each fixed χ; bias → 0 as χ → ∞. |
| M4 dimension fit (A1) | 1D / quasi-1D near-exact; **walls in 2D** (cylinder width W → cut entropy ∝W → χ ~ e^{cW}) | 1D gapped: small constant χ; 1D critical: χ grows polynomially; 2D: feasible only for narrow cylinders (W ≲ 6–8 for spin-½). |
| M5 statistics & local dim (A3) | Spin / hard-core boson / soft-core boson / fermion (Jordan-Wigner or MPO fermion) | Local dimension d appears in cost as O(d·χ³) per site; large d (Hubbard d=4, soft-core boson) raises prefactor but not the exponent. Fermions handled natively via Jordan-Wigner string in MPS. |
| M6 entanglement regime (B5) | Area-law (cheap, constant χ) / area+log 1D-critical (χ grows polynomially) | Volume-law states (excited, thermal, real-time beyond t*) are inaccessible at reasonable χ. |
| M7 sign-problem dependence (C12) | Sign-immune | Not a Monte Carlo method; no sign problem regardless of frustration or doping. |
| M8 symmetry exploitation (C9/C10) | U(1) / SU(2) block-sparse tensors; Z₂ / parity; translation (iDMRG unit cell); point group (quantum numbers per site) | SU(2) multiplet tensors give ≳10× speedup at fixed accuracy; U(1) particle-number conservation shrinks block sizes roughly by √χ. |
| M9 time complexity | O(N · w · d · χ³) per sweep | N = sites, w = MPO bond (long-range → w large), d = local dim, χ = bond dim. Leading cost is from the two-site update contraction: O(χ³) at each of N sites (w, d prefactors suppressed; full cost O(N·w·d·χ³) — see table value). |
| M10 memory | O(d · χ²) | Stores one MPS tensor per site (d × χ × χ) plus the environment and Hamiltonian MPO; dominant term is O(d·χ²) per tensor. |
| M11 control knob | Bond dimension χ (truncation error ε_trunc = discarded weight) | Increasing χ reduces truncation error; convergence checked by extrapolating energy vs ε_trunc → 0. |
| M12 scale frontier | Large 1D chains (N ~ 10³–10⁴ routine); narrow 2D cylinders up to W ~ 6–8; thermodynamic limit directly via iDMRG/VUMPS | Practical χ ceiling set by χ³ time cost; supercomputer runs reach χ ~ 10⁴ for critical 1D chains. |
| M13 primary approximation / bias | Finite-χ truncation (controlled): the MPS ansatz restricts entanglement; truncation error ε_trunc → 0 as χ → ∞ | Bias is systematic and controlled; energy is a variational upper bound at fixed χ. |
| M14 hard blocker / failure mode | 2D systems: χ ~ e^{cW} per cylinder width W (exponential wall); volume-law entanglement (real-time t > t*, excited states, thermal states); long-range interactions raise MPO bond w, inflating cost | Frustrated 2D magnets, doped Hubbard at moderate χ, real-time beyond the entanglement barrier all push beyond practical reach. |

### Cost & scaling

- Time: O(N · w · d · χ³) per sweep (N sites, MPO bond w, local dim d, bond dim χ)
- Memory: O(d · χ²) — one MPS tensor per site plus environment tensors
- Control knob: bond dimension χ — controls truncation error ε_trunc (discarded weight)
- Scale frontier: N ~ 10³–10⁴ (1D); narrow cylinders W ≲ 6–8 (2D); thermodynamic limit via iDMRG/VUMPS

### Accuracy & guarantees

- Class: controlled-bias, deterministic; variational upper bound on energy at fixed χ
- Primary approximation & its control: finite-χ MPS truncation; bias → 0 monotonically as χ → ∞; convergence verified by ε_trunc extrapolation
- Error scaling: energy error ~ O(ε_trunc); ε_trunc decreases exponentially with χ for gapped systems, polynomially for critical systems

### Tasks it computes

- Ground-state energy and wavefunctions for 1D/quasi-1D systems
- Few low excited states (targeted DMRG sweeps in different symmetry sectors)
- Spectral gap from the first excited-state energy
- Entanglement entropy and entanglement spectrum (directly from the MPS Schmidt values)
- Correlation functions ⟨O_i O_j⟩ and order parameters
- Correlation length (from transfer-matrix / dominant VUMPS eigenvalue)
- Dynamical structure factor S(q,ω) (correction-vector DMRG or post-TDVP)

### Recommended for (models / regimes)

- **Primary GS solver for 1D gapped systems** (spin chains, Hubbard chain, t-J chain): essentially exact at moderate χ ~ 100–500
- **1D critical systems** (XXX chain, transverse-field Ising at Jc): larger χ (polynomial growth with L), finite-size scaling needed
- **Quasi-1D / ladder geometries**: ladders, zig-zag chains, narrow cylinders — gold standard, χ scales exponentially with ladder width
- **2D as benchmarking tool on cylinders**: torus / cylindrical Hubbard, Heisenberg on width-W cylinders (W ≤ 6 practical)
- Per `method-property-map.md`: optimal when A1=1D, B5=area-law or area+log, C12=sign-ful (frustrated), C9/C10 present (big speedup); disfavored for A1=2D bulk, D13=real-time, or B5=volume-law

### Key reference

[@schollwoeck_2010_density] — the authoritative modern reference: formulates DMRG as MPS variational optimization, covers finite/infinite systems, symmetries, excited states, dynamical spectra, and cost scaling.
Rendered: `../../literature/mps-based-algorithm/1008.3477_the-density-matrix-renormalization-group-in-the-age-of-matri.md` _(reused)_.

### Benchmarks

- 1D Heisenberg chain: GS energy per site e₀ = −0.44315 J (N→∞, iDMRG χ~500) — reproduced to 6+ digits by χ extrapolation [@schollwoeck_2010_density].
- 2D Heisenberg square lattice (cylinder W=8, χ=4096): e₀ ≈ −0.3347 J/site, consistent with QMC benchmark −0.33699 within 0.5% [survey §3.1].
- Entanglement entropy scaling: S ~ (c/3) ln(ξ) for 1D CFT (c=1), verified for XXX chain χ~200 [survey §3.1].

## How it is used / Operational

**Owning skill:** `/method-mps` (primary); tool skills `/using-itensors`, `/using-mpskit`, `/using-tenpy`.

**Default workflow:**
1. Apply symmetry (U(1) particle number / SU(2) spin) to label the target quantum-number sector.
2. Initialize MPS randomly (or from a product state); set χ_init ~ 10–50.
3. Run finite-system DMRG sweeps (left-to-right + right-to-left), solving the local 2-site eigenvalue problem at each bond, until energy converges < 10⁻⁸ per sweep.
4. Increase χ (warmup sweeps) until truncation error ε_trunc < 10⁻⁷ and energy is χ-converged.
5. For thermodynamic limit: switch to iDMRG (fixed unit cell) or VUMPS (uniform MPS); verify via transfer-matrix spectrum.
6. Extract observables from the optimized MPS; entanglement entropy is read directly from Schmidt values.

**Verification pointers:**
- Cross-check GS energy against ED Lanczos (small N) or QMC (sign-free models) at the same parameters.
- Plot energy vs ε_trunc and extrapolate to ε_trunc → 0 to bound the systematic truncation error.
- Verify sum rules for S(q,ω) if computed.

**Cross-links:**
- Survey: `method-survey.md` §3.1 (DMRG / MPS — finite and infinite)
- Model↔method gate: `method-property-map.md` (MPS/DMRG profile)
- Complementary methods: TEBD (real-time dynamics, §5.1), TDVP (§5.2), PEPS/iPEPS (2D bulk), ED (benchmark oracle for small clusters)

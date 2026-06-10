---
name: method-mps
description: Use when an MPS / matrix-product-state reproduction or calculation needs method-level route and tool selection — ground states, order parameters, correlations, gaps, dynamics, or finite-T of 1D and quasi-1D (narrow-cylinder) Hamiltonians, in either the finite-chain regime (DMRG, TEBD) or the infinite / uniform regime (VUMPS, IDMRG, iTEBD, TDVP). Covers picking the algorithm and routing to the tool.
---

# Method MPS

## Overview

A Matrix Product State (MPS) writes the wavefunction of a 1D (or narrow quasi-1D) quantum system as a chain of small tensors, one per site, linked by **bond** indices. The bond size — the **bond dimension D** (also written χ) — is the single accuracy knob: it caps how much entanglement the state can carry, so the method is *controlled* (systematically improvable by raising D).

- **What it does.** Represent the state compactly, then either **variationally minimize the energy** (sweeping, DMRG / VUMPS) or **evolve in imaginary time** (TEBD / TDVP) to reach the ground state; real-time evolution gives dynamics. Observables (energy, order parameters, correlations, gaps, entanglement) are read off the converged tensors.
- **Two regimes.** **Finite** — an open or periodic chain of fixed length L (DMRG, TEBD). **Infinite / uniform** — one small **unit cell** of tensors repeated forever, giving the thermodynamic limit *directly* with no finite-size extrapolation (VUMPS, IDMRG, iTEBD).
- **Target.** Ground-state energy per site, order parameters, correlation functions and the correlation length, the gap, entanglement entropy; with time evolution, dynamics and (via purification / METTS) finite temperature.
- **What's approximated.** Truncating the bonds to finite D discards the smallest entanglement. Exact for gapped 1D as D grows; for **gapless / critical** systems the finite D imposes an effective correlation length (finite-entanglement scaling), so D must be pushed and scaled.

**Infinite-regime ground states — VUMPS.** Among the infinite-MPS ground-state algorithms, **VUMPS** (Variational Uniform MPS) converges the variational gradient to machine precision — *even at criticality*, where IDMRG and iTEBD stall — which is exactly the comparison in FIG.7 of the VUMPS paper (arXiv:1701.07035).

> **When this card is invoked, before any choice, orient the user with this table (interaction principles below), filling the right column with *their* actual problem — Hamiltonian, geometry, target. If those aren't fixed yet, use the table to elicit them.**

| Ingredient | What it is | Your setup |
|---|---|---|
| Hamiltonian H | the 1D / quasi-1D model and its couplings | *(user's model + couplings)* |
| Geometry | finite chain (length L, OBC/PBC) **or** infinite/uniform (unit-cell length) | *(finite L or infinite; cylinder width if quasi-1D)* |
| Bond dimension D | the MPS link size — the accuracy knob | *(target D / D-series)* |
| Algorithm | DMRG · TEBD · VUMPS · IDMRG · iTEBD · TDVP | *(which, and why)* |
| Target | energy / order parameter / correlations / gap / dynamics / finite-T | *(which observable, which states)* |
| What's approximated | finite-D truncation (+ Trotter step for TEBD) | *(D-convergence / τ→0 plan)* |

> **Interaction principles — all user-facing surfacing in this card.** Plain language, no jargon: define every term, symbol, and axis before first use. No walls of words — a few sentences or one compact table per turn. One decision at a time, recommendation-first with one-line pros/cons. Precise and concise; let the user feel each choice, never a silent default.

## Sources

- Tool skills:
  - `/using-mpskit` — **MPSKit.jl** (Julia): infinite MPS (VUMPS, IDMRG, IDMRG2), finite DMRG, TDVP. The canonical route for uniform/infinite ground states in this harness.
  - `/using-tenpy` — **TeNPy** (Python): iTEBD (the algorithm MPSKit lacks), iDMRG, VUMPS, finite DMRG/TEBD, finite-T purification.
  - `/using-itensors` — **ITensorMPS.jl** (Julia): finite DMRG / TEBD; infinite via ITensorInfiniteMPS.
- Primary literature (rendered in `.knowledge/literature/mps-based-algorithm/`):
  - **1701.07035** — Zauner-Stauber, Fishman, Verstraete et al., PRB **97**, 045145 (2018) — VUMPS; the source for the infinite-regime Details, the gradient-norm stop criterion, and the FIG.7 benchmark.
- Foundational (pull with `/download-ref` if needed): White PRL 69 (1992) / PRB 48 (1993) — DMRG; Vidal PRL 91 (2003), 93 (2004) — TEBD; McCulloch arXiv:0804.2509 (2008) — IDMRG; Haegeman et al. PRL 107 (2011), PRB 94 (2016) — tangent space / TDVP; Schollwöck Ann. Phys. 326 (2011) — MPS review.

## Select method — step 1

### Suited for
- **Ground states** — energy per site, order parameters, correlation functions, gaps, entanglement — of **1D chains and narrow quasi-1D cylinders**. The workhorse for these.
- **Thermodynamic limit directly** (infinite/uniform regime): no finite-size extrapolation — VUMPS / IDMRG / iTEBD give the per-site energy of the infinite system; the correlation length comes from the transfer matrix; gapless vs gapped is diagnosed by finite-entanglement scaling in D.
- **Critical / gapless 1D** — feasible but D-hungry; VUMPS is the cleanest converger here.
- **Dynamics** (real-time TEBD / TDVP) and **finite temperature** (purification / METTS) — supported, but treat as beyond the basic ground-state reproduction unless the target figure is explicitly dynamics or thermodynamics.

### Worked examples

Anchor the user's problem to the nearest row and quote its scale as a concrete reference. The four FIG.7 panels of 1701.07035 are an infinite-MPS convergence-speed benchmark (wall time / iterations vs gradient norm) across the three infinite algorithms; *D* is the bond dimension, the cell is the repeated unit.

| Ref | Model | Problem type | Scale | Calculated |
|---|---|---|---|---|
| 1701.07035 FIG.7a | spin-1 XXZ, Δ=1 (Haldane, **gapped**) | infinite ground state, convergence speed | D=120, 1-site cell, no symmetry | e₀ (≈ −1.401484); VUMPS drives ‖B‖→~1e-12 |
| 1701.07035 FIG.7b | spin-½ XXZ, Δ=2 (**gapped** AFM) | infinite ground state | D=54, 2-site cell | e₀ (no closed form) |
| 1701.07035 FIG.7c | spin-½ XXZ, Δ=1 (isotropic Heisenberg, **critical**) | infinite ground state — the hard case | D=70, 1-site cell via sublattice rotation | e₀ = ¼ − ln2 ≈ −0.4431; **VUMPS reaches ‖B‖~1e-12 while IDMRG / iTEBD stall ~1e-4** |
| 1701.07035 FIG.7d | Hubbard chain | infinite ground state (fermionic) | 2-site cell | e₀ |
| classic | spin-½ Heisenberg / XXZ, finite chain | finite ground state, finite-size trend | DMRG, L up to ~100s, D~few×100 | E(L), order parameter, correlations → 1/L extrapolation |

### Route elsewhere — when MPS isn't the right tool

MPS fits **1D and narrow quasi-1D**. Route away when:

| Target | Better tool | Why |
|---|---|---|
| Genuinely 2D / wide systems | PEPS (`/method-peps`) | MPS bond dimension blows up exponentially with cylinder width |
| Classical stat-mech / finite-T tensor networks | LTRG (`/method-ltrg`) | different contraction; MPS isn't the natural object |
| Full spectrum / level statistics, small system | ED (`/method-ed`) | MPS gives low-lying states, not the whole spectrum |
| Large-scale unfrustrated 2D/3D ground states | QMC (`/method-qmc`) | sign-free QMC scales better when there's no sign problem |

> **When the user's goal falls outside 1D/quasi-1D:** recognize it before any setup; explain *what fits better and why* in a short what/why table; stay warm — guide, don't dismiss. (Interaction principles above.)

### Options & trade-offs

| Algorithm | Regime | Good at | Weak at | When to use |
|---|---|---|---|---|
| **DMRG** | finite | robust, mature ground states of gapped 1D / cylinders; order parameters & correlations | finite-size *and* finite-D error → needs extrapolation; slow/unstable for gapless | finite chains and cylinders; anything needing edge physics or 1/L trends |
| **VUMPS** | infinite | **variational uniform fixed point; fastest, cleanest convergence — gradient ‖B‖→machine precision even at criticality** | needs a translation-invariant setup; per-iteration effective eigensolves | the **default for infinite ground states**; the FIG.7 winner, especially critical |
| **IDMRG** | infinite | thermodynamic limit by growing + translating a DMRG cell; reuses DMRG machinery; MPO Hamiltonians | converges to the true uniform fixed point slower than VUMPS; can stall at criticality | infinite ground states when DMRG infrastructure is already in hand |
| **iTEBD** | infinite | simple; imaginary-time projection from a product state; thermodynamic limit | Trotter error (τ→0 needed); slow near criticality; awkward for long-range H | infinite, short-range, gapped; a preparation/evolution route |
| **TEBD (real-time) / TDVP** | finite & infinite | dynamics; TDVP handles long-range / MPO Hamiltonians | entanglement growth caps reachable time | dynamics targets (out of basic reproduction scope) |

### Routing — surface to the user

> **Present the choice as a table:** which algorithm, when to choose it, which fits their case. Make them feel the one consequence that decides it:
> - **Finite chain / cylinder, or edge physics / 1/L trends needed → DMRG.**
> - **Infinite / thermodynamic-limit ground state → VUMPS** (the default): it converges the tangent-space gradient to machine precision even at criticality, where IDMRG and iTEBD stagnate — the exact lesson of FIG.7. Pick IDMRG/iTEBD only to reproduce a paper that used them, or to *compare* convergence (as FIG.7 does).
> - **Dynamics → TEBD/TDVP** (flag as beyond basic ground-state scope).
> When reproducing, the deciding fact is usually *which algorithm the paper used* — confirm that first.

## Select software — step 2

### Routing rule
**If the chosen algorithm is available in MPSKit, use MPSKit; otherwise route to TeNPy or ITensorMPS.jl.** MPSKit is the harness's canonical Julia tensor-network stack and covers the whole infinite-MPS family except one — **iTEBD**, which forces a route to TeNPy.

### The packages

- **MPSKit.jl** (Julia; Verstraete-group / QuantumKitHub, maintained) — VUMPS, IDMRG, IDMRG2, GradientGrassmann, finite DMRG / DMRG2, TDVP. **No TEBD of any kind** (time evolution is TDVP / WII / TaylorCluster). Pairs with **MPSKitModels.jl** (ready Hamiltonians: `heisenberg_XXZ`, `heisenberg_XYZ`, Hubbard, …) and **TensorKit.jl** (tensors, abelian/non-abelian symmetries). → `/using-mpskit`.
- **TeNPy** (Python; Hauschild & Pollmann, maintained) — **iTEBD** (`TEBDEngine`), iDMRG, VUMPS, finite DMRG / TEBD, finite-T purification. The route whenever the target *is* iTEBD, or when a Python ecosystem is preferred. → `/using-tenpy`.
- **ITensorMPS.jl** (Julia; ITensor project) — finite DMRG / TEBD with the observer/sweeps interface; infinite via **ITensorInfiniteMPS.jl**. → `/using-itensors`.

### Feature matrix — algorithm × package

| Algorithm | MPSKit | TeNPy | ITensorMPS |
|---|---|---|---|
| finite DMRG | ✓ | ✓ | ✓ |
| finite TEBD | ✗ | ✓ | ✓ |
| **iTEBD** | **✗** | **✓** | (ITensorInfiniteMPS) |
| IDMRG | ✓ | ✓ | ITensorInfiniteMPS |
| **VUMPS** | **✓** | ✓ | — |
| TDVP | ✓ | ✓ | ✓ |

> **The one gotcha to surface:** MPSKit has **no TEBD** — a paper's iTEBD curve must come from TeNPy (this is exactly what FIG.7's iTEBD panel required). Everything else infinite (VUMPS, IDMRG) stays in MPSKit.

### Surface to the user

> **Surface the software choice** as a short what/why table (interaction principles above): the recommended package for the chosen algorithm (per the routing rule and feature matrix), what it is and who maintains it, and 1–2 real alternatives with their setup state. Offer `Search web for official paper code / setup` unless forbidden or already verified. Be honest that a custom convergence probe (per-iteration trajectory, gradient norm) may need a package iteration hook or a `Pkg.develop` clone — see reproduce-paper step 2.

### Handoff
Invoke **/using-mpskit** for infinite (VUMPS/IDMRG) or finite work in the Julia stack; **/using-tenpy** for iTEBD or the Python route; **/using-itensors** for ITensorMPS finite work. The tool skill owns bond dimension, sweeps, tolerance, unit-cell construction, symmetry setup, the convergence probe, and the time estimate. This card owns algorithm choice, the conceptual knobs, and verification.

## Method setup — step 3

Each knob with its default and a consolidated principle/effect (with scaling where it matters). Package-specific values (constructor keywords, env vars) live in the `/using-*` cards. *(Math unicode/plain.)*

| Knob | Default | Principle, effect & scaling |
|---|---|---|
| **Bond dimension D (χ)** | problem-dependent (FIG.7: 54–120; cylinders & critical want larger) | the single accuracy lever — caps the entanglement the state carries. Energy decreases monotonically and asymptotes as D grows; **gapless/critical** systems never fully converge at fixed D (finite-entanglement scaling: effective ξ ~ D^κ) so D must be scaled. Cost ~D³ per local update |
| **Unit cell** (infinite) | smallest cell compatible with the ground-state order | the repeated translation period. **Must be ≥ the period of the order**, or the ansatz literally cannot represent the state — a Néel / AFM ground state needs a **2-site** cell, a uniform / Haldane state a **1-site** cell. *Symmetry-breaking trick:* a sublattice rotation can fold an ordered 2-site state back to a 1-site cell — FIG.7c rotates every second spin (π about z), mapping critical XXZ to a 1-site problem |
| **Tolerance / stop criterion** | VUMPS/IDMRG: gradient norm ‖B‖ < 1e-10…1e-12; DMRG: ΔE/sweep + 2-site variance; iTEBD: energy plateau | the convergence target. **Tangent-space gradient norm ‖B‖** — the norm of the projected energy gradient, →0 at the variational optimum (paper Eq.34) — is the right stop signal for VUMPS/IDMRG; in MPSKit it is `calc_galerkin`, in TeNPy `tangent_projector_test`. DMRG uses energy change per sweep and the variance ⟨H²⟩−⟨H⟩². Too loose → biased energy; too tight → wasted sweeps |
| **Imaginary-time step τ** (iTEBD) | schedule 0.1 → 5e-4 in stages | Trotter error ~τ² (2nd order). Refine τ→0 in stages, running each to its energy plateau. **Pitfall:** a small τ alone makes per-step ΔE tiny *regardless of convergence* — never read that as converged; combine τ-refinement with enough total imaginary time |
| **Max iterations / sweeps** | VUMPS/IDMRG: ~100s; DMRG: ~10s of sweeps | a work cap; the stop criterion should fire first. Hitting the cap = not converged — raise it or D, don't report it |
| **Symmetry** | none, or U(1) Sz / particle number (SU(2) when available) | exploiting a conserved quantity block-diagonalizes the tensors → smaller, faster, and pins the sector. **The VUMPS paper deliberately uses no symmetry** to benchmark the bare algorithm; for production, U(1) Sz is a large speedup but fixes the sector — match the paper |
| **Initial state** | random, or a product state in the target sector | random explores but can land in a metastable state; a product state (Néel, dimer) in the right sector is more robust and pins the symmetry sector. Restart with a new seed if convergence stalls in a local minimum |

> **Confirm the setup with the user before running — one knob per turn, never batched (interaction principles above).**
>
> 1. **Orient once.** One plain hook — e.g. *"The bond dimension D is the dial: bigger D = more entanglement captured = closer to exact, at ~D³ cost. For an infinite system we also pick the repeating unit cell, which must be big enough to hold the magnetic order."* Then tie each knob to its role.
> 2. **Loop, one knob per turn.** Recommended option first, labeled "(Recommended)" only with a technical reason (the paper's value when reproducing), one-line why, then 1–2 alternatives with one-line pro/con.
> 3. **Ask one, STOP, wait.** Never batch; never accept a silent default.
> 4. **Lead with the two that decide the result:** (1) **bond dimension D** — the accuracy lever; too small reads as converged but is biased, fix is a D-series until the energy stops moving (and finite-entanglement scaling if gapless); (2) **unit cell** — too small cannot represent the order at all; match it to the ground-state period (or use the rotation trick). Then tolerance / stop criterion, then the rest.

### Cost & resource estimate

Wall time is **one measured rate × a fixed amount of work**: the per-iteration work is a firm count of D³ tensor operations; the unknown is the per-operation throughput (BLAS rate, threading), settled by one timing probe. Written in four quantities: **D** = bond dimension, **d** = physical (local) dimension, **L_cell** = unit-cell / chain length, **n_iter** = iterations or sweeps.

| Axis | Scaling |
|---|---|
| **Compute** | per iteration ∝ L_cell · d · D³ — dominated by the local effective eigensolve (VUMPS/DMRG) or SVD (iTEBD) on the D×D bonds; × n_iter. **Iterations differ by algorithm**: VUMPS reaches a given ‖B‖ in fewer iterations than IDMRG/iTEBD (the FIG.7 point), and critical systems need both more iterations and larger D |
| **Memory** | O(L_cell · d · D²) for the tensors + O(D² · χ_MPO) for the Hamiltonian environments — modest; compute, not memory, is usually the gate |
| **Wall time** | (L_cell · d · D³ · n_iter) ÷ throughput; throughput is the 1–2 order-of-magnitude unknown, settled by one short timing probe at the target D |

*FIG.7 illustration (D=54–120, d=2–3, 1–2-site cell, no symmetry): seconds to a few minutes on a laptop, single-thread. Larger D (cylinders, near-critical, 2D-as-cylinder) scales as D³ → route to a cluster (`/using-slurm`). Symmetry (U(1)) cuts the effective D substantially.*

> **Surface the cost before any scale choice (reproduce-paper step 4).** Plain language: wall time is *one measured rate × a firm D³ work count* — show the work for their D, name the single unknown (throughput, settled by one probe), and that **D is the dial that sets the cost**. **If the target figure is itself a wall-time benchmark** (like FIG.7), threading and warm-up handling are governed by reproduce-paper's *performance benchmark* rules — core/thread count is a confirmed knob, and JIT/setup/measurement time is excluded.

## Details

Generic methodology; paper/model facts live in `/reproduce-paper` and `.knowledge/models/`. Math is unicode/plain.

### Notation
- **MPS**: state as a chain of tensors A_i, each carrying a physical index (dimension d) and two bond indices (dimension D).
- **Bond dimension D (χ)**: the link size; the accuracy/entanglement cap.
- **Canonical form**: a gauge where tensors are left- or right-isometries; the *mixed* canonical form keeps a single center tensor — the object VUMPS optimizes.
- **Transfer matrix**: the D²×D² map built from a tensor and its conjugate; its second eigenvalue sets the correlation length.
- **Unit cell**: for an infinite MPS, the finite set of tensors repeated forever (length L_cell).
- **Tangent space**: the space of first-order variations of a uniform MPS at fixed D; the energy gradient lives here, and its norm is **‖B‖**.

### Infinite / uniform MPS — the regime VUMPS lives in

A uniform (translation-invariant) MPS repeats one unit cell of tensors infinitely, representing the **thermodynamic limit directly**. Working in the mixed canonical form, the state is fixed by a left isometry A_L, a right isometry A_R, a center tensor A_C, and a bond matrix C (Eq.29 convention of 1701.07035). Three algorithms find the ground state:

- **VUMPS.** The energy is stationary when the tangent-space gradient vanishes. VUMPS solves two coupled **effective eigenvalue problems** — for the center tensor A_C and the bond matrix C against the Hamiltonian environments — then re-gauges to a consistent (A_L, A_R, A_C, C). Iterating drives the **tangent-space gradient norm ‖B‖ → 0** (the variational optimum). Because it optimizes the uniform state *directly* (not a finite cell extrapolated outward), it converges fastest and cleanest, including at criticality. It exploits no symmetry by default. ‖B‖ — paper Eq.34, the projected gradient — is the convergence diagnostic, computed by `calc_galerkin` (MPSKit) or `tangent_projector_test` (TeNPy).
- **IDMRG.** Run two-site DMRG on a growing chain and translate the converged center cell outward; the bulk tensor approaches the uniform fixed point. Reuses all DMRG machinery and MPO Hamiltonians, but reaches a given ‖B‖ in *more* iterations than VUMPS and can stall near criticality.
- **iTEBD.** Apply imaginary-time Trotter gates e^{−τh} to the infinite MPS and re-canonicalize by SVD truncating back to D; imaginary time projects onto the ground state. Simple, but carries Trotter error (τ→0 needed) and converges slowly near criticality.

### Finite MPS — DMRG and TEBD
- **DMRG**: sweep site-to-site, locally minimizing the energy by solving an effective eigenproblem on one or two sites, truncating the updated bond to D. Robust for gapped finite chains and cylinders; carries both finite-size and finite-D error.
- **TEBD**: split H into bond gates, apply Trotterized e^{−τH} (imaginary time → ground state; real time → dynamics), truncate to D after each layer.
- **TDVP**: project the (real or imaginary) time evolution onto the tangent space of fixed-D MPS; handles long-range / MPO Hamiltonians where TEBD's gate decomposition is awkward.

### The convergence diagnostic ‖B‖
For the variational (tangent-space) methods the right convergence signal is **not** the energy change but the **norm of the projected energy gradient ‖B‖** (Eq.34). It is the size of the best tangent-space improvement to the current state; ‖B‖→0 ⇔ a true variational fixed point. Energy can look settled while ‖B‖ is still large (a near-plateau that is not yet stationary), so stop on ‖B‖, report the energy. MPSKit: `calc_galerkin(below, H, above, envs)` per site; TeNPy: `tangent_projector_test(env_data)`. A per-site RMS over the cell gives one scalar.

## Verification

### Intermediate (mid-run)
- **Gradient / variance falling.** ‖B‖ (VUMPS/IDMRG) or the 2-site variance (DMRG) decreases monotonically toward the tolerance; a stall above tolerance = not converged (raise D or iterations, check the unit cell).
- **Energy monotone & flattening.** Energy per site decreases and asymptotes. For **iTEBD**, watch a plateau at *each* τ stage — and do not mistake a tiny per-step ΔE at small τ for convergence (it shrinks with τ regardless).
- **Correlation length finite.** From the transfer matrix's second eigenvalue; it should be finite and grow with D (diverging-with-D is the critical signature).

### Final verification + expert criticism
- **D-convergence.** Energy vs D monotone and asymptoting; for **gapless/critical**, do finite-entanglement scaling in D rather than claiming a converged value at one D.
- **Cross-method / exact agreement.** VUMPS, IDMRG, iTEBD agree on the energy (FIG.7c: ¼−ln2 for critical Heisenberg; ≈−1.401484 for the spin-1 Haldane chain). Disagreement at the same D flags a setup error.
- **Symmetry sector correct.** Total Sz / particle number of the result matches the intended sector (see `.knowledge/symmetry-cheatsheet.md`).

> **Criticize:** unit cell too small for the order (can't represent Néel on a 1-site cell) → wrong state silently; D too small read as converged (no D-series) → biased energy; **iTEBD false convergence** (small τ → tiny ΔE regardless of truncation — must refine τ *and* run each stage to its plateau); reading the energy before ‖B‖ has converged; for a wall-time benchmark, leaving JIT/warm-up/setup time in the clock or comparing stacks at different thread counts (see reproduce-paper *performance benchmark* rules); claiming a critical-system value at fixed D without finite-entanglement scaling.

## Citations

Rendered under `.knowledge/literature/mps-based-algorithm/`:

- `1701.07035_*.md` — Zauner-Stauber, Fishman, Verstraete et al., PRB **97**, 045145 (2018) — VUMPS; the primary source for the infinite-regime Details, the ‖B‖ stop criterion (Eq.34), the Eq.29 canonical convention, and the FIG.7 benchmark.

Foundational (pull with `/download-ref` if needed): White PRL 69 (1992), PRB 48 (1993) — DMRG; Vidal PRL 91 (2003), 93 (2004) — TEBD; McCulloch arXiv:0804.2509 (2008) — IDMRG; Haegeman et al. PRL 107 (2011), PRB 94 (2016) — tangent space / TDVP; Schollwöck Ann. Phys. 326 (2011) — MPS review. Tool setup lives in `/using-mpskit`, `/using-tenpy`, `/using-itensors`.

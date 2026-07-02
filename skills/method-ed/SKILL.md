---
name: method-ed
description: Use when an exact diagonalization track, ED reproduction, full spectrum, symmetry sector, scar, ETH, level statistics, quench dynamics, finite-temperature Lanczos / thermal pure quantum (FTLM/TPQ), Chebyshev/KPM or continued-fraction spectral function, interior-spectrum / MBL eigenstates, or finite-cluster oracle needs method-level route and tool selection.
---

# Method ED

## Overview

Exact diagonalization (ED) writes the many-body Hamiltonian in an explicit finite basis — or applies it matrix-free — and extracts eigenvalues, eigenvectors, dynamics, or thermal traces with **no approximation beyond the finite cluster**. It is the small-system oracle: the reference every approximate method (DMRG, QMC, VMC, NQS, VQE) is calibrated against, and the only method that natively returns the *full spectrum with all eigenvectors*.

- **What it does.** Six routes over one machinery: dense full diagonalization (complete spectrum), Lanczos/Krylov (ground and low-lying states), Krylov real-time evolution (exact quench dynamics), FTLM/TPQ (finite temperature by stochastic trace), continued-fraction/KPM (spectral functions), and interior solvers (shift-invert / polynomial filter, for mid-spectrum eigenstates).
- **The one scale variable is D** — the dimension of the *symmetry-reduced block*, never the site count N alone. Every cost, memory, and feasibility statement in this card is a statement about D.
- **What's approximated.** Nothing, within a route: dense and Lanczos eigenpairs are exact to machine precision (residual-checked); FTLM/TPQ and KPM carry a controlled stochastic error (shrinks with random-vector count R); the only physics bias is the finite cluster itself — finite-size effects are the thing to scale out, not a convergence knob.

> **When this card is invoked, before any choice, orient the user with this table (interaction principles below), filling the right column with *their* actual problem. If those aren't fixed yet, use the table to elicit them.**

| Ingredient | What it is | Your setup |
|---|---|---|
| Hamiltonian H | the model and couplings on a finite cluster | *(user's model + couplings)* |
| Basis / constraint | local space per site; any constrained Hilbert space (e.g. Rydberg blockade) | *(spin-½ / electron / constrained rule)* |
| Boundary & cluster | OBC/PBC; for 2D the cluster shape, aspect ratio, allowed momenta | *(boundary, cluster)* |
| Symmetry sectors | conserved quantum numbers that block-diagonalize H: Sz / particle number, momentum k, parity p, spin flip z | *(which are imposed, which deliberately not)* |
| Target observable | what the figure needs: spectrum, states, dynamics, T>0 curves, spectral function | *(the plotted quantity + which states)* |
| Route | dense full · Lanczos · Krylov dynamics · FTLM/TPQ · CF/KPM · interior | *(decided by the observable, below)* |
| Block dimension D | the symmetry-reduced dimension — sets memory and wall time | *(compute before any estimate)* |

> **Interaction principles — all user-facing surfacing in this card.** Plain language, no jargon: define every term, symbol, and axis before first use. No walls of words — a few sentences or one compact table per turn. One decision at a time, recommendation-first with one-line pros/cons. Precise and concise; let the user feel each choice, never a silent default.

## Sources

- **Methodology reference** (reproduction-grade algorithms: basis construction, symmetry adaptation, Lanczos, continued fraction, FTLM/TPQ estimators, validation anchors): `references/ed-methodology.md`
- **Method-zoo cards** (M1–M14 property tables, cost classes): `.knowledge/methods/ed-full`, `ed-lanczos`, `ftlm-tpq`, `kpm`; `fci` is the quantum-chemistry sibling (same wall, different tooling). Model → method gate: `.knowledge/method-property-map.md`.
- **Knowledge cards**: `.knowledge/symmetry-cheatsheet.md` (conserved quantities, lattice point groups — the sector inventory), `.knowledge/conventions.md` (sign / normalization defaults), `.knowledge/limits.md` (exact limits for anchor checks).
- Tool skills: `/using-xdiag` — **XDiag.jl** (Julia), the canonical symmetry-resolved ED stack; `/using-quspin` — **QuSpin** (Python), the fallback and the constrained-basis (`user_basis`) route.
- Expert sources (distilled into this card): `docs/ed/interview.html` — practitioner interview; `docs/ed/review.html` — 2026 landscape: feasibility ceilings, 16-tool catalog, tricks list.
- Track README: `tracks/ed/README.md`
- Literature (rendered under `.knowledge/literature/ed/`): Sandvik `1101.3281`; Weiße & Fehske `10-1007-978-3-540-74686-7-18`; XDiag `2505.02901`; QuSpin `1610.03042`.

## Select method — step 1

### Suited for

- **Full spectrum with every eigenvector** — scar towers, ETH diagnostics, level statistics, eigenstate entanglement, exact thermodynamics by canonical sum. No other method returns this at all.
- **Exact oracle** — ground/low-lying states on small clusters to calibrate DMRG / QMC / VMC / NQS runs at the same size.
- **Exact real-time dynamics** — quenches, revivals, Loschmidt echoes with no Trotter error and no truncation, out to any time the block affords.
- **Finite temperature** — exact canonical sums at full-spectrum sizes; FTLM/TPQ pushes 10–15 sites further with controlled stochastic error.
- **Spectral functions on finite clusters** — S(q,ω), A(ω), σ(ω) by continued fraction or KPM.
- The selecting judgment *(interview Q1.2)*: **choose ED for what other methods cannot do.** If the target only needs a ground-state expectation at large size, ED is the cross-check, not the workhorse.

### Worked examples — the ED track target

The track paper (Turner et al., Nature Physics 14, 745 (2018) — PXP quantum many-body scars) exercises three routes on one model; `.knowledge/models/rydberg-pxp/MODEL.md` owns the model facts. The constrained (blockaded) chain has Fibonacci-scale dimension D ~ φ^N ≈ 1.618^N, not 2^N — at N = 32 (PBC) that is ≈ 4.9×10⁶ vs 4.3×10⁹, three orders of magnitude, which decides both feasibility and tooling.

| Figure | Target | Route | Sector discipline | Scale |
|---|---|---|---|---|
| Fig 2 | \|Z₂⟩ quench revivals, fidelity vs t | Krylov time evolution in the constrained basis | constrained enumeration correct (dim = Fibonacci/Lucas count) | N ≈ 24–32, D up to ~5×10⁶ |
| Fig 3 | scar tower: \|⟨Z₂\|E_n⟩\|² vs E | dense full spectrum in one fully specified sector | k = 0 and k = π blocks (with inversion), where \|Z₂⟩ has weight | per-sector D ~ 10⁴–10⁵ → dense |
| Fig 4 | level statistics (ETH-like bulk) | dense full spectrum, gap-ratio statistic | **one fully resolved sector** (k, inversion); degeneracies and the zero-energy subspace removed | same blocks as Fig 3 |
| anchor | Heisenberg chain N = 16 ground state | Lanczos | (k=0, p=+1, z=+1): E₀ = −7.1422964 J | the standard code check (Sandvik Table 2) |

### Route elsewhere when

| Target | Better tool | Why |
|---|---|---|
| Block D beyond the frontier even after all symmetries (dense ≳ 10⁵–10⁶ local, Lanczos ≳ 10⁹–10¹⁰ local) | `/method-mps`, `/method-qmc`, `/method-vmc` | the d^N wall is physical; approximate methods exist for exactly this |
| 1D / quasi-1D ground state at large L, no full spectrum needed | `/method-mps` (DMRG) | polynomial in L instead of exponential |
| Sign-free finite-T at large size | `/method-qmc` (SSE) | stochastic trace without the Hilbert-space wall |
| 2D ground states beyond small tori | `/method-peps`, `/method-qmc` | ED tops out near N = 36–48 even at the frontier |
| Quantum-chemistry Hamiltonians (orbitals + integrals) | `fci` zoo card | same method, different tooling (selected-CI / FCIQMC ecosystems) |

### Options & trade-offs

The sub-method routes. Memory and time are in D; z = nonzeros per row ≈ Hamiltonian terms per site; Λ = Lanczos iterations (≈ 50–200 for extremal eigenpairs).

| Route | Zoo card | Returns | Cost | When |
|---|---|---|---|---|
| **Dense full ED** | `ed-full` | all eigenvalues + eigenvectors of a block | O(D³) time, O(D²) memory | full-spectrum targets: scar/ETH overlaps, level statistics, exact thermodynamics. D ≲ 10⁵ workstation |
| **Lanczos / Krylov** | `ed-lanczos` | few extremal eigenpairs | Λ × O(z·D) time, O(D) memory | ground state, gaps, low-lying tower; the oracle route |
| **Krylov dynamics** | `ed-lanczos` | ψ(t) exactly | matvecs per step × steps | quenches, revivals; machine-precision per step, no Trotter error |
| **Interior** (shift-invert / POLFED) | `ed-lanczos` | eigenpairs in an energy window | shift-invert: LU memory wall ~10⁶; polynomial filter: K matvecs per step, O(D) memory | MBL, mid-spectrum states beyond dense reach |
| **FTLM / TPQ** | `ftlm-tpq` | thermodynamic curves, T > 0 | R random vectors × M_L matvecs per sector | finite T beyond full-diagonalization sizes; stochastic error ∝ 1/√(R·D) |
| **Continued fraction / KPM** | `ed-lanczos` / `kpm` | S(q,ω), A(ω), σ(ω) | one extra Lanczos run / M Chebyshev matvecs | dynamical response; CF sharper at discrete poles, KPM smoother for continua |

### Routing — surface to the user

> **The target observable decides the route** *(interview Q1.1)* — present it as: what the figure needs → what that forces.
> - **Scar / ETH / level statistics / eigenstate properties → full spectrum → dense, in one fully specified sector.** Not negotiable: these observables need all eigenpairs of a block.
> - **Ground state, gap, low-lying tower → Lanczos** in the expected ground-state sector.
> - **Quench / revival dynamics → Krylov time evolution** from the initial state's sector.
> - **Thermodynamics → all sectors**: exact canonical sum when every block is dense-able, else FTLM/TPQ.
> - **Spectral function → continued fraction** (discrete poles) or **KPM** (smooth spectra).
> - **Mid-spectrum eigenstates at large D → shift-invert / polynomial filter**, only with an explicit memory/filter budget.
> When reproducing, the paper's route wins — confirm it first, deviate only with the deviation recorded.

## Select software — step 2

### Routing rule

**`/using-xdiag` by default** for research-grade ED: symmetry-adapted blocks (generic space-group irreps), Lanczos, Krylov time evolution, Julia harness runs. **`/using-quspin` when** the paper/official code is Python or QuSpin, a QuSpin example matches the target, or the Hilbert space is *constrained* — `user_basis` is the clean constrained-basis route. **No GPU by default** *(interview Q7.1)*: no front-line ED tool ships GPU kernels (2026 review); consider GPU only on an explicit requirement. If neither tool expresses the target cleanly, the fork is official paper code / web search / custom basis-and-matrix build (the practitioner default for unusual bases — `references/ed-methodology.md` is written to make that reproducible) — recorded as a deviation.

### The packages

- **XDiag** (C++17 core, `XDiag.jl` Julia wrapper; Wietek group, MPI-PKS Dresden; Apache-2.0) — the only public implementation of sublattice coding + generic space-group irreps in an ITensors-style API; spin-½ to N ≈ 50 distributed (D ~ 10¹¹). Lanczos, Krylov real/imaginary time evolution, dense extraction for small blocks. Expert judgment *(review)*: the canonical choice; advanced sparse solvers and spectral transformations. Sharp edges: no SU(2), no GPU, no native constrained bases; distributed (MPI) build has no symmetrized blocks yet. → `/using-xdiag`
- **QuSpin** (Python + Cython kernels; Weinberg & Bukov; BSD-3) — `user_basis` with Numba precheck is *the* way to handle constrained Hilbert spaces (PXP, quantum dimer, Rydberg) without dropping to raw NumPy; 1D symmetry blocks by keyword, general-basis maps for any lattice; `eigsh`, full `eigh`, Krylov `expm_multiply_parallel`, one-liner shift-invert; the FTLM reference implementation (example 21). Expert judgment *(review)*: user friendly. Sharp edges: single node only (no MPI), memory ceiling D ~ 10⁷–10⁸, maintenance velocity slowed. → `/using-quspin`

### Feature matrix — capability × package

| Capability | XDiag | QuSpin |
|---|---|---|
| U(1) sectors (Sz / particle number) | ✓ | ✓ |
| Space-group irreps (momentum + point group) | ✓ generic, any lattice | 1D built-ins; general-basis maps |
| **Constrained basis (PXP-type)** | **✗** — full space + projector ops | **✓ `user_basis`** |
| Dense full spectrum | `matrix` + LAPACK | `eigh` |
| Lanczos low-lying | ✓ | ✓ (ARPACK) |
| Krylov time evolution | ✓ | ✓ (`expm_multiply_parallel`) |
| Shift-invert interior | ✗ | ✓ one-liner (`sigma=`) |
| FTLM / TPQ | imaginary-time primitives | example-21 FTLM |
| Distributed (MPI) | ✓ (no symmetrized blocks) | ✗ |
| GPU | ✗ | ✗ |

> **The one gotcha to surface (and the track's own fork):** a constrained Hilbert space decides the tool. XDiag has no constrained-basis block — a PXP target in XDiag means working in the full 2^N space with projector-dressed operators, ~three orders of magnitude larger at N = 32. QuSpin's `user_basis` enumerates the constrained space directly. Check the enumerated dimension against the exact count (Fibonacci/Lucas for PXP — the model card carries it) before trusting anything downstream.

### Surface to the user

> **Surface the software choice** as a short what/why table (interaction principles above): the recommended package for the chosen route, what it is and who maintains it, and 1–2 real alternatives with their setup state. Offer `Search web for official paper code / setup` unless forbidden or already verified. Be honest when the route means implementing a probe or estimator by hand (FTLM sums, a custom constrained basis) — that is a place the reproduction can silently diverge.

### Handoff

Invoke **/using-xdiag** or **/using-quspin**. The tool skill owns package parameter values (tolerances, iteration caps, dtype, thread count), code shape, and the measured rate in the time estimate. This card owns the route, the sector list, the work counts, and verification.

## Method setup — step 3

Each knob with its default and the judgment behind it. Package-specific expression (constructor keywords, block arguments) lives in the `/using-*` cards.

| Knob | Default | Principle, effect & scaling |
|---|---|---|
| **Symmetries to impose** | all U(1) charges (Sz, particle number) always; spatial symmetries (translation, parity, point group, spin flip) when the paper uses them or the observable requires them — inventory per `.knowledge/symmetry-cheatsheet.md` | U(1) is free — it filters enumeration without changing basis states *(interview Q2.1)*. Each spatial symmetry divides D by ~N or \|G\| but adds representative/phase bookkeeping — **the place bugs enter** *(Q4.3)*, surfaced by the Hermiticity check *(Q4.4)*. Record every exact symmetry deliberately not used. Level statistics require *all* of them resolved |
| **Sector to diagonalize** | problem-driven *(Q2.3)* | low-energy target → the expected ground-state sector; ETH/scars → the largest sector, or the sector the initial/reference state lives in; thermodynamics → all sectors, summed with multiplicities. Wrong sector = a correct answer to the wrong problem |
| **Boundary & cluster** | match the paper; PBC for momentum-resolved data and level statistics | problem-driven *(Q3.1–3.2)*: 2D cluster choice fixes aspect ratio, allowed momenta, point group — it is part of the physics, not a numerical detail. Twisted BC add momentum resolution (more k-points) at the cost of complex H *(Q9.3)* |
| **Solver knobs per route** | Lanczos tolerance ~1e-12, iterations until the residual beats the observable tolerance; reorthogonalization **off for the ground state, full/selective for excited states and spectra**; FTLM/TPQ: R = 20–100, M_L = 50–100, more R at low T; KPM: order M sets resolution ≈ bandwidth/M, Jackson kernel; interior: explicit window + filter degree or LU memory budget | ghosts (spurious eigenvalue copies) appear exactly when many eigenpairs are pulled without reorthogonalization; FTLM/TPQ error ∝ 1/√(R·D) — check FTLM ≈ TPQ; interior solves are fragile without an explicit budget |
| **SU(2)** | never block-diagonalize with it — use it as a check *(Q9.2)* | no front-line tool implements non-abelian blocks; compute S(S+1) = ⟨S²⟩ on returned states and check multiplet degeneracies instead |
| **Basis representation** | package basis; custom only for constrained spaces the package cannot express | state→index lookup is the tool's job (hash map usually fastest *(Q4.2)*; Lin tables / sublattice coding at large N); the *method-level* choice is package basis vs `user_basis` vs hand-rolled — decided in step 2 |

> **Confirm the setup with the user before running — one knob per turn, never batched (interaction principles above).** Lead with the two that decide the result: (1) **the sector list** — wrong or incomplete sectors silently change the problem (and make level statistics meaningless); (2) **the route** — dense vs sparse fixes both what you get and what it costs. Then boundary/cluster, then solver knobs.

### Cost & resource estimate

Wall time is **one measured rate × a firm work count**. This card supplies the count; the tool skill measures the rate (one timing probe). All counts are in D — compute D first:

- **Dimension bookkeeping:** full space d^N (2^N spin-½, 4^L Hubbard); fixed Sz: C(N, N↑); Hubbard fixed (N↑,N↓): C(L,N↑)·C(L,N↓); constrained spaces: exact combinatorial count (PXP: Fibonacci/Lucas, ~φ^N); translation ÷ ~N; point group ÷ ~\|G\|.
- **Dense full ED:** memory 8·D² bytes (real; ×2 complex) for the matrix plus eigenvector/workspace of the same order; time ∝ D³. Anchors *(2026 review)*: workstation D ≈ 6×10⁴ in seconds, ≈ 1.5×10⁵ in hours (256–512 GB); fat node + ELPA/ScaLAPACK D ≈ 5×10⁵–10⁶.
- **Lanczos:** memory 2–3 vectors × 8·D bytes (+ all Λ vectors if fully reorthogonalizing); work = Λ × matvec, matvec ≈ z·D. Anchors: workstation/GPU-node D ~ 10⁸–10⁹; distributed frontier D ~ 10¹⁰–10¹² (XDiag N ≈ 50 Heisenberg at D ~ 10¹¹).
- **Dynamics:** (matvecs per Krylov step) × time steps. **FTLM/TPQ:** R × M_L matvecs per sector. **KPM:** M × R matvecs.
- Past D > 2×10⁹, 32-bit index arithmetic silently overflows — 64-bit indices end-to-end *(review tricks list)*.

> **Surface the cost before any scale choice (reproduce-paper step 4).** Plain language: show D for their sectors, the work count for the route, and the single unknown (the matvec or dense-eigh rate, settled by one probe). D is set by the sector bookkeeping — symmetries are the cost lever, not threads.

## Details

Generic methodology; the derivations live in `references/ed-methodology.md` — basis encoding and lookup (§Hilbert-space & basis construction), momentum/parity/spin-flip representatives and phases (§Symmetry adaptation), Lanczos recurrence, ghosts and reorthogonalization, Jacobi-Davidson (§Diagonalization), continued-fraction spectral estimator (§Observables), FTLM/TPQ estimators (§Finite temperature), and the exact validation anchors (§Validation / benchmarks). Paper/model facts live in `/reproduce-paper` and `.knowledge/models/`.

### Notation

- `N`: physical sites or orbitals; `d`: local dimension.
- `D`: dimension of the selected symmetry-reduced block — the scale variable.
- Sector: fixed quantum-number block (Sz / particle number, momentum k, parity p, spin flip z).
- `z`: nonzeros per row of H (≈ terms per site); Λ: Lanczos iterations; R, M_L: FTLM/TPQ random vectors and Krylov depth; M: KPM expansion order.
- Level-spacing ratio: r_n = min(s_n, s_{n−1}) / max(s_n, s_{n−1}); ⟨r⟩ ≈ 0.386 Poisson, ≈ 0.5295 GOE — valid only inside one fully resolved sector.

### Pitfalls

- **Unresolved symmetries** — level statistics from mixed sectors are meaningless; degeneracies and zero-energy subspaces (PXP) must be handled before gap ratios.
- **Basis convention drift** — spin vs Pauli normalization, fermion ordering, site indexing must match `.knowledge/conventions.md` and the model card; a factor-of-2 in couplings is the classic wrong-first-energy.
- **Symmetry-phase bugs** — representative mapping and character phases in projected bases are the most common silent failure; non-Hermiticity is how they surface *(interview Q4.4; review tricks)*.
- **Dense overuse** — building H densely when only extremal states are needed wastes O(D²) memory; matrix-free Lanczos is the default beyond small blocks.
- **Lanczos ghosts** — repeated spurious eigenvalues when pulling many states without reorthogonalization.
- **Interior-state fragility** — shift-invert/filter targets need explicit budgets and residual checks.
- **Degeneracy handling** — near-degenerate eigenvectors are basis-dependent; compare invariant subspaces or projectors.

## Verification — implementation stage

### Intermediate (mid-run)

Print before diagonalizing, in this order *(interview Q5.1)*:

1. **Block dimension vs combinatorics** — the first printout; **stop on mismatch** *(Q6.2)*. For constrained bases, against the exact count (Fibonacci/Lucas for PXP).
2. **Hermiticity error** — surfaces symmetry-projection and phase bugs before they cost a run.
3. **Memory vs estimate** — **stop if far above** the D-based estimate *(Q6.2)*.
4. Healthy-run signals *(Q6.1)*: stable per-iteration matvec time, monotone residual decay, expected degeneracy pattern.

### Final verification + expert criticism

- **Residual** ‖H·ψ − E·ψ‖ for every reported eigenpair; **symmetry expectation values** of all imposed quantum numbers on returned states.
- **Anchors**: free/zero-coupling limit against the single-particle solution *(Q5.3)*; exact small-system values (2-site Heisenberg −3J/4; Sandvik N = 16 table; Bethe ansatz) and `.knowledge/limits.md`.
- **Benchmark against an independent value — always** *(Q8.2)*. The expert failure mode *(Q6.3)*: a run that converges cleanly on the **wrong matrix** — every solver diagnostic passes because H itself is wrong. Only an external benchmark catches it.
- **Dense/sparse cross-check** on a smaller block; **SU(2) multiplet check** where applicable; **sum rules** for spectral functions (∫A(ω)dω = ‖A|ψ₀⟩‖²) and η→0 stability; **FTLM ≈ TPQ** within error bars for finite-T.
- **Level statistics** only within one fully resolved sector, degeneracies removed.

> **Criticize:** level statistics over mixed or partially resolved sectors; a converged Lanczos trusted without an external benchmark (wrong-matrix failure); excited states or spectra pulled without reorthogonalization (ghosts counted as physics); a constrained-basis dimension never checked against the exact count (constraint silently wrong); the zero-energy degenerate subspace left inside PXP gap ratios; thermodynamic-limit claims from one cluster with no size series; SU(2) "imposed" by assumption instead of checked via ⟨S²⟩.

## Citations

- `.knowledge/literature/ed/1101.3281_computational-studies-of-quantum-spin-systems.md` — Sandvik: spin basis, momentum/parity/spin-flip bases, Lanczos, finite-T sums; the N = 16 anchor table.
- `.knowledge/literature/ed/10-1007-978-3-540-74686-7-18.md` — Weiße & Fehske: fermion/Hubbard basis, translation symmetry, Lanczos, Jacobi-Davidson.
- `.knowledge/literature/ed/2505.02901_xdiag-exact-diagonalization-for-quantum-many-body-systems.md` — XDiag: sublattice coding, Lin tables, spectral functions, TPQ/FTLM vocabulary.
- `.knowledge/literature/ed/1610.03042_quspin-a-python-package-for-dynamics-and-exact-diagonalisati.md` — QuSpin reference.
- Gap-filling estimators (continued fraction: Gagliano–Balseiro 1987, Dagotto RMP 1994; FTLM: Jaklič–Prelovšek 1994; TPQ: Sugiura–Shimizu 2012/2013) — supplied with full formulas in `references/ed-methodology.md`.

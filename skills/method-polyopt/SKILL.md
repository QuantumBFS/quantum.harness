---
name: method-polyopt
description: Use when a noncommutative polynomial optimization reproduction needs method-level route and tool selection — certified lower bounds on ground-state energy via the moment-SOS / SOHS (NPA-style) hierarchy solved as a semidefinite program, Bell-inequality maximum quantum violation, or state-polynomial / tracial optimization. Triggers include polynomial optimization, SOS / SOHS relaxation, moment-SOS hierarchy, NPA hierarchy, certified energy lower bound, Bell inequality, semidefinite relaxation, NCTSSoS.
---

# Method PolyOpt

## Overview

PolyOpt turns a hard optimization over quantum operators into a **semidefinite program (SDP) whose optimum is a provable bound** on the true answer.

- **What it does.** Minimizing a polynomial in noncommuting operator variables — a Hamiltonian H over all states, a Bell expression, a state/trace polynomial — is intractable directly. Relax it: replace the operators by their **moments** (expectation values ⟨w⟩ of operator words w) and demand the **moment matrix** (the matrix whose entries are those moments) be **positive semidefinite (PSD)** — the consistency condition any genuine quantum state's moments satisfy. That relaxation is an SDP, and its optimum is a **one-sided certificate** — a *lower* bound on a minimum (or *upper* on a maximum). This is the **moment-SOS / sum-of-Hermitian-squares (SOHS)** hierarchy, also called the **NPA hierarchy**.
- **Target.** A *certified* number: a lower bound E_lb ≤ E₀ on a ground-state energy, the largest value quantum mechanics allows for a Bell expression (its **Tsirelson bound**), or two-sided bounds on an observable's ground-state expectation.
- **What's approximated.** The relaxation is exact only in the limit of infinite **relaxation order d** (half the degree of the moment matrix). At finite d the bound is rigorous but loose; raising d tightens it **monotonically**. Sparsity/symmetry truncations shrink the SDP at a controlled cost.
- **Its unique place in the harness.** Every other method returns an *estimate* — a variational upper bound, a stochastic estimate, a finite-size value. PolyOpt returns a **rigorous lower bound**. That makes it the rigorous half of a cross-check, not a competitor to DMRG / QMC / VMC.

**Four problem types** — operator optimization, Bell inequality, state-polynomial optimization, property certification — and one decides the whole formulation. Step 1 classifies them (with the trade-offs); step 3 formulates.

> **When this card is invoked, before any choice, orient the user with this table, filling the right column with *their* actual problem — objective, operators, target. If those aren't fixed yet, use the table to elicit them.**

| Ingredient | What it is | Your setup |
|---|---|---|
| Objective | what to bound — a Hamiltonian to minimize, a Bell expression to maximize, a state/trace polynomial | *(user's objective)* |
| Operators | the operator variables and their algebra (Pauli, fermionic, bosonic, dichotomic = ±1-valued, projector, free) | *(operators + algebra)* |
| Constraints | the operators' algebraic relations + any extra equality / inequality constraints | *(constraints, if any)* |
| Relaxation order d | the SDP size and the single tightening knob; the bound is monotone in d | *(target order / order series)* |
| Target | a certified bound, a Bell maximum, or GNS-reconstructed operators | *(which, and whether GNS is needed)* |
| What's approximated | finite relaxation order (+ sparsity / symmetry truncation) | *(order-convergence plan)* |

> **Interaction principles — all user-facing surfacing in this card.** Plain language, no jargon: define every term and symbol before first use. No walls of words — a few sentences or one compact table per turn. One decision at a time, recommendation-first with one-line pros/cons. Precise and concise; let the user feel each choice, never a silent default.

## Sources

- Tool skills (step-2 targets): `/using-qmbcertify` — the structured certifier for 1D/2D (J1-J2) Heisenberg models (Mosek); `/using-nctssos` — the general NC-polyopt engine for any algebra / Bell / state-polynomial (Clarabel/Mosek).
- Primary literature (rendered in `.knowledge/literature/polynomial-optimization/`; each carries its source URL in the frontmatter):
  - **2604.01555** — Wang, Jansen, Frérot, Renou, Magron, Acín (2026) — *structured* NPA certification scaling to 16×16 lattices; the current state of the art.
  - **2310.05844** — Wang et al., PRX 14, 031006 (2024) — the predecessor that introduced structure-exploiting SDP relaxations and observable bounds (the "SDP Old" baseline).
  - **10.1007/978-3-319-33338-0** — Burgdorf, Klep, Povh, *Optimization of Polynomials in Non-Commuting Variables* (Springer, 2016) — the foundational monograph on the eigenvalue/trace moment-SOHS hierarchy.
- The modeling craft in this card (problem-type classification, algebra selection, formulation, sparsity, GNS) is **distilled from the `polyopt-guide` skill** (`exAClior/easy-nctssos`, authored by the NCTSSoS maintainers) — absorbed here rather than referenced, so method and software stay decoupled.

## Select method — step 1

### Suited for
- A **certified lower bound** on a ground-state energy, the **maximum quantum violation** of a Bell inequality, or **two-sided bounds** on a ground-state observable — for small-to-moderate operator counts where the SDP is affordable.
- Best when you need *rigor*, not the state: PolyOpt brackets E₀ from below to complement a variational upper bound.

### Worked examples — demonstrated reach

Anchor the user's problem to the nearest row and quote its scale as a concrete reference point. These are capability anchors from the literature (Sources), not reproduction mandates.

| Ref | Problem | Type | Scale reached | Certified |
|---|---|---|---|---|
| 2604.01555 | square-lattice Heisenberg energy | operator min | up to 16×16 (256 spins), structured SDP | E/spin lower bound, sub-percent gap vs QMC |
| 2604.01555 | J1-J2 Heisenberg chain, energy + correlations | operator + observable | N = 40 | E/spin, spin correlations, structure factor S(π,π) — two-sided |
| 2310.05844 | ground-state property bounds | operator + observable | moderate lattices | energy + observable bounds (the predecessor hierarchy) |
| Burgdorf-Klep-Povh | eigenvalue / trace optimization | operator / tracial | foundational | the moment-SOHS hierarchy itself |
| NPA (0803.4290) | CHSH / I3322 Bell violation | Bell (dichotomic) | few operators | Tsirelson bound (2√2 for CHSH) |

### Route elsewhere — when PolyOpt isn't the right tool

| Target | Better tool | Why |
|---|---|---|
| The ground *state* (wavefunction, correlations, order parameters) | DMRG `/method-mps`, VMC `/method-vmc`, QMC `/method-qmc` | PolyOpt returns a bound + moment data, not the state (GNS reconstructs *a* realizing state, not the lattice ground state). |
| Large lattices, thermodynamic limit | DMRG / QMC / PEPS | SDP cost grows ~O(n^d) in operator count; without heavy structure it does not scale. |
| Full spectrum, dynamics, finite-T thermodynamics | ED `/method-ed`, MPS `/method-mps`, LTRG `/method-ltrg` | the hierarchy targets the extremal eigenvalue, not the spectrum or temperature. |

> **When the goal falls outside PolyOpt:** recognize it before any setup; explain *what fits better and why* in a short what/why table; stay warm — guide, don't dismiss.

### Options & trade-offs — the four problem types

| Type | Objective looks like | Formulation note |
|---|---|---|
| **Operator optimization** | minimize H = Σ couplings × operator words | the common case; SDP gives a lower bound on the minimum eigenvalue |
| **Bell inequality** | maximize a Bell expression B | maximize B = minimize −B; the operator-vs-tracial grouping is the key modeling choice |
| **State-polynomial** | products of expectations, ⟨A⟩⟨B⟩, tr(AB)−tr(A)tr(B) | needs the state-polynomial formulation (tr(·)/s(·) wrappers); the trickiest setup |
| **Property certification** | does quantity Q satisfy a bound? | a feasibility problem — add Q as a constraint |

### Certification role — the verification ladder

PolyOpt's output is a one-sided certificate; use it as such:
- A converged variational energy E_var is an **upper** bound; the SDP gives a **lower** bound E_lb ≤ E₀ ≤ E_var. A small gap certifies both. Compose with `/cross-method-check`.
- Tightness signal: the **flat-extension / flatness test** — when the moment matrix is flat, the bound is (numerically) exact and GNS reconstruction is reliable.
- Convergence knob: the bound is monotone in relaxation order. Report **bound-vs-order**, not a single number.

## Select software — step 2

**Routing rule: a 1D/2D (J1-J2) Heisenberg model where you want maximum scale → `/using-qmbcertify`; everything else → `/using-nctssos`.** The choice turns on whether the structured certifier already specializes for the model.

| | `/using-qmbcertify` | `/using-nctssos` |
|---|---|---|
| **Use when** | the problem is a **1D/2D (J1-J2) Heisenberg** model and you want the tightest certified bound at large size | **any other** NC-polyopt problem — other algebras, custom Hamiltonians, Bell, state-/trace-polynomials |
| **How it scales** | hard-codes the model's symmetries plus reduced-density-matrix (RDM) and state-optimality constraints (see Details) → block-diagonalizes the SDP by many orders of magnitude (reaches 16×16) | generic correlative + term sparsity; scales to local Hamiltonians of moderate size |
| **Solver** | Mosek only (free academic license) | Clarabel (open-source) or Mosek |
| **Returns** | an **exact** (rationally rounded) certified bound | a numeric SDP bound + moment data + GNS |

> **Surface the software choice to the user** as a short what/why table: which engine, why it fits (the deciding fact is whether the structured symmetries apply — they are what let QMBCertify reach 16×16 where the general solver cannot), and the one consequence (Mosek license for QMBCertify vs open-source Clarabel for NCTSSoS). Let the user feel the choice even when one engine is the obvious fit.

**Handoff.** Once the engine is fixed, invoke `/using-qmbcertify` or `/using-nctssos` — it owns install/run, the package's run knobs (step 3 software side), and the cost estimate. This card owns the modeling (below): algebra, objective, relaxation strategy.

## Method setup — step 3

The modeling decisions this card owns, distilled into knobs. Software-side values (solver backend, API knob names) live in the using-card.

| Knob | What to decide | Effect & default |
|---|---|---|
| **Problem type** | operator / Bell / state-poly / certification (step 1) | sets the whole formulation; most reproductions are operator optimization |
| **Algebra** | which operator algebra the variables obey (table below) | the most important modeling choice — a richer algebra encodes more relations → a tighter bound at the same order |
| **Objective & constraints** | the Hamiltonian/Bell/state polynomial + any extra equality/inequality constraints | min vs max: the SDP minimizes — maximize f by minimizing −f and negating; add constraints to strengthen (e.g. RDM positivity) |
| **Relaxation order d** | the single tightening knob | bound monotone in d; cost ~n^d. Start d=2; raise for a tighter bound, or higher when GNS reconstruction is needed |
| **Sparsity / structure** | which reductions to exploit | correlative (variable cliques) + term (monomial blocks) for any local problem; for Heisenberg, the structured symmetries + RDM positivity (these are what `/using-qmbcertify` automates) |
| **GNS reconstruction** | only if you need concrete realizing operators, not just the bound | needs higher order; reliable when the moment matrix is flat |

**Algebra — pick by the operators' physics (the relations it auto-enforces give the tighter bound):**

| Operators in the problem | Algebra | Relations enforced | Note |
|---|---|---|---|
| Pauli sx, sy, sz on spin-½ sites | **Pauli** | s²=I + product rules sx·sy=i·sz | tightest for spins; the product rules beat bare Unipotent at the same order |
| fermionic creation/annihilation | **Fermionic (CAR)** | {aᵢ,aⱼ†}=δᵢⱼ, {aᵢ,aⱼ}=0 | Hubbard, t-J, free fermions |
| bosonic creation/annihilation | **Bosonic (CCR)** | [aᵢ,aⱼ†]=δᵢⱼ | ∞-dim Hilbert space; GNS gives finite approximations |
| ±1 measurement observables | **Unipotent** | U²=I only | abstract Bell observables, not physical spins |
| projective measurements | **Projector** | P²=P | I3322, measurement compatibility |
| no special relations | **free NonCommutative** | none | add custom constraints by hand |

> **Confirm the setup with the user before running — one knob per turn, never batched (interaction principles above).**
> 1. **Orient once.** One plain-language hook: *"We rewrite your minimization as a positivity (SDP) problem whose answer is a guaranteed lower bound on the true energy; raising one knob (the relaxation order) tightens the guarantee."* Tie each knob to its role.
> 2. **Then loop, leading with the two that decide the result:** (1) **algebra** — the richer the encoded relations, the tighter the bound; (2) **relaxation order d** — the monotone tightening knob, traded against cost ~n^d. Then objective/constraints, sparsity/structure, and GNS only if reconstruction is wanted.
> 3. Recommended option first (labeled when there's a technical reason — e.g. the paper's value when reproducing), one-line why, 1–2 alternatives with one-line pro/con. **Ask one question, then STOP and wait** before the next knob.
> 4. Capture the agreed choices (algebra, order, sparsity/structure, drafted objective/constraints, solver) as `run.json` `params` rows (`name`, `value`, `source`, `why`, `risk`, `fix`) **before** the run, so the proposal-first report is faithful. Then hand env + execution to the chosen using-card.

### Cost & resource estimate — feeds step 4

Estimate before the first run (AGENTS.md: decide compute before running). **The SDP size, not the algebra, sets the cost.**

- The moment matrix at order d is indexed by operator words up to degree d; for n operators its dimension grows ~n^d (dense). Interior-point SDP cost scales steeply in that dimension — **memory is the usual first wall**.
- **Sparsity** (correlative cliques + term blocks) and, for Heisenberg, the **structured symmetry block-diagonalization** are the difference between feasible and not: in the structured case the binding cost is the *largest residual block*, which the reductions can drive down by many orders of magnitude (the state of the art reaches 16×16 lattices on a workstation).
- Practical reads: small operator counts at order 2 solve in seconds–minutes locally; order 3+ (needed for GNS) or n past a few dozen without structure is cluster territory. Probe at low order, read the reported block sizes, then decide local vs `/using-slurm`.

> **Surface the cost to the user before any scale choice (reproduce-paper step 4).** Plain language: cost is set by the SDP block size, which the relaxation order and the system size drive up and which sparsity/symmetry drive back down; show the per-size reality (small problems on a laptop; large structured lattices on a workstation/cluster) and let the user feel that picking the order and size sets the cost.

## Details

Generic methodology; paper/model facts live in `/reproduce-paper` and `.knowledge/models/`. Math is unicode/plain.

### The idea
A minimization min_state ⟨H⟩ is hard because the set of valid quantum states is hard to describe. Replace the state by a **linear functional ℓ on operator words** (the moments ⟨w⟩) that need only satisfy necessary conditions: ℓ(1)=1, ℓ is positive on Hermitian squares (the moment matrix M with Mᵤᵥ = ℓ(u⋆v) is PSD), and ℓ respects the algebra's relations. Minimizing ℓ(H) over all such ℓ is an SDP, and because every true state gives a valid ℓ, its optimum **lower-bounds** the true minimum. Restricting words to degree ≤ d gives the order-d relaxation; larger d adds constraints and tightens the bound monotonically. Dually, a feasible point is a **sum-of-Hermitian-squares** decomposition certifying H − E_lb ⪰ 0.

### Structured reductions (why it scales)
The general hierarchy blows up; exploiting the problem's structure is what makes large systems feasible:
- **Sparsity.** *Correlative sparsity* groups variables into cliques by which co-appear in a term (each clique → a smaller moment matrix); *term sparsity* finds block structure from which monomials actually appear. Both shrink the SDP for any local Hamiltonian. **Caveat: stabilization ≠ exactness** — the term-sparsity graph can stop growing while the bound stays strictly loose; raise the order or go dense to gauge the gap.
- **Symmetries (Heisenberg-specific, automated in `/using-qmbcertify`).** Sign, conjugate, permutation, dihedral, and (in 2D) translation symmetry **block-diagonalize** the SDP — taking the max block size from ~10⁹ down to ~10¹ in the demonstrated 1D case.
- **Strengthenings.** *Reduced-density-matrix positivity* (PSD constraints on k-body RDMs, block-diagonal by U(1) magnetization) and *state-optimality conditions* add valid constraints that tighten the bound without raising the order.

### Notation
- **Moment ℓ(w) = ⟨w⟩** — expectation of operator word w; the SDP variables.
- **Relaxation order d** — half-degree of the moment matrix; the single tightening knob, bound monotone in d.
- **Moment-SOS / SOHS (NPA) hierarchy** — the moment relaxation and its sum-of-Hermitian-squares dual.
- **CS / TS** — correlative / term sparsity. **GNS** — reconstruct concrete operators/state realizing the optimum (needs higher order). **Flatness** — a rank condition on the moment matrix certifying the bound is exact.

### Pitfalls
- **It is a bound, not the state.** Don't read lattice correlations off GNS as the ground state's; GNS gives *a* realizing representation.
- **Loose at low order is not a bug.** Raise the order, enrich the algebra (Pauli product rules beat bare Unipotent), or add structural constraints (RDM positivity).
- **min vs max.** The SDP minimizes; maximize f by minimizing −f and negating.
- **Solver status.** Trust the bound only on a clean solve status; a stalled/infeasible SDP is not a bound.
- **Pauli needs complex coefficients.** Products like sx·sy=i·sz generate imaginary terms, so the objective is built over the complex numbers.

### Verification

**Intermediate (mid-run) — partial confirmation while solving.** Watch three signals:
- **Solver status & residual** — a clean optimal status with shrinking primal/dual residuals. A stalled or iteration-limited solve is *not yet a bound*.
- **Bound monotone across orders** — raising the order should make the bound tighten (increase, for a lower bound). A drop signals a setup or solver-status problem, not physics.
- **Flatness trend** — the moment matrix moving toward flat means the bound is approaching exact (and GNS will be reliable).

**Final.**
- **Cross-method bracket** — PolyOpt lower bound vs an independent variational upper bound (the primary check; `/cross-method-check`).
- **Flatness** — flatness test true ⇒ bound numerically exact.
- **Limits** — trivial-parameter and small-N analytic checks via `.knowledge/limits.md`.

> **Criticize:** trusting a bound from a stalled/infeasible solve; reporting a single order instead of bound-vs-order; treating a sparsity-stabilized bound as exact (stabilization ≠ exactness); reading GNS moments as the lattice ground state; a sign error in min-vs-max; a too-loose algebra (Unipotent where Pauli's product rules apply).

## Citations

Rendered under `.knowledge/literature/polynomial-optimization/` (see Sources):
- `2604.01555_…md` — Wang et al. (2026) — structured NPA certification to 16×16 lattices; the source for the structured reductions (symmetries, RDM positivity, state optimality).
- `2310.05844_…md` — Wang et al., PRX 14, 031006 (2024) — the predecessor structure-exploiting hierarchy with observable bounds.
- `10-1007-978-3-319-33338-0.md` — Burgdorf, Klep, Povh (2016) — the foundational moment-SOHS monograph.
- NPA hierarchy: Navascués, Pironio, Acín, *New J. Phys.* **10**, 073013 (2008), [arXiv:0803.4290](https://arxiv.org/abs/0803.4290).
- Modeling craft distilled from the `polyopt-guide` skill (`exAClior/easy-nctssos`).
- Software: `/using-qmbcertify` (QMBCertify.jl + Mosek) and `/using-nctssos` (NCTSSoS.jl + Clarabel/Mosek).

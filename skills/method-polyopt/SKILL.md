---
name: method-polyopt
description: Use when a noncommutative polynomial optimization reproduction needs method-level route and tool selection — certified lower bounds on ground-state energy via the moment-SOS / SOHS (NPA-style) hierarchy solved as a semidefinite program, Bell-inequality maximum quantum violation, or state-polynomial / tracial optimization. Triggers include polynomial optimization, SOS / SOHS relaxation, moment-SOS hierarchy, NPA hierarchy, certified energy lower bound, Bell inequality, semidefinite relaxation, NCTSSoS.
---

# Method PolyOpt

## Overview

PolyOpt turns a hard optimization over quantum operators into a **semidefinite program (SDP) whose optimum is a provable bound** on the true answer.

- **What it does.** Minimizing a polynomial in noncommuting operator variables — a Hamiltonian H over all states, a Bell expression, a polynomial in expectation values — is intractable directly. Relax it: replace the operators by their **moments** (expectation values ⟨w⟩ of operator words w) and require the **moment matrix** (the matrix of those moments) to be **positive semidefinite (PSD)** — a consistency condition every genuine quantum state's moments satisfy. That relaxation is an SDP, and its optimum is a **one-sided certificate**: a *lower* bound on a minimum (an *upper* on a maximum). This is the **moment-SOS / sum-of-Hermitian-squares (SOHS)** hierarchy, also called the **NPA hierarchy**.
- **Target.** A *certified* number: a lower bound E_lb ≤ E₀ on a ground-state energy, the largest value quantum mechanics allows for a Bell expression (its **Tsirelson bound**), or two-sided bounds on a ground-state observable.
- **What's approximated — two layers.** (1) *The relaxation:* with a finite **basis** of operator words the bound is loose; enlarging the basis (longer words, higher order) tightens it **monotonically**. (2) *The numerics:* the solver returns the bound to finite precision — the digits you may claim are capped by its **residuals** (how exactly the returned solution satisfies the SDP), not by the printed decimals; a claim beyond that needs exact rational post-processing (arXiv:2512.17713: floating-point "bounds" can — and often do — exceed the true optimum).
- **Its place in the harness.** Every other method returns an *estimate* — a variational upper bound, a stochastic mean, a finite-size value. PolyOpt returns a **rigorous lower bound**: the rigorous half of a bracket E_lb ≤ E₀ ≤ E_var, a partner to DMRG / QMC / VMC rather than a competitor. For observable certification it even *consumes* a variational upper bound as input (step 1).

**Four problem types** — operator optimization, Bell inequality, state-polynomial optimization, observable certification — and which one it is fixes the whole formulation. Step 1 classifies; step 3 formulates.

> **When this card is invoked, before any choice, orient the user with this table, filling the right column with *their* actual problem — objective, operators, target. If those aren't fixed yet, use the table to elicit them.**

| Ingredient | What it is | Your setup |
|---|---|---|
| Objective | what to bound — a Hamiltonian to minimize, a Bell expression to maximize, a polynomial in expectations, an observable to certify | *(user's objective)* |
| Operators | the operator variables and their algebra (Pauli, fermionic, bosonic, dichotomic = ±1-valued, projector, free) | *(operators + algebra)* |
| Constraints | the algebra's relations + any extra equality / inequality constraints (for observable certification: the energy window) | *(constraints, if any)* |
| Basis & order | which operator words enter the moment matrix — the accuracy/cost dial (order d = max word length) | *(basis plan / order series)* |
| Target | a certified bound, a Bell maximum, or concrete operators rebuilt from the solution (GNS reconstruction) | *(which, and whether GNS is needed)* |
| What's approximated | finite basis/order + solver precision (digits = residuals) | *(tightening plan)* |

> **Interaction principles — all user-facing surfacing in this card.** Plain language, no jargon: define every term and symbol before first use. No walls of words — a few sentences or one compact table per turn. One decision at a time, recommendation-first with one-line pros/cons. Precise and concise; let the user feel each choice, never a silent default.

## Sources

- **Methodology reference** (reproduction-grade algorithm, parameters, validation, gap analysis): `references/polyopt-methodology.md`
- Tool skills (step-2 targets): `/using-qmbcertify` — the structured certifier for 1D/2D (J1-J2) Heisenberg models (Mosek); `/using-nctssos` — the general NC-polyopt engine for any algebra / Bell / state-polynomial (Clarabel/Mosek).
- Primary literature (rendered in `.knowledge/literature/polynomial-optimization/`; each carries its source URL in the frontmatter):
  - **2604.01555** — Wang, Jansen, Frérot, Renou, Magron, Acín (2026) — *structured* NPA certification scaling to 16×16 lattices; the current state of the art.
  - **2310.05844** — Wang et al., PRX 14, 031006 (2024) — the predecessor that introduced the energy-window observable certification and the structure-exploiting relaxations.
  - **10.1007/978-3-319-33338-0** — Burgdorf, Klep, Povh, *Optimization of Polynomials in Non-Commuting Variables* (Springer, 2016) — the foundational monograph (eigenvalue/trace hierarchy, GNS, flatness, rational certificates).
- Online (pull with `/download-ref` if needed): NPA, *New J. Phys.* **10**, 073013 (2008), arXiv:0803.4290 — the original hierarchy; Naceur, Wang, Magron, Acín, arXiv:2512.17713 — exact rational certification of solver bounds.
- The modeling craft in this card (problem-type classification, algebra selection, formulation, sparsity, GNS) is **distilled from the `polyopt-guide` skill** (`exAClior/easy-nctssos`, authored by the NCTSSoS maintainers) — absorbed here rather than referenced, so method and software stay decoupled.

## Select method — step 1

### Suited for
- A **certified lower bound** on a ground-state energy, the **maximum quantum violation** of a Bell inequality, or **two-sided bounds** on a ground-state observable — wherever *rigor* is the point.
- **Complementary certification, not a replacement**: pair it with a variational/stochastic method and the pair brackets the truth. No sign problem — frustrated spins and fermions are equally admissible.

### Worked examples — demonstrated reach *and its limits*

Anchor the user's problem to the nearest row; quote the scale **and the lesson**. Capability anchors from the literature (Sources), not reproduction mandates.

| Ref | Problem | Scale | Certified result | Lesson |
|---|---|---|---|---|
| 2604.01555 Tab.3 | Heisenberg chain energy | N up to 100 | E/spin within ~2×10⁻⁵ relative of DMRG | near-exact in 1D unfrustrated |
| 2604.01555 Tab.8 | square-lattice Heisenberg energy | up to **16×16 (256 spins)** | 0.7% gap vs QMC | the structured-SDP scale record (32 cores / 1 TB) |
| 2604.01555 Tab.4 | J₁-J₂ chain energy | N=40, J₂ up to 2 | exact at the Majumdar-Ghosh point J₂=0.5; worst 0.7% at J₂=1 | frustration costs accuracy; the MG point is a free end-to-end check |
| 2604.01555 Tab.5-7 | chain correlations, structure factor | N=40, two-sided | 0.01% at short range; up to ~100% deep in frustration | a Hamiltonian-local basis bounds long-range observables loosely |
| 2310.05844 Tab.X; 2604 Tab.9 | 2D long-range order C(L/2,L/2) | L = 4…16 | LRO certified (lower bound > 0) only for L ≤ 8; sign lost by L=16 | finite-size bounds do **not** extrapolate to the thermodynamic limit |
| 2310.05844 Tabs.XIII-XV | 2D J₁-J₂ energy + correlations | L=10 (N=100), frustrated | energy 1-7% above best variational; correlation sign changes certified | certification where no exact method exists — at few-percent looseness |
| NPA / BKP | CHSH; I3322 Bell violation | few operators | CHSH exact (2√2) at low level; I3322 exact value still open | small Bell problems converge fast — but not all close |

### Route elsewhere — when PolyOpt isn't the right tool

| Target | Better tool | Why |
|---|---|---|
| The ground *state* itself (wavefunction, entanglement, fidelities) | DMRG `/method-mps`, VMC `/method-vmc`, QMC `/method-qmc` | PolyOpt returns bounds + moment data, not a state (GNS rebuilds *a* realizing model, not the lattice ground state) |
| Best-possible energies of sign-free models | QMC `/method-qmc`, DMRG `/method-mps` | certified accuracy beyond 1D is ~10⁻³…10⁻² relative — orders looser than those estimates; certify *alongside* them, don't replace them |
| Thermodynamic limit | infinite-size methods (`/method-mps` VUMPS, `/method-peps`, QMC) | finite-size SDP bounds grow looser with size and cannot be extrapolated |
| Full spectrum, dynamics | ED `/method-ed`, MPS `/method-mps` | the hierarchy targets the extremal eigenvalue; no dynamics formulation exists |
| Finite temperature | LTRG `/method-ltrg`, QMC `/method-qmc` | certified finite-T relaxations exist (Fawzi-Fawzi-Scalet 2024) but have no large-scale demonstrations yet |

> **When the goal falls outside PolyOpt:** recognize it before any setup; explain *what fits better and why* in a short what/why table; stay warm — guide, don't dismiss.

### Options & trade-offs — the four problem types

| Type | Objective looks like | Formulation note |
|---|---|---|
| **Operator optimization** | minimize H = Σ couplings × operator words | the common case; SDP gives a lower bound on the minimum eigenvalue |
| **Bell inequality** | maximize a Bell expression B | encode as minimize −B; key choice: party-wise commuting groups (standard) vs tracial |
| **State-polynomial** | products of expectations — ⟨A⟩⟨B⟩, variances | needs the state-polynomial formulation (wrappers in `/using-nctssos`); the trickiest setup |
| **Observable certification** | bound ⟨O⟩ at the ground state | min *and* max ℓ(O) under an **energy window** E_lb ≤ ℓ(H) ≤ E_ub — **E_ub is a variational input** (DMRG/QMC); the certificate inherits its gap |

> **Surface the classification one question per turn — most problems classify at question 1; stop as soon as the type is fixed, and confirm it before any setup.**
>
> | Ask | Answer → type |
> |---|---|
> | 1. What are you bounding? | a Hamiltonian's minimum → operator · a Bell expression's maximum → Bell · a product of expectations → state-polynomial · an observable at the ground state → observable certification |
> | 2. *(only if still unclear)* Are the variables physical operators or abstract ±1 outcomes? | physical → operator / certification · abstract outcomes → Bell |
> | 3. *(only if still unclear)* Is the objective linear in the state? | linear → operator / Bell · products of expectations → state-polynomial |

Two types carry a modeling sub-choice worth surfacing (the using-card expresses it; this card decides it):
- **Bell — operator vs tracial.** *Operator* (recommended, the standard quantum-mechanics choice): each party's measurements in a **separate group**, so different parties' operators commute. *Tracial* (**tracial** = scored by a trace, ⟨·⟩ = tr(·), rather than by a state): one group, transpose trick — it converges to a *different* mathematical value (the von Neumann-algebra optimum); use only to study the tracial relaxation itself.
- **State-polynomial — the wrappers.** When the objective multiplies expectations (⟨A⟩⟨B⟩), wrap operator expressions as `tr(·)` or `s(·)` (**expectation in an arbitrary state**), then assemble the state polynomial. `/using-nctssos` carries the API.

### Certification role — the bracket

PolyOpt's output is one half of a two-sided certificate; plan the other half:
- A variational energy E_var is an **upper** bound; the SDP gives the **lower** bound: E_lb ≤ E₀ ≤ E_var. A small gap certifies both. Compose with `/cross-method-check`.
- **Observable certification needs the variational value as an *input*** (the energy window) — pull it from the paper or plan the variational run first.
- Report **bound-vs-order/basis**, not a single number.

## Select software — step 2

**Routing rule: a 1D/2D (J1-J2) Heisenberg model where you want maximum scale → `/using-qmbcertify`; everything else → `/using-nctssos`.** The choice turns on whether the structured certifier already specializes for the model.

| | `/using-qmbcertify` | `/using-nctssos` |
|---|---|---|
| **Use when** | the problem is a **1D/2D (J1-J2) Heisenberg** model and you want the tightest certified bound at large size | **any other** NC-polyopt problem — other algebras, custom Hamiltonians, Bell, state-/trace-polynomials |
| **How it scales** | hard-codes the model's symmetries plus RDM and state-optimality constraints → block-diagonalizes the SDP by many orders of magnitude (reaches 16×16) | generic correlative + term sparsity, or symmetry (Wedderburn) reduction for group-invariant problems — one lever or the other per run; scales to local Hamiltonians of moderate size |
| **Solver** | Mosek only (free academic license) | Clarabel (open-source) or Mosek |
| **Returns** | a certified numeric bound + Gram-matrix export (**exact rational certification is a separate post-step — packaged for 1D chains only**) | a numeric SDP bound + moment data + GNS |

> **Surface the software choice — four short lines, not a wall:**
> - **What they are:** QMBCertify.jl (the structured certifier) and NCTSSoS.jl (the general engine), both from the NCTSSoS author J. Wang's group.
> - **The deciding fact:** whether the baked-in Heisenberg symmetries apply — they are what reach 16×16 where the general engine cannot.
> - **The one consequence:** QMBCertify hard-requires Mosek (free *academic license*); NCTSSoS defaults to open-source Clarabel.
> - **When reproducing the structured-certification paper, the reassuring fact:** QMBCertify *is* the paper's own published code.
>
> Let the user feel the choice even when one engine is the obvious fit.

**Handoff.** Once the engine is fixed, invoke `/using-qmbcertify` or `/using-nctssos` — it owns install/run, the package's run knobs (step 3 software side), and the cost estimate. This card owns the modeling (below): algebra, objective, basis, relaxation strategy.

## Method setup — step 3

The modeling decisions this card owns. Software-side values (API names, solver settings) live in the using-card. Two kinds of rows: **confirm** = determined by the problem — state it and let the user ratify; **decide** = a genuine choice — recommend, then ask.

| Knob | Kind | Default / how to set | Effect |
|---|---|---|---|
| **Problem type** | confirm | from step 1's classification | fixes the whole formulation |
| **Algebra** | confirm | the most specific algebra the operators obey (table below) | richer relations → smaller basis *and* tighter bound — a free win |
| **Encoding** | confirm | minimize H directly; maximize f as minimize −f; complex coefficients for Pauli; party-wise commuting groups for Bell | a sign or coefficient-type error silently bounds the wrong thing |
| **Monomial basis + range r** | **decide — the expert knob** | words on contiguous sites up to length d, plus two-body words σᵢᵃσᵢ₊ⱼᵇ out to range r as memory allows; re-tailor the words to a non-local target observable | where tightness per cost is won; a Hamiltonian-local basis leaves long-range observables loose |
| **Relaxation order d** | decide | the lowest order containing the objective (usually d=2); climb while the bound still moves and the budget allows | monotone tightening; SDP size grows ~×n per step |
| **Sparsity (CS/TS)** | decide | on for any local Hamiltonian (correlative = variable cliques; term = monomial blocks) | big SDP shrink; **TS stabilization ≠ exactness** — the bound can stay below the dense one |
| **Symmetry** | confirm | exploit every symmetry the model has | exact for symmetric ground states — but restricts to the symmetric sector (beware at degeneracies / critical points) |
| **Strengthenings** | decide | RDM positivity on (k ≈ 8 is the cost/benefit sweet spot); linear state-optimality on; **PSD state-optimality off** — documented solver failures in frustrated regimes | tighten at fixed order, for extra SDP size |
| **Side to solve** | confirm | the dual (SOHS) side — fewer constraints, same optimum | constant-factor speed |
| **Solver & tolerances** | decide | per using-card; trustworthy digits = solver residuals | beyond-residual claims need exact rational post-processing |
| **GNS reconstruction** | decide | off unless explicit operators are needed | needs a flat moment matrix and a higher order |

**Algebra — pick by the operators' physics (the relations it auto-enforces give the tighter bound):**

| Operators in the problem | Algebra | Relations enforced | Note |
|---|---|---|---|
| Pauli sx, sy, sz on spin-½ sites | **Pauli** | s²=I + product rules sx·sy=i·sz | tightest for spins; the product rules beat bare Unipotent at the same order |
| fermionic creation/annihilation | **Fermionic (CAR)** | {aᵢ,aⱼ†}=δᵢⱼ, {aᵢ,aⱼ}=0 | Hubbard, t-J, free fermions |
| bosonic creation/annihilation | **Bosonic (CCR)** | [aᵢ,aⱼ†]=δᵢⱼ | ∞-dim Hilbert space; GNS gives finite approximations |
| ±1 measurement observables | **Unipotent** | U²=I only | abstract Bell observables — *not* physical spins (Pauli there would wrongly fix the dimension) |
| projective measurements | **Projector** | P²=P | I3322, measurement compatibility |
| no special relations | **free NonCommutative** | none | add custom constraints by hand |

> **Confirm the setup with the user before running — one knob per turn, never batched (interaction principles above).**
> 1. **Orient once.** One plain-language hook: *"We rewrite your minimization as a positivity problem whose answer is a guaranteed lower bound on the true energy. The words we put in the moment matrix are the dial: more and longer words = a tighter guarantee, at steeply growing cost."*
> 2. **Confirm, then decide.** Run the *confirm* rows first as statements to ratify — type, algebra, encoding, symmetry — even when they look obvious (a silent sign convention is exactly what the user catches at a glance). Then loop the *decide* rows one per turn, leading with the two that set the result: **basis + range r** and **order d** on the general engine; on the structured route (basis family package-built) **order/range + which strengthenings**.
> 3. Recommended option first (labeled when there's a technical reason — e.g. the paper's value when reproducing), one-line why, 1-2 alternatives with one-line pro/con. **Ask one question, then STOP and wait.**
> 4. Record each agreed choice in the invoking workflow's plan (e.g. `/reproduce-paper`'s parameter rows) **before** the run, so the proposal-first report is faithful. Then hand env + execution to the chosen using-card.

### Cost & resource estimate — feeds step 4

Cost is one measured rate × a firm work count — and for an SDP the firm count is the **post-reduction block inventory**, known *before* solving: assemble the SDP without solving and read the block statistics (the structured route even has closed-form block sizes).

| Axis | Scaling |
|---|---|
| **Compute** | interior-point iterations (~tens) × a per-iteration factorization cost set by the largest PSD blocks and the constraint count. The reductions are the whole game: 1D Heisenberg N=100, d=4 — max block 8.1×10⁹ naive → 3.2×10⁸ after Pauli equalities → 12,001 after sparsity → **31** after symmetry (2604.01555 Tab.2) |
| **Memory** | the usual **first wall** — grows ~quadratically in the constraint count; 128 GB carried N=100 (1D) and L=10 (2D); 16×16 took 1 TB |
| **Wall time** | anchors (Mosek, **single core**, 2310.05844): chain N=40 ≈ 3.3 h, N=100 ≈ 12 h; 2D L=6/8/10 ≈ 1.8 / 9.7 / 21 h — per parameter point |

**Probe protocol:** assemble without solving, read the block statistics, and sanity-check them (a structured Pauli chain at d=4 must *not* show a ~10⁶ dense block — if it does, the reductions didn't fire; abort and fix). Then one low-order solve measures the throughput. Then decide local vs `/using-slurm`.

> **Surface the cost to the user before any scale choice (reproduce-paper step 4).** Plain language: the basis/order and the system size drive the SDP blocks up, sparsity and symmetry drive them back down, and memory — not time — is usually what runs out first. Show the per-size reality (chains in hours on one core; large structured lattices on a fat workstation) and let the user feel that picking basis, order, and size *is* picking the cost.

## Details

Generic methodology; paper/model facts live in `/reproduce-paper` and `.knowledge/models/`. Math is unicode/plain.

### The idea
A minimization min_state ⟨H⟩ is hard because the set of valid quantum states is hard to describe. Replace the state by a **linear functional ℓ on operator words** (the moments ⟨w⟩) that need only satisfy necessary conditions: ℓ(1)=1, ℓ is positive on Hermitian squares (the moment matrix M with Mᵤᵥ = ℓ(u⋆v) is PSD), and ℓ respects the algebra's relations. Minimizing ℓ(H) over all such ℓ is an SDP, and because every true state gives a valid ℓ, its optimum **lower-bounds** the true minimum. Restricting words to a finite basis gives the truncated relaxation; enlarging the basis adds constraints and tightens the bound monotonically. Dually, a feasible point is a **sum-of-Hermitian-squares** decomposition certifying H − E_lb ⪰ 0 — and it is this dual (SOHS) side one actually solves (fewer constraints, same optimum, no duality gap).

### Structured reductions (why it scales)
The general hierarchy blows up; exploiting the problem's structure is what makes large systems feasible:
- **Basis locality.** Words supported on contiguous sites (1D) or compact clusters (2D), plus long-range two-body words out to range r — the hand-crafted core of the published large-N results. The basis is chosen for the *Hamiltonian*; bounding a non-local observable well needs words tailored to *it*.
- **Sparsity.** *Correlative sparsity* groups variables into cliques (each clique → a smaller moment matrix); *term sparsity* finds block structure from the monomials that actually appear. **Caveat: stabilization ≠ exactness** — the term-sparsity iteration can stop growing while the bound stays strictly below the dense-basis bound at the same order.
- **Symmetries (Heisenberg-specific, automated in `/using-qmbcertify`).** Sign, conjugate, permutation, dihedral, and translation symmetry **block-diagonalize** the SDP (translation via circulant/DFT structure; 2D adds a second round). Together with the algebraic equalities and the sparse basis they take the 1D max block from ~10⁹ to ~10¹ (Tab.2 cascade above). Exact for symmetric ground states — with the symmetric-sector caveat (step 3).
- **Strengthenings.** *RDM positivity* (PSD constraints on k-body reduced density matrices, block-diagonal by U(1) magnetization; k ≈ 8 sweet spot) and *state-optimality conditions* (ℓ([H,u]) = 0, plus a PSD variant known to destabilize solvers in frustrated regimes) tighten the bound without enlarging the basis.

### Notation
- **Moment ℓ(w) = ⟨w⟩** — expectation of operator word w; the SDP variables.
- **Relaxation order d** — the max word length in the basis; the ladder the bound climbs monotonically.
- **Moment-SOS / SOHS (NPA) hierarchy** — the moment relaxation and its sum-of-Hermitian-squares dual.
- **CS / TS** — correlative / term sparsity. **GNS** — rebuild concrete operators/state realizing the optimal moments.
- **Flatness** — the moment matrix's rank stops growing as the order rises; certifies the bound is (numerically) exact and GNS is reliable.
- **Residuals** — how exactly the returned solution satisfies the SDP's constraints; they cap the digits a bound claim may carry.

### Pitfalls
- **A solver's "lower bound" can exceed the true optimum** when the returned point is slightly infeasible — even with an OPTIMAL status. Quote digits at the residual level; certify beyond only via rational post-processing.
- **It is a bound, not the state.** Don't read GNS moments as lattice ground-state correlations; GNS gives *a* realizing representation.
- **Observable certificates inherit the variational input.** The energy window's upper side comes from DMRG/QMC; a loose E_ub directly loosens the certified interval.
- **Basis-vs-observable mismatch.** A Hamiltonian-local basis certifies energies tightly while leaving long-range correlators uselessly wide — re-tailor the words per observable.
- **min vs max.** The SDP minimizes; maximize f by minimizing −f and negating.
- **Pauli needs complex coefficients.** sx·sy = i·sz generates imaginary terms; build the objective over ℂ.
- **Too-loose algebra.** Unipotent where Pauli applies wastes tightness; Pauli where Bell's dimension-freeness is the point is *wrong*, not just loose.
- **TS stabilization ≠ exactness**; **no thermodynamic-limit extrapolation** from a finite-size bound series; **symmetric-sector restriction** at degeneracies; **PSD state-optimality can break the solver** in frustrated regimes — drop it and re-run, don't paper over a stalled solve.

## Verification

The run's own output already carries the correctness signals — read them; they're free. Anything that costs extra compute is **opt-in**: only when a result looks wrong, debugging hasn't resolved it, and the user explicitly asks to check. Then propose 2-3 checks from the menu below — what each confirms, its rough cost — and run only what's confirmed (the same opt-in rule the invoking workflow enforces, e.g. `/reproduce-paper`'s implementation stage).

### Intermediate output — free, read on every run
- **Before the solve:** the assembled block statistics vs expectation — if the structure machinery didn't fire (one huge dense block where many small blocks are expected), abort and fix; never pay for a solve that's already wrong.
- **At the solve:** **solver status** — only a clean optimal status is a bound; stalled / slow-progress / iteration-limited = *no certificate*. **Residuals / duality gap** — the digits the bound may claim.
- **After:** the sandwich, E_lb ≤ reference value. And if an order/basis series is already in the plan: the bound must rise monotonically — a *decrease* on enlarging the basis is mathematically impossible and means a modeling bug, not physics.

### Opt-in checks — the user-triggered menu

| Check | Confirms | Rough cost |
|---|---|---|
| Anchor point — Majumdar-Ghosh J₂=0.5 (exact), CHSH 2√2, small-N vs ED | the whole pipeline, end to end | one small solve — cheap |
| Dense vs sparse at low order | the sparse basis isn't hiding looseness | one extra solve |
| Order/basis escalation | how far from converged the bound is | one larger solve — the cost driver |
| Flatness test + GNS round-trip | bound (numerically) exact; extraction meaningful | cheap, on existing moment data |
| Rational certification | the claim survives floating-point doubt | post-processing; frontier claims only |
| Cross-method bracket (`/cross-method-check`) | the bound against an independent upper bound | one independent run |

> **Criticize (expert probes for a challenged result):** trusting a stalled/infeasible solve; quoting printed decimals beyond the residuals; one order with no series; a sign error in min-vs-max; Unipotent where Pauli applies (or Pauli where Bell's dimension-freeness is the point); TS stabilization read as convergence; GNS moments read as the lattice ground state; a long-range observable certified with a Hamiltonian-local basis; "exact certification" claimed without a verified rational rounding.

## Citations

Rendered under `.knowledge/literature/polynomial-optimization/` (see Sources):
- `2604.01555_…md` — Wang et al. (2026) — structured NPA certification to 16×16 lattices; the source for the basis/symmetry reductions, the block-size cascade (Tab.2), and the strengthening caveats (Remarks 3.1, 6.1).
- `2310.05844_…md` — Wang et al., PRX 14, 031006 (2024) — energy-window observable certification; single-core wall-time anchors; RDM k=8 sweet spot.
- `10-1007-978-3-319-33338-0.md` — Burgdorf, Klep, Povh (2016) — the moment-SOHS hierarchy, GNS, flatness, rational certificates.
- NPA hierarchy: Navascués, Pironio, Acín, *New J. Phys.* **10**, 073013 (2008), [arXiv:0803.4290](https://arxiv.org/abs/0803.4290). Exact rational certification: Naceur, Wang, Magron, Acín, [arXiv:2512.17713](https://arxiv.org/abs/2512.17713).
- Modeling craft distilled from the `polyopt-guide` skill (`exAClior/easy-nctssos`).
- Software: `/using-qmbcertify` (QMBCertify.jl + Mosek) and `/using-nctssos` (NCTSSoS.jl + Clarabel/Mosek).

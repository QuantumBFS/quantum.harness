---
name: method-polyopt
description: Use when a noncommutative polynomial optimization reproduction needs method-level route and tool selection — certified lower bounds on ground-state energy via the moment-SOS / SOHS (NPA-style) hierarchy solved as a semidefinite program, Bell-inequality maximum quantum violation, or state-polynomial / tracial optimization. Triggers include polynomial optimization, SOS / SOHS relaxation, moment-SOS hierarchy, NPA hierarchy, certified energy lower bound, Bell inequality, semidefinite relaxation, NCTSSoS.
---

# Method PolyOpt

The certified-bound track. Relax a noncommutative polynomial optimization problem (minimize a Hamiltonian over operators, maximize a Bell expression, optimize a state/trace polynomial) into a semidefinite program whose optimum is a **provable lower bound** on the true minimum — the moment-SOS / SOHS hierarchy. Raising the relaxation order tightens the bound monotonically; correlative and term sparsity make larger systems tractable.

Its place in the harness is unique: every other method returns an *estimate* (variational upper bound, stochastic estimate, finite-size value). PolyOpt returns a *rigorous lower bound*. That makes it the natural rigorous half of a cross-check, not a competitor to DMRG/QMC/VMC.

> **When this card is invoked, before any choice, orient the user with this table, filling the right column with *their* actual problem — objective, operators, target. If those aren't fixed yet, use the table to elicit them. The algebra/variant choice itself is deferred to `/polyopt-guide`; this table only frames the problem at routing altitude.**

| Ingredient | What it is | Your setup |
|---|---|---|
| Objective | what to bound — a Hamiltonian to minimize, a Bell expression to maximize, a state/trace polynomial | *(user's objective)* |
| Operators | the operator variables and their algebra (Pauli, fermionic, bosonic, …) | *(operators; algebra deferred to `/polyopt-guide`)* |
| Constraints | the operators' algebraic relations + any extra equality / inequality constraints | *(constraints, if any)* |
| Relaxation order d | the SDP size and the single tightening knob; the bound is monotone in d | *(target order / order series)* |
| Target | a certified bound, a Bell maximum, or GNS-reconstructed operators | *(which, and whether GNS is needed)* |
| What's approximated | finite relaxation order (+ sparsity truncation) | *(order-convergence plan)* |

> **Interaction principles — all user-facing surfacing in this card.** Plain language, no jargon: define every term and symbol before first use. No walls of words — a few sentences or one compact table per turn. One decision at a time, recommendation-first with one-line pros/cons. Precise and concise; let the user feel each choice, never a silent default.

## Route

1. **Use PolyOpt** when the target is a certified lower bound on a ground-state energy, the maximum quantum violation of a Bell inequality, or a state-/trace-polynomial bound — for small-to-moderate operator counts where the SDP is affordable.
2. **Route elsewhere** when PolyOpt is the wrong tool:

   | Target | Better tool | Why |
   |---|---|---|
   | The ground *state* itself (wavefunction, correlations, order parameters) | DMRG `/method-mps`, VMC `/method-vmc`, QMC `/method-qmc` | PolyOpt returns a bound + moment data, not the state (GNS reconstructs *a* realizing state, not the lattice ground state). |
   | Large lattices, thermodynamic limit | DMRG / QMC / PEPS | SDP cost grows ~O(nᵒʳᵈᵉʳ) in the operator count; it does not scale to large N. |
   | Full spectrum, dynamics, finite-T thermodynamics | ED `/method-ed`, MPS `/method-mps`, LTRG `/method-ltrg` | the hierarchy targets the extremal eigenvalue, not the spectrum or temperature. |

3. **Best paired**, not solo: a PolyOpt lower bound under a variational upper bound *brackets* E₀. Compose with `/cross-method-check`.

## Certification role — verification ladder

PolyOpt's output is a one-sided certificate. Use it as such:

- A converged variational energy E_var is an **upper** bound; the PolyOpt SDP gives a **lower** bound E_lb ≤ E₀ ≤ E_var. A small gap certifies both.
- Tightness signal: the flat-extension / flatness test (`test_flatness`) — when the moment matrix is flat, the bound is (numerically) exact and GNS reconstruction is reliable.
- Convergence knob: the bound is monotone in relaxation order. Report bound-vs-order, not a single number.

## Delegation — polyopt-guide owns the modeling

The modeling craft is **delegated, not re-derived here**. At the modeling step, **explicitly invoke `/polyopt-guide`** (the Skill tool) — the upstream skill from `exAClior/easy-nctssos`, authored by the NCTSSoS maintainers — to drive: problem-type classification, algebra selection, objective/constraint formulation, sparsity configuration, and GNS post-processing.

- **Variant routing is polyopt-guide's job, not this card's.** Operator polyopt vs state-polynomial vs trace/tracial vs Bell is a *modeling* choice, expressed in NCTSSoS by the objective type (`Polynomial` vs `NCStatePolynomial`, `symmetric_canon` vs `cyclic_canon`) through one unified `polyopt` / `cs_nctssos` hierarchy — there is no solver-level algorithm fork to own here. `method-polyopt` routes only at the cross-method altitude (PolyOpt vs ED/DMRG/QMC/VMC).
- **Precedence on conflict (ground truth).** If anything in this card ever contradicts `/polyopt-guide` *within the modeling domain it owns* — variant routing, algebra, formulation, sparsity, relaxation-order craft, GNS — **`/polyopt-guide` wins** and this card defers to it. The harness remains authoritative only on *integration plumbing*: environment/install (via `/using-nctssos`), `run.json`, the reproduce-paper spine, reports, verification, and the local-vs-cluster decision. polyopt-guide wins on *what to compute and how to model it*; the harness wins on *where it runs and how it is recorded*.

## Implementation — control flow

Software is owned by **`/using-nctssos`** (NCTSSoS.jl + Clarabel; `make install nctssos`). Run `/setup-julia` first if Julia is not usable. NCTSSoS.jl is the canonical (and only needed) tool here — actively developed, backed by the Julia community, and a clean fit with the harness's Julia stack and SDP backends.

On the `/reproduce-paper` path, this card slots into the spine as steps 1–3 and keeps the structured workflow:

1. Confirm PolyOpt is the right method (route-elsewhere above) and frame the certification role.
2. **Explicitly invoke `/polyopt-guide`** for the modeling dialogue, inside the run dir. It drafts the script and stops at its own review pause (it never force-runs).
3. Capture polyopt-guide's choices (algebra, relaxation order, sparsity algorithms, solver, drafted objective/constraints) as `run.json` `params` rows (each with `name`, `value`, `source`, `why`, `risk`, `fix`) **before** the run, so the proposal-first report is faithful.
4. Hand env + execution to `/using-nctssos` (which pre-satisfies the env polyopt-guide checks for, then runs the harvested script the harness way — local-vs-cluster decided here).
5. Spine appends results, renders the final report, runs the verification ladder.

Artifacts: drafted script → `tracks/polyopt/solutions/<model>_<brief>.jl`; data + reports → the timestamped run dir under `tracks/polyopt/results/`. For ad-hoc `/solve`, use the lighter `scripts/` + `results/` convention.

## Cost estimate — feeds the resource gate

Estimate before the first run (AGENTS.md: decide compute before running). The SDP size, not the algebra, sets the cost:

- The moment matrix at relaxation order `d` is indexed by monomials up to degree `d`; for `n` operators its dimension grows ~`n^d` (dense). SDP solve cost (interior-point) scales steeply in that dimension — memory is the usual first wall.
- **Correlative sparsity** (clique decomposition) and **term sparsity** (block structure) cut this dramatically when the Hamiltonian is local; they are the difference between feasible and not at n ≳ 10–20.
- Practical reads: small operator counts at order 2 solve in seconds–minutes locally; pushing order to 3+ (needed for GNS) or n past a few dozen without sparsity is where it blows up. Probe at low order, watch the matrix dimension, then decide local vs `/using-slurm`.

## Details

### Notation
- **Relaxation order `d`** — half-degree of the moment matrix; the single tightening knob. Bound is monotone in `d`.
- **Moment-SOS / SOHS hierarchy** — sum-of-Hermitian-squares dual of the moment relaxation; the SDP whose optimum lower-bounds the true minimum.
- **Correlative sparsity (CS)** — decompose variables into cliques. **Term sparsity (TS)** — exploit which monomials actually appear. Both shrink the SDP.
- **GNS reconstruction** — build concrete operators/state realizing the optimum from the converged moment data (needs higher order).
- **Flatness / flat extension** — rank condition on the moment matrix certifying the bound is exact.

### Pitfalls
- **It is a bound, not the state.** Do not read lattice correlations off GNS as if they were the ground state's; GNS gives *a* realizing representation.
- **Loose at low order.** A loose bound is not a bug — raise the order or add the algebraic relations the algebra encodes (e.g. Pauli product rules tighten vs bare unipotent). Defer the algebra choice to `/polyopt-guide`.
- **min vs max.** The SDP minimizes; maximize f by minimizing −f and negating. (polyopt-guide handles this.)
- **Solver status.** Trust the bound only on a clean solve status; a stalled/infeasible SDP is not a bound.

### Verification

**Intermediate (mid-run) — partial confirmation while solving.** Keep it simple; watch three signals:
- **Solver status & residual** — the SDP returns a clean optimal status with primal/dual residuals shrinking. A stalled or iteration-limited solve is *not yet a bound*.
- **Bound monotone across orders** — raising the relaxation order should make the bound increase (tighten). A drop signals a setup or solver-status problem, not physics.
- **Flatness trend** — the moment matrix moving toward flat means the bound is approaching exact (and GNS will be reliable).

**Final.**
- **Cross-method bracket** — PolyOpt lower bound vs an independent variational upper bound (the primary check; `/cross-method-check`).
- **Flatness** — `test_flatness` true ⇒ bound numerically exact.
- **Limits** — trivial-parameter and small-N analytic checks via `.knowledge/limits.md`.

### Citations
- NCTSSoS.jl — J. Wang et al., [github.com/QuantumSOS/NCTSSoS.jl](https://github.com/QuantumSOS/NCTSSoS.jl).
- Navascués, Pironio, Acín, *New J. Phys.* **10**, 073013 (2008) — the NPA hierarchy. [arXiv:0803.4290](https://arxiv.org/abs/0803.4290).
- Wang, Magron, Lasserre, "TSSOS," *SIAM J. Optim.* **31**, 30 (2021) — term sparsity. [arXiv:1912.08899](https://arxiv.org/abs/1912.08899).
- Pironio, Navascués, Acín, *SIAM J. Optim.* **20**, 2157 (2010) — moment problems with NC variables. [arXiv:0903.4368](https://arxiv.org/abs/0903.4368).

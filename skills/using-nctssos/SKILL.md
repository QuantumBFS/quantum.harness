---
name: using-nctssos
description: Use when choosing or running NCTSSoS.jl (with a Clarabel or Mosek SDP backend) for general noncommutative polynomial optimization — the moment-SOS / SOHS hierarchy giving certified bounds, correlative/term sparsity, symmetry reduction (Wedderburn block-diagonalization, Clifford detection), state-polynomial / tracial optimization, GNS reconstruction — or for NCTSSoS setup failures. One of the two step-2 handoff targets from /method-polyopt (the general-purpose engine).
---

# NCTSSoS

Software-stack skill for **NCTSSoS.jl** — the harness's general-purpose noncommutative polynomial optimization (NC polyopt) solver. It owns the **software layer**: install/run mechanics, the package's run knobs (step 3), and the time/cost estimate (feeds step 4). It is one of the two **step-2 handoff targets** from `/method-polyopt`; the other is `/using-qmbcertify` (the structure-exploiting one, specialized to Heisenberg models).

It does **not** own method selection or the modeling craft. Cross-method routing, the certification role, and the *modeling* — problem type, algebra, objective/constraint formulation, sparsity strategy, GNS purpose — live in **`/method-polyopt`**. This card carries the NCTSSoS API surface and the env/run mechanism to *execute* what that skill decides, not the decisions themselves.

> **Am I the right card?** NCTSSoS handles **any NC-polyopt problem** — any algebra (Pauli, fermionic, bosonic, dichotomic, projector, free), any custom Hamiltonian, Bell expressions, state-/trace-polynomials — generically via correlative + term sparsity or symmetry reduction (Clarabel or Mosek backend). For 1D/2D (J1-J2) Heisenberg at large size the structured `/using-qmbcertify` scales further. `/method-polyopt` owns this routing call (step 2); this card executes.

## Sources

- Stack contract: `skills/using-nctssos/stack.toml`
- Method card: `skills/method-polyopt/SKILL.md` (owns algebra / objective / strategy decisions)
- Sibling engine: `/using-qmbcertify` (structured certifier for Heisenberg models)
- Install target: `make install nctssos`
- Smoke test: `julia --project=julia-env -e 'using NCTSSoS, Clarabel'`
- Official docs (verify the current API here): `https://quantumsos.github.io/NCTSSoS.jl/`, repo `https://github.com/QuantumSOS/NCTSSoS.jl`

## What NCTSSoS is — step 2 (the general-purpose handoff target)

- **The library.** NCTSSoS.jl (J. Wang et al., successor to NCTSSOS) — a Julia package for sparse NC polyopt via the structured moment-SOHS hierarchy. Builds an SDP and solves it with a JuMP-compatible backend (Clarabel, open-source; Mosek, faster, academic license). Registered in the Julia General registry at **v0.1.0**; the docs carry an explicit performance caveat for this version ("performance issues — a better version planned"), so weigh absolute timings accordingly.
- **Canonical for** certified lower bounds on operator polynomial minima (ground-state energy), Bell-inequality maxima, and state-/trace-polynomial optimization, with correlative + term sparsity and GNS reconstruction.
- **Algebras** it enforces automatically: Pauli, Fermionic (CAR), Bosonic (CCR), Unipotent, Projector, free NonCommutative. *Which* algebra fits a given problem is `/method-polyopt`'s decision (it is a physics/modeling choice); the constructors that express each are below.
- **Efficiency.** Sparsity — correlative (CS) via `MF`/`MMD` orderings (minimum-fill-in / minimum-degree) and term (TS) via block structure — is the lever that makes larger problems feasible; the SDP solve dominates wall time and memory. For group-invariant problems, symmetry reduction (below) is the alternative lever — the two are mutually exclusive.

## Run mechanics

1. Consult `stack.toml`; run `/setup-julia` first when Julia is not usable, then `make install nctssos`.
2. Take the modeling decisions from `/method-polyopt` (algebra, objective/constraints, relaxation order, sparsity strategy) and express them in the API below — do not re-decide them here.
3. Run the harvested script the harness way: save it to `tracks/polyopt/solutions/` (or `scripts/` for `/solve`), execute, save the bound + diagnostics + plot to the run dir.
4. Use cluster execution (`/using-slurm`) when the relaxation order, operator count, or a scan pushes the SDP past the local threshold (see the cost estimate).

### Canonical run shape

The unified entry point is `polyopt(objective, registry)` → `cs_nctssos(pop, config)`; the variant (operator / state / trace / Bell) is set by how the objective is built — that construction follows `/method-polyopt`'s modeling, not this card's. *(Illustrative; not a fixed model.)*

```julia
using NCTSSoS, Clarabel

# variables + objective follow /method-polyopt's algebra + formulation, e.g.:
registry, (sx, sy, sz) = create_pauli_variables(1:N)
ham = sum(ComplexF64(1/4) * op[i] * op[mod1(i+1, N)] for op in (sx, sy, sz) for i in 1:N)

pop    = polyopt(ham, registry)
config = SolverConfig(optimizer = Clarabel.Optimizer, order = 2, ts_algo = MMD())
result = cs_nctssos(pop, config)

println("certified lower bound: ", result.objective)   # E_lb ≤ E₀
```

### Algebra constructors (API surface)

One constructor per algebra; `/method-polyopt` picks which. Each returns a `registry` plus operator vectors. Separate label groups commute; one shared group does not (the operator-vs-tracial distinction for Bell).

| Algebra | Constructor | Enforces |
|---|---|---|
| Pauli (spin-½) | `create_pauli_variables(1:N)` → `(sx, sy, sz)` | `s²=I`, `sx·sy=i·sz`; **needs `ComplexF64` coefficients** |
| Fermionic (CAR) | `create_fermionic_variables(1:N)` → `(c, cdag)` | `{aᵢ,aⱼ†}=δᵢⱼ`, `{aᵢ,aⱼ}=0` |
| Bosonic (CCR) | `create_bosonic_variables(1:N)` → `(a, adag)` | `[aᵢ,aⱼ†]=δᵢⱼ` (∞-dim; GNS gives finite approximations) |
| Unipotent (±1 observables) | `create_unipotent_variables([("A",1:2),("B",1:2)])` | `U²=I`; no cross-product rules |
| Projector (projective measurements) | `create_projector_variables([("P",1:3),("Q",1:3)])` | `P²=P` |
| Free NonCommutative | `create_noncommutative_variables([("X",1:2)])` | none; pass `ineq_constraints=[...]` for ball/custom relations |

### State-polynomial / tracial objectives

For objectives that multiply expectations (⟨A⟩⟨B⟩, covariances) or score by a trace, build an `NCStatePolynomial` instead of a plain operator polynomial: wrap operator expressions with `tr(·)` (trace / maximally-mixed expectation) or `s(·)` (expectation in an arbitrary state), combine, then pass to the same `cs_nctssos` hierarchy. For Bell, the **operator vs tracial** choice (decided in `/method-polyopt`) is realized by the grouping — separate label groups for the operator formulation (parties commute), one shared group for the tracial relaxation (transpose trick). Verify the exact constructors against the official docs.

### Symmetry reduction (Wedderburn block-diagonalization)

When the problem is invariant under a finite group — signed permutations of operators (Bell party/measurement swaps) or Clifford symmetries of a Pauli Hamiltonian — the moment matrix block-diagonalizes into one smaller PSD block per symmetry sector (computed via SymbolicWedderburn). *Whether* a usable group exists and which generators express it is `/method-polyopt`'s call; this is the API:

```julia
# Manual generators — signed permutations of registry operators:
spec = SymmetrySpec(                       # kwargs: check_invariance=true,
    SignedPermutation(                     #         offblock_check=:randomized|:full|:off
        A[1].word[1] => A[2].word[1],
        A[2].word[1] => A[1].word[1],
        B[2].word[1] => (-1, B[2].word[1])), ...)

# Pauli Hamiltonians — automatic Clifford detection (SympleQ, graph-automorphism based):
spec = sympleq_symmetry_spec(ham)          # misses term-fixing Cliffords — union manually:
spec = SymmetrySpec(spec.clifford_generators..., CliffordSymmetry(:SWAP, 1, 2))

config = SolverConfig(optimizer = ..., symmetry = spec,
                      cs_algo = NoElimination(), ts_algo = NoElimination())  # required
result = cs_nctssos(pop, config)
result.symmetry    # SymmetryReport: group_order, invariant_moment_count, psd_block_sizes
```

**Symmetry and sparsity are mutually exclusive** (current MVP scope):
- **Requires** a dense single-clique relaxation (`NoElimination` for both CS and TS), Monoid/Pauli algebras, real signed-permutation/Clifford actions, and multiplicity-free scalar blocks — anything outside raises `ArgumentError` instead of silently building the wrong relaxation.
- **Blocks** `cs_nctssos_higher` and GNS reconstruction (the reduced `monomap` lacks the dense moments).
- **When to prefer it:** the group is large relative to the moment basis (CHSH: one 5×5 block → three 1×1; 2-site Heisenberg: order-48 group, scalar blocks). Prefer CS/TS for large, weakly symmetric problems.
- **Docs** (under the official docs root): `manual/symmetry_adapted_basis/`, `manual/clifford_symmetry_detection/`; examples `examples/generated/chsh_symmetry/`, `examples/generated/pauli_clifford_symmetry/`. New algebras (e.g. fermionic actions) are developer territory — `manual/extending_symmetry/`.

## Parameters — step 3 (software)

The source for NCTSSoS-specific run knobs unless the paper or `/method-polyopt` fixes a value. The *meaning* and *selection* of algebra, objective variant, and sparsity strategy come from `/method-polyopt`; this is the API surface to express them.

| Knob (`SolverConfig`) | Effect | Starting point |
|---|---|---|
| `order` | Relaxation order — the tightening knob; bound monotone in it; cost grows ~`n^order`. | 2 (standard). 3+ only for tighter bound or GNS. |
| `cs_algo` | Correlative sparsity elimination (`MF`, `MMD`, `MaximalElimination`, `AsIsElimination`, `NoElimination`). | `NoElimination()` for small n; `MF()`/`MMD()` to scale local Hamiltonians. |
| `ts_algo` | Term sparsity ordering (`MMD`, `MF`, `MaximalElimination`, `NoElimination`). | `MMD()` is a good default for local problems. |
| `optimizer` | SDP backend. | `Clarabel.Optimizer` (open-source). Mosek if available and faster is needed. |
| `symmetry` | Wedderburn block-diagonalization from a `SymmetrySpec` of group generators (see above). | Off. Turn on for dense relaxations of group-invariant problems; **requires** `cs_algo = ts_algo = NoElimination()`. |
| GNS knobs (`H_deg`, `hankel_deg`) | Reconstruction degree/dimension. | Only when reconstructing; `H_deg=order`, `hankel_deg=order-1`. |

Iterative refinement: `cs_nctssos_higher(pop, result, config)` re-refines the term-sparsity graph from a prior solve (1–2 steps usually converge). **Stabilization ≠ exactness** — the TS graph can stop gaining edges while the bound stays strictly loose; if so, raise `order` or disable TS to gauge the gap.

### Sparsity debugging

Inspect the SDP without solving — sizes the run and shows whether CS/TS found useful structure:

```julia
sparsity = compute_sparsity(pop, config)
sparsity.corr_sparsity.cliques                  # CS clique decomposition
sparsity.corr_sparsity.clq_mom_mtx_bases        # moment-matrix basis size per clique
sparsity.cliques_term_sparsities                # TS blocks per clique
```

### GNS + flatness API

```julia
# Solve at sufficient order (order ≥ hankel_deg + 1), then reconstruct:
gns = gns_reconstruct(result, H_deg, hankel_deg; atol=1e-6)
gns.matrices    # Dict — concrete operator representations
gns.xi          # distinguished vector |Ω⟩
gns.rank        # quotient Hilbert-space dimension

# Tightness certificate:
flat = test_flatness(gns.hankel_matrix, gns.full_basis, gns.basis; atol=1e-8)
flat.is_flat    # true ⇒ relaxation numerically exact, GNS reliable
```

Correlation functions / order parameters read off the solved moment map (the low-level `moment_result`'s `monomap`; verify against the docs) via `symmetric_canon(NCTSSoS.expval(...))`.

## Caller Contract

The scientific values — model, objective, algebra, target bound, relaxation order, validation target — are caller-supplied (from `/method-polyopt` + the model card). This skill turns agreed values into a runnable NCTSSoS script and executes it the harness way; it does not originate the modeling decisions.

## Time estimate — feeds step 4

- Cost is set by the **SDP size**: the moment matrix dimension ~`n^order` (dense), shrunk by CS/TS. Solve time and memory rise steeply in that dimension; memory is usually the first wall.
- Small operator counts at order 2 solve in seconds–minutes on a laptop; order 3+ or n past a few dozen without sparsity is cluster territory.
- First-run Julia precompilation is setup time, not solve time; report separately.
- Uncertain cases: probe at order 2 with sparsity on, read the moment-matrix sizes from `compute_sparsity`, then extrapolate before committing to a higher order. Feeds `/reproduce-paper`'s step-4 resource confirmation and the local-vs-`/using-slurm` decision.

---

*The modeling concepts behind these knobs (algebra selection, formulation, sparsity strategy, GNS) are documented method-side in `/method-polyopt`, distilled there from the `polyopt-guide` skill (exAClior/easy-nctssos).*

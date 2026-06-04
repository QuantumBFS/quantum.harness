---
name: using-nctssos
description: Use when choosing or running NCTSSoS.jl (with a Clarabel or Mosek SDP backend) for noncommutative polynomial optimization — the moment-SOS / SOHS hierarchy giving certified bounds, correlative/term sparsity, state-polynomial / tracial optimization, GNS reconstruction — or for NCTSSoS setup failures. The step-2 handoff target from /method-polyopt.
---

# NCTSSoS

Software-stack skill for NCTSSoS.jl — the harness's canonical noncommutative polynomial optimization solver. It owns the **software layer**: install/run mechanics, software parameters (step 3), and the time/cost estimate (feeds step 4). It is the **step-2 handoff target** from `/method-polyopt`.

It does **not** own method selection or the modeling craft. Cross-method routing and the certification role live in `/method-polyopt`; the *modeling* — problem type, algebra, formulation, sparsity, GNS — is owned by **`/polyopt-guide`** (reused upstream from `exAClior/easy-nctssos`). This card carries the NCTSSoS API surface and the env/run mechanism to *execute* what those skills decide, not the decisions themselves.

> **Precedence.** On any conflict in the modeling domain (algebra, formulation, sparsity, variant routing, GNS), **`/polyopt-guide` is ground truth** and this card defers. This card is authoritative only on the env/install mechanism and harness execution.

## Sources

- Stack contract: `skills/using-nctssos/stack.toml`
- Method card: `skills/method-polyopt/SKILL.md`
- Modeling brain: `/polyopt-guide` (algebra / sparsity / postprocessing reference files)
- Install target: `make install nctssos`
- Smoke test: `julia --project=julia-env -e 'using NCTSSoS, Clarabel'`
- Official docs (verify the current API here): `https://quantumsos.github.io/NCTSSoS.jl/`, repo `https://github.com/QuantumSOS/NCTSSoS.jl`

## What NCTSSoS is — step 2 (the handoff target)

- **The library.** NCTSSoS.jl (J. Wang et al., successor to NCTSSOS) — a Julia package for sparse noncommutative polynomial optimization via the structured moment-SOHS hierarchy. Builds an SDP and solves it with a JuMP-compatible backend (Clarabel, open-source; Mosek, faster, academic license).
- **Canonical for** certified lower bounds on operator polynomial minima (ground-state energy), Bell-inequality maxima, and state-/trace-polynomial optimization, with correlative + term sparsity and GNS reconstruction.
- **Algebras** it enforces automatically: Pauli, Fermionic (CAR), Bosonic (CCR), Unipotent, Projector, free NonCommutative. Choosing among them is `/polyopt-guide`'s job.
- **Efficiency.** Sparsity (CS via `MF`/`MMD` orderings, TS via block structure) is the lever that makes larger problems feasible; the SDP solve dominates wall time and memory.

## Run mechanics

1. Consult `stack.toml`; run `/setup-julia` first when Julia is not usable, then `make install nctssos`.
2. **Pre-satisfy the env before invoking polyopt-guide.** polyopt-guide checks `Project.toml`/solver availability and adapts; with `make install nctssos` already done, that check is a no-op — its ad-hoc `pkg> add` advice is superseded by the harness env.
3. Run the harvested script the harness way: save it to `tracks/polyopt/solutions/` (or `scripts/` for `/solve`), execute, save the bound + diagnostics + plot to the run dir.
4. Use cluster execution (`/using-slurm`) when the relaxation order, operator count, or a scan pushes the SDP past the local threshold (see the cost estimate).

### Canonical run shape

The unified entry point is `polyopt(objective, registry)` → `cs_nctssos(pop, config)`; the variant (operator / state / trace / Bell) is set by how the objective is built — that construction is `/polyopt-guide`'s output, not this card's.

```julia
using NCTSSoS, Clarabel

# variables + objective are built by /polyopt-guide for the chosen algebra, e.g.:
registry, (sx, sy, sz) = create_pauli_variables(1:N)
ham = sum(ComplexF64(1/4) * op[i] * op[mod1(i+1, N)] for op in (sx, sy, sz) for i in 1:N)

pop    = polyopt(ham, registry)
config = SolverConfig(optimizer = Clarabel.Optimizer, order = 2, ts_algo = MMD())
result = cs_nctssos(pop, config)

println("certified lower bound: ", result.objective)   # E_lb ≤ E₀
```

Higher-order refinement: `cs_nctssos_higher(pop, result, config)`. Tightness: `test_flatness(...)`. GNS: `gns_reconstruct(...)` — all detailed in `/polyopt-guide`'s postprocessing reference.

## Parameters — step 3 (software)

The source for NCTSSoS-specific run knobs unless the paper or `/polyopt-guide` fixes a value. What to pin:

| Knob | Effect | Starting point |
|---|---|---|
| `order` | Relaxation order — the tightening knob; bound monotone in it; cost grows ~`n^order`. | 2 (standard). 3+ only when tighter bound or GNS is needed. |
| `cs_algo` | Correlative sparsity elimination (`MF`, `MMD`, `MaximalElimination`, `NoElimination`). | Off for small n; `MF`/`MMD` to scale local Hamiltonians. |
| `ts_algo` | Term sparsity ordering (`MMD`, …). | `MMD` is a good default for local problems. |
| `optimizer` | SDP backend. | `Clarabel.Optimizer` (open-source). Mosek if available and faster is needed. |
| GNS knobs (`H_deg`, `hankel_deg`) | Reconstruction degree/dimension. | Per `/polyopt-guide` — only when reconstructing. |

The *meaning* and *selection* of algebra, objective variant, and sparsity strategy come from `/polyopt-guide`; this table is just the API surface to express them.

## Caller Contract

The scientific values — model, objective, algebra, target bound, relaxation order, validation target — are caller-supplied (from `/method-polyopt` + `/polyopt-guide` + the model card). This skill turns agreed values into a runnable NCTSSoS script and executes it the harness way; it does not originate the modeling decisions.

## Time estimate — feeds step 4

- Cost is set by the **SDP size**: the moment matrix dimension ~`n^order` (dense), shrunk by CS/TS. Solve time and memory rise steeply in that dimension; memory is usually the first wall.
- Small operator counts at order 2 solve in seconds–minutes on a laptop; order 3+ or n past a few dozen without sparsity is cluster territory.
- First-run Julia precompilation is setup time, not solve time; report separately.
- Uncertain cases: probe at order 2 with sparsity on, read the reported moment-matrix sizes, then extrapolate before committing to a higher order. Feeds `/reproduce-paper`'s step-4 resource confirmation and the local-vs-`/using-slurm` decision.

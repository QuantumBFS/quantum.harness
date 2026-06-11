---
name: using-qmbcertify
description: Use when choosing or running QMBCertify.jl — the dedicated structured-NPA certifier for ground-state properties of 1D/2D (J1-J2) Heisenberg spin models, producing numeric certified lower/upper bounds on energy, correlations, structure factors, and partition functions via a Mosek SDP, with Gram-matrix export feeding an exact rational post-certification step (1D chains) — or for QMBCertify setup failures. One of the two step-2 handoff targets from /method-polyopt (the structure-exploiting one).
---

# QMBCertify

Software-stack skill for **QMBCertify.jl** — a special-purpose certifier that pushes the noncommutative-polynomial-optimization (NC polyopt) hierarchy to large spin lattices by baking in the full algebraic structure of Heisenberg models. It owns the **software layer**: install/run mechanics, the package's run knobs (step 3), and the time/cost estimate (feeds step 4). It is one of the two **step-2 handoff targets** from `/method-polyopt`; the other is `/using-nctssos` (the general engine).

It does **not** own method selection or the modeling craft. Cross-method routing, the certification role, the choice of algebra/objective/observable, and the relaxation strategy live in `/method-polyopt`. This card carries the QMBCertify API surface and the env/run mechanism to *execute* what that skill decides.

> **Am I the right card?** QMBCertify handles **1D/2D (J1-J2) Heisenberg** certified bounds; for any other algebra, Hamiltonian, or Bell / state-polynomial problem the engine is `/using-nctssos`. `/method-polyopt` owns this routing call (step 2) — and the reason it scales (the model's symmetries + RDM positivity + state optimality, detailed there); this card executes.

## Sources

- Stack contract: `skills/using-qmbcertify/stack.toml`
- Method card: `skills/method-polyopt/SKILL.md` (owns algebra / objective / strategy decisions)
- Sibling engine: `/using-nctssos` (general NC-polyopt solver)
- Install target: `make install qmbcertify`
- Smoke test: `julia --project=julia-env -e 'using QMBCertify'`
- Repo + examples (verify the current API here): `https://github.com/wangjie212/QMBCertify` — `examples/` carries runnable templates for every capability below.
- License: **CeCILL-2.1** (GPL-compatible French free-software license; the file is `LICENSE.en`, which is why GitHub's sidebar shows "NOASSERTION"). Not registered in the Julia General registry — install is by repo URL (the make target does this).
- Reference paper (the structured hierarchy this package implements): rendered in `.knowledge/literature/polynomial-optimization/` — see `/method-polyopt` Citations.
- Exact-rounding framework (the post-certification layer, bundled for 1D chains via the framework authors' PR): Naceur, Wang, Magron, Acín, arXiv:2512.17713.

## What QMBCertify is — step 2 (the structure-exploiting handoff target)

- **The library.** QMBCertify.jl (J. Wang) — a Julia package that bounds ground-state properties of quantum many-body systems via the **structured NPA hierarchy**. Its core deliverable is the **numeric SDP bound**: `GSB` builds the structured moment SDP and solves it with **Mosek**; with `Gram=true` it also exports the Gram matrices (the SDP's sum-of-squares certificate blocks).
- **Exact rational certification is a post-processing layer, not the solve.** The rounding pipeline — project the Gram blocks onto the exact SOHS identity in rational arithmetic, then shift the optimum by a rigorous Arblib minimum-eigenvalue enclosure — comes from a separate certification framework (Naceur, Wang, Magron, Acín — arXiv:2512.17713) whose 1D-chain implementation is bundled as `certify_qmb` / `certify_qmb_corr`. Report the SDP optimum as a *numeric* certified bound; call a number *exactly* certified only after that post-step runs cleanly.
- **Scope (honest boundary).** Currently the **1D and 2D (J1-J2) Heisenberg models** only. The symmetry exploitation, monomial bases, and reduced-density-matrix blocks are specialized to these models; it is not a general NC-polyopt solver. The exact-rounding layer is narrower still: `certify_qmb` hard-codes the **1D (J1-J2) Heisenberg chain** — 2D square-lattice runs get the numeric bound + Gram export, with no packaged exact certification.
- **Capabilities** — one runnable template per capability in `examples/`:

  | Capability | Example | Exactness |
  |---|---|---|
  | Energy bounds | `certified_energy.jl` | numeric + 1D exact post-step |
  | Correlation / observable / structure-factor bounds | `certified_corr.jl` (self-contained `certify_qmb_corr` driver) | numeric + 1D exact post-step |
  | Ground-state-property bounds | `ground_state.jl` | numeric |
  | Partition-function bounds | `partition_function.jl` (`PFB`) | numeric only |
  | Reduced-density-matrix positivity blocks | `rdm_block.jl` | numeric |
  | Manual SOHS-identity reconstruction from exported Gram matrices | `certify.jl` | the ground truth for the Gram-export format |
- **Solver.** Mosek 11 (commercial; **free academic license** required) via `MosekTools`/`JuMP`. There is no open-source-solver path — Mosek is a hard dependency. DMRG cross-checks ship through `ITensors`/`ITensorMPS`.
- **Why it scales.** The structured reductions block-diagonalize the SDP by the model's symmetries; the binding cost is the largest residual block (see the cost estimate), not the bare moment-matrix dimension.

## Run mechanics

1. Consult `stack.toml`; run `/setup-julia` first when Julia is not usable, then `make install qmbcertify` (adds QMBCertify + Mosek + ITensors to `julia-env`). Mosek needs a license file (`MOSEKLM_LICENSE_FILE` / `~/mosek/mosek.lic`) — confirm it resolves before the run, or the SDP solve aborts.
2. Take the modeling decisions from `/method-polyopt` (model, couplings, observable, relaxation order, which structural strengthenings to switch on) and express them as the `GSB` call's arguments — do not re-decide them here.
3. Run the harness way: save the script to `tracks/polyopt/solutions/` (or `scripts/` for `/solve`), execute, save the certified bound + diagnostics + plot to the run dir.
4. Use cluster execution (`/using-slurm`) when the lattice size or relaxation order pushes Mosek past the local memory wall (see the cost estimate).

### Canonical run shape

Two steps: `GSB` builds and solves the structured SDP — the **numeric certified bound**, the package's core deliverable — then, **for 1D chains only**, `certify_qmb` post-processes it into an exact rational certificate. *(The Hamiltonian is passed as a support/coefficient list in QMBCertify's normal form — `examples/certified_energy.jl` is the ground truth for the encoding; the snippet below is illustrative, not a fixed model.)*

```julia
using QMBCertify

# Hamiltonian terms (support words + coefficients) and the relaxation order
# come from /method-polyopt; e.g. a J1-J2 Heisenberg setup:
supp = [[1, 4], [1, 7]]          # nearest- + next-nearest-neighbour terms
coe  = [3/4, 3/4 * J2]
N, d = 16, 2                     # system size, relaxation order

# Build + solve the structured SDP (Mosek). pso/lso are ON by default —
# pass 0 explicitly for the lightest run.
opt, data = GSB(supp, coe, N, d;
                lattice="chain", rdm=0, extra=1, pso=0, lso=0,
                three_type=[1,1], Gram=true, QUIET=true)

# Post-process (1D chains only): exact rational certificate from the Gram blocks
result = certify_qmb(data, N, coe[1], opt; tol_gram=1e-15, tol_dft=1e-12, snn=true, J2=J2)

result.newbound   # the exactly certified bound = numeric optimum + rigorous eigenvalue shift
result.oldbound   # the raw (uncertified) Mosek numeric optimum, for comparison
```

> **Master-state caveat (verified 2026-06).** `certify_qmb` on current master throws `UndefVarError: i` — commit `70c9a4f` rewrote its Frobenius-check loops in `src/certification/energy_cert.jl` as `for block in …` while still indexing `G1_blocks_proj[i]`. The pipeline underneath (`round_project_qmb` → `rigorous_min_eig`) is intact: if the bug is still present at run time, fix the two loops locally or call those helpers directly. Smoke-test the post-step before promising an exact bound; on failure, report the numeric bound + exported Gram matrices.

For correlations/observables use `certify_qmb_corr` (`examples/certified_corr.jl`) — a self-contained driver that runs its own `GSB` solves plus a rationalized DMRG reference (`dmrg_heisenberg_rat`). For partition functions use `PFB` (`examples/partition_function.jl`) — numeric bounds, no exact-rounding layer. All detailed in the repo `examples/`.

## Parameters — step 3 (software)

The source for QMBCertify-specific run knobs unless `/method-polyopt` or the paper fixes a value. The *meaning* and *selection* (relaxation strategy, which strengthenings physics needs) come from `/method-polyopt`; this is the API surface to express them.

`GSB` builds and solves the structured SDP — its run knobs (semantics verified against `src/bound_gsp.jl` / `src/basic_function.jl`, master 2026-06):

| Knob (`GSB`) | Effect | Starting point |
|---|---|---|
| `d` | Relaxation order — the monomial-basis degree (the moment matrix reaches degree 2d); the tightening knob, cost grows steeply in it. | per `/method-polyopt`; 2 is standard. |
| `extra` | Long-range reach of the two-site basis words — chain: separations up to `extra+1` sites (the paper's long-range parameter r = extra+1); square: appends `extra` further displacement vectors to the L-dependent two-site family. Degree is set by `d`, not this. | per `/method-polyopt`; `0` = nearest-neighbour only. |
| `lattice` | `"chain"` (1D) or `"square"` (2D); selects the geometry and its symmetry group. | per the model. |
| `rdm` | k-site reduced-density-matrix positivity on k *contiguous* sites (U(1)-block-diagonalised). Only `8`/`9`/`10` are implemented; `false`/`0` = off. | per `/method-polyopt`; `0` is the lightest, examples use 8–10. |
| `pso` | PSD state-optimality blocks; the value caps the *word length* of their localizing basis (`0` = off). **On by default (`3`).** | per `/method-polyopt`; pass `pso=0` explicitly for the lightest run. |
| `lso`, `lol` | Linear state-optimality constraints (⟨[H, m]⟩ = 0 over a generated monomial family m); `lol` (default `L`) caps that family's site range. **On by default (`true`).** | per `/method-polyopt`; pass `lso=0` to disable. |
| `energy`, `correlation` | Switch from energy to **two-sided observable bounds**: pass a known `[lb, ub]` energy bracket as `energy` and set `correlation=true` to bound an observable over near-ground states (`GSB`'s own `J2` kwarg supplies the NNN coefficient in the bracket constraint). | `[]` / `false` (energy mode). |
| `three_type` | Site-gap pattern of the three-site basis words — chain: the two successive gaps (`[1,1]` = an adjacent triple); square: selects one of two fixed displacement families. Active only at `d ≥ 3`. | `[1,1]` default. |
| `SU2_symmetry` | Exploit SU(2) invariance for further reduction. | per the model. |
| `Gram` | Export the Gram (SOHS certificate) matrices — **required** for any exact post-certification (`certify_qmb` or the manual `certify.jl` route). Off by default. | `true` whenever certifying. |

`certify_qmb` post-processes a **1D-chain** solve into an exact rational certificate — it projects the rounded Gram blocks onto the exact SOHS identity in rational arithmetic, then shifts the numeric optimum by a rigorous (Arblib) minimum-eigenvalue enclosure:

| Knob (`certify_qmb`) | Effect | Starting point |
|---|---|---|
| `snn`, `J2` | **Define the certified Hamiltonian** — `snn=true` adds the J2 (next-nearest-neighbour) term, so the certificate is verified against the J1-J2 model. **Match these to the model you actually solved**, or you certify the wrong Hamiltonian. | per the model (`snn=true`, `J2` for J1-J2; `snn=false` for plain Heisenberg). |
| `tol_gram`, `tol_dft` | Tolerances for the Gram / discrete-Fourier rounding to rationals. | `1e-15` / `1e-12` (the example's values; the function's own defaults are `1e-12` / `1e-20`). |
| `eig_prec` | Eigenvalue precision (Arblib bits) for the rigorous PSD enclosure that produces the shift. | `256` default; raise if rounding fails. |

## Caller Contract

The scientific values — model, couplings, observable, relaxation order, which structural strengthenings to enable, validation target — are caller-supplied (from `/method-polyopt` + the model/physics cards). This skill turns agreed values into a runnable QMBCertify script and executes it the harness way; it does not originate the modeling decisions.

## Time estimate — feeds step 4

- Cost is set by the **largest residual SDP block** after the symmetry / sparsity / RDM reductions, not the bare moment-matrix dimension — the whole point of the package is that this residual is small even at large lattices. Mosek interior-point time and memory rise steeply in that residual block size.
- The binding resource is **memory** (Mosek factorizations); the reference results used a 32-core / 1 TB workstation, with `MOSEK 11` as the solver.
- Higher `d`, larger `extra`, `rdm`, and the `pso` / `lso` strengthenings (on by default) each enlarge the SDP — probe at `d=2` with the strengthenings off (`rdm=0, pso=0, lso=0`), read the reported block sizes, then decide what to enable and whether to go local or `/using-slurm`.
- First-run Julia precompilation (QMBCertify + Mosek + ITensors) is setup time, not solve time; report it separately. Feeds `/reproduce-paper`'s step-4 resource confirmation and the local-vs-cluster decision.

---

*The modeling concepts behind these knobs (the structured NPA hierarchy, the five symmetries, RDM positivity, state optimality) are documented method-side in `/method-polyopt`, distilled there from the `polyopt-guide` skill (exAClior/easy-nctssos) and the package's reference paper.*

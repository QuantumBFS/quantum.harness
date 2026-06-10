---
name: using-qmbcertify
description: Use when choosing or running QMBCertify.jl — the dedicated structured-NPA certifier for ground-state properties of 1D/2D (J1-J2) Heisenberg spin models, producing exact (rationally rounded) certified lower/upper bounds on energy, correlations, structure factors, and partition functions via a Mosek SDP — or for QMBCertify setup failures. One of the two step-2 handoff targets from /method-polyopt (the structure-exploiting one).
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
- Reference paper (the structured hierarchy this package implements): rendered in `.knowledge/literature/polynomial-optimization/` — see `/method-polyopt` Citations.

## What QMBCertify is — step 2 (the structure-exploiting handoff target)

- **The library.** QMBCertify.jl (J. Wang) — a Julia package that certifies ground-state properties of quantum many-body systems via the **structured NPA hierarchy**. It builds the moment SDP, solves it with **Mosek**, then *rounds the floating-point Gram matrices (the SDP's sum-of-squares certificate matrices) to an exact, provably PSD rational certificate* — so the reported bound is rigorous, not merely numerical.
- **Scope (honest boundary).** Currently the **1D and 2D (J1-J2) Heisenberg models** only. The symmetry exploitation, monomial bases, and reduced-density-matrix blocks are specialized to these models; it is not a general NC-polyopt solver.
- **Capabilities** (see `examples/`): certified **energy** bounds (`certified_energy.jl`), certified **correlation / observable / structure-factor** bounds (`certified_corr.jl`), **ground-state-property** bounds (`ground_state.jl`), **partition-function** bounds (`partition_function.jl`, via `PFB`), and **reduced-density-matrix positivity** blocks (`rdm_block.jl`).
- **Solver.** Mosek 11 (commercial; **free academic license** required) via `MosekTools`/`JuMP`. There is no open-source-solver path — Mosek is a hard dependency. DMRG cross-checks ship through `ITensors`/`ITensorMPS`.
- **Why it scales.** The structured reductions block-diagonalize the SDP by the model's symmetries; the binding cost is the largest residual block (see the cost estimate), not the bare moment-matrix dimension.

## Run mechanics

1. Consult `stack.toml`; run `/setup-julia` first when Julia is not usable, then `make install qmbcertify` (adds QMBCertify + Mosek + ITensors to `julia-env`). Mosek needs a license file (`MOSEKLM_LICENSE_FILE` / `~/mosek/mosek.lic`) — confirm it resolves before the run, or the SDP solve aborts.
2. Take the modeling decisions from `/method-polyopt` (model, couplings, observable, relaxation order, which structural strengthenings to switch on) and express them as the `GSB` call's arguments — do not re-decide them here.
3. Run the harness way: save the script to `tracks/polyopt/solutions/` (or `scripts/` for `/solve`), execute, save the certified bound + diagnostics + plot to the run dir.
4. Use cluster execution (`/using-slurm`) when the lattice size or relaxation order pushes Mosek past the local memory wall (see the cost estimate).

### Canonical run shape

Two steps: `GSB` builds and solves the structured SDP (numeric bound), then `certify_qmb` rounds it to an exact certified bound. *(The Hamiltonian is passed as a support/coefficient list in QMBCertify's normal form — `examples/certified_energy.jl` is the ground truth for the encoding; the snippet below is illustrative, not a fixed model.)*

```julia
using QMBCertify

# Hamiltonian terms (support words + coefficients) and the relaxation order
# come from /method-polyopt; e.g. a J1-J2 Heisenberg setup:
supp = [[1, 4], [1, 7]]          # nearest- + next-nearest-neighbour terms
coe  = [3/4, 3/4 * J2]
N, d = 16, 2                     # system size, relaxation order

# Build + solve the structured SDP (Mosek)
opt, data = GSB(supp, coe, N, d;
                lattice="chain", rdm=0, extra=1, pso=0, lso=0,
                three_type=[1,1], Gram=true, QUIET=true)

# Round the numeric solution to an EXACT certified bound
result = certify_qmb(data, N, coe[1], opt; tol_gram=1e-15, tol_dft=1e-12, snn=true, J2=J2)

result.newbound   # the exactly certified bound = numeric optimum + rigorous shift
result.oldbound   # the raw (uncertified) Mosek numeric optimum, for comparison
```

For correlations/observables use `certify_qmb_corr` (`examples/certified_corr.jl`); for partition functions use `PFB` (`examples/partition_function.jl`). All detailed in the repo `examples/`.

## Parameters — step 3 (software)

The source for QMBCertify-specific run knobs unless `/method-polyopt` or the paper fixes a value. The *meaning* and *selection* (relaxation strategy, which strengthenings physics needs) come from `/method-polyopt`; this is the API surface to express them.

`GSB` builds and solves the structured SDP — its run knobs:

| Knob (`GSB`) | Effect | Starting point |
|---|---|---|
| `d` | Relaxation order — the monomial-basis degree (the moment matrix reaches degree 2d); the tightening knob, cost grows steeply in it. | per `/method-polyopt`; 2 is standard. |
| `extra` | Long-range reach — includes two-site monomials separated by up to `extra+1` sites (the paper's long-range parameter r = extra+1); captures longer-range correlations. Degree is set by `d`, not this. | per `/method-polyopt`; `0` = nearest-neighbour only. |
| `lattice` | `"chain"` (1D) or `"square"` (2D); selects the geometry and its symmetry group. | per the model. |
| `rdm` | Order of the reduced-density-matrix positivity constraint (U(1)-block-diagonalised). `0` = off. | per `/method-polyopt`; examples use 8–10, `0` is the lightest. |
| `pso`, `lso` | State-optimality strengthenings (PSD / linear) from the optimality conditions. | per `/method-polyopt`; `0` for the lightest run. |
| `energy`, `correlation` | Switch from energy to **two-sided observable bounds**: pass a known `[lb, ub]` energy bracket as `energy` and set `correlation=true` to bound an observable over near-ground states. | `[]` / `false` (energy mode). |
| `three_type` | Which three-body monomial families enter the basis. | `[1,1]` default. |
| `SU2_symmetry` | Exploit SU(2) invariance for further reduction. | per the model. |
| `Gram` | Return the Gram matrices — **required** for `certify_qmb` exact rounding. | `true` whenever certifying. |

`certify_qmb` rounds the numeric solution to an exact rational certificate:

| Knob (`certify_qmb`) | Effect | Starting point |
|---|---|---|
| `snn`, `J2` | **Define the certified Hamiltonian** — `snn=true` adds the J2 (next-nearest-neighbour) term, so the certificate is verified against the J1-J2 model. **Match these to the model you actually solved**, or you certify the wrong Hamiltonian. | per the model (`snn=true`, `J2` for J1-J2; `snn=false` for plain Heisenberg). |
| `tol_gram`, `tol_dft` | Tolerances for the Gram / discrete-Fourier rounding to rationals. | `1e-15` / `1e-12`. |
| `eig_prec` | Eigenvalue precision (Arblib) for the rigorous PSD enclosure that produces the shift. | raise if rounding fails. |

## Caller Contract

The scientific values — model, couplings, observable, relaxation order, which structural strengthenings to enable, validation target — are caller-supplied (from `/method-polyopt` + the model/physics cards). This skill turns agreed values into a runnable QMBCertify script and executes it the harness way; it does not originate the modeling decisions.

## Time estimate — feeds step 4

- Cost is set by the **largest residual SDP block** after the symmetry / sparsity / RDM reductions, not the bare moment-matrix dimension — the whole point of the package is that this residual is small even at large lattices. Mosek interior-point time and memory rise steeply in that residual block size.
- The binding resource is **memory** (Mosek factorizations); the reference results used a 32-core / 1 TB workstation, with `MOSEK 11` as the solver.
- Higher `d`, larger `extra`, and turning on `rdm` / `pso` / `lso` each enlarge the SDP — probe at `d=2` with the strengthenings off, read the reported block sizes, then decide what to enable and whether to go local or `/using-slurm`.
- First-run Julia precompilation (QMBCertify + Mosek + ITensors) is setup time, not solve time; report it separately. Feeds `/reproduce-paper`'s step-4 resource confirmation and the local-vs-cluster decision.

---

*The modeling concepts behind these knobs (the structured NPA hierarchy, the five symmetries, RDM positivity, state optimality) are documented method-side in `/method-polyopt`, distilled there from the `polyopt-guide` skill (exAClior/easy-nctssos) and the package's reference paper.*

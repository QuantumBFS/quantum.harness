---
name: using-sse
description: Use when choosing or running StochasticSeriesExpansion.jl or Carlo.jl for sign-free QMC/SSE workflows, MPI setup, or SSE setup failures.
---

# SSE

Software-stack skill for the SSE route: StochasticSeriesExpansion.jl on Carlo.jl. It owns the **software layer**: run mechanics, **software parameters (step 3)**, and the **time estimate (feeds step 4)**. It is the **step-2 handoff target** from `/method-qmc` once the SSE route is chosen.

It does **not** own method selection, SSE theory, or the sign-freeness / autocorrelation "why" → `/method-qmc`; model choice → `.knowledge/models/`; paper figure facts → `/reproduce-paper`. This card carries the Carlo/SSE job shape and parameter values, not the method.

## Sources

- Stack contract: `skills/using-sse/stack.toml`
- Method card: `skills/method-qmc/SKILL.md`
- Install target: `make install sse`
- Smoke test: `julia --project=julia-env -e 'using Carlo, StochasticSeriesExpansion'`
- Official docs (verify the current API here — there is no in-repo software paper): StochasticSeriesExpansion.jl `https://lukas.weber.science/StochasticSeriesExpansion.jl/stable/`; tutorial `https://lukas.weber.science/StochasticSeriesExpansion.jl/stable/tutorial.html`; Carlo.jl `https://lukas.weber.science/Carlo.jl/dev/`

## What SSE on Carlo is — step 2 (the handoff target)

What `/method-qmc` routes here for, and what to confirm before running.

- **The packages.** StochasticSeriesExpansion.jl (Lukas Weber) is the sign-free SSE QMC engine; Carlo.jl is the Monte Carlo job framework underneath it — task scheduling, checkpointing, MPI parallelization, and result collection.
- **Canonical for** sign-problem-free spin / boson lattices: finite-temperature observables (susceptibility, magnetization, Binder ratios) and ground states via large `beta`. The tutorial runs a honeycomb magnet susceptibility-vs-`T` curve.
- **Efficiency.** Carlo.jl runs independent chains / parameter points in parallel via MPI and checkpoints long runs; throughput scales with the task count, not within a single chain.
- **Features to confirm fit the target** before routing here: a built-in model (e.g. `MagnetModel`), the `measure` observable set, the lattice `unitcell`, a `T` / `beta` scan, and MPI ranks. **Confirm sign-freeness first** — if the sign is uncontrolled for this lattice / coupling-signs / basis, stop and reroute (the criterion is `/method-qmc`'s).

## Run mechanics

1. Confirm the model is sign-problem-free for the chosen lattice, coupling signs, and basis; stop or reroute if not.
2. Consult `stack.toml` for CPU vs MPI smoke tests and compose with `/using-slurm` for scheduled runs.
3. Pin thermalization, samples, chains, bins, update type, estimator, seed policy, and target uncertainty (values from *Parameters*).
4. Report autocorrelation / binning diagnostics with the measured observable.

Follow the package tutorial's job-script shape:

```julia
using Carlo
using Carlo.JobTools
using StochasticSeriesExpansion

tm = TaskMaker()
tm.sweeps = 80000
tm.thermalization = 10000
tm.binsize = 100

tm.model = MagnetModel
tm.S = 1
tm.J = 1
tm.measure = [:magnetization]

for L in [10, 20]
    tm.lattice = (unitcell = UnitCells.honeycomb, size = (L, L))
    for T in range(0.05, 4.0, 20)
        tm.T = T
        task(tm)
    end
end

job = JobInfo(
    splitext(@__FILE__)[1],
    StochasticSeriesExpansion.MC;
    run_time = "24:00:00",
    checkpoint_time = "30:00",
    tasks = make_tasks(tm),
)

start(job, ARGS)
```

Run locally with `julia --project=julia-env scripts/<job>.jl run`. Run under MPI only inside the selected remote allocation (the `sse:cpu_mpi` profile; `sse:cpu` for single-process); cluster modules, partitions, and `mpirun`/`srun` details live in `skills/using-slurm/profiles/<profile>.md`.

```
mpirun -n <ranks> julia --project=julia-env scripts/<job>.jl run
```

Read the resulting `<job>.results.json` with `Carlo.ResultTools.dataframe`. Plot the primary observable versus the physical scan axis, with one curve per system size or `beta`.

## Parameters — step 3 (software)

The source for SSE/Carlo-specific reproduction knobs unless the paper or official code fixes a value. Starting points are software practice, not paper-anchored: begin from each, then converge it — the convergence check (β sweep, bin size, sweeps/chains), not the starting number, is what makes the result trustworthy.

What to pin:

- **Validity:** sign-problem-free basis, lattice, coupling signs, `T` / `beta`, and boundary. Stop or reroute if the sign is uncontrolled (criterion → `/method-qmc`).
- **Markov chain:** update type, thermalization sweeps, measurement sweeps, sweep definition, chains / replicas, seed policy, checkpoint cadence.
- **Estimator:** measured observable, normalization, improved estimator if used, bin size, autocorrelation handling, target uncertainty.
- **Runtime profile:** serial CPU vs MPI, process count, allocation, and whether the run is a parameter scan.
- **Diagnostics the tool exposes:** acceptance / update rates, binning stability, autocorrelation time, independent-chain spread. The convergence *criteria* are the method card's.

Concrete starting points:

| Knob | Effect | Starting point |
|---|---|---|
| `sweeps` | Statistical precision after thermalization. | 1e4 for smoke; 8e4+ for tutorial-scale curves. |
| `thermalization` | Removes initial-state bias. | 10%–20% of sweeps; increase near criticality. |
| `binsize` | Controls saved bin granularity. | Small compared with sweeps; larger than short autocorrelation scales. |
| `T` / `beta` | Physical temperature or ground-state projection. | Scan temperature for curves; for a ground state increase `beta` until stable. |
| `L` | System size. | At least three sizes for a scaling claim. |
| `measure` | Observable set. | `[:magnetization]` for susceptibility and Binder diagnostics. |
| MPI ranks | Independent task throughput. | Use only when the Carlo task count is large enough to keep ranks busy. |

## Caller Contract

The scientific values — model, lattice, coupling signs, observable, temperature grid, validation target — are caller-supplied; resolve open ones via the step-4 brainstorm, deferring SSE theory and the sign / autocorrelation criteria to `/method-qmc` and model physics to the model card. This skill turns agreed values into a runnable Carlo/SSE job; it does not originate them.

## Time estimate — feeds step 4

Estimate from `thermalization_sweeps + measurement_sweeps`, cost per sweep, number of chains, and autocorrelation time; the result feeds `/reproduce-paper`'s step-4 resource confirmation.

- Per-sweep cost scales with lattice size, operator-string length, and update type; low temperature usually grows the operator string and the autocorrelation.
- Effective independent samples are fewer than raw samples when autocorrelation is large; include the binning / autocorrelation penalty.
- MPI reduces wall time only when chains or parameter points parallelize cleanly; use `stack.toml` for the MPI smoke test and `/using-slurm` for scheduled runs.
- For uncertain cases, time a short non-production chain to estimate sweep rate and an autocorrelation proxy, then show paper-size and local-PC-in-15-min estimates before asking scale.

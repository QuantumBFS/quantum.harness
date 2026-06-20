# StochasticSeriesExpansion.jl + Carlo.jl — API & Examples Reference

Single-file usage reference for the **SSE QMC** route: `StochasticSeriesExpansion.jl`
(the sign-free stochastic series expansion quantum Monte Carlo engine, by Lukas Weber)
running on top of `Carlo.jl` (the generic Monte Carlo job framework: task scheduling,
parallelization, checkpointing, error analysis).

All math is in UTF-8 unicode. Code blocks are verbatim from the official docs / example
package. Verify the live API against the source links at the bottom — there is no in-repo
software paper, so these docs are authoritative.

## What this stack does

- **SSE QMC** is a finite-temperature quantum Monte Carlo method. It samples the
  high-order Taylor (series) expansion of `exp(−β H)` as a string of bond operators.
  It is **exact** (up to statistical error and equilibration) for **sign-problem-free**
  Hamiltonians — chiefly unfrustrated/bipartite spin-`S` magnets and bosonic lattices.
- It computes finite-`T` observables: energy, magnetization, uniform/staggered
  susceptibility, Binder ratios, specific heat, correlation functions. Ground-state
  properties are obtained by taking `β = 1/T` large.
- `StochasticSeriesExpansion.jl` ships an **abstract-loop** algorithm that *automatically*
  determines the worm/loop updates (traditionally hand-derived per model), so users can
  run high-performance SSE without being a QMC expert. Out of the box it supports
  **anisotropic spin-`S` quantum magnets**; it is extensible to arbitrary models via the
  `AbstractModel` interface (which may then reintroduce a sign problem).
- `Carlo.jl` underneath handles: parallel independent runs (MPI), checkpointing of long
  runs, automatic binning + jackknife error analysis, and a CLI (`run`/`status`/`merge`/
  `delete`) attached to each job script via `start(job, ARGS)`.
- Applied in the literature to Heisenberg-type magnets, frustrated magnets in multi-site
  (cluster) bases, and magnets coupled to cavity photons.

**Confirm sign-freeness first.** If the lattice / coupling signs / basis give an
uncontrolled sign, stop — SSE results are then meaningless. That criterion is owned by
`/method-qmc`, not by this card.

---

## Part 1 — Carlo.jl (the job framework)

### 1.1 Installation

```julia
] add Carlo
] add StochasticSeriesExpansion
```

For a system MPI build, configure `MPI.jl`; system HDF5 binaries may also need `HDF5.jl`
configuration.

### 1.2 Job script anatomy

Every Carlo job is a Julia script that (a) builds a list of tasks with `TaskMaker`,
(b) wraps them in a `JobInfo`, and (c) calls `start(job, ARGS)` to expose the CLI.
Reference Ising example:

```julia
#!/usr/bin/env julia

using Carlo
using Carlo.JobTools
using Ising

tm = TaskMaker()
tm.sweeps = 10000
tm.thermalization = 2000
tm.binsize = 100

tm.Lx = 10
tm.Ly = 10

Ts = range(0.1, 4, length=20)
for T in Ts
    task(tm; T=T)
end

job = JobInfo(@__FILE__, Ising.MC;
    checkpoint_time="30:00",
    run_time="15:00",
    tasks=make_tasks(tm)
)

start(job, ARGS)
```

### 1.3 JobTools — TaskMaker, task, make_tasks

`TaskMaker()` accumulates parameters by free field assignment; each `task()` call snapshots
the current field state into one task. This makes parameter scans concise.

| Function | Signature | Purpose |
|---|---|---|
| `TaskMaker` | `TaskMaker()` | Mutable parameter accumulator; assign any field (`tm.x = ...`). |
| `task` | `task(tm::TaskMaker; kwargs...)` | Snapshot current fields into a new task; kwargs override **for that task only**. |
| `make_tasks` | `make_tasks(tm::TaskMaker)::Vector{TaskInfo}` | Build the task list to pass as `JobInfo(... tasks=...)`. |
| `current_task_name` | `current_task_name(tm::TaskMaker)` | Name the *next* `task(tm)` call will produce. |

```julia
tm = TaskMaker()
tm.sweeps = 10000
tm.thermalization = 2000
tm.binsize = 500

task(tm; T=0.04)
tm.sweeps = 5000
for T in range(0.1, 10, length=5)
    task(tm; T=T)
end

tasks = make_tasks(tm)
```

**Required TaskInfo parameters** (every task must define):

| Param | Meaning |
|---|---|
| `sweeps` | Minimum number of **measurement** sweeps to perform. The only field that may be raised for an existing/finished calculation (to gather more statistics). |
| `thermalization` | Number of **thermalization** (equilibration) sweeps before any measurement. |
| `binsize` | Number of samples Carlo merges into one saved bin before writing to disk (internal default binning for error analysis). |

### 1.4 JobInfo

```julia
JobInfo(
    job_directory_prefix::AbstractString,
    mc::Type;
    checkpoint_time::Union{AbstractString, Dates.Period},
    run_time::Union{AbstractString, Dates.Period},
    tasks::Vector{TaskInfo},
    rng::Type = Random.Xoshiro,
    ranks_per_run::Union{Integer, Symbol} = 1,
)
```

- `job_directory_prefix` — output location; typically `@__FILE__` (or
  `splitext(@__FILE__)[1]`). Produces `<prefix>.data/` and `<prefix>.results.json`.
- `mc` — the `AbstractMC` (or `StochasticSeriesExpansion.MC`) **type** to run.
- `checkpoint_time` — wall-clock cadence for writing checkpoints (`"[[hours:]minutes:]seconds"`).
- `run_time` — total wall budget; on expiry the job checkpoints and exits cleanly so it can resume.
- `tasks` — output of `make_tasks(tm)`.
- `rng` — RNG type (default `Random.Xoshiro`); see RNG docs for reproducibility.
- `ranks_per_run` — MPI ranks per single Monte Carlo run (default `1` = trivial parallelism); `>1` enables *parallel run mode* (Section 1.8).

### 1.5 The AbstractMC interface

A custom Monte Carlo algorithm is a mutable struct `YourMC <: AbstractMC` plus the methods
below. (For SSE you do **not** implement these — `StochasticSeriesExpansion.MC` already
does; you implement an `AbstractModel` instead, Part 2.)

| Method | Signature | Purpose |
|---|---|---|
| constructor | `YourMC(params::AbstractDict)` | Build the MC from task parameters (`params[:T]`, `params[:Lx]`, …). |
| `init!` | `Carlo.init!(mc, ctx::MCContext, params::AbstractDict)` | Initialize config when started from scratch. |
| `sweep!` | `Carlo.sweep!(mc, ctx::MCContext)` | Perform one MC sweep/update of the configuration. |
| `measure!` | `Carlo.measure!(mc, ctx::MCContext)` | Record one measurement via `measure!(ctx, :Name, value)`. |
| `write_checkpoint` | `Carlo.write_checkpoint(mc, out::HDF5.Group)` | Save full simulation state to `out`. |
| `read_checkpoint!` | `Carlo.read_checkpoint!(mc, in::HDF5.Group)` | Restore full state from `in`. |
| `register_evaluables` | `Carlo.register_evaluables(::Type{YourMC}, eval::AbstractEvaluator, params::AbstractDict)` | Define post-processed/derived observables (Section 1.6). Runs after the sim; no access to live state. |

**MCContext** (`ctx`) — the handle the framework passes into `init!`/`sweep!`/`measure!`:

| API | Purpose |
|---|---|
| `ctx.rng` | The configured RNG — use it for *all* randomness (reproducibility/checkpointing). |
| `measure!(ctx, name::Symbol, value)` | Record a scalar or vector float sample for observable `name`. |
| `register_observable!(ctx, obsname::Symbol; binsize::Integer, shape::Tuple=(), T=Float64)` | Pre-register an observable with custom binning/shape/type. |
| `is_thermalized(ctx)::Bool` | `true` once the thermalization phase finished. Guard measurements taken inside `sweep!` with this. |

Measurements may be taken inside `sweep!` (for efficiency), but only when
`is_thermalized(ctx)` is true.

### 1.6 Evaluables — derived observables with error propagation

Derived quantities (susceptibility, Binder ratio, specific heat) are nonlinear functions of
observable *averages*; naive error bars are wrong because of sample correlations. Carlo uses
**jackknifing** to produce bias-corrected values with correct error bars.

```julia
evaluate!(func::Function, eval::AbstractEvaluator, name::Symbol, (ingredients::Symbol...))
```

Defines evaluable `name` as `func` applied to the listed observable averages. Register them
inside `register_evaluables`:

```julia
evaluate!(eval, :Susceptibility, (:Magnetization2,)) do mag2
    return Lx * Ly * mag2 / T
end

evaluate!(eval, :BinderRatio, (:Magnetization2, :Magnetization4)) do mag2, mag4
    return mag2 * mag2 / mag4
end
```

### 1.7 Running, status, merging, restart (CLI)

`start(job, ARGS)` turns the script into a CLI. Commands (`<job>` = the script, made
executable, or `julia --project=julia-env scripts/<job>.jl <cmd>`):

```bash
./myjob run                 # run (single process)
mpirun -n $num_cores ./myjob run   # run across MPI ranks (trivial parallelism)
./myjob status              # table: completed/target sweeps, #runs, thermalization fraction
./myjob merge               # (re)build myjob.results.json from current data (mid-run OK)
./myjob delete              # remove myjob.data/ and myjob.results.json
./myjob run --restart       # restart from scratch ignoring existing checkpoints
./myjob --help              # all commands + their shortcut forms
```

Output layout: `myjob.data/` holds per-task HDF5 files; on completion `myjob.results.json`
holds averaged measurements with error bars. `merge` lets you read partial results before a
job finishes. Each command has a short alias visible in `--help`.

### 1.8 Parallelism / MPI

Two models:

1. **Trivial parallelism (default, `ranks_per_run = 1`).** `mpirun -n N` runs `N`
   independent runs that share parameters (results averaged) or cover different tasks.
   Throughput scales with rank count; it does **not** shorten thermalization of a single chain.
2. **Parallel run mode (`ranks_per_run > 1`).** A single MC run spans several ranks — for
   population control or data exchange between replicas. The interface gains an `MPI.Comm`:

   ```julia
   Carlo.init!(mc, ctx::MCContext, params::AbstractDict, comm::MPI.Comm)
   Carlo.sweep!(mc, ctx::MCContext, comm::MPI.Comm)
   Carlo.measure!(mc, ctx::MCContext, comm::MPI.Comm)
   Carlo.write_checkpoint(mc, out::Union{HDF5.Group,Nothing}, comm::MPI.Comm)
   Carlo.read_checkpoint!(mc, in::Union{HDF5.Group,Nothing}, comm::MPI.Comm)
   ```

   Only **rank 0** may call `measure!` on the `MCContext` and only rank 0 receives a real
   `HDF5.Group` (others get `nothing`); you must MPI-communicate results/state to rank 0.
   The communicator is also available in the constructor as `params[:_comm]`.
   `register_evaluables` is unchanged.

### 1.9 ResultTools — reading `.results.json`

```julia
ResultTools.dataframe(result_json::AbstractString)
```

Returns a Tables.jl-compatible dictionary (use as-is or wrap in a `DataFrame`). Observables
and their error bars become **Measurements.jl** measurements (value ± error); task
parameters and observables both appear as columns.

```julia
using Plots
using DataFrames
using Carlo.ResultTools

df = DataFrame(ResultTools.dataframe("example.results.json"))

plot(df.T, df.Energy; xlabel = "Temperature", ylabel="Energy per spin",
     group=df.Lx, legendtitle="L")
```

---

## Part 2 — StochasticSeriesExpansion.jl (the SSE engine)

You run SSE by pointing `JobInfo` at `StochasticSeriesExpansion.MC` and setting
`tm.model` to an `AbstractModel` plus its physical parameters. The `MagnetModel` covers
anisotropic spin-`S` magnets without writing any algorithm code.

### 2.1 Predefined models

#### MagnetModel `<: AbstractModel`

Hamiltonian:

```
H = Σ_⟨i,j⟩ J_ij ( Sᵢ·Sⱼ + (1 + d_ij) Sᵢᶻ Sⱼᶻ )
    + Σ_i [ hᵢ Sᵢᶻ + D_z,i (Sᵢᶻ)² + D_x,i (Sᵢˣ)² ]
```

| Param (`tm.` field) | Meaning | Default |
|---|---|---|
| `lattice` | Lattice structure: `(unitcell = UnitCells.<name>, size = (Lx, Ly))`. | (required) |
| `S` | Spin magnitude per site. | `1//2` |
| `J` | Exchange coupling `J_ij`. | (required) |
| `d` | Exchange (XXZ) anisotropy `d_ij` on the `SᶻSᶻ` term. | `0` |
| `h` | Uniform z-field `h_i`. | `0` |
| `D_z` | Single-ion z-anisotropy `D_z,i (Sᶻ)²`. | `0` |
| `D_x` | Single-ion x-anisotropy `D_x,i (Sˣ)²`. | `0` |
| `parameter_map` | Assign distinct parameters to different bonds/sites (sublattice-resolved couplings). | — |
| `measure` | Vector of observables to record. | — |

Supported `measure` entries:
- `:magnetization` — uniform magnetization → uniform susceptibility `MagChi` etc.
- `:staggered_magnetization` — staggered (Néel) order parameter.
- any `Type{<:AbstractOpstringEstimator}` — a custom operator-string estimator.

Note: in the tutorial script the field is named `tm.Dz` for the single-ion z-anisotropy;
the models page documents it as `D_z`. Confirm against the installed version (Section
"Pitfalls").

**parameter_map** for sublattice/bond-resolved couplings (honeycomb example):

```julia
tm.parameter_map = (;
    J = (:J1, :J2, :J3),
    S = (:Sa, :Sb),
)
tm.J1 = 1.0
tm.J2 = 0.5
tm.J3 = 1.5
tm.Sa = 1//2
tm.Sb = 1
```

#### ClusterModel `<: AbstractModel` (experimental)

Wraps another `AbstractModel` to simulate it in a **cluster basis** — the route to keep
frustrated systems sign-free by grouping sites into clusters.

| Param | Meaning |
|---|---|
| `inner_model` | The underlying `AbstractModel` to simulate. |
| `cluster_bases` | Tuple of `ClusterBasis` objects (one per cluster type). |
| `measure_quantum_numbers` | `Vector` of `(; name::Symbol, quantum_number::Int)` to measure. |

#### ClusterBasis

```julia
ClusterBasis(quantum_numbers::Vector{NTuple{N,T}}, transformation::AbstractMatrix{T})
```

- `quantum_numbers` — the set of quantum-number tuples labeling cluster states.
- `transformation` — unitary whose columns are the cluster basis states.

### 2.2 Lattices / unit cells

In the `UnitCells` module:

| `UnitCells.<name>` | Lattice |
|---|---|
| `square` | Square lattice. |
| `columnar_dimer` | Square lattice of dimers (columnar). |
| `honeycomb` | Honeycomb lattice. |
| `triangle` | Triangular lattice. |

Used as `tm.lattice = (unitcell = UnitCells.honeycomb, size = (L, L))`.

### 2.3 SSE-specific simulation parameters

Set on the `TaskMaker` alongside the Carlo-level `sweeps`/`thermalization`/`binsize`.

**Required:**

| Param | Meaning |
|---|---|
| `T` | Temperature (sets `β = 1/T` internally). Large `T`⁻¹ (small `T`) → ground state. |
| `model` | The `AbstractModel` type (e.g. `MagnetModel`). |

**Optional (algorithm tuning, sensible defaults exist):**

| Param | Meaning |
|---|---|
| `init_opstring_cutoff` | Initial padded operator-string length; grown dynamically at runtime. |
| `diagonal_warmup_sweeps` | Diagonal-only sweeps at init before the first loop update; helps dilute operator strings. |
| `init_num_worms` | Starting number of worms/loops per sweep; auto-tuned by a controller afterward. |
| `num_worms_attenuation_factor` | Sensitivity of the worm-count control loop; higher = faster equilibration but noisier. |
| `target_worm_length_fraction` | Controller target: combined loop length ≈ `target_worm_length_fraction * num_operators`. |

### 2.4 Worked example — complete SSE QMC job (from the tutorial)

A spin-1 honeycomb magnet (modeling BaNi₂V₂O₈), susceptibility vs temperature for two
sizes. Verbatim:

```julia
using Carlo
using Carlo.JobTools
using StochasticSeriesExpansion

tm = TaskMaker()
tm.sweeps = 80000
tm.thermalization = 10000
tm.binsize = 100

temperatures = range(0.05, 4, 20)
system_sizes = [10, 20]

J_n = 8.07 # meV
D_EP = 0.04556 # meV

tm.model = MagnetModel
tm.S = 1
tm.J = 1
tm.Dz = D_EP / J_n

tm.measure = [:magnetization]
for L in system_sizes
    tm.lattice = (unitcell = UnitCells.honeycomb, size = (L, L))

    for T in temperatures
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

Run it (file `bani2v2o8.jl`):

```bash
mpirun -n $NCORES julia bani2v2o8.jl run
# or single-process:
julia --project=julia-env bani2v2o8.jl run
```

Produces `bani2v2o8.data/` (raw HDF5) and `bani2v2o8.results.json` (post-processed,
with error bars). Read and plot:

```julia
using Plots, DataFrames, LaTeXStrings, Carlo.ResultTools

df = DataFrame(ResultTools.dataframe("bani2v2o8.results.json"))
df.L = [lattice["size"][1] for lattice in df.lattice]

plot(df.T, df.MagChi, group=df.L,
    xlabel = L"Temperature $T/J$",
    ylabel = L"Magnetic susceptibility $χ^z J$",
    legend_title = "L"
)
```

The DataFrame contains every simulation parameter plus observables; `:magnetization`
yields `MagChi` (uniform magnetic susceptibility) among others.

### 2.5 Custom-model interface (`AbstractModel`)

For models beyond `MagnetModel`, implement `YourModel <: AbstractModel`. SSE decomposes
`H` into **bond operators** acting on a few sites each; in the diagrammatic picture each
site has incoming/outgoing legs.

**Required constructor:** `YourModel(parameters::AbstractDict{Symbol, <:Any})` — receives
the Carlo task parameters (lattice, couplings, …).

| Method | Signature | Purpose |
|---|---|---|
| `generate_sse_data` | `generate_sse_data(model::YourModel) -> SSEData` | Translate model into the bond graph + bond Hamiltonians the abstract-loop SSE needs. |
| `get_opstring_estimators` | `get_opstring_estimators(model::YourModel) -> Vector{Type{<:AbstractOpstringEstimator}}` | Operator-string estimators for observables (run fused in one loop for efficiency). |
| `leg_count` | `leg_count(model::Type{YourModel}) -> Integer` | Max legs per bond operator (e.g. 4 for a 2-site Heisenberg bond). |
| `normalization_site_count` | `normalization_site_count(model::YourModel) -> Integer` | Physical site count used to normalize observables. |

The `SSEData` structure encodes the bond graph and the per-bond Hamiltonians; estimators
are `AbstractOpstringEstimator` subtypes. (See the SSE data-structure page for the internal
layout.)

---

## Part 3 — Full Carlo custom-MC skeleton (Ising.jl, verbatim)

The canonical `AbstractMC` reference: 2D classical Ising via Metropolis. Use it as the
template when you must write a *non-SSE* Monte Carlo on Carlo. Verbatim from `Ising.jl`:

```julia
module Ising

using Carlo
using HDF5

mutable struct MC <: AbstractMC
    T::Float64

    spins::Matrix{Int8}
end

function MC(params::AbstractDict)
    Lx = params[:Lx]
    Ly = get(params, :Ly, Lx)
    T = params[:T]
    return MC(T, zeros(Lx, Ly))
end

function Carlo.init!(mc::MC, ctx::MCContext, params::AbstractDict)
    mc.spins .= rand(ctx.rng, Bool, size(mc.spins)) .* 2 .- 1
    return nothing
end

function periodic_elem(spins::AbstractArray, x::Integer, y::Integer)
    return spins[mod1.((x, y), size(spins))...]
end

function Carlo.sweep!(mc::MC, ctx::MCContext)
    Lx = size(mc.spins, 1)

    for _ = 1:length(mc.spins)
        i = rand(ctx.rng, eachindex(mc.spins))
        x, y = fldmod1(i, size(mc.spins, 1))

        neighbor(dx, dy) = periodic_elem(mc.spins, x + dx, y + dy)
        ratio = exp(
            -2.0 / mc.T *
            mc.spins[x, y] *
            (neighbor(1, 0) + neighbor(-1, 0) + neighbor(0, 1) + neighbor(0, -1)),
        )

        if ratio >= 1 || ratio > rand(ctx.rng)
            mc.spins[x, y] *= -1
        end
    end
    return nothing
end

function Carlo.measure!(mc::MC, ctx::MCContext)
    mag = sum(mc.spins) / length(mc.spins)

    energy = 0.0

    correlation = zeros(size(mc.spins, 1))
    for y = 1:size(mc.spins, 2)
        for x = 1:size(mc.spins, 1)
            neighbor(dx, dy) = periodic_elem(mc.spins, x + dx, y + dy)
            energy += -mc.spins[x, y] * (neighbor(1, 0) + neighbor(0, 1))

            correlation[x] += mc.spins[1, y] * mc.spins[x, y]
        end
    end

    measure!(ctx, :Energy, energy / length(mc.spins))
    measure!(ctx, :Energy2, (energy / length(mc.spins))^2)

    measure!(ctx, :Magnetization, mag)
    measure!(ctx, :AbsMagnetization, abs(mag))
    measure!(ctx, :Magnetization2, mag^2)
    measure!(ctx, :Magnetization4, mag^4)

    measure!(ctx, :SpinCorrelation, correlation ./ size(mc.spins, 2))
    return nothing
end

function Carlo.register_evaluables(
    ::Type{MC},
    eval::AbstractEvaluator,
    params::AbstractDict,
)
    T = params[:T]
    Lx = params[:Lx]
    Ly = get(params, :Ly, Lx)

    evaluate!(eval, :BinderRatio, (:Magnetization2, :Magnetization4)) do mag2, mag4
        return mag2 * mag2 / mag4
    end

    evaluate!(eval, :Susceptibility, (:Magnetization2,)) do mag2
        return Lx * Ly * mag2 / T
    end

    evaluate!(eval, :SpecificHeat, (:Energy2, :Energy)) do energy2, energy
        return Lx * Ly * (energy2 - energy^2) / T^2
    end

    evaluate!(eval, :SpinCorrelationK, (:SpinCorrelation,)) do corr
        corrk = zero(corr)
        for i = 1:length(corr), j = 1:length(corr)
            corrk[i] += corr[j] * cos(2π / length(corr) * (i - 1) * (j - 1))
        end
        return corrk
    end

    return nothing
end

function Carlo.write_checkpoint(mc::MC, out::HDF5.Group)
    out["spins"] = mc.spins
    return nothing
end

function Carlo.read_checkpoint!(mc::MC, in::HDF5.Group)
    mc.spins .= read(in, "spins")
    return nothing
end

function Carlo.parallel_tempering_log_weight_ratio(mc::MC, parameter::Symbol, new_value)
    if parameter != :T
        error("parallel tempering not implemented for $parameter")
    end

    energy = 0.0
    for y = 1:size(mc.spins, 2)
        for x = 1:size(mc.spins, 1)
            neighbor(dx, dy) = periodic_elem(mc.spins, x + dx, y + dy)
            energy += -mc.spins[x, y] * (neighbor(1, 0) + neighbor(0, 1))
        end
    end

    return -(1 / new_value - 1 / mc.T) * energy
end

function Carlo.parallel_tempering_change_parameter!(mc::MC, parameter::Symbol, new_value)
    if parameter != :T
        error("parallel tempering not implemented for $parameter")
    end

    mc.T = new_value
end

end # module Ising
```

The two `parallel_tempering_*` methods are optional — implement them only to enable
parallel tempering over a parameter (here `:T`).

---

## Part 4 — Pitfalls

- **Thermalization vs measurement sweeps are separate budgets.** `thermalization` sweeps
  produce *no* recorded data; `sweeps` is the measurement count. Near criticality (large
  autocorrelation / small `T`) increase `thermalization` substantially — `status` reports
  the thermalization fraction, watch it reach 1.0 across runs. Only `sweeps` may be raised
  for an already-finished job to collect more statistics.
- **Binning and error bars.** `binsize` merges raw samples into bins before storage; error
  bars come from bins, so `binsize` must exceed the autocorrelation time or error bars are
  underestimated. Derived quantities (susceptibility, Binder, specific heat) must go through
  `evaluate!`/`register_evaluables` so jackknifing propagates correlated errors correctly —
  never compute them by hand from averaged columns. `ResultTools.dataframe` returns
  `value ± error` (Measurements.jl); trust those, not raw ratios.
- **β / temperature convention.** You set `T`; the engine uses `β = 1/T`. There is no
  separate `beta` knob — for a ground state, *lower* `T` (raise `β`) until observables stop
  moving. Low `T` grows the operator string and the per-sweep cost and autocorrelation;
  budget wall time accordingly.
- **Sign problem.** SSE is only exact when sign-free. Frustrated / non-bipartite couplings
  or a bad basis silently break this — `MagnetModel` on a frustrated lattice is *not*
  automatically safe; use `ClusterModel`/`ClusterBasis` or reroute. Confirm sign-freeness
  before any production run (criterion → `/method-qmc`).
- **MPI / parallelism.** Default `mpirun -n N` gives trivial parallelism: more independent
  chains, *not* faster thermalization of one chain, and only useful when the task count
  keeps ranks busy. `ranks_per_run > 1` (parallel run mode) changes the interface signatures
  (adds `MPI.Comm`) and restricts `measure!`/checkpointing to rank 0 — don't mix the two
  interface forms. Run MPI only inside an allocation (use the `sse:cpu_mpi` profile).
- **Always use `ctx.rng`** for randomness inside `init!`/`sweep!`/`measure!` — using the
  global RNG breaks reproducibility and checkpoint/restart correctness.
- **Field-name drift.** The single-ion z-anisotropy appears as `tm.Dz` in the tutorial but
  `D_z` on the models page; lattice `size` is read back from results as a dict
  (`lattice["size"][1]`). Confirm exact field names against the installed package version
  (`@doc MagnetModel`) before committing a long run.
- **`merge` for partial results.** You don't need to wait for a job to finish — `merge`
  rebuilds `.results.json` from whatever bins exist so far.

---

## Source links

- StochasticSeriesExpansion.jl index — https://lukas.weber.science/StochasticSeriesExpansion.jl/stable/
- SSE tutorial — https://lukas.weber.science/StochasticSeriesExpansion.jl/stable/tutorial.html
- SSE predefined models — https://lukas.weber.science/StochasticSeriesExpansion.jl/stable/models.html
- SSE parameters — https://lukas.weber.science/StochasticSeriesExpansion.jl/stable/parameters.html
- SSE custom-model interfaces — https://lukas.weber.science/StochasticSeriesExpansion.jl/stable/interfaces.html
- SSE simulation data structure — https://lukas.weber.science/StochasticSeriesExpansion.jl/stable/sse_data.html
- Carlo.jl index (install / usage / CLI) — https://lukas.weber.science/Carlo.jl/dev/index.html
- Carlo.jl AbstractMC — https://lukas.weber.science/Carlo.jl/dev/abstract_mc.html
- Carlo.jl Evaluables — https://lukas.weber.science/Carlo.jl/dev/evaluables.html
- Carlo.jl JobTools — https://lukas.weber.science/Carlo.jl/dev/jobtools.html
- Carlo.jl ResultTools — https://lukas.weber.science/Carlo.jl/dev/resulttools.html
- Carlo.jl RNG — https://lukas.weber.science/Carlo.jl/dev/rng.html
- Carlo.jl parallel run mode — https://lukas.weber.science/Carlo.jl/dev/parallel_run_mode.html
- Carlo.jl parallel tempering — https://lukas.weber.science/Carlo.jl/dev/parallel_tempering.html
- Carlo.jl covariance estimation — https://lukas.weber.science/Carlo.jl/dev/covariance.html
- Ising.jl reference AbstractMC example — https://github.com/lukas-weber/Ising.jl

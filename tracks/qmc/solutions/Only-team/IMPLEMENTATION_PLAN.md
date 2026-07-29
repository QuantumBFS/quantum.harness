# Minimal TFIM Cluster Monte Carlo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` or
> `superpowers:executing-plans` to execute this plan task-by-task. The user
> must choose the execution mode before Task 1 begins. No task authorizes a
> commit, push, or pull-request update.

**Goal:** Build a minimal, independent, verifiable Julia
discrete-imaginary-time cluster Monte Carlo program for the ferromagnetic
two-dimensional transverse-field Ising model on triangular and honeycomb
lattices.

**Architecture:** A single `MinimalTFIM` module includes focused files for
configuration, lattices, weights, updates, measurements, statistics, and MPI
orchestration. Deterministic unit tests establish geometry, sign, probability,
measurement, and statistics formulas before any stochastic benchmark runs.
MPI uses complete, independent Markov chains and only rank zero writes shared
output.

**Tech stack:** Julia 1.10 or newer, MPI.jl 0.20, StableRNGs.jl 1, and Julia
standard libraries `Random`, `TOML`, `Statistics`, and `Test`.

## Global constraints

- Work only under `tracks/qmc/solutions/Only-team/`.
- Write generated data only under `tracks/qmc/results/Only-team/`.
- Preserve the raw `J1` value; `J1=-1` is never rewritten as a positive
  coupling parameter.
- Reject `J1>=0`, `J2!=0`, and `hTrfd<=0`.
- Only `triangular` and `honeycomb` lattices with periodic boundaries are
  accepted.
- The method name in public documentation is
  `discrete-imaginary-time cluster Monte Carlo for the transverse-field Ising model`.
- Do not stage `.knowledge/`; do not use `git add .`.
- Do not commit, push, create a pull request, or update pull request #224
  without a later explicit user instruction.
- Do not relax fixed formula tolerances beyond `rtol=1e-13` and
  `atol=1e-14`.
- Each task stops after its test report and waits for user confirmation.
- The existing team and challenge tables in `README.md` remain intact.

## Locked file map

| File | Responsibility |
|---|---|
| `Project.toml` | Package identity, dependencies, and compatibility |
| `Manifest.toml` | Instantiated dependency lock |
| `src/MinimalTFIM.jl` | Top-level module, includes, and public exports |
| `src/Config.jl` | TOML parsing, validation, parameter derivation, path policy |
| `src/Lattices.jl` | Unified lattice type and both periodic geometries |
| `src/Weights.jl` | Temporal indexing, couplings, local formula, complete test weight |
| `src/Updates.jl` | State, diagnostics, local sweep, cluster construction, update cycle |
| `src/Measurements.jl` | Time segments, sampled slices, `m2` and `m4` accumulation |
| `src/Statistics.jl` | Bin records, filtering, SEM, final summaries |
| `src/MPIDriver.jl` | Independent chains, reductions, output policy and serialization |
| `scripts/run.jl` | Command-line entry point and MPI lifetime |
| `configs/*.toml` | Baseline and two smoke configurations |
| `test/runtests.jl` | Filterable deterministic, MPI, and statistical test groups |
| `README.md` | Model, algorithm, commands, outputs, limitations |

The implementation must not add another source file without a design
amendment.

---

### Task 1: Package shell, configuration parsing, and parameter derivation

**Files:**

- Create: `tracks/qmc/solutions/Only-team/Project.toml`
- Generate: `tracks/qmc/solutions/Only-team/Manifest.toml`
- Create: `tracks/qmc/solutions/Only-team/src/MinimalTFIM.jl`
- Create: `tracks/qmc/solutions/Only-team/src/Config.jl`
- Create: `tracks/qmc/solutions/Only-team/test/runtests.jl`
- Create: `tracks/qmc/solutions/Only-team/configs/baseline-triangular.toml`
- Create: `tracks/qmc/solutions/Only-team/configs/smoke-triangular.toml`
- Create: `tracks/qmc/solutions/Only-team/configs/smoke-honeycomb.toml`

**Interfaces produced:**

```julia
struct SimulationConfig
    lattice::Symbol
    NumL1::Int
    NumL2::Int
    J1::Float64
    J2::Float64
    hTrfd::Float64
    BetaT::Float64
    IfSetDltau::Bool
    FixedDltau::Float64
    input_LTrot::Int
    LTrot::Int
    Dltau::Float64
    nLocal::Int
    nWolff::Int
    nWarm::Int
    NmBin::Int
    NSwep::Int
    NmMeaConfg::Int
    discard_initial_bins::Int
    trim_extrema::Bool
    statistics_mode::Symbol
    seed::UInt64
    initial_state::Symbol
    output_dir::String
    CpTau::Float64
    K_space::Float64
    K_tau::Float64
    p_space::Float64
    p_tau::Float64
    raw_input::Dict{String,Any}
end

load_config(path::AbstractString; repo_root::AbstractString)::SimulationConfig
derive_couplings(J1::Float64, hTrfd::Float64, Dltau::Float64)
validate_statistics_feasibility(config::SimulationConfig)::Nothing
```

- [ ] **Step 1.1: Create the package declaration**

Use this exact dependency set:

```toml
name = "MinimalTFIM"
uuid = "ea616a78-a45d-4cb3-86e6-f7f64bdb4542"
authors = ["Xingcan-Liu"]
version = "0.1.0"

[deps]
MPI = "da04e1cc-30fd-572f-bb4f-1f8673147195"
Random = "9a3f8284-a2c9-5f02-9a11-845980a1fd5c"
StableRNGs = "860ef19b-820b-49d6-a774-d7a799459cd3"
Statistics = "10745b16-79ce-11e8-11f9-7d13ad32a3b2"
TOML = "fa267f1f-6049-4f14-aa54-33bafae1ed76"

[compat]
julia = "1.10"
MPI = "0.20"
StableRNGs = "1"

[extras]
Test = "8dfed614-e22c-5e08-85e1-65c5234f0b40"

[targets]
test = ["Test"]
```

Instantiate once to generate the declared dependency lock:

```bash
cd tracks/qmc/solutions/Only-team
julia --project=. -e 'using Pkg; Pkg.instantiate()'
```

- [ ] **Step 1.2: Create the three exact configurations**

`configs/baseline-triangular.toml`:

```toml
lattice = "triangular"
NumL1 = 6
NumL2 = 6
J1 = -1.0
J2 = 0.0
hTrfd = 4.768
BetaT = 6.0
IfSetDltau = true
FixedDltau = 0.02
LTrot = 400
nLocal = 0
nWolff = 5
nWarm = 3000
NmBin = 11
NSwep = 1000
NmMeaConfg = 5
discard_initial_bins = 1
trim_extrema = true
statistics_mode = "bin_sem"
seed = 20260728
initial_state = "random"
output_dir = "tracks/qmc/results/Only-team/baseline-triangular"
```

`configs/smoke-triangular.toml`:

```toml
lattice = "triangular"
NumL1 = 3
NumL2 = 3
J1 = -1.0
J2 = 0.0
hTrfd = 4.768
BetaT = 0.12
IfSetDltau = true
FixedDltau = 0.02
LTrot = 8
nLocal = 1
nWolff = 2
nWarm = 20
NmBin = 5
NSwep = 10
NmMeaConfg = 3
discard_initial_bins = 1
trim_extrema = true
statistics_mode = "bin_sem"
seed = 20260728
initial_state = "random"
output_dir = "tracks/qmc/results/Only-team/smoke-triangular"
```

`configs/smoke-honeycomb.toml`:

```toml
lattice = "honeycomb"
NumL1 = 3
NumL2 = 3
J1 = -1.0
J2 = 0.0
hTrfd = 2.1325
BetaT = 0.12
IfSetDltau = true
FixedDltau = 0.02
LTrot = 8
nLocal = 1
nWolff = 2
nWarm = 20
NmBin = 5
NSwep = 10
NmMeaConfg = 3
discard_initial_bins = 1
trim_extrema = true
statistics_mode = "bin_sem"
seed = 20260729
initial_state = "random"
output_dir = "tracks/qmc/results/Only-team/smoke-honeycomb"
```

- [ ] **Step 1.3: Write failing configuration tests**

Add a `config` test group selected by
`TFIM_TEST_GROUP=config`. It must assert:

```julia
@test cfg.input_LTrot == 400
@test cfg.LTrot == 300
@test cfg.Dltau == 0.02
@test cfg.J1 == -1.0
@test cfg.CpTau < 0
@test cfg.K_space > 0
@test cfg.K_tau > 0
@test_throws ArgumentError load_with(J1=0.0)
@test_throws ArgumentError load_with(J2=0.1)
@test_throws ArgumentError load_with(hTrfd=0.0)
@test_throws ArgumentError load_with(lattice="square")
@test_throws ArgumentError load_with(NumL1=2)
@test_throws ArgumentError load_with(statistics_mode="jackknife")
```

The test-only `load_with` helper starts from the baseline dictionary, applies
the supplied keyword overrides, writes a temporary TOML file below the ignored
result tree, and calls `load_config` with the known repository root.

Include separate assertions that a derived odd `LTrot` is raised to the next
even value, `NmMeaConfg` is checked against final `LTrot`, and an output path
outside the allowed result tree is rejected.

At the top of `runtests.jl`, use this group policy:

```julia
const TEST_GROUP = get(ENV, "TFIM_TEST_GROUP", "all")
run_group(name) = TEST_GROUP == "all" ||
                  TEST_GROUP == name ||
                  (TEST_GROUP == "fast" &&
                   name in ("config", "lattice", "weights", "cluster",
                            "measurement", "statistics", "driver"))
```

- [ ] **Step 1.4: Run the tests and confirm the expected failure**

Run:

```bash
cd tracks/qmc/solutions/Only-team
TFIM_TEST_GROUP=config julia --project=. test/runtests.jl
```

Expected: failure because `SimulationConfig` and `load_config` are undefined.

- [ ] **Step 1.5: Implement the minimum parser**

Implementation rules:

```julia
input_LTrot = Int(raw["LTrot"])
LTrot = raw["IfSetDltau"] ?
    ceil(Int, Float64(raw["BetaT"]) / Float64(raw["FixedDltau"])) :
    input_LTrot
LTrot = isodd(LTrot) ? LTrot + 1 : LTrot
Dltau = Float64(raw["BetaT"]) / LTrot
```

Use a stable evaluation of `CpTau`:

```julia
x = hTrfd * Dltau
log_tanh_x = log(-expm1(-2x)) - log1p(exp(-2x))
CpTau = 0.5 * log_tanh_x
K_space = -Dltau * J1
K_tau = -CpTau
p_space = -expm1(-2K_space)
p_tau = -expm1(-2K_tau)
```

After evaluation, require finite `CpTau`, `K_space`, and `K_tau`, with
`CpTau < 0`, `K_space > 0`, and `K_tau > 0`. If Float64 cannot resolve these
signs for an extreme input product, reject the configuration explicitly.

Resolve `output_dir` from the repository root with `abspath` and `normpath`,
then require it to be a strict descendant of
`tracks/qmc/results/Only-team/`.

- [ ] **Step 1.6: Run Task 1 tests**

Run:

```bash
TFIM_TEST_GROUP=config julia --project=. test/runtests.jl
```

Expected: all configuration tests pass. Report the number passed and stop for
user confirmation.

---

### Task 2: Unified triangular and honeycomb lattices

**Files:**

- Create: `tracks/qmc/solutions/Only-team/src/Lattices.jl`
- Modify: `tracks/qmc/solutions/Only-team/src/MinimalTFIM.jl`
- Modify: `tracks/qmc/solutions/Only-team/test/runtests.jl`

**Interfaces produced:**

```julia
struct Lattice
    kind::Symbol
    NumL1::Int
    NumL2::Int
    N::Int
    neighbors::Vector{Vector{Int}}
    bonds::Vector{NTuple{2,Int}}
end

build_lattice(kind::Symbol, NumL1::Int, NumL2::Int)::Lattice
validate_lattice(lattice::Lattice)::Nothing
```

- [ ] **Step 2.1: Write failing lattice tests**

For sizes `3×3`, `4×5`, and `6×6`, assert:

```julia
tri = build_lattice(:triangular, L1, L2)
@test tri.N == L1*L2
@test all(length(ns) == 6 for ns in tri.neighbors)
@test length(tri.bonds) == 3 * tri.N

hon = build_lattice(:honeycomb, L1, L2)
@test hon.N == 2L1*L2
@test all(length(ns) == 3 for ns in hon.neighbors)
@test length(hon.bonds) == 3 * hon.N ÷ 2
```

For both lattices, assert no self-neighbor, no duplicate neighbor, valid
indices, and reciprocal adjacency.

- [ ] **Step 2.2: Run and confirm failure**

```bash
TFIM_TEST_GROUP=lattice julia --project=. test/runtests.jl
```

Expected: failure because `build_lattice` is undefined.

- [ ] **Step 2.3: Implement periodic indexing and bond deduplication**

Use zero-based coordinates internally for the formulas and convert to Julia
indices at the boundary. Construct `neighbors` first; obtain `bonds` by adding
`(min(i,j),max(i,j))` to a set and sorting the final vector.

Triangular displacements:

```julia
((-1,0), (-1,1), (0,1), (1,0), (1,-1), (0,-1))
```

Honeycomb links:

```julia
A(x,y) => ((x,y,:B), (x-1,y,:B), (x,y-1,:B))
B(x,y) => ((x,y,:A), (x+1,y,:A), (x,y+1,:A))
```

Call `validate_lattice` before returning.

- [ ] **Step 2.4: Run Task 2 tests**

```bash
TFIM_TEST_GROUP=lattice julia --project=. test/runtests.jl
```

Expected: all lattice tests pass. Report and wait.

---

### Task 3: Complete test weight and local Metropolis update

**Files:**

- Create: `tracks/qmc/solutions/Only-team/src/Weights.jl`
- Create: `tracks/qmc/solutions/Only-team/src/Updates.jl`
- Modify: `tracks/qmc/solutions/Only-team/src/MinimalTFIM.jl`
- Modify: `tracks/qmc/solutions/Only-team/test/runtests.jl`

**Interfaces produced:**

```julia
mutable struct UpdateDiagnostics
    local_attempts::Int
    local_accepts::Int
    cluster_size_sum::Int
    cluster_count::Int
end

mutable struct SimulationState
    spins::Matrix{Int8}
    diagnostics::UpdateDiagnostics
end

tau_minus(tau::Int, LTrot::Int)::Int
tau_plus(tau::Int, LTrot::Int)::Int
initialize_state(config::SimulationConfig, lattice::Lattice, rng)::SimulationState
reset_diagnostics!(diagnostics::UpdateDiagnostics)::Nothing
total_log_weight(spins, lattice::Lattice, config::SimulationConfig)::Float64
local_terms(spins, site::Int, tau::Int, lattice::Lattice, config::SimulationConfig)
local_sweep!(state::SimulationState, lattice::Lattice, config::SimulationConfig, rng)::Nothing
```

- [ ] **Step 3.1: Write failing weight and initialization tests**

Test:

```julia
@test tau_minus(1, 6) == 6
@test tau_plus(6, 6) == 1
@test sort(unique(vec(random_state.spins))) == Int8[-1, 1]
@test all(==(Int8(1)), ordered_state.spins)
@test size(state.spins) == (lattice.N, config.LTrot)
```

For at least 20 random configurations per lattice and 20 random spacetime
sites per configuration:

```julia
before = total_log_weight(spins, lattice, config)
IsSpin, Rtp0 = local_terms(spins, site, tau, lattice, config)
spins[site,tau] = -spins[site,tau]
after = total_log_weight(spins, lattice, config)
@test isapprox(after-before, -2*IsSpin*Rtp0; rtol=1e-13, atol=1e-14)
```

- [ ] **Step 3.2: Add fixed local regressions**

Assert the exact anchors from `DESIGN.md`, including both `IsSpin=+1` and
`IsSpin=-1`.

- [ ] **Step 3.3: Run and confirm failure**

```bash
TFIM_TEST_GROUP=weights julia --project=. test/runtests.jl
```

Expected: failure because weight and update interfaces are undefined.

- [ ] **Step 3.4: Implement the complete weight and local sweep**

`total_log_weight` iterates `lattice.bonds` once per time slice and each
temporal forward bond once per site and time slice.

`local_sweep!` uses:

```julia
if delta_log_weight >= 0 || rand(rng) < exp(delta_log_weight)
    state.spins[site,tau] = -IsSpin
    state.diagnostics.local_accepts += 1
end
state.diagnostics.local_attempts += 1
```

The traversal order is exactly time outer, site inner.
`reset_diagnostics!` sets all four counters to zero at the start of each
production bin. The driver separately accumulates their integer totals across
all bins.

- [ ] **Step 3.5: Run Task 3 tests**

```bash
TFIM_TEST_GROUP=weights julia --project=. test/runtests.jl
```

Expected: all initialization, periodic-time, formula, and local-update tests
pass. Report and wait.

---

### Task 4: Basic single-cluster Wolff update

**Files:**

- Modify: `tracks/qmc/solutions/Only-team/src/Updates.jl`
- Modify: `tracks/qmc/solutions/Only-team/test/runtests.jl`

**Interfaces produced:**

```julia
should_add(candidate_spin::Int8, cluster_spin::Int8,
           visited::Bool, probability::Float64, uniform_draw::Float64)::Bool
build_cluster(state::SimulationState, lattice::Lattice,
              config::SimulationConfig, rng)::Vector{Int}
wolff_update!(state::SimulationState, lattice::Lattice,
              config::SimulationConfig, rng)::Int
update_cycle!(state::SimulationState, lattice::Lattice,
              config::SimulationConfig, rng)::Nothing
```

- [ ] **Step 4.1: Write failing probability and membership tests**

Assert:

```julia
@test !should_add(Int8(1), Int8(-1), false, 1.0, 0.0)
@test !should_add(Int8(1), Int8(1), true, 1.0, 0.0)
@test !should_add(Int8(1), Int8(1), false, 0.0, 0.0)
@test should_add(Int8(1), Int8(1), false, 1.0, prevfloat(1.0))
```

For fixed seeds on both lattices:

```julia
members = build_cluster(state, lattice, config, rng)
@test length(members) == length(unique(members))
@test all(1 <= idx <= length(state.spins) for idx in members)
```

Verify that a zero-probability synthetic configuration returns only the seed
and an all-aligned unit-probability synthetic configuration reaches the entire
connected spacetime lattice.

- [ ] **Step 4.2: Run and confirm failure**

```bash
TFIM_TEST_GROUP=cluster julia --project=. test/runtests.jl
```

- [ ] **Step 4.3: Implement stack-based cluster construction**

Map a linear spacetime index with:

```julia
site = mod1(index, lattice.N)
tau = fld(index - 1, lattice.N) + 1
index = site + (tau - 1)*lattice.N
```

Mark a candidate before pushing it. Check every spatial neighbor with
`p_space`, then `tau_minus` and `tau_plus` with `p_tau`. Flip members only
after the cluster is complete. Do not perform a final acceptance test.

`update_cycle!` calls `nLocal` complete sweeps followed by `nWolff` cluster
updates, preserving zero counts.

- [ ] **Step 4.4: Run Task 4 tests**

```bash
TFIM_TEST_GROUP=cluster julia --project=. test/runtests.jl
```

Expected: all cluster and update-order tests pass. Report and wait.

---

### Task 5: Segmented imaginary-time measurements

**Files:**

- Create: `tracks/qmc/solutions/Only-team/src/Measurements.jl`
- Modify: `tracks/qmc/solutions/Only-team/src/MinimalTFIM.jl`
- Modify: `tracks/qmc/solutions/Only-team/test/runtests.jl`

**Interfaces produced:**

```julia
mutable struct BinAccumulator
    m2_sum::Float64
    m4_sum::Float64
    measurement_count::Int
end

tau_segments(LTrot::Int, count::Int)::Vector{UnitRange{Int}}
sample_measurement_slices(segments, rng)::Vector{Int}
measure_at_slices(spins::Matrix{Int8}, slices::Vector{Int})
measure!(accumulator::BinAccumulator, state::SimulationState,
         segments, rng)::Nothing
```

- [ ] **Step 5.1: Write failing segmentation tests**

For `(LTrot,NmMeaConfg)=(10,3)`, require segment lengths `[4,3,3]`,
nonoverlap, and exact union `1:10`. Repeat for divisible and single-segment
cases.

Use a hand-constructed spin matrix and fixed slices to assert:

```julia
expected_m2 = mean((sum(spins[:,tau])/N)^2 for tau in slices)
expected_m4 = mean((sum(spins[:,tau])/N)^4 for tau in slices)
@test measure_at_slices(spins, slices) == (expected_m2, expected_m4)
```

Add a counterexample where squaring the time-averaged magnetization gives a
different result.

- [ ] **Step 5.2: Run and confirm failure**

```bash
TFIM_TEST_GROUP=measurement julia --project=. test/runtests.jl
```

- [ ] **Step 5.3: Implement segmentation and measurement**

Use:

```julia
base, remainder = divrem(LTrot, count)
length_k = base + (k <= remainder)
```

Sample one integer uniformly from each range with the explicit RNG.
`measure!` increments its count exactly once.

- [ ] **Step 5.4: Run Task 5 tests**

```bash
TFIM_TEST_GROUP=measurement julia --project=. test/runtests.jl
```

Expected: all measurement tests pass. Report and wait.

---

### Task 6: Bin records, filtering, and standard errors

**Files:**

- Create: `tracks/qmc/solutions/Only-team/src/Statistics.jl`
- Modify: `tracks/qmc/solutions/Only-team/src/MinimalTFIM.jl`
- Modify: `tracks/qmc/solutions/Only-team/test/runtests.jl`

**Interfaces produced:**

```julia
struct BinRecord
    bin::Int
    m2::Float64
    m4::Float64
    Q::Float64
end

bin_record(bin::Int, m2::Float64, m4::Float64)::BinRecord
bin_sem(values::Vector{Float64})::NamedTuple
filter_series(records::Vector{BinRecord}, field::Symbol,
              discard::Int, trim::Bool)::NamedTuple
summarize_bins(records::Vector{BinRecord}, config::SimulationConfig)::NamedTuple
```

- [ ] **Step 6.1: Write failing formula tests**

Assert:

```julia
record = bin_record(1, 0.25, 0.125)
@test record.Q == 0.5
```

For `x=[1.0,2.0,4.0,7.0]`, compare `bin_sem` to:

```julia
mu = sum(x)/length(x)
err = sqrt(sum((x .- mu).^2)/(length(x)*(length(x)-1)))
```

Create bin records where `m2` and `Q` extrema occur at different bin numbers.
Assert initial removal occurs first and each series removes its own minimum
and maximum.

- [ ] **Step 6.2: Run and confirm failure**

```bash
TFIM_TEST_GROUP=statistics julia --project=. test/runtests.jl
```

- [ ] **Step 6.3: Implement independent filtering**

Do not mutate the input records. Return values plus retained and removed bin
indices. Throw `ArgumentError` if fewer than two samples remain.

- [ ] **Step 6.4: Run Task 6 tests**

```bash
TFIM_TEST_GROUP=statistics julia --project=. test/runtests.jl
```

Expected: all statistics tests pass. Report and wait.

---

### Task 7: MPI independent-chain driver and output policy

**Files:**

- Create: `tracks/qmc/solutions/Only-team/src/MPIDriver.jl`
- Create: `tracks/qmc/solutions/Only-team/scripts/run.jl`
- Modify: `tracks/qmc/solutions/Only-team/src/MinimalTFIM.jl`
- Modify: `tracks/qmc/solutions/Only-team/test/runtests.jl`

**Interfaces produced:**

```julia
deterministic_seed(base_seed::UInt64, rank::Integer)::UInt64
reduce_bin(bin::Int, m2_rank::Float64, m4_rank::Float64,
           comm)::Union{Nothing,BinRecord}
prepare_output_directory(path::AbstractString, comm)::Nothing
write_results(path, config, summary, records, diagnostics, seeds, wall_time)::Nothing
run_simulation(config::SimulationConfig, comm=MPI.COMM_WORLD)::Union{Nothing,NamedTuple}
```

- [ ] **Step 7.1: Write failing seed and serial-driver tests**

Assert four distinct rank seeds from one base seed and exact repeatability.
Run a tiny configuration twice under `MPI.COMM_SELF`, each to a fresh empty
result directory, then compare `bins.csv` and `results.csv` byte for byte.

Assert a nonempty output directory produces a clear error before sampling.

- [ ] **Step 7.2: Run and confirm failure**

```bash
TFIM_TEST_GROUP=driver julia --project=. test/runtests.jl
```

- [ ] **Step 7.3: Implement the rank-local loop**

The exact loop is:

```julia
for _ in 1:config.nWarm
    update_cycle!(state, lattice, config, rng)
end

for bin in 1:config.NmBin
    reset diagnostics and measurement accumulator
    for _ in 1:config.NSwep
        update_cycle!(state, lattice, config, rng)
        measure!(accumulator, state, segments, rng)
    end
    @assert accumulator.measurement_count == config.NSwep
    reduce rank-local m2 and m4
end
```

Use fixed two-element `Float64` send and receive buffers for each bin
reduction. Root divides both sums by `MPI.Comm_size(comm)` and computes Q.
Do not reduce a per-rank Q.

- [ ] **Step 7.4: Implement root-only output**

`results.csv` has exactly:

```text
lattice,NumL1,NumL2,NumNS,J1,J2,hTrfd,BetaT,LTrot,Dltau,nprocs,total_measurements,m2,m2_error,binder_Q,binder_Q_error,statistics_mode
```

`bins.csv` has exactly:

```text
bin,m2_bin,m4_bin,Q_bin
```

`metadata.toml` includes raw and actual parameters, couplings, probabilities,
Julia version, MPI size, rank seeds, sampling counts, filter counts,
diagnostics, wall time, and a safely queried Git commit.

Reduce diagnostic counts and sums at each bin and accumulate them on root.
When local attempts are zero, serialize `local_acceptance` as
`"not_applicable"`; when cluster count is zero, serialize both cluster means
as `"not_applicable"`. Otherwise:

```text
local_acceptance = total_local_accepts/total_local_attempts
mean_cluster_size = total_cluster_size/total_cluster_count
mean_cluster_fraction =
    total_cluster_size/(total_cluster_count*NumNS*LTrot)
```

Reduce elapsed wall time with `MPI.MAX`, so metadata reports the slowest rank
rather than rank zero's local duration.

- [ ] **Step 7.5: Implement the command entry point**

`scripts/run.jl` accepts exactly one configuration path, initializes MPI when
needed, calls `run_simulation`, reports errors on rank zero, and finalizes MPI
in a `finally` block.

- [ ] **Step 7.6: Run Task 7 serial tests**

```bash
TFIM_TEST_GROUP=driver julia --project=. test/runtests.jl
```

Expected: serial driver, output schema, overwrite rejection, and exact
repeatability tests pass. Report and wait.

---

### Task 8: Fixed numerical regressions and MPI smoke tests

**Files:**

- Modify: `tracks/qmc/solutions/Only-team/test/runtests.jl`
- Modify if required by a failing formula test:
  `tracks/qmc/solutions/Only-team/src/Weights.jl`
- Modify if required by a failing MPI test:
  `tracks/qmc/solutions/Only-team/src/MPIDriver.jl`

**Interfaces consumed:** All Task 1–7 interfaces.

- [ ] **Step 8.1: Consolidate fixed Float64 regressions**

For `J1=-1`, `J2=0`, `hTrfd=4.768`, `Dltau=0.02`, assert every numerical
anchor in `DESIGN.md` with `rtol=1e-13`, `atol=1e-14`. These tests must use
production functions, not duplicate formulas.

- [ ] **Step 8.2: Install the MPI.jl launcher**

Run:

```bash
julia --project=. -e 'using MPI; MPI.install_mpiexecjl()'
```

Confirm the printed launcher path and store it in a shell variable used only
for the following commands.

- [ ] **Step 8.3: Run one-rank and two-rank smoke tests**

Use test-generated unique output directories under the ignored result tree:

```bash
TFIM_TEST_GROUP=mpi JULIA_MPI_TEST_NPROCS=1 julia --project=. test/runtests.jl
TFIM_TEST_GROUP=mpi JULIA_MPI_TEST_NPROCS=2 julia --project=. test/runtests.jl
```

The test runner launches `scripts/run.jl` through MPI.jl's launcher and checks:

- process exit status is zero;
- metadata reports the requested MPI size;
- rank seeds are distinct;
- `bins.csv` has `NmBin` data rows;
- only one copy of each common output exists;
- `total_measurements=nprocs*NmBin*NSwep`.

- [ ] **Step 8.4: Run deterministic suite**

```bash
TFIM_TEST_GROUP=fast julia --project=. test/runtests.jl
```

Expected: all Tasks 1–8 deterministic and MPI tests pass. Report exact totals
and wait.

---

### Task 9: Independent small-system and equilibration benchmarks

**Files:**

- Modify: `tracks/qmc/solutions/Only-team/test/runtests.jl`
- Create generated data only under:
  `tracks/qmc/results/Only-team/`

**Interfaces produced only inside tests:**

```julia
exact_small_system_moments(config::SimulationConfig, lattice::Lattice)
combined_error_agreement(a, ea, b, eb; zmax=5.0)::Bool
```

- [ ] **Step 9.1: Estimate compute before running**

Use the exact enumeration size:

```text
triangular 3×3, LTrot=2
spacetime spins=18
configurations=2^18=262144
```

Estimate enumeration operations and the proposed Monte Carlo sweep count.
Proceed locally only if the estimate is below ten minutes and 16 GB.

- [ ] **Step 9.2: Implement the exact test-only benchmark**

Enumerate all `2^18` states. For each state, compute `logW` with the production
`total_log_weight`, subtract the maximum log weight before exponentiating, and
accumulate normalized `m2` and `m4` using both time slices. Save the resulting
numbers as test-local values, not production output.

- [ ] **Step 9.3: Add the stochastic comparison**

Use a predeclared five-standard-error rule:

```julia
@test abs(mc_m2-exact_m2) <= 5 * mc_m2_error
@test abs(mc_Q-exact_Q) <= 5 * mc_Q_error
```

The Monte Carlo test must use enough bins for the declared trimming policy and
a fixed seed. Do not change the acceptance rule after seeing the result.

- [ ] **Step 9.4: Add ordered-versus-random comparison**

Run otherwise identical fixed-seed configurations and assert:

```julia
abs(a-b) <= 5 * sqrt(ea^2+eb^2)
```

for both `m2` and Q after the declared warmup.

- [ ] **Step 9.5: Run statistical tests**

```bash
TFIM_TEST_GROUP=statistical julia --project=. test/runtests.jl
```

If a test fails, first inspect warmup traces, exact-anchor consistency, and
sampling code. Consult the user-designated diagnostic material only after
these independent checks fail. Any change to warmup or sample count is
reported before rerunning.

Expected: both statistical comparisons pass without altering formula
tolerances. Report estimates, errors, z-scores, wall time, and wait.

---

### Task 10: Documentation, policy scans, and fresh-environment rerun

**Files:**

- Modify: `tracks/qmc/solutions/Only-team/README.md`
- Modify if documentation reveals an interface mismatch:
  the directly affected source or test file only

**Interfaces consumed:** Final commands, configuration fields, and output
schemas from Tasks 1–9.

- [ ] **Step 10.1: Extend README without removing registration**

Add:

- Hamiltonian and raw `J1=-1` convention;
- discrete imaginary-time mapping and effective log weight;
- `CpTau`, local ratio, and both cluster probabilities;
- both periodic lattice definitions;
- warmup, bin, sweep, update, and measurement ordering;
- MPI independent-chain behavior;
- `m2` and Q definitions;
- filtering and SEM formula;
- serial, MPI, and test commands;
- output files and non-overwrite policy;
- finite `Dltau` limitation;
- explicit first-release exclusions.

- [ ] **Step 10.2: Add static policy tests**

Scan the implementation tree for:

- drive-letter absolute paths;
- the prohibited naming-policy patterns defined by the approved design;
- unexpected files outside the locked file map.

Construct naming patterns from code points so the test source does not contain
the strings it rejects:

```julia
forbidden_terms = [
    String(Char.([0x79fb, 0x690d])),
    String(Char.([0x65e7, 0x4ee3, 0x7801])),
    String(Char.([0x6c, 0x65, 0x67, 0x61, 0x63, 0x79])),
    String(Char.([0x66, 0x6f, 0x72, 0x74, 0x72, 0x61, 0x6e])),
    String(Char.([0x70, 0x6f, 0x72, 0x74, 0x65, 0x64])),
    String(Char.([0x70, 0x6f, 0x72, 0x74, 0x69, 0x6e, 0x67])),
    String(Char.([0x74, 0x72, 0x61, 0x6e, 0x73, 0x6c, 0x61, 0x74, 0x65, 0x64])),
]
```

Apply a case-insensitive whole-word rule to English patterns and a direct
substring rule to the two non-Latin patterns. Scan filenames and readable
text under `README.md`, `src/`, `configs/`, `scripts/`, and `test/`, then scan
the smoke-run CSV and TOML outputs. `Project.toml` and `Manifest.toml` are
dependency metadata, not public algorithm text. `DESIGN.md` and
`IMPLEMENTATION_PLAN.md` remain subject to path and placeholder checks.

- [ ] **Step 10.3: Run all tests**

```bash
julia --project=. test/runtests.jl
```

Expected: fast, serial, output, and statistical groups pass.

- [ ] **Step 10.4: Verify a fresh project environment**

Create a temporary Julia depot under the ignored result tree and instantiate
without altering tracked files:

```bash
mkdir -p ../../results/Only-team
TFIM_TEST_DEPOT="$(mktemp -d ../../results/Only-team/fresh-depot.XXXXXX)"
JULIA_DEPOT_PATH="$TFIM_TEST_DEPOT" julia --project=. -e 'using Pkg; Pkg.instantiate(); Pkg.test()'
```

Keep the temporary depot as generated test output. Cleanup, if requested,
targets only the printed explicit directory.

- [ ] **Step 10.5: Run final one-rank and two-rank smoke configurations**

Copy each smoke configuration to a test-generated file with a new empty output
directory, then run the same entry point with one and two ranks. Inspect
`results.csv`, `bins.csv`, and `metadata.toml`.

- [ ] **Step 10.6: Audit repository scope**

Run:

```bash
git status --short
git diff -- tracks/qmc/solutions/Only-team/
git diff --check -- tracks/qmc/solutions/Only-team/
```

Confirm:

- only approved solution files are new or modified;
- generated results remain ignored;
- pre-existing `.knowledge/` changes are still present and untouched;
- there is no staged content;
- no commit or remote action occurred.

- [ ] **Step 10.7: Present completion evidence and stop**

Report:

- deterministic test total;
- MPI one-rank and two-rank status;
- ordered/random comparison;
- exact small-system comparison;
- wall times;
- created source and documentation paths;
- serial and MPI rerun commands.

Wait for explicit user approval before any staging, commit, push, or update to
pull request #224.

## Plan self-review checklist

Before Task 1 execution:

- [ ] Every requirement in `DESIGN.md` maps to one task above.
- [ ] Function signatures are identical where produced and consumed.
- [ ] No implementation step writes outside the two allowed trees.
- [ ] No step stages or changes existing `.knowledge/` files.
- [ ] Fixed numerical regressions use production formulas.
- [ ] The MPI test uses the same `scripts/run.jl` path as normal runs.
- [ ] Statistical tolerances are declared before results are seen.
- [ ] No placeholder or deferred requirement remains.

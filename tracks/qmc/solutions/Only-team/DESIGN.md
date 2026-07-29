# Minimal discrete-imaginary-time cluster Monte Carlo design

## Objective and scope

Implement a minimal, independent, verifiable Julia program for the
two-dimensional ferromagnetic transverse-field Ising model:

```text
H = J1 Σ_<i,j> σz_i σz_j - hTrfd Σ_i σx_i
```

The sign and parameter conventions are binding:

- `J1 < 0`; `J1 = -1` is a ferromagnetic coupling of strength one.
- `J2 = 0`.
- `hTrfd > 0`.
- Spatial and imaginary-time boundary conditions are periodic.
- Supported lattices are `triangular` and `honeycomb`.
- The simulation samples the full configuration space rather than a fixed
  Z2 symmetry sector.
- The primary observables are ferromagnetic `m2` and the Binder moment ratio
  `Q = <m2>^2/<m4>`.

The implementation is a discrete-imaginary-time cluster Monte Carlo program
for the transverse-field Ising model. It is not SSE and does not implement a
continuous-time algorithm.

## Allowed paths and repository boundaries

Source and documentation are confined to:

```text
tracks/qmc/solutions/Only-team/
```

Generated results are confined to:

```text
tracks/qmc/results/Only-team/
```

The result tree is gitignored and is never force-added. Existing changes under
`.knowledge/` remain untouched and are excluded from any future staging.
There is no commit, push, or pull-request update until all required tests pass
and the user explicitly approves it. Any later update targets the existing
pull request #224.

## Architecture

Use one top-level `MinimalTFIM` module with focused source files included into
that module. This keeps configuration, geometry, weights, updates,
measurements, statistics, and MPI orchestration independently testable without
introducing a hierarchy of subpackages.

Planned files:

```text
tracks/qmc/solutions/Only-team/
├── DESIGN.md
├── Project.toml
├── Manifest.toml
├── README.md
├── configs/
│   ├── baseline-triangular.toml
│   ├── smoke-triangular.toml
│   └── smoke-honeycomb.toml
├── src/
│   ├── MinimalTFIM.jl
│   ├── Config.jl
│   ├── Lattices.jl
│   ├── Weights.jl
│   ├── Updates.jl
│   ├── Measurements.jl
│   ├── Statistics.jl
│   └── MPIDriver.jl
├── scripts/
│   └── run.jl
└── test/
    └── runtests.jl
```

`Project.toml` contains compatibility bounds for Julia, MPI.jl, and
StableRNGs.jl; `Manifest.toml` records the instantiated dependency set.
Random-number generation, TOML parsing, numerical summaries, timing, CSV
serialization, and tests otherwise use Julia standard libraries.
The existing README keeps its team and challenge registration and gains the
scientific, algorithmic, test, and run documentation described here.

## Configuration and derived parameters

The TOML parser validates:

- `lattice` is `triangular` or `honeycomb`.
- `NumL1 >= 3` and `NumL2 >= 3`.
- `J1 < 0`, `J2 == 0`, and `hTrfd > 0`.
- `BetaT > 0`, `FixedDltau > 0`, and input `LTrot > 0`.
- `nLocal`, `nWolff`, `nWarm`, `NmBin`, and `NSwep` are nonnegative.
- `1 <= NmMeaConfg <= LTrot`.
- `0 <= discard_initial_bins < NmBin`.
- `statistics_mode == "bin_sem"`.
- `initial_state` is `random` or `ordered`.
- `output_dir` is inside `tracks/qmc/results/Only-team/`.

Parameter derivation is:

```text
if IfSetDltau
    LTrot = ceil(Int, BetaT/FixedDltau)
end
if isodd(LTrot)
    LTrot += 1
end
Dltau = BetaT/LTrot
```

For `BetaT=6`, `FixedDltau=0.02`, `IfSetDltau=true`, and input
`LTrot=400`, the result is `LTrot=300` and `Dltau=0.02`.

The configuration object retains the raw input values as well as the final
values. In particular, metadata distinguishes input `LTrot`, final `LTrot`,
`FixedDltau`, and actual `Dltau`.

The parser accepts the specified nonnegative count domain. Before a production
run, the driver additionally checks that:

- `NSwep > 0`;
- after initial-bin removal, at least two bins remain when extrema are not
  trimmed;
- before extrema trimming, at least four bins remain, leaving at least two
  afterward.

Each run rejects an existing nonempty output directory. Only rank zero checks
and creates the directory; it broadcasts success or failure before other ranks
proceed.

## Lattice representation

The shared lattice object provides:

```julia
lattice.N
lattice.neighbors
lattice.bonds
```

`neighbors` stores the complete symmetric adjacency list. `bonds` stores every
undirected spatial bond exactly once. Monte Carlo updates only use this shared
interface.

### Triangular lattice

Sites have coordinates `x=0:NumL1-1`, `y=0:NumL2-1`, with
`N=NumL1*NumL2`. The six neighbor displacements are:

```text
(-1,0), (-1,+1), (0,+1), (+1,0), (+1,-1), (0,-1)
```

Coordinates are reduced modulo the two lattice lengths. Construction verifies
degree six, no self-edge, no duplicate neighbor, symmetric adjacency, and
`3N` undirected bonds.

### Honeycomb lattice

Each unit cell contains `A(x,y)` and `B(x,y)`, with
`N=2*NumL1*NumL2`. Adjacency is:

```text
A(x,y): B(x,y), B(x-1,y), B(x,y-1)
B(x,y): A(x,y), A(x+1,y), A(x,y+1)
```

Coordinates are periodic. Construction verifies degree three, no self-edge,
no duplicate neighbor, symmetric adjacency, and `3N/2` undirected bonds.

## State and random-number generation

The state is:

```julia
spins::Matrix{Int8}
```

with shape `N × LTrot` and values restricted to `-1` and `+1`.
`random` initialization samples each element independently; `ordered`
initialization fills the matrix with `+1`.

Every stochastic function receives its RNG explicitly. A stable integer
mixing function maps `(base_seed, rank)` to a distinct `UInt64`; each rank
constructs a `StableRNG` from that value. Metadata records every rank seed.

## Effective weight

For `x = hTrfd*Dltau`, define:

```text
CpTau   = 0.5*log(tanh(x))
K_space = -Dltau*J1
K_tau   = -CpTau
```

The implementation may evaluate `log(tanh(x))` through an algebraically
equivalent stable expression so that large positive `x` does not round
`CpTau` to zero. Valid parameters satisfy `CpTau < 0`, `K_space > 0`, and
`K_tau > 0`.

The effective classical log weight is:

```text
logW =
    -Dltau*J1*Σ_(spatial bond, tau) spins[i,tau]*spins[j,tau]
    -CpTau*Σ_(site, tau) spins[site,tau]*spins[site,tau_plus]
```

`total_log_weight` evaluates this expression directly only for tests.

## Local Metropolis update

A complete local sweep visits `tau` in the outer loop and `site` in the inner
loop. At the selected spin:

```text
IsSpin = spins[site,tau]
I1 = Σ_(j in neighbors[site]) spins[j,tau]
I2 = 0
I3 = spins[site,tau_minus] + spins[site,tau_plus]

Rtp0 = -Dltau*(J1*I1 + J2*I2) - CpTau*I3
delta_log_weight = -2*IsSpin*Rtp0
```

If `delta_log_weight >= 0`, the flip is accepted. Otherwise it is accepted
when `rand(rng) < exp(delta_log_weight)`. The update records attempted and
accepted flips during production bins.

The exact-difference test temporarily flips one spin and verifies:

```text
total_log_weight(after) - total_log_weight(before)
≈ delta_log_weight
```

for random configurations of both lattices.

For `J1=-1`, `J2=0`, `hTrfd=4.768`, and `Dltau=0.02`, fixed regressions are:

```text
CpTau   ≈ -1.17656041848794
K_space ≈  0.02000000000000
K_tau   ≈  1.17656041848794

p_space ≈ 0.0392105608476768
p_tau   ≈ 0.904928005445148
```

For a triangular all-aligned local environment with `IsSpin=+1`, `I1=6`,
`I2=0`, and `I3=2`:

```text
Rtp0              ≈  2.47312083697588
delta_log_weight  ≈ -4.94624167395176
weight_ratio      ≈  0.00711008077869917
accept_probability ≈ 0.00711008077869917
```

Changing only `IsSpin` to `-1` gives:

```text
weight_ratio       ≈ 140.645378178525
accept_probability = 1.0
```

## Wolff cluster update

Bond-addition probabilities are:

```text
p_space = 1 - exp(-2*abs(J1)*Dltau)
p_tau   = 1 - exp(-2*abs(CpTau))
```

They may be evaluated as `-expm1(-2K)` for small-coupling stability.

The update uses an integer-index stack, a `BitMatrix` membership marker, and a
member vector:

```text
choose one uniform seed from 1:N*LTrot
record the seed spin and mark the seed
push the seed on the stack

while the stack is nonempty
    pop one spacetime site
    inspect every spatial neighbor
    inspect tau_minus and tau_plus
    if the candidate is unmarked, has the seed spin,
       and its bond trial succeeds:
        mark it and push it
end

flip every marked member
return cluster size
```

Each spacetime site enters at most once. There is no final Metropolis test.
Production diagnostics record cluster count, total cluster size, mean cluster
size, and mean cluster fraction.

## Update and sampling loop

Warmup and production use the same update ordering:

```text
update_cycle:
    nLocal complete local sweeps
    nWolff single-cluster updates
```

The driver is:

```text
initialize once

for warm_step in 1:nWarm
    update_cycle
end

for bin in 1:NmBin
    reset bin accumulators

    for sweep in 1:NSwep
        update_cycle
        measure
    end

    finalize rank-local bin
    reduce bin means to rank zero
    finalize global bin on rank zero
end

filter bins and write final statistics on rank zero
```

Warmup does not measure and does not contribute to reported diagnostics.
The baseline configuration keeps `nLocal=0`, `nWolff=5` exactly.

## Imaginary-time measurement

At setup, `1:LTrot` is divided into `NmMeaConfg` contiguous, nonoverlapping
segments. If division has a remainder, the earliest segments receive one
additional slice. The union of the segments is exactly `1:LTrot`.

For each production measurement, one imaginary-time slice is sampled uniformly
from each segment. For every selected slice:

```text
m_tau = Σ_i spins[i,tau]/N
```

The configuration estimators are:

```text
m2_config = mean(m_tau^2 over selected tau)
m4_config = mean(m_tau^4 over selected tau)
```

Each rank accumulates `m2_config` and `m4_config` once per production sweep.

## MPI independent chains

Each rank reads the same configuration, constructs the full lattice and spin
matrix, uses its own deterministic seed, performs a complete warmup, and runs
all bins and sweeps independently. There is no spatial decomposition and no
barrier between sweeps.

At the end of each bin:

```text
m2_rank_bin = m2_sum/measurement_count
m4_rank_bin = m4_sum/measurement_count

m2_bin = sum_over_ranks(m2_rank_bin)/nprocs
m4_bin = sum_over_ranks(m4_rank_bin)/nprocs
Q_bin  = m2_bin^2/m4_bin
```

All ranks have `measurement_count=NSwep`. Only rank zero stores global bins and
writes shared output. Diagnostic totals are reduced from counts and sums rather
than by averaging per-rank ratios.

The program supports the same entry point under one or multiple ranks. The
test environment may use MPI.jl's launcher when a system MPI launcher is not
installed; the program remains compatible with a standard MPI launcher.

## Bin statistics

After all formal bins:

1. Remove the first `discard_initial_bins` bins.
2. Form independent `m2_bin` and `Q_bin` sequences.
3. If `trim_extrema=true`, sort each sequence independently and remove one
   minimum and one maximum.
4. Compute each remaining sequence's mean and standard error.

For a sequence `x` of length `n`:

```text
mean = Σx/n
error = sqrt(Σ(x-mean)^2/(n*(n-1)))
```

The `m2` and `Q` filters may remove different bin numbers. Metadata records
the mode, initial-bin count, trimming flag, counts before and after filtering,
and the retained or removed bin indices.

## Output

Only rank zero writes:

- `results.csv`, containing
  `lattice,NumL1,NumL2,NumNS,J1,J2,hTrfd,BetaT,LTrot,Dltau,nprocs,`
  `total_measurements,m2,m2_error,binder_Q,binder_Q_error,statistics_mode`;
- `bins.csv`, containing `bin,m2_bin,m4_bin,Q_bin`;
- `metadata.toml`, containing raw input, derived parameters, couplings,
  probabilities, runtime environment, rank seeds, update diagnostics, wall
  time, and the Git commit when it can be read safely.

When no local update was requested, metadata records local attempts and
accepts as zero and the acceptance ratio as `not_applicable`; it never reports
a misleading numeric zero. The same rule applies to cluster means when no
cluster update was requested.

`total_measurements` is defined as:

```text
nprocs*NmBin*NSwep
```

It counts generated production configuration estimates before bin filtering.

## Verification design

### Fast deterministic tests

1. Triangular degree is six.
2. Triangular undirected bond count is `3N`.
3. Honeycomb degree is three.
4. Honeycomb undirected bond count is `3N/2`.
5. Both lattices have no self-edge, duplicate neighbor, or asymmetric edge.
6. Imaginary-time boundary indexing is periodic.
7. `CpTau` matches the fixed numerical regression.
8. `K_space` and `K_tau` match the fixed numerical regression.
9. `p_space` and `p_tau` match the fixed numerical regression.
10. Local `Rtp0` matches the fixed numerical regression.
11. Local weight ratios match the two fixed-spin regressions.
12. Local acceptance probabilities match the fixed regressions.
13. The local formula matches the complete log-weight difference on both
    lattices over multiple random cases.
14. Cluster members are unique.
15. Cluster spacetime indices are valid.
16. Spatial and temporal cluster trials obey their probabilities, including
    deterministic zero- and one-probability boundaries.
17. A fixed-seed serial run is exactly reproducible.
18. Segmented imaginary-time measurement computes the mean of per-slice
    second and fourth powers.
19. `Q_bin=m2_bin^2/m4_bin`.
20. The bin standard-error formula matches a hand-computed case.
21. Initial-bin removal selects the expected bins.
22. Independent extrema trimming selects the expected `m2` and `Q` values.
27. A nonempty output directory is rejected.
28. Runtime files contain no platform-specific absolute path.
29. Names, documentation, comments, configurations, and emitted labels pass
    the naming-policy scan.

### MPI integration tests

23. A one-rank smoke run completes through the MPI driver.
24. A two-rank smoke run completes, uses distinct seeds, and has only rank
    zero write common output.

### Statistical tests

25. Ordered and random initial states agree after sufficient warmup according
    to a predeclared combined-error criterion.
26. A small triangular-lattice run agrees with a fixed independent benchmark
    within its predeclared statistical tolerance.

The preferred independent benchmark is obtained by enumerating a sufficiently
small spacetime system using `total_log_weight`, then saving the resulting
number as a fixed test anchor. External diagnostic material is consulted only
if this independent check fails.

Statistical tests run separately from the fast deterministic suite. Fixed
formula regressions retain `rtol <= 1e-13` and `atol <= 1e-14`; their
tolerances are not relaxed to hide sign or probability errors.

## Explicit exclusions

The first release does not implement:

- SSE or any continuous-time method;
- `J2`, antiferromagnetic, or frustrated interactions;
- energy, correlation length, or dynamic observables;
- tau-segment cluster optimization;
- Swendsen-Wang or geometry updates;
- geometric-skipping acceleration;
- MPI spatial decomposition;
- GPU execution;
- checkpoint or restart;
- automatic finite-size fitting.

## Implementation stages and gates

Each stage begins with a failing test, adds the minimum implementation, and
ends by running and reporting its tests:

1. Configuration parsing and parameter derivation.
2. Both lattices and their invariants.
3. Complete test weight and local update.
4. Basic Wolff update.
5. Segmented imaginary-time measurement.
6. `bin_sem` statistics.
7. MPI independent chains.
8. Fixed numerical regressions.
9. Statistical benchmark comparison.
10. README and fresh-environment rerun.

Before a nontrivial statistical run, estimate sweep cost, memory, and wall
time. Runs expected to stay below ten minutes and 16 GB remain local; anything
larger requires the cluster workflow and a separately reviewed run setup.

No stage authorizes a commit or remote change. After the design is approved
and recorded, a separate implementation plan defines the exact test-first
steps and commands for these stages.

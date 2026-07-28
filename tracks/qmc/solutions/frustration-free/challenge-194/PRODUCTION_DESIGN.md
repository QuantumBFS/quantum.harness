# Challenge 194 Production Design

## Scope and phase boundaries

This design advances the validated Day-0 implementation through four
independently gated phases:

1. production Poisson/Newman-Ziff engine, restartable artifacts, and
   correctness/performance calibration;
2. exploratory pilot at the preregistered sigma, size, and kappa grids;
3. frozen production sampling, using cluster capacity only after the local
   performance gate passes;
4. transition, density-jump, finite-cluster-scale, uncertainty, figure, and
   report analysis.

The phases are sequential. Pilot execution is forbidden until the production
engine passes the three-way sampler gate. Confirmatory production is forbidden
until the pilot freezes the retained coupling windows and analysis-plan hash.
Pilot batches never enter confirmatory likelihoods.

## Backend decision

The primary implementation is a Numba-compiled, single-trajectory engine.
Python remains responsible for mathematical references, orchestration,
validation, artifact publication, analysis, and plotting.

A standalone C++17 backend is authorized only if the measured Numba engine
fails either part of this frozen gate on one complete `L = 2^18` trajectory
through the full pilot kappa grid, including basic observables:

- steady-state wall time at most 120 seconds on one CPU core;
- peak resident memory at most 4 GiB.

Compilation time is measured and reported separately. The gate uses fresh
subprocesses, reports median and maximum values over five steady-state runs,
and does not hide failed or outlying runs. A C++ fallback requires a recorded
capability report and must pass the same scientific validation suite.

## Module boundaries

The implementation remains under this challenge directory and adds focused
modules:

```text
src/long_range_percolation/
├── counter_rng.py       # Philox counter streams and unbiased bounded integers
├── alias.py             # immutable distance-class alias table
├── poisson_sweep.py     # monotone event process and duplicate suppression
├── observables.py       # incremental and checkpoint graph measurements
├── artifacts.py         # schemas, hashes, atomic publication, resume
├── benchmark.py         # correctness and resource capability gates
├── pilot.py             # frozen pilot request construction
└── analysis.py          # transition, scale, bootstrap, and sensitivity fits
scripts/
├── validate_production.py
├── benchmark_production.py
├── run_pilot.py
├── run_production.py
└── analyze_production.py
```

No implementation is copied from ONMC. The existing quadratic and geometric
samplers remain independent scientific oracles.

## Counter-based randomness

The production engine uses Philox4x32-10 with published Random123 test vectors.
Each trajectory receives a disjoint key derived from:

```text
(master_seed, phase, L, sigma_grid_id, replica, stream_id)
```

The derivation is canonical, versioned, and hashed. Pilot and confirmatory
phases use distinct namespaces. Thread count, job-array order, retries, and
machine scheduling cannot change a trajectory stream.

The engine records the Philox algorithm/version, key material hash, initial
counter, terminal counter, and conversion version. Floating uniforms use a
fixed open-interval mapping. Uniform integers use rejection sampling, never
modulo reduction. Alias-column, alias-threshold, edge-offset, and exponential
draws use registered stream identifiers so refactoring one draw family cannot
silently perturb another.

## Alias table and event process

For each exact `(L, sigma)`, construct the immutable class weights

```text
w_d = M_d J_d
Lambda = sum_d w_d
```

and a Walker alias table in deterministic distance order. The table stores
the kernel hash, class multiplicities, normalized-weight residual, and alias
invariants. Tests compare alias frequencies with exact `w_d/Lambda` under one
simultaneous threshold.

For each trajectory:

1. initialize `kappa = 0`;
2. advance by `Delta kappa ~ Exp(Lambda)`;
3. draw a distance class from the alias table;
4. draw one canonical edge offset uniformly in that class;
5. encode the edge as a unique unsigned 64-bit class-offset identifier;
6. ignore the event if that edge identifier is already open;
7. otherwise insert it, join its endpoints, and update incremental moments;
8. record requested observables whenever the event time crosses a frozen
   coupling.

Repeated events are required by the Poisson construction and are not treated
as errors. Open-edge membership uses a deterministic open-addressed hash set
whose load factor never exceeds 0.70. Growth is deterministic and preserves
the trajectory stream. Capacity, probes, duplicate fraction, and rehash count
are diagnostics.

This event process gives exact independent Bernoulli marginals
`1 - exp(-kappa J_e)` at every retained coupling while coupling the entire
trajectory across kappa.

## Incremental connectivity and observables

The Numba union-find stores parent, component size, and a four-bit quarter-ring
arc mask. Successful joins update in constant amortized time:

- open-edge count;
- component count;
- `sum_C |C|^2`;
- `sum_C |C|^4`;
- largest-component size;
- whether any component intersects all four fixed quarter-ring arcs.

At every retained coupling, one `O(L)` root scan computes:

- deterministic largest and second-largest component sizes;
- `S1/L` and `S2/L`;
- `Q_G = sum |C|^4 / (sum |C|^2)^2`;
- four-sector crossing indicator;
- consistency checks against incremental moments.

Expensive measurements run only on a deterministic thinning schedule bound to
the trajectory ID:

- full `S1/L` histogram contribution;
- exact-small/logarithmic-large finite-cluster bins;
- bond-length histogram;
- pair connectivity at registered logarithmic separations;
- finite-cluster connectivity;
- finite-cluster structure factors for modes `m = 0,...,8`.

The largest cluster uses a deterministic tie rule. Its pair contribution is
removed per realization before ensemble averaging; subtracting
`E[S1/L]^2` is forbidden. Measurement timing is reported separately and must
not dominate unthinned sampling.

## Restartable and immutable artifacts

Results live under:

```text
tracks/qmc/results/frustration-free/challenge-194/<run-id>/
```

The run bundle contains:

```text
request.json
environment.json
kernel/
seed-manifest.json
capability.json
batches/
progress.json
analysis-plan.json
derived/
figures/
manifest.json
```

One trajectory is the smallest restart unit. The 120-second performance gate
makes mid-trajectory checkpoints unnecessary; interruption loses at most one
trajectory. Each completed trajectory or fixed-size trajectory batch is
written to a unique partial file, flushed, fsynced, semantically reloaded,
hashed, and atomically renamed. The parent directory is fsynced after publish.

`progress.json` is regenerated only from verified immutable batches. Resume
requires exact agreement of request hash, source revision, clean-tree status,
environment lock hash, kernel hash, analysis-plan hash, RNG version, and seed
assignment. Existing valid artifacts are never overwritten. Stale, extra,
partially published, or hash-mismatched files fail closed.

The raw batch schema stores every trajectory as the resampling unit and keeps
all retained couplings from that trajectory together. Aggregates never replace
raw batches.

## Production correctness gate

The Poisson engine must pass before any pilot:

1. published Philox vectors and counter/stream separation;
2. unbiased bounded-integer tests at difficult non-power-of-two bounds;
3. alias frequencies versus exact class weights;
4. Poisson event-count and interarrival distributions;
5. exact edge-frequency marginals at every validation coupling;
6. no-edge probability and open-edge count mean/variance;
7. bond-length histograms and component partitions;
8. `S1`, `S2`, `Q_G`, four-sector crossing, and component moments;
9. all-graph distributions for `L <= 6`;
10. three-way agreement among quadratic, geometric, and Poisson samplers for
    `L <= 256`;
11. `kappa = 0`, saturated coupling, antipodal class, tiny/huge finite
    parameter, hash-growth, and duplicate-event limits;
12. identical trajectory output across process counts and scheduling orders.

Statistical checks use fixed seeds and preregistered familywise thresholds.
No failed seed is replaced. Exact invariants use exact or deterministic
floating tolerances. The gate publishes a machine-readable report with raw
counts and margins to every threshold.

## Performance calibration

Correctness and performance are separate gates. The benchmark harness runs in
fresh subprocesses and records:

- JIT compilation time;
- steady-state wall and CPU time;
- peak RSS;
- events generated and unique edges opened per second;
- union operations per second;
- duplicate fraction and hash probes;
- basic-observable and thinned-measurement cost;
- output bytes per trajectory.

Benchmark points are `L = 2^10, 2^14, 2^18` for all four pilot sigma values.
The quadratic oracle is benchmarked only through `L = 256`; geometric and
Poisson engines are compared at every feasible benchmark size.

The Numba backend proceeds only if correctness passes and the frozen
`L = 2^18` gate is met. Optimization may change layout, compilation strategy,
and batching, but not model semantics, RNG mapping, retained observables, or
artifact schemas without repeating validation.

## Pilot

The exploratory pilot is frozen as:

- `sigma = 0.8, 0.9, 1.0, 1.1`;
- `L = 2^10, 2^14, 2^18`;
- `kappa_j = 0.25 * 1.25^j`, retaining values at most `6`;
- separate pilot-only seed namespace;
- at least eight independent trajectory streams per `(sigma, L)` pilot cell;
- complete basic observables at every coupling;
- deterministic thinned measurements.

Local execution first covers `L = 2^10` and the calibrated benchmark cells.
After the performance gate, remaining pilot cells are emitted as immutable
cluster jobs. The pilot succeeds only if the common change region of both
`Q_G` crossings and four-sector crossing probabilities is bracketed for
`sigma <= 1`, and the `sigma = 1.1` drift is visible without being labeled a
transition.

If a bracket is missing, the grid may be extended only by a new versioned
pilot request; old pilot data remain immutable and excluded from confirmatory
fits.

## Cluster policy

Cluster execution begins only after local scientific validation and Numba
optimization are complete. Jobs are parallelized by `(sigma, L, trajectory
batch)`; no two jobs share writable output. Each worker is single-threaded,
and nodes are filled with as many independent workers as allowed by measured
RSS and core count, with no BLAS/Numba oversubscription.

Before submission, a profile-specific dry run verifies CPU, memory, walltime,
Python/Numba compatibility, filesystem atomic rename behavior, and output
paths. The first real array is monitored through startup, first batch
publication, and semantic reload before scaling to the full allocation.

Once verified, use all suitable idle CPU capacity within account and partition
limits. Large arrays remain restartable per trajectory batch. Cluster results
are fetched by manifest, hashes are rechecked locally, and only verified
batches enter analysis.

## Frozen confirmatory production

After the pilot, freeze:

- retained coupling windows and at least 12 near-critical sigma-one points;
- all retained sigma sizes `2^10, 2^12, 2^14, 2^16, 2^18`;
- sigma-one intermediate sizes `2^11, 2^13, 2^15, 2^17`;
- at least eight independent streams per trajectory batch;
- stopping ceilings and deterministic thinning;
- analysis-plan hash.

Sampling for a cell stops when both dimensionless-observable standard errors
are at most `0.01` near transition and relative spectral-scale error is at
most `8%`, or at the preregistered realization ceiling. Stopping decisions
use completed immutable batches only.

`L = 2^20` remains excluded unless the information-gain and projected
eight-hour gates in `DESIGN.md` pass.

## Analysis

Transition location uses two primary estimators:

1. pairwise `Q_G(L)` and `Q_G(2L)` crossings;
2. four-sector crossing-probability crossings.

Their extrapolated 95% intervals must overlap or the transition is reported
unresolved. For `sigma = 1`, the full `S1/L` distribution is tested for one
versus two components; a stable antimode permits an equal-weight
pseudotransition and peak-separation analysis. Maximum slope is not a primary
transition estimator.

Finite-cluster scale extraction follows the preregistered spectral model:

```text
F_L(k)^-1 = a0 + a_sigma |q|^sigma + a2 q^2
xi_sigma = (a_sigma/a0)^(1/sigma)
```

Unresolved coefficients produce censored bounds. Synthetic propagators must
validate the extractor before physical fits.

At `sigma = 1`, compare exactly the four registered models: fixed `2/3`,
free essential exponent, algebraic, and fixed `2/3` with one logarithmic
correction. Every nested bootstrap resamples streams and then batches, keeps
whole monotone trajectories together, and refits transition location, scales,
and nonlinear models. Deletion tests follow `DESIGN.md` without post-hoc model
selection.

`sigma = 0.8` and `0.9` are continuous-side controls. `sigma = 1.1` is a
negative control: only crossover drift is reported, never a finite critical
point.

## Figures and final report

Final artifacts include:

- transition crossings with simultaneous uncertainty bands;
- `S1/L` distributions and density-jump diagnostics at `sigma = 1`;
- finite-cluster spectral-scale extraction with censored points;
- fixed-`2/3`, free-essential, algebraic, and logarithmic-correction
  comparisons;
- deletion/sensitivity summaries;
- coarse sigma controls;
- benchmark and convergence diagnostics.

Every figure is bound to source batch hashes and analysis-plan hash. The final
report states setup, kernel convention, resource usage, validation status,
transition interval, density-jump evidence, scaling verdict, controls,
limitations, and exact reproduction commands.

The accepted outcomes are support, falsification on accessible scales, or an
honest inconclusive result. No positive physics conclusion is required.

## Failure rules

- Any three-way sampler disagreement blocks pilot execution.
- Any artifact/hash/provenance mismatch blocks resume and analysis.
- Missing overlap between the two transition estimators yields “unresolved.”
- Fewer than eight uncensored scale points, transition-dominated exponent
  uncertainty, or indistinguishable candidate predictions yield
  “inconclusive.”
- A drifting `sigma > 1` crossover is never reinterpreted as a transition.
- Numba performance-gate failure triggers a recorded optimization pass and
  then, if still failing, a separately validated C++17 backend.

# Challenge 194 design

## Scientific objective

Determine what can be concluded, with controlled finite-size and model-selection
uncertainty, about the one-dimensional long-range `q=1` random-cluster model:

1. identify and simulate the pinned finite-ring model without importing
   thresholds from different short-distance or boundary conventions;
2. locate or bound the transition across a small decay-exponent map;
3. at the marginal point `sigma = 1`, test whether the finite-cluster
   crossover scale supports Cardy's formal `q -> 1` continuation
   `nu_tilde = 2/3`;
4. separate a giant-cluster plateau from finite-cluster connectivity before
   making any statement about `eta`.

The accepted conclusions are support, falsification on accessible scales, a
different model identification, or an explicitly inconclusive result.

## Pinned model

For even `L`, vertices are `Z/LZ`. Every unordered pair `{i, j}` is sampled
once and independently:

```text
p_ij(kappa, sigma) = 1 - exp[-kappa J_L,sigma(i-j)]
J_L,sigma(r) = sum_{n in Z} |r + nL|^[-(1+sigma)].
```

There are no loops, duplicate edges, distance cutoff, Kac normalization, or
independently tuned nearest-neighbor probability. At `q=1`, the FK cluster
weight is one, so the measure is an independent Bernoulli product measure.

For `s = 1 + sigma` and `1 <= d <= L/2`,

```text
J_L,sigma(d) =
    L^(-s) [zeta(s, d/L) + zeta(s, 1-d/L)].
```

At `sigma = 1`,

```text
J_L,1(d) = (pi/L)^2 csc^2(pi d/L).
```

Distance classes have multiplicity `L` for `d < L/2` and `L/2` for the
antipodal class `d = L/2`.

This model is not Gori et al.'s minimum-image `C/r^(1+sigma)` model. Its
finite-size thresholds and corrections must be determined independently.

## Theoretical anchors and claim boundary

At `sigma = 1`, the infinite-volume asymptotic tail coefficient is `kappa`.
The rigorous literature implies:

- no percolation for `kappa <= 1`;
- if the percolation density `theta` is nonzero, then
  `kappa theta^2 >= 1`;
- a finite threshold exists on the pinned diagonal, but its value is not
  known exactly;
- the onset of `theta` is necessarily discontinuous;
- strictly subcritical pair connectivity retains an algebraic `r^-2` tail.

These results do not establish Cardy's `nu_tilde = 2/3`, a critical `eta`, or
an exact `kappa_c`. The density jump is compatible with an essential
divergence of a finite-cluster crossover scale on the subcritical side.

For `sigma > 1`, the infinite-volume decay exponent is greater than two and
there is no finite-`kappa` percolation transition. `sigma = 1.1` is therefore
a negative control whose pseudocritical drift must not be reported as a
finite transition.

## Implementation architecture

All committed implementation stays under this challenge directory.

```text
challenge-194/
├── README.md
├── DESIGN.md
├── PLAN.md
├── pyproject.toml
├── uv.lock
├── references/
├── src/long_range_percolation/
│   ├── kernel.py
│   ├── union_find.py
│   ├── oracle.py
│   ├── sampler.py
│   ├── observables.py
│   ├── artifacts.py
│   └── analysis.py
├── tests/
└── scripts/
```

Python owns mathematical reference routines, orchestration, immutable
artifacts, and analysis. A Numba-compiled production kernel owns the
large-system edge process and union-find updates. A standalone C++17 backend
is considered only if a preregistered Numba performance gate fails.

No implementation is copied from the external ONMC repository. It is a
GPL-3.0 algorithm reference for long-range sampling and is not an oracle for
the pinned model.

## Kernel layer

The production kernel table is computed once for each exact `(L, sigma)` and
reused across all `kappa` values.

- `sigma = 1`: analytic `csc^2` expression using a stable `sin(pi x)`
  evaluation.
- other `sigma`: symmetric Hurwitz-zeta expression.
- independent oracle: high-precision direct image summation with a bounded
  tail remainder.

Kernel artifacts include `L`, canonical binary `sigma`, implementation
version, source revision, array hash, and analytic-identity residuals.

## Sampling layers

### Quadratic oracle

For every unordered pair `i < j`, compute its distance class, form
`p = -expm1(-kappa J_d)`, sample one uniform random number, and stream open
edges into union-find. This costs `O(L^2)` time and `O(L)` memory and is used
only for exact and cross-backend validation, primarily through `L = 256`.

### Geometric-skipping sampler

Within one distance class, closed edges before the next open edge follow a
geometric distribution because `1 - p_d = exp(-kappa J_d)`. This gives an
unbiased `O(L + E_open alpha(L))` sampler and is the first accelerated
implementation because it is simple to audit independently.

### Poisson/Newman-Ziff sweep

The production path couples all `kappa` values in one realization.
Associate each edge with an independent Poisson process of rate `J_d`. The
edge is open at coupling `kappa` if its first event time is at most `kappa`.

The total event rate is

```text
Lambda = sum_edges J_e
       = L zeta(1+sigma) [1 - L^(-(1+sigma))].
```

Distance classes are sampled from an alias table with weight `M_d J_d`, and
an edge within the class is selected uniformly. Events are generated in
increasing `kappa`; duplicate events on already-open edges are ignored.
Union-find is updated incrementally and observables are recorded at the
frozen `kappa` grid.

This produces exact Bernoulli marginals for every retained coupling while
sharing work across the full coupling scan. Because couplings within one
trajectory are correlated, the complete trajectory is one resampling unit.

### Randomness

Use a pinned counter-based generator keyed by:

```text
(master_seed, L, sigma_grid_id, replica, stream_id)
```

Uniform-to-integer conversion uses rejection rather than modulo reduction.
Thread scheduling must not alter streams. RNG version, compiler/JIT version,
floating-point mode, and seed keys are stored in every artifact.

## Exact validation gate

Production runs are forbidden until all of the following pass:

1. distance-class multiplicities sum to `L(L-1)/2`;
2. general kernel agrees with high-precision image summation;
3. every `sigma = 1` kernel entry agrees with the `csc^2` identity;
4. the global kernel sum agrees with
   `L zeta(1+sigma) [1 - L^(-(1+sigma))]`;
5. no-edge probability agrees with
   `exp[-kappa sum_edges J_e]`;
6. open-edge mean and variance agree with the independent Bernoulli sums;
7. all graphs for `L <= 6` reproduce exact product-measure and component
   probabilities;
8. quadratic, geometric-skipping, and Poisson-sweep samplers agree for
   `L <= 256` on edge frequencies, bond-length histograms, component
   partitions, `S1`, and `S2`;
9. `kappa = 0`, large-`kappa`, and antipodal-edge limits pass;
10. minimum-image and image-summed kernels are demonstrated to disagree at
    finite `L`, preventing accidental convention substitution.

Statistical comparisons use preregistered simultaneous tolerances rather
than requiring bitwise equality between independent samplers.

## Observables

### Every realization and retained coupling

- largest and second-largest component fractions `S1/L`, `S2/L`;
- geometric cumulant
  `Q_G = sum_C |C|^4 / (sum_C |C|^2)^2`;
- a pinned four-sector crossing indicator: one component intersects all four
  fixed quarter-ring arcs;
- open-edge count;
- component moments needed for consistency checks.

### Thinned measurements

- full `S1/L` histogram;
- exact-small and logarithmic-large finite-cluster size bins;
- bond-length histogram;
- pair connectivity at registered logarithmic separations;
- finite-cluster connectivity;
- finite-cluster structure factors for modes `m = 0, ..., 8`.

Expensive correlation measurements use a deterministic thinning schedule
bound to the replica ID. Measurement work must remain `O(L)` per selected
graph and must not silently dominate the sampler.

## Connectivity definitions

The translationally averaged connectivity is

```text
G_L(r) = E[L^-1 sum_i 1{i connected to i+r}].
```

For a deterministic largest-cluster tie rule, define its pair contribution
per realization and subtract it before ensemble averaging. Subtracting
`E[S1/L]^2` is not equivalent and is forbidden.

Report separately:

- direct decay exponent from `G(r) ~ r^(-eta_dir)`;
- Fisher convention `eta_F = eta_dir + 1` in one dimension;
- finite-cluster connected decay;
- giant-cluster plateau;
- largest-cluster fraction.

No `eta` claim is accepted without naming the convention and subtraction.

## Transition location

The two primary dimensionless estimators are:

1. pairwise `Q_G(L)` and `Q_G(2L)` crossings;
2. four-sector crossing-probability crossings.

Their extrapolated 95% intervals must overlap. Otherwise the transition is
reported as unresolved.

At `sigma = 1`, the complete `S1/L` distribution is additionally tested for
one versus two components. If a stable antimode exists, an equal-weight
pseudotransition and its peak separation are tracked. The maximum slope of
`S1/L` is not a primary transition estimator.

For `sigma > 1`, only crossover drift is reported; no finite critical point
is fitted.

## Finite-cluster scales

An ordinary second-moment correlation length is invalid because subcritical
connectivity has an algebraic tail.

### Primary spectral crossover

For finite clusters, measure

```text
F_L(k) = L^-1 E[sum_{C != C1} |sum_{x in C} exp(ikx)|^2].
```

Fit registered low-momentum mode sets to

```text
F_L(k)^-1 = a0 + a_sigma |q|^sigma + a2 q^2,
q_m = 2 sin(pi m/L),
```

and define `xi_sigma = (a_sigma/a0)^(1/sigma)` only when both coefficients
are positive and resolved. Otherwise store a censored bound. Mode sets
`1:4`, `1:8`, and `2:8` are registered sensitivity checks.

This estimator must first recover known scales from synthetic propagators
with nonanalytic tails, exponential crossovers, and pure algebraic controls.

### Secondary mass cutoff

Fit the site-weighted finite-cluster distribution to a power law with a
registered cutoff over controlled mass windows. The resulting `s_c` is a
systematic transition-scale check. It is converted to a spatial length only
if an independently stable mass-length relation is demonstrated.

## Parameter and sampling plan

### Pilot

- `sigma = 0.8, 0.9, 1.0, 1.1`;
- `L = 2^10, 2^14, 2^18`;
- geometric grid `kappa_j = 0.25 * 1.25^j` with `kappa_j <= 6`;
- separate pilot seeds;
- bracket the common change region of both transition observables;
- benchmark oracle, geometric skipping, and Poisson sweep.

### Frozen production

- all retained `sigma`: `L = 2^10, 2^12, 2^14, 2^16, 2^18`;
- `sigma = 1`: add intermediate powers `2^11, 2^13, 2^15, 2^17`;
- at least 12 retained near-critical couplings at `sigma = 1`;
- at least 8 independent streams per cell or trajectory batch;
- `L = 2^20` only if the registered information-gain and runtime gate passes.

Pilot data are excluded from confirmatory likelihoods.

Sampling stops at a cell when both dimensionless-observable standard errors
are at most `0.01` near transition and the relative spectral-scale error is
at most `8%`, or when the registered realization ceiling is reached.

## Preregistered scaling hypotheses

For subcritical reduced coupling

```text
t = (kappa_c - kappa) / kappa_c,
y = log(xi),
```

compare exactly four primary models:

1. fixed Cardy continuation: `y = a + A t^(-2/3)`;
2. free essential: `y = a + A t^(-nu_tilde)`;
3. algebraic: `y = a - nu log(t)`;
4. fixed `2/3` with one registered logarithmic correction.

`kappa_c` is refit in every bootstrap replicate and constrained by the
independent transition interval. The primary model score is leave-one-
coupling-block-out predictive performance. AICc and parametric-bootstrap
goodness-of-fit are secondary diagnostics.

Supporting fixed `2/3` requires:

- acceptable bootstrap goodness-of-fit;
- no residual trend in coupling or size;
- predictive performance statistically competitive with the best model;
- algebraic scaling loses by more than two score standard errors;
- the free-essential interval contains `2/3`;
- the log-correction interval contains zero;
- all registered deletion tests preserve the conclusion.

Deletion tests raise the minimum size, delete each size, alter the coupling
window by one point, delete nearest/farthest critical points, switch spectral
mode sets, switch to the secondary scale only when the independently stable
mass-length criterion above passes, and propagate the full transition-location
uncertainty.

Failure of stability yields an inconclusive result, not a post-hoc preferred
fit.

## Uncertainty

Independent graph trajectories are partitioned into immutable batches. Use
a nested bootstrap that resamples seed streams, then batches within streams,
and reruns transition interpolation, scale extraction, and nonlinear fits.
Couplings from the same monotone trajectory remain grouped.

Report percentile intervals, covariance-aware fit diagnostics, and
simultaneous bands for primary curves. Raw batches, not only aggregated
means, are retained.

## Artifacts and publication

Artifacts are written to challenge-specific ignored result directories:

```text
tracks/qmc/results/frustration-free/challenge-194/<run-id>/
```

Every run stores:

- immutable request/configuration;
- kernel hash and validation report;
- source revision and dirty-state rejection;
- environment lock hash;
- seed manifest;
- raw batch files;
- progress/completion state;
- analysis plan hash;
- derived analysis and figure hashes.

Files are staged, validated, fsynced, and atomically renamed. Existing valid
artifacts are never silently overwritten. Resume accepts only artifacts whose
configuration, software, and dependency hashes match.

## Failure and stopping rules

- Stop before production if exact enumeration or sampler agreement fails.
- Stop a backend if its measured throughput misses the frozen production
  budget; switch backends only through a recorded capability gate.
- Do not extend to `L = 2^20` unless the largest current sizes are censored,
  competing hypotheses differ by more than one combined standard error
  there, and the projected run is below eight hours.
- Stop exponent discrimination as inconclusive if fewer than eight uncensored
  scale points remain, transition uncertainty dominates the exponent
  interval, or candidate predictions differ by less than two combined
  standard errors over the attainable range.
- Never reinterpret a drifting `sigma > 1` crossover as a transition.

## Minimum deliverable

Within the hackathon window, the minimum scientifically valid result is:

1. exact and accelerated samplers passing the full validation gate;
2. a bounded `sigma = 1` transition interval from two dimensionless
   observables;
3. direct evidence for or against a density jump;
4. finite-cluster scale estimates with censored points retained;
5. fixed-`2/3`, free-essential, algebraic, and log-corrected comparisons with
   deletion tests;
6. coarse controls at `sigma = 0.8, 0.9, 1.1`;
7. an honest support, falsification-on-accessible-scales, or inconclusive
   verdict.

The design does not require a positive `2/3` result. Reproducible
falsification or a demonstrated identifiability limit is an accepted outcome.

# Challenge 194 Production Pipeline Design

## Goal

Turn the verified 96-cell P0 Pilot into an immutable P1 refinement, a
preregistered confirmatory production campaign, finite-size-scaling results,
figures, and a reproducible final report without allowing exploratory data to
enter confirmatory likelihoods.

## Scope and ordering

The work is split into four independently reviewable subsystems:

1. P0 download, local verification, deterministic analysis, and P1 protocol.
2. Extended observable schema and P1 execution.
3. Confirmatory preregistration and cluster production.
4. Scaling analysis, figures, report, and Task 12 public API/documentation.

Each subsystem has its own TDD plan and immutable publication boundary. A
later subsystem cannot run until all upstream artifacts verify by hash and
schema.

## Existing immutable evidence

- Scientific-engine revision: `877ab9393f320bfe31ff74a26c3db1fb205d7ef3`.
- Correctness report SHA256:
  `036b4b8a06164716aff5f40cc38ac4855a212026a556e1c5fe33ce32ce0babb8`.
- Correctness run-spec SHA256:
  `5b3eea4c460e14a57aec9df606447137d787a5c66dd7e98e1dffdcf566f430e2`.
- P0 orchestration revision: `739880d9ccdcffbfc8a15310250349bd11d63bbb`.
- P0 merged progress SHA256:
  `ea29a8163a5d3e85768842d64fac4c719f5aeadf965b3318b305fb7a2cc2d15f`.
- P0 contains exactly 96 verified trajectories: four sigma values, three
  lengths, and eight fresh Pilot replicas.

The remote P0 tree is copied without modification. Local verification must
pass before analysis reads any trajectory.

## P0 analysis and deterministic P1 selection

For each sigma and nonzero P0 coupling, aggregate whole-trajectory estimates
of `Q_G`, four-sector crossing probability, `S1/L`, and `S2/L`. Report the
mean, sample standard error, and exact contributing request hashes.

The P1 bracket is selected from adjacent P0 coupling intervals by this frozen
rule:

1. Use the two largest P0 sizes.
2. Mark intervals containing a sign change in the difference of their mean
   `Q_G` values.
3. Mark intervals where either size's four-sector crossing probability spans
   the closed range `[0.25, 0.75]` between adjacent checkpoints.
4. For `sigma <= 1`, select the narrowest interval marked by both estimators.
   If no common interval exists, fail closed and issue a versioned P0-extension
   protocol instead of choosing post hoc.
5. For `sigma = 1.1`, select the interval with the largest absolute
   finite-difference change in the largest-size crossing probability, breaking
   ties by lower coupling. Label it a crossover refinement only.

P1 uses nine points per selected interval: both endpoints and seven recursively
bisected interior points. Every point is serialized with `float.hex()` and the
ordered grid is hashed. P1 uses the same three lengths as P0 and 16 fresh
replicas per `(sigma, L)`, under the existing exploratory `pilot` phase with a
new P1 grid namespace and master seed. P0 replicas are never reused.

## Extended observables

The current ten-column basic observable matrix remains unchanged. A versioned
extended measurement group is added at every registered checkpoint:

- exact-small and logarithmic-large finite-cluster size bins;
- bond-length histogram;
- pair connectivity at preregistered logarithmic separations;
- finite-cluster connectivity with the largest component removed;
- finite-cluster structure factors for modes `m = 0,...,8`.

The full `S1/L` distribution is formed from whole trajectories; it is not
approximated by an in-trajectory histogram. Extended arrays use frozen shapes,
explicit little-endian dtypes, bounded byte counts, and hashes included in the
trajectory and batch manifests. Existing schema versions remain readable but
cannot satisfy P1 or confirmatory loaders.

Measurements remain `O(L)` per checkpoint up to fixed registered bin/mode
factors. The Python reference and Numba implementation receive independent
small-system oracles. Any scientific-engine change triggers the full 120-cell
correctness gate and a new approval registry before P1.

## P1 execution and acceptance

P1 is exploratory. It runs as immutable single-threaded Slurm cells with fresh
RNG identities, atomic HDF5/JSON publication, no-clobber semantics, and
manifest-based local download.

P1 succeeds only when:

- both primary estimators bracket a common change region for `sigma <= 1`;
- sigma `1.1` shows size drift without being labeled a transition;
- extended observables pass semantic reload and bounded consistency checks;
- all cells complete or are resumed under the identical source and run spec.

The P1 analysis freezes confirmatory windows but contributes no samples to
confirmatory fits.

## Confirmatory preregistration

The confirmatory protocol is committed before any confirmatory trajectory is
generated. It freezes:

- retained sigma/coupling windows, with at least 12 near-critical sigma-one
  couplings;
- lengths `2^10, 2^12, 2^14, 2^16, 2^18` for retained sigmas;
- sigma-one intermediate lengths `2^11, 2^13, 2^15, 2^17`;
- at least eight independent streams per immutable trajectory batch;
- a disjoint `confirmatory` RNG phase and master seed;
- deterministic thinning, realization ceilings, and stopping checks;
- the exact analysis-plan SHA256.

Sampling stops only at completed batch boundaries when both dimensionless
observable standard errors are at most `0.01` near transition and relative
spectral-scale error is at most `8%`, or when the preregistered ceiling is
reached. `L=2^20` remains excluded unless the documented information-gain and
projected eight-hour gates pass.

## Analysis

Primary transition estimators are pairwise `Q_G(L)`/`Q_G(2L)` crossings and
four-sector crossing-probability crossings. Their extrapolated 95% intervals
must overlap; otherwise the transition is reported unresolved.

At sigma one, fit the complete `S1/L` distribution with registered one- versus
two-component diagnostics. A stable antimode permits equal-weight
pseudotransition and peak-separation analysis. Maximum slope is diagnostic,
not a primary transition estimator.

Finite-cluster scales use

`F_L(k)^-1 = a0 + a_sigma |q|^sigma + a2 q^2`

and `xi_sigma = (a_sigma/a0)^(1/sigma)`. Unresolved coefficients become
censored bounds. Sigma-one scaling compares exactly four models: fixed `2/3`,
free essential exponent, algebraic, and fixed `2/3` with one logarithmic
correction.

Nested bootstrap resamples whole streams and then immutable batches, refitting
transition locations, spectral scales, and nonlinear models. Sigma `0.8` and
`0.9` are continuous-side controls. Sigma `1.1` is a negative control and
never receives a finite critical-point claim.

## Figures and report

Generated artifacts include crossing plots with simultaneous uncertainty,
sigma-one `S1/L` distributions, spectral-scale fits with censored points,
four-model comparisons, deletion/sensitivity summaries, coarse sigma controls,
and resource/convergence diagnostics.

Every table and figure records source batch hashes, run-spec hash, analysis
plan hash, source revision, and generation command. The final report states
the kernel convention, validation evidence, resources, transition interval,
density-jump evidence, scaling verdict, controls, limitations, and exact
reproduction commands. Accepted outcomes are support, falsification on
accessible scales, or an honest inconclusive result.

## Public API and documentation

Task 12 exports the stable model, RNG, alias, observable, request/result,
reference, and production entry points from `long_range_percolation`.
README commands cover environment verification, P0/P1/confirmatory execution,
immutable download verification, analysis, plotting, restart behavior, and
the performance-gate waiver without describing it as passed.

## Failure handling

- Hash, schema, provenance, path, semantic, or source drift fails closed.
- Partial/intent markers are preserved for diagnosis and never silently
  deleted.
- Exploratory and confirmatory namespaces cannot be merged.
- Missing brackets create a new versioned exploratory request.
- Unresolved fits remain censored or inconclusive; no post-hoc model or window
  selection is allowed.

# Issue #28 Pure-Neural VMCRG Easy Goal Design

Date: 2026-07-28

Status: approved after repository audit

Implementation plan:
`../plans/2026-07-28-issue28-pure-neural-vmcrg.md`

## Objective

Complete the two-dimensional Easy Goal in QuantumBFS/quantum.harness Issue #28:
use a neural network, rather than a truncated hand-written coupling
expansion, to represent renormalized Hamiltonians in variational Monte Carlo
renormalization group (VMCRG).

The completed challenge must demonstrate the full path on the periodic
45 x 45 Ising model:

1. train a pure neural VMCRG bias with no trainable or fixed 13-operator
   branch;
2. use the learned neural Hamiltonian as the microscopic Hamiltonian for the
   next RG iteration;
3. complete at least five consecutive neural-to-neural RG iterations;
4. retain all five preregistered training seeds;
5. compare unbiased Metropolis, traditional 13-operator VMCRG, and pure
   neural VMCRG under matched budgets;
6. establish that the neural route improves accumulated held-out
   representational error while preserving sampling efficiency.

The 45 x 45 x 45 three-dimensional spin-glass Hard Goal is explicitly a
later project. It is not part of this completion boundary and no three-
dimensional claim may be inferred from the two-dimensional result.

All user-facing CLI text, progress summaries, plots, and HTML report content
use Simplified Chinese. Internal JSON keys, Python APIs, and immutable status
codes remain ASCII English for machine compatibility; every status code has a
Simplified-Chinese display label at the presentation boundary.

## Issue Alignment

Issue #28 asks whether a more expressive neural ansatz can replace the
nearest-neighbor and longer-range truncated coupling expansion used for
renormalized Hamiltonians. It also motivates the replacement by two linked
problems: representational bias accumulated over repeated RG iterations and
slow Monte Carlo relaxation.

This design therefore treats the following as non-negotiable:

- the primary ansatz is a conventional neural network, not an MPS;
- the 13 published operators are baselines and diagnostics only;
- a one-round linear-to-neural experiment is insufficient;
- sampling is evaluated against both unbiased and traditional VMCRG;
- a null or negative result is retained without seed selection or threshold
  changes.

The existing MPS implementation and results remain available as an optional
structured-model comparison. They do not contribute to any Issue #28 success
gate.

## Repository Audit and Reuse Boundary

The repository audit on 2026-07-28 established a clean pre-change test
baseline of `142 passed` when pytest is run from `tracks/mps/DMRG` with the
root virtual environment.

Reuse these verified components rather than reimplementing them:

- `MultiOperatorOptimizer`, `MultiOperatorBiasedMetropolis`, and
  `FastMultiOperatorBiasedMetropolis` for the traditional 13-operator route;
- `run_paper_even_rg.py`, `validate_frozen_even_basis.py`, and
  `compare_paper_autocorrelation.py` as sources for B0 convergence,
  independent-moment, and autocorrelation checks;
- `D4EvenLocalMLP`, `LocalEnergyCache`, and their analytic gradients for the
  pure-neural energy;
- `HybridNeuralVMCRGOptimizer` and `RobbinsMonroSGD` as the starting point for
  the pure-neural optimizer, after the schedule and stopping contract below
  are made explicit;
- the existing pure-neural validation, projection, ablation, hierarchical
  bootstrap, source hashing, and no-overwrite patterns;
- existing atomic JSON helpers, while extracting a shared artifact helper
  instead of importing MPS-specific workflow code.

The following capabilities are genuinely missing and may be added:

- a general exact-enumeration oracle for joint microscopic/block-spin states;
- a JAX automatic-differentiation oracle used only on small exact problems;
- a frozen bridge/BAR estimator for held-out VMCRG objectives;
- a neural microscopic-Hamiltonian sampler and dual neural-cache update;
- a pure-neural checkpoint with protocol, model, RNG, and gauge hashes;
- paired seed-bundle validation and five-round manifest dependencies;
- one unified Issue #28 stage runner and result classifier.

MPS-specific configuration, optimization, checkpoint, plotting, and result
code remains intact for optional comparison but is not extended to implement
the pure-neural route.

## Frozen Physical Setup

- Microscopic model at round zero:
  `H_0(sigma) = -K sum_<ij> sigma_i sigma_j`.
- Coupling: `K = 0.436`.
- Lattice: periodic 45 x 45 square lattice.
- Spin values: `sigma_i in {-1, +1}`.
- RG prescription: non-overlapping 3 x 3 majority blocks with the existing
  tie-free odd-block convention and origin `(0, 0)`.
- Reference distribution: independent uniform block spins.
- Minimum repeated-RG depth: five completed transformations.
- Formal repetitions: five preregistered, independent seed bundles.

Before any non-trivial computation, these assumptions must be shown to the
user for confirm-or-correct as required by the harness compute policy.

## Primary Neural Representation

Reuse the existing `D4EvenLocalMLP` implementation with the configuration
already selected by the latest pure-neural work:

- radius 3;
- hidden width 32;
- multiscale features that preserve the inner 3 x 3 patch explicitly and
  pool only the outer D4 shells;
- shared local density on every lattice site, giving exact translation
  invariance;
- exact D4 and global Z2 symmetry;
- no output constant term;
- all 13 linear-bias coefficients fixed identically to zero.

The trainable bias is therefore

`V_theta(mu) = sum_r f_theta(P_r mu)`,

with no `J dot S_13` skip connection. The 13-operator and candidate-26
registries may project frozen outputs for interpretation, but neither may
feed the neural network or alter its energy during a pure-neural run.

## Energy, Normalization, Sign, and Gauge Convention

There is one energy convention throughout code, protocols, checkpoints, and
reports:

- `V_theta(mu) = sum_r f_theta(P_r mu)` is a total energy;
- `U_phi(sigma)` and every traditional Hamiltonian are also total energies;
- a Metropolis decision consumes a total one-flip energy difference;
- optimizer diagnostics, held-out objectives, and reported cross-model
  errors divide total quantities by the applicable lattice-site count;
- every RG handoff is exactly `U_next = -V_frozen`; no additional sign is
  introduced by serialization, projection, or plotting.

Additive constants are removed only for comparison, never by changing a
Metropolis delta. Before formal runs, create one independent uniform-spin
gauge reference set with a frozen generator, lattice size, configuration
count, dtype, byte order, and seed. Save the compressed reference set and its
SHA-256 hash. Every neural model, traditional model, and RG round is centered
by subtracting its mean total energy on this same set. Manifests record the
reference hash and fail closed on a mismatch.

The gauge-centered energy is used for model-to-model distances and round
handoff verification. Raw total energies and all local deltas remain
available for reproducibility. A save/load or handoff check passes only when
the before/after energy vectors differ by one fitted constant with maximum
residual `<= 1e-10`.

## Neural Hamiltonian Contract

The same neural energy must work in two roles:

1. a variational bias on block spins;
2. the microscopic Hamiltonian for the next RG iteration.

Introduce a focused neural-Hamiltonian protocol around the existing MLP and
cache implementations. It must provide:

- total energy for a periodic spin lattice;
- side-effect-free one-spin-flip energy proposals;
- proposal commit with exact local cache updates;
- direct full recomputation for verification;
- deterministic serialization, loading, and content hashing;
- removal of the unidentifiable additive energy constant for model
  comparison;
- finite-value and shape validation at every load and update boundary.

No neural forward pass may scan the full lattice inside a spin proposal.
Only local densities whose receptive fields contain the changed spin may be
recomputed. The compiled and Python reference paths must consume the same
model parameters and random stream.

## Repeated-RG Data Flow

Round zero starts from the nearest-neighbor Ising Hamiltonian. For RG round
`r`:

1. sample microscopic configurations from `U_r(sigma)` with the current
   variational bias `V_r(tau_3(sigma))`;
2. optimize a pure neural `V_r` so the biased block-spin distribution matches
   the uniform reference;
3. freeze the model and evaluate it only on independent validation streams;
4. define the next renormalized Hamiltonian as
   `U_(r+1)(mu) = -V_r(mu) + constant`;
5. remove the additive gauge by centering on a fixed independent reference
   set;
6. serialize `U_(r+1)` with its protocol, source checkpoint, code hashes, and
   round manifest;
7. instantiate the translation-invariant `U_(r+1)` on a fresh periodic
   45 x 45 lattice for the next 3 x 3 transformation.

The fixed lattice size at each iteration avoids conflating representational
drift with a shrinking finite lattice. The learned local density and
couplings are transferred; sampled spin configurations are not reused across
rounds.

A formal seed counts as complete only after five valid round manifests and
five frozen validation bundles exist. A single successful round may be
reported as a milestone but not as Issue #28 completion.

## Optimization Route

Use the existing stochastic VMCRG gradient and the optimizer route supported
by current diagnostics:

- Robbins-Monro SGD with the literal schedule
  `eta_t = eta_0 (t + t_0)^(-p)` and `0.5 < p <= 1`;
- independent gradient accumulation before each update;
- Polyak averaging over the declared final training fraction;
- independent model, optimizer, validation, projection, objective, and
  autocorrelation random streams;
- no supervised checkpoint in any formal run;
- no fixed-learning-rate Adam in the primary route.

Every runnable protocol must provide explicit values, with no formal-mode
defaults, for:

- `eta_0`, `t_0`, and `p`;
- independent sweeps and target samples per gradient batch;
- gradient-accumulation batches per update;
- minimum and maximum update counts;
- monitoring frequency and consecutive-window patience;
- Polyak averaging start update and averaging fraction;
- global L2 gradient-clip threshold;
- parameter-drift window and threshold;
- held-out monitoring-objective slope/uncertainty threshold;
- gradient-norm upper threshold;
- operator-equivalence and patch-TV thresholds;
- checkpoint frequency and progress frequency.

After every update, parameters, gradients, energies, and optimizer state are
checked for finite values. Gradient clipping occurs before the parameter
update and both unclipped and clipped norms are logged.

Stopping uses a dedicated monitoring stream, not the final validation or
formal objective streams. A run may stop successfully only after its minimum
update count and after all of the following hold for the preregistered number
of consecutive monitoring windows:

1. the held-out monitoring objective has plateaued within its uncertainty;
2. the gradient-norm upper diagnostic is below its threshold;
3. operator-equivalence and excess patch-TV gates pass;
4. gauge-centered parameter/function drift is below threshold;
5. no finite-value or cache check has failed.

Reaching the maximum update count without this conjunction is classified
`NOT_CONVERGED`, not success. Final validation starts only after the training
checkpoint is frozen and uses new streams.

The exact schedules and stopping thresholds are selected using N0/N1 and the
non-formal variance pilot, then frozen in versioned protocol files before any
formal seed is run. A failed formal protocol is never repaired in place. Any
revision requires a new protocol version, disjoint seeds, and a new output
directory.

## Execution Stages

### B0: Traditional VMCRG baseline certification

Before neural work, certify the comparator on the same periodic 45 x 45
Ising model, `K = 0.436`, 3 x 3 majority blocking, and canonical published
13-operator basis. Reuse the paper reproduction implementation and produce a
new compact certification manifest that proves:

- the canonical operator-basis hash, signs, coordinates, D4 instances, and
  per-site normalization match the frozen protocol;
- all traditional local energy deltas agree with full recomputation;
- the formal variational trajectory satisfies coupling-drift, gradient, and
  frozen target-moment convergence gates;
- principal renormalized couplings and their uncertainty are consistent with
  the verified paper-baseline evidence;
- the handoff `U_next = -V_frozen` is correct on an independent configuration
  set up to the common additive gauge;
- frozen traditional VMCRG reduces autocorrelation relative to unbiased
  Metropolis on matched measurements.

B0 uses certification seeds disjoint from all neural formal seed bundles.
The traditional arm is still retrained inside each later paired formal bundle
so neural-versus-linear differences remain paired.

### N0: Exact small-lattice oracle

No one square lattice can simultaneously support exact enumeration, 3 x 3
blocking, and the formal radius-3 MLP: exact enumeration is capped near 20
spins while a nondegenerate radius-3 periodic model needs at least 7 x 7.
N0 therefore uses two complementary exact oracles rather than weakening the
formal model:

1. a periodic 3 x 6 oracle-only rectangular lattice with 3 x 3 majority
   blocking and `2^18` microscopic states, used to enumerate the exact
   coarse distribution, VMCRG objective, target distances, simple even-bias
   gradient, bias sign, and `U_next = -V` handoff;
2. a periodic square identity-RG problem with at most 16 spins and a reduced
   radius-1 D4/Z2 MLP, used to enumerate the exact neural objective and to
   compare JAX automatic differentiation, the existing analytic gradient,
   finite differences, and Monte Carlo gradient estimates.

The rectangular oracle is isolated from the production square-lattice
sampler; it does not broaden the formal physical setup. Full radius-3
symmetry and local-delta behavior remain covered by deterministic production
tests on sufficiently large lattices.

N0 also compares every proposed one-spin local energy difference with direct
total-energy recomputation and independently checks uniform-reference
normalization. JAX is an oracle-only dependency installed through the
existing `make install jax` target; production Monte Carlo remains
NumPy/Numba.

N0 blocks N1 on any sign, normalization, target, automatic-differentiation,
analytic-gradient, Monte Carlo-gradient, or local-delta discrepancy outside
its frozen tolerance.

### N1: Random-initialization identity certification

Implement and run the already-designed identity-RG experiment from random
initialization. It must establish that the optimizer reaches the known
identity solution without a supervised checkpoint. Run a short pilot, two
independent replications, then a formal three-seed certification before
advancing.

### N2: One-round 45 x 45 pure-neural RG

Run the physical `K = 0.436`, `b = 3` problem with the pure multiscale MLP.
Freeze and evaluate the model on independent data. The 13- and candidate-26
projections are diagnostics; held-out distribution and variational endpoints
own the pass/fail decision.

### N3: Neural-to-neural implementation and pilot

Implement the neural microscopic-Hamiltonian contract, verify one round of
handoff, and perform a single-seed five-round pilot using seed bundles that
cannot appear in formal work. Record per-round endpoint variance, wall time,
peak memory, checkpoint size, log volume, and final-output size.

Use this pilot to estimate the expected hierarchical confidence-interval
width and power of the fixed five-seed design for the representation and
sampling endpoints. The power report is descriptive and cannot increase,
replace, or select formal seeds after N4 begins. If estimated power is low,
the formal protocol must state in advance that a consistent effect direction
with a threshold-crossing confidence interval is a valid scientific negative
result.

### N4: Formal five-seed, five-round experiment

Run five independent seed bundles. Each bundle completes five dependent RG
rounds. All seeds and rounds enter the final analysis regardless of outcome.

### N5: Three-arm attribution and report

At matched microscopic inputs and measurement budgets, compare:

1. unbiased Metropolis;
2. traditional 13-operator VMCRG;
3. pure neural VMCRG.

Generate compact data, figures, a consolidated runnable entry point, and a
challenge completion report. Existing MPS results may appear only in a
clearly labelled optional comparison section.

## Correctness Gates

These gates must pass before scientific metrics are interpreted:

- the canonical published 13-operator basis serialization has the exact
  protocol SHA-256 hash;
- JAX automatic-differentiation, analytic, finite-difference, exact-enumeration,
  and Monte Carlo gradients agree within their separately frozen deterministic
  or statistical tolerances;
- local energy deltas agree with full recomputation to absolute error
  `<= 1e-10`;
- microscopic and bias incremental caches show no drift above `1e-10` over
  long deterministic random flip sequences;
- Python reference and compiled samplers produce identical trajectories for
  the same random stream;
- D4 and Z2 symmetry errors remain `<= 5e-14`;
- the pure-neural fixed 13-operator bias is represented by an exact all-zero
  float64 vector and has exact L-infinity norm zero at config load, training,
  checkpoint, resume, evaluation, and report boundaries;
- serialization and round handoff preserve independent-configuration
  energies up to one additive constant and `1e-10` numerical error;
- identity neural-to-neural mapping does not drift beyond the preregistered
  frozen-distribution and held-out-energy bounds;
- five-round manifests form an unbroken hash-linked dependency chain;
- formal seed streams are unique and outputs cannot overwrite a nonempty
  directory;
- a checkpoint whose protocol, code, operator-basis, gauge-reference,
  predecessor-round, or seed-bundle hash differs is rejected;
- interrupted writes recover only from a complete atomically renamed
  checkpoint whose internal hashes verify;
- no NaN, infinity, missing manifest, reused formal seed, partial checkpoint,
  or overwritten output is accepted.

A correctness failure stops the affected run immediately. It is a software
or protocol failure, not a scientific null result.

## Frozen Held-Out Objective Protocol

For a bias `V`, report the per-site VMCRG objective relative to the common
zero-bias anchor:

`Omega[V] - Omega[0] = log(Z_V / Z_0) + E_target[V]`,

with total energies inside the estimator and division by the coarse-site
count only after the total difference is formed.

Use stratified Bennett acceptance ratio (BAR) estimates across a frozen
linear bridge `V_lambda = lambda V`. The non-formal pilot starts from
`lambda = [0, 0.125, 0.25, 0.5, 0.75, 0.875, 1]`. It may add bridge points
only before the formal protocol is signed. The final neural and linear
lambda ladders, samples per chain, independent chains per bridge, thermal
schedule, and measurement spacing are literal arrays/values in the protocol;
formal execution cannot adapt them from observed results.

Both arms use the same deliberately shared zero-bias anchor ensemble within
a seed/round pair. All nonzero bridge ensembles use independent neural or
linear objective streams. The target expectation uses a further independent
uniform-reference stream. Shared anchor use is recorded explicitly and is
not implemented by sharing mutable RNG state.

Every adjacent bridge interval must pass all frozen overlap diagnostics:

- BAR overlap scalar `>= 0.03`;
- forward and reverse Kish effective-sample fractions each `>= 0.10`;
- forward/reverse closure disagreement `<= 3.0` combined standard errors;
- finite BAR root, uncertainty, and target expectation.

If any interval fails, that arm/round objective is classified
`UNIDENTIFIABLE_OVERLAP`. It cannot be imputed, treated as improvement, or
removed from the seed aggregate.

The whole independent Markov chain is the jackknife unit; individual
correlated measurements are never treated as independent. The final
uncertainty calculation is hierarchical over formal seed bundle and chain,
with a preregistered bootstrap seed. The protocol records separate streams
for the shared anchor, each bridge chain in each arm, the target expectation,
and the hierarchical bootstrap.

The primary paired round effect is
`DeltaOmega_r = Omega_neural,r - Omega_linear,r`, obtained by subtracting the
two estimates tied to the common anchor. The formal estimator name, BAR
solver tolerances, bridge ladders, overlap gates, jackknife unit, bootstrap
unit, sample counts, and every seed are hashed before N4. No estimator or
threshold can change after formal output is observed.

## Scientific Endpoints

### Per-seed, per-round requirements

- frozen maximum operator-equivalence bound `<= 0.02`;
- frozen excess patch-TV upper bound `<= 0.02`;
- held-out variational objective improves over the zero-bias state;
- all measurements use streams not used for training or parameter averaging;
- the pure-neural model completes the next-round handoff.

The 13-operator projection residual is reported but is not an absolute
representation gate: a neural model is intended to learn interactions beyond
that truncated basis. Stable candidate-26 or other held-out components must
be retained as physical output rather than projected away.

### Neural versus traditional representation

The primary representation endpoint for seed `s` is the five-round sum of
the matched held-out VMCRG objective difference per coarse site:

`R_rep(s) = sum_(r=1)^5 [Omega_total_neural(s,r) - Omega_total_linear(s,r)] / N_coarse`.

Objective artifacts store both the total estimate and the derived per-site
estimate; the formula above performs the site normalization exactly once.

Each round uses frozen models and independent evaluation streams. The
free-energy estimator, overlap diagnostic, jackknife unit, and common
zero-bias anchor are frozen in the formal protocol. An estimate that fails
its overlap diagnostic is classified as unidentifiable, not favourable.

The pure-neural route passes the representation endpoint only when the
hierarchical 95% confidence upper bound for `R_rep` is below zero and at
least four of five seed-level values are negative. Per-round excess patch-TV,
candidate-26 moments, and other held-out correlations are supporting
diagnostics; they are reported separately and are never combined post hoc
into a different primary score.

### Sampling endpoints

Against unbiased Metropolis, pure-neural VMCRG must show a statistically
significant reduction in integrated autocorrelation time and improvement in
effective samples per second.

Against traditional 13-operator VMCRG, use the approved 10% non-inferiority
margins:

- hierarchical 95% upper confidence bound for
  `tau_neural / tau_linear <= 1.10`;
- hierarchical 95% lower confidence bound for
  `ESS_per_second_neural / ESS_per_second_linear >= 0.90`.

Sampling budgets, proposal schedules, thermalization, thinning, observables,
hardware class, and timing boundaries must be matched. Training cost and
measurement cost are reported separately and together.

## Statistical Contract

- Five preregistered formal seed bundles are mandatory.
- All five must finish or be classified with an explicit failure reason.
- Every seed and every completed round is retained in tables and plots.
- Correctness and frozen-distribution gates apply individually.
- Scientific comparisons use a seed-and-chain hierarchical bootstrap with
  preregistered bootstrap seeds and 95% intervals.
- Directional improvement requires at least four of five seed-level effects
  in the claimed direction.
- No seed replacement, checkpoint selection, threshold relaxation, or
  result-dependent protocol extension is permitted.

Each formal bundle contains explicit, mutually distinct streams for:

- paired initial-condition generation;
- microscopic state initialization and evolution;
- neural training;
- traditional linear training;
- training monitoring/stopping;
- final frozen validation;
- 13/candidate-26 projection;
- shared objective zero-bias anchor;
- neural bridge objectives;
- linear bridge objectives;
- target objective expectation;
- autocorrelation measurement;
- hierarchical bootstrap.

Each stream is stored as a NumPy `SeedSequence` entropy/spawn-key record, not
only as an opaque scalar seed. The validator rejects a duplicate stream
within or across formal bundles. Neural and traditional arms begin from
byte-identical paired initial spin configurations and use matched walkers,
sampling budget, thermalization, measurement length, observables, thread
count, compiled/reference mode, and hardware class. They then evolve with
independent RNG states. Accidental RNG-state sharing is a protocol failure.

Primary analysis uses within-bundle paired differences before aggregating
across bundles. Hardware, thread, timing-boundary, and initial-state hashes
are included in every arm manifest.

If the scientific endpoints fail while correctness holds, the challenge run
is a valid negative result. It completes the experiment but does not support
the claim that the Easy Goal succeeded.

The variance/resource pilot uses disjoint non-formal bundles. Formal seed
count remains exactly five even if the pilot predicts low power. Once the
first formal bundle starts, no extra or replacement seed may be added. A
four-of-five directional result whose confidence interval misses a gate is
reported as `SCIENTIFIC_NEGATIVE_INSUFFICIENT_PRECISION`, not promoted to
success.

## Compute Strategy

Local execution is limited to deterministic tests, exact small-lattice
checks, and pilots estimated below 10 minutes and 16 GB resident memory.

All 45 x 45 formal training, five-round chains, five-seed replications, and
long autocorrelation measurements default to the configured Slurm cluster.
Before submission:

1. read the active cluster profile;
2. estimate wall time, memory, and output size from the completed pilot;
3. run the harness Slurm precheck and probe compatible partitions;
4. submit a one-node, short-wall smoke job;
5. verify the first log and first result manifest before scaling out.

Formal work is organized as five independent seed chains. Within each seed,
rounds 1 through 5 have explicit dependencies and consume only the verified
checkpoint from the previous round. Seeds run in parallel where the queue
allows. If a single round exceeds a partition wall limit, its training is
resumable from an atomic checkpoint without changing the frozen protocol.

Every long-running process emits flushed progress estimates roughly 10-50
times per run and writes an incremental manifest after each unit of work.
Submission, monitoring, failure classification, resume, and result fetching
compose with the harness `using-slurm` workflow. No partition or resource
request is invented before reading the active profile.

## Failure Handling

- Correctness, cache, symmetry, serialization, or non-finite failures abort
  immediately and block downstream rounds.
- A failed scientific gate does not erase the run. Remaining safe,
  preregistered measurements continue when they are needed to classify the
  result.
- A failed round prevents later rounds for that seed and is recorded as
  censored-by-failure, not silently dropped.
- Cluster preemption or wall timeout may resume only from the latest atomic
  checkpoint with matching protocol and code hashes.
- A protocol mismatch, stale checkpoint, or duplicate seed fails closed.
- Existing output directories are never overwritten.

Every terminal stage result has exactly one top-level classification:

- `CORRECTNESS_FAILURE`: deterministic physics, gradient, sign, cache,
  trajectory, serialization, or finite-value contract failed;
- `PROTOCOL_FAILURE`: seed, hash, dependency, hardware-matching, output,
  checkpoint, or preregistration contract failed;
- `SCIENTIFIC_NEGATIVE`: correctness and protocol held, but convergence,
  overlap, representation, sampling, power, or confidence gates did not
  support the claim;
- `EASY_GOAL_SUCCESS`: every required B0 and N0 gate passed and all N1-N5
  success conditions passed for the complete formal data set.

These classifications are mutually exclusive. A report may describe the
underlying failure in detail but cannot rename it to a more favourable class.

## Unified Fresh-Checkout Entry

Provide one top-level command under `reproduce.py`, named `issue28-easy`,
that validates its locked protocol and can execute or resume the dependency
graph in this exact order:

`B0 -> N0 -> N1 -> N2 -> N3 -> N4 -> N5`.

It supports a dry-run/preview, a stage or `--through` selector, and explicit
local or Slurm backend selection. Formal 45 x 45 work refuses the local
backend unless its measured pilot estimate is below the harness local-compute
limits. A fresh checkout run states required setup, including `make skills`
and the existing `make install jax` target for the N0 oracle.

Each seed/round/stage writes an independent manifest, frozen-validation
result, resource record, and status before the next dependency is released.
N5 consumes only verified manifests and emits paired three-arm data, exact
figure-source tables, a consolidated status JSON, and the final report.

The entry never shells through an opaque monolithic script. Each stage has a
callable Python API and focused CLI so tests can exercise dependency and
fail-closed behavior without launching formal compute.

## Tests

Add focused tests before implementation for:

- canonical traditional 13-operator serialization/hash, signs,
  normalization, convergence-gate inputs, and B0 handoff;
- exact 3 x 6 coarse distribution, target distance, objective, bias sign,
  and `U_next = -V` handoff;
- exact/JAX/analytic/finite-difference/Monte Carlo gradient agreement;
- BAR on analytically known free-energy differences, bridge overlap
  classification, common-anchor pairing, and chain-level jackknife;
- literal Robbins-Monro schedule values and rejection of omitted formal
  parameters;
- multi-condition stopping, hard-cap `NOT_CONVERGED`, gradient clipping,
  parameter drift, and non-finite aborts;
- total-energy/per-site normalization and common gauge-reference hashing;
- neural microscopic energy versus explicit full summation;
- one-flip neural microscopic delta versus full recomputation;
- simultaneous microscopic-neural and coarse-bias cache updates;
- exact zero 13-operator branch at every pure-neural boundary;
- reference versus compiled trajectory identity;
- model save/load and content-hash stability;
- round handoff modulo an additive constant;
- identity neural-to-neural invariance;
- five-round manifest dependency validation;
- paired seed-bundle uniqueness, intentional common-anchor use, accidental
  RNG-sharing rejection, matched-arm metadata, and non-overwrite behavior;
- hierarchical endpoint and non-inferiority calculations;
- interrupted-round resume with matching and mismatching hashes.

The unified-entry tests must prove B0-N5 order, correctness-gate blocking,
scientific-negative continuation to reporting, per-seed/per-round manifest
creation, and all four terminal classifications without performing a large
run.

The complete existing test suite must continue to pass. MPS tests remain in
the suite because the implementation is preserved, but they are not Issue
#28 acceptance tests.

## Artifacts

The implementation plan will assign exact paths, but the durable output must
include:

- one canonical `PLAN.md` for the pure-neural Issue #28 route;
- the versioned design and implementation-plan documents;
- versioned B0 baseline, N0 exact-oracle, objective-estimator,
  Robbins-Monro, identity, one-round, five-round, seed-bundle, resource-pilot,
  and formal protocol files;
- the canonical operator-basis record, gauge-reference set, and their hashes;
- a consolidated runnable command that starts from a fresh checkout;
- per-seed/per-round manifests, compact checkpoints, summaries, and logs;
- per-stage correctness/protocol/scientific classification records;
- exact data underlying every figure;
- three-arm comparison figures with uncertainty and seed counts;
- a short run report stating setup, settings, pass/fail gates, residual
  uncertainty, and the boundary excluding the 3D Hard Goal;
- a self-contained HTML challenge report after the submission-cleanliness
  gate passes.

Large raw chains and intermediate checkpoints stay ignored or remote. Only
compact reproducibility artifacts and final evidence are candidates for
version control.

## Migration From the Current MPS Plan

The current root `PLAN.md` describes an MPS-residual challenge and must stop
being the canonical Issue #28 plan. Preserve its content as a dated optional
MPS-comparison plan; do not delete its code, tests, results, or provenance.

Historical paper-reproduction, pure-neural pilot, MPS, and LTRG evidence is
not redundant and must not be deleted. Generated caches and duplicated
planning text may be removed only after the canonical replacement and archive
are verified. The MPS-oriented package metadata and README wording must be
updated or clearly scoped so they no longer misidentify the primary
challenge.

The replacement root plan must:

- name the Issue #28 pure-neural Easy Goal explicitly;
- place N1 through N5 in dependency order;
- place B0 and N0 before N1 and include the non-formal variance/resource
  pilot before N4;
- mark already verified pure-neural evidence as baseline, not final success;
- make five neural-to-neural rounds and five formal seeds hard gates;
- exclude MPS metrics from completion;
- defer the 3D spin-glass Hard Goal.

## Completion Definition

The two-dimensional Easy Goal is successful only when all of the following
are true:

1. B0 certifies the traditional comparator and N0 certifies exact signs,
   objectives, gradients, targets, and local deltas;
2. a pure neural ansatz with exact zero 13-operator branch is used under the
   frozen total-energy, per-site-reporting, handoff, and gauge conventions;
3. the BAR objective, Robbins-Monro training, seed bundles, power caveat, and
   fail-closed hashes are frozen before formal execution;
4. random-initialization identity certification passes;
5. five independent formal seeds each complete five consecutive
   neural-to-neural RG rounds;
6. every claimed round passes correctness and frozen-distribution gates;
7. accumulated held-out representation error is statistically lower than
   the traditional 13-operator route;
8. sampling is significantly better than unbiased Metropolis and
   non-inferior to traditional VMCRG under the approved margins;
9. all results, including failures, are included in the final report with one
   of the four frozen terminal classifications;
10. the fresh-checkout runner, protocols, compact evidence, figures, and report are
   reproducible from a fresh checkout.

Anything less is reported as progress or a valid negative experiment, not as
successful completion of Issue #28's two-dimensional Easy Goal.

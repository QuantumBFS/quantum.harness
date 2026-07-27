# Challenge #15 Scalable NQS v1 Design

> Status: user-approved design, awaiting written-spec review
>
> Date: 2026-07-28
>
> Project: BOTS:848, Harnessing Quantum 2026 Challenge #15
>
> Baseline: [Benchmark v0](../../../tracks/qmc/solutions/BOTS-848/docs/benchmark-v0.md)

## 1. Outcome and boundary

Benchmark v0 remains the minimum acceptance benchmark. It has already passed at
`N=6`, but its projected random-feature candidate uses an ED-sized exact
`L^2` projector and Ritz optimization. Scalable v1 must reproduce the same
physical target without using a complete many-body basis, a complete
Hamiltonian, an exact angular-momentum projector, or ED-derived variational
coefficients in the candidate path.

The immediate outcome is a fair comparison of three bounded candidates:

1. occupation-space autoregressive NQS;
2. continuous, fixed-degree holomorphic NQS;
3. an `L=2` CF-Flow-style prototype.

One candidate advances only if it passes the frozen `N=6` gates through a
scalable code path. The winner is then trained at `N=8`; successful `N=8`
evidence unlocks cluster runs at `N=10` and `N=12`.

Chiral spectral weights, Landau-level mixing, thermodynamic extrapolation, and
the paper's `L=N` transport gap remain later research extensions. They do not
enter the scalable-v1 route comparison.

## 2. Fixed physical contract

Every route uses the same problem definition:

- Haldane sphere with `N` fully spin-polarized electrons;
- filling `nu=1/3` and flux `2Q=3(N-1)`;
- strict lowest-Landau-level Hilbert space;
- chord-distance Coulomb interaction
  `1/(sqrt(Q) * |Omega_i-Omega_j|)`;
- raw LLL energy in `e^2/(epsilon*l_B)` as the primary comparison convention;
- background-subtracted and density-corrected paper convention as a derived
  report field only;
- an `L=0` ground state and the lowest `L=2` neutral excitation;
- the primary quantity `Delta_2=E_2-E_0`;
- one shared variational family for the two sectors, with sector-specific heads
  allowed;
- one reduced `L=2` state from which the five `M=-2,...,2` components are
  generated. Five independently trained networks are not a valid multiplet.

Benchmark v0's `N=6, 2Q=15` ED result is the accuracy oracle. Candidate
training and model selection may use the Hamiltonian and symmetry definition,
but not the oracle energies, eigenvectors, projectors, or gaps.

## 3. What “scalable” means

A candidate is scalable when all training, sampling, local estimators, and
symmetry diagnostics operate on individual configurations or polynomial-size
connected neighborhoods. Runtime and memory may grow with `N`, orbital count,
network width, sample count, or Monte Carlo autocorrelation time; they may not
grow because the code allocates or enumerates the complete many-body Hilbert
space.

The candidate path must not:

- enumerate the full fixed-`M` or full-LLL basis;
- construct a dense or sparse matrix for the complete many-body Hamiltonian;
- diagonalize `H` or `L^2`;
- build or apply an exact many-body `L` projector;
- solve a Ritz/generalized-eigenvalue problem over the ED-sized space;
- import or read Benchmark v0 oracle values, vectors, or projected features
  during training, early stopping, hyperparameter selection, or checkpoint
  selection.

The candidate path may use:

- analytic monopole harmonics, Clebsch-Gordan coefficients, Wigner matrices,
  and one-body ladder rules;
- the polynomial-size configurations connected to one sampled configuration by
  the two-body Hamiltonian or by `L_+`, `L_-`, and `L^2`;
- tiny exact fixtures at `N<=4` in unit tests, provided they are not imported by
  a production candidate run;
- the `N=6` ED oracle inside the separate post-freeze evaluator.

`scalable_path_valid` is a new hard gate. Static dependency checks, runtime
manifests, peak-memory measurements, and an `N=8` smoke test provide evidence
for it; a low wall time at `N=6` alone does not.

## 4. Architecture and common contract

The implementation is split into small components with one-way dependencies:

- `PhysicsSpec`: immutable geometry, flux, interaction, sectors, and energy
  conventions;
- `ProtocolConfig`: frozen seeds, optimization/sample budgets, thresholds, and
  resource ceilings;
- route-specific trainer: produces a frozen checkpoint without access to the
  ED oracle;
- `CandidateAdapter`: exposes a common evaluation surface;
- `ScalableEvaluator`: runs symmetry, VMC, resource, and post-freeze ED checks;
- result writer: emits one common `run.json`, resource record, and concise
  attempt journal.

Production modules and the frozen protocol live under
`tracks/qmc/solutions/BOTS-848/scalable_v1/`; route-specific code is isolated
under its `routes/` subdirectory so the evaluator does not depend on route
internals. The committed protocol is
`tracks/qmc/solutions/BOTS-848/scalable_v1/protocol.json`.

The approved candidate interface is:

```text
sample(n_samples, seed) -> SampleBatch
logpsi(config_batch) -> complex log amplitudes
local_energy(config_batch) -> complex local estimators
local_l2(config_batch) -> complex local Casimir estimators
generate_multiplet() -> map M=-2,...,2 to derived state handles
resource_metrics() -> wall, peak RSS/VRAM, throughput, ESS/s
```

`config_batch` is a typed native representation: fixed-particle-number orbital
occupations for route 1 and sphere spinor coordinates for routes 2 and 3. The
evaluator never assumes a route's internal network architecture. Training is a
route-specific command, but it must consume `PhysicsSpec` and `ProtocolConfig`
and produce the same frozen-checkpoint manifest.

```mermaid
flowchart LR
    A["PhysicsSpec + ProtocolConfig"] --> B["route-specific blind trainer"]
    B --> C["frozen checkpoint + manifest hash"]
    C --> D["CandidateAdapter"]
    D --> E["symmetry and VMC evaluator"]
    D --> F["resource and N=8 smoke evaluator"]
    E --> G["post-freeze N=6 ED comparison"]
    F --> H["common run.json"]
    G --> H
```

## 5. Candidate routes

### Route 1: occupation-space autoregressive NQS

This is the recommended first route. It samples fixed-`N`, fixed-`M` orbital
occupations with an autoregressive amplitude/phase model. Occupation states are
Slater determinants of the `2Q+1` monopole orbitals, so LLL membership and
fermionic antisymmetry are exact by construction.

The `L=0,M=0` and `L=2,M=0` states share the autoregressive trunk and use
sector-specific heads. Training uses energy plus stochastic `L^2` mean and
variance penalties. `local_l2` is evaluated from the polynomial-size
configurations reached by analytic angular-momentum ladder moves; it never uses
an exact projector. The other four `M` components are obtained by applying
analytic many-body ladder actions to the frozen reduced state. If direct
autoregressive sampling is unavailable for a ladder-derived component, its
adapter uses Metropolis sampling of the derived amplitude.

For the required finite-rotation check, the evaluator estimates the rotated
Fock-space amplitude with importance sampling. A matrix element between two
Slater configurations is the determinant of a one-body Wigner-rotation
submatrix, so each sampled contribution is polynomial-cost and no rotated full
basis vector is formed.

Primary risk: a flexible fixed-`M` model can lower its energy while retaining
unwanted `L` admixture. The deciding evidence is therefore `Var(L^2)` and the
finite-rotation five-component covariance test, not energy alone.

### Route 2: continuous fixed-degree holomorphic NQS

This route evaluates the wavefunction directly on sphere spinors. It uses a
polynomial-width sum of antisymmetrized determinants whose single-particle
orbitals are learned linear combinations of degree-`2Q` monopole polynomials.
The coefficients are coordinate-independent outputs of the parameterization;
no anti-holomorphic coordinate or unconstrained coordinate-dependent
coefficient may enter. This makes exchange antisymmetry and LLL closure exact
while avoiding a full determinant-basis expansion.

The ground and excited states share the determinant generator. Angular-momentum
coupling supplies scalar and rank-2 heads, and a single rank-2 head generates
the five-component tower. Direct coordinate-space Metropolis sampling provides
energies and symmetry residuals.

Primary risk: a polynomial-rank determinant expansion may be too weak to reach
the Laughlin correlations at a useful cost. Rank is therefore a declared model
capacity, and both energy variance and peak memory are reported as it changes.

### Route 3: `L=2` CF-Flow-style prototype

This route starts from a Clebsch-Gordan-coupled composite-fermion particle-hole
seed in the `L=2` sector, rather than the paper's maximally separated `L=N`
transport-gap excitation. A shared SO(3)-equivariant flow deforms the `L=0`
and reduced `L=2` states, after which the rank-2 tower is generated from the
same equivariant object.

Generic coordinate backflow is not automatically LLL. The route therefore
measures the covariant anti-holomorphic derivative/cyclotron residual without
using a many-body LLL projector. A finite but small leakage labels the result
`prototype` and fails `lll_valid`; the route can pass only if the implemented
flow is restricted to a fixed-degree holomorphic map with an accompanying
construction-level certificate. There is no fallback to exact projection.

Primary risk: the paper's useful expressivity may rely on higher-Landau-level
content. A hard-gate failure is still a useful result because it identifies the
precise obstruction to using CF-Flow as the Challenge #15 final ansatz.

## 6. Oracle-isolated training and reveal

True human blinding is impossible: Benchmark v0 values are already committed
and have been inspected. Scalable v1 therefore makes a narrower, auditable
claim called **pipeline blinding**:

- `human_blind=false` is always recorded;
- `oracle_isolated=true` requires that training, early stopping, capacity
  choice, and checkpoint choice consume no ED artifact or ED-derived number;
- the legacy summary field `blind_training_valid` is true only when
  `oracle_isolated=true` and the frozen-manifest audit passes.

Before reveal, a route writes and hashes its checkpoint, optimizer state,
training log, selected capacity, and manifest. The evaluator verifies the hash
and forbidden-dependency audit before loading the `N=6` ED reference. Any
post-reveal retraining is a new attempt with `blind_training_valid=false` unless
it uses a newly frozen protocol that does not encode the revealed discrepancy.

Step 1 produces and commits the exact `ProtocolConfig` before any route code is
implemented. It fixes:

- comparison seeds and the number of independent training runs;
- total optimizer updates and local-energy evaluations per sector;
- post-training sample count, burn-in, chains, blocking rule, and minimum ESS;
- symmetry residual, Casimir, multiplet-splitting, and MC-error thresholds;
- model-capacity ceilings and allowed route-specific capacity mapping;
- per-run wall, CPU/GPU, RAM/VRAM, and checkpoint limits;
- the fixed `N=8` no-training smoke batch used for growth measurements.

The values are chosen using oracle-free microbenchmarks and resource
calibration; the public Hamiltonian and local estimators may be used, but no ED
reference may be read. They cannot be changed after the first route begins. If a
shared budget is physically impossible for one route, Step 1 must fail rather
than silently granting that route a different budget.

## 7. Gates, metrics, and winner selection

### Hard gates

The scalable-v1 candidate must pass all Benchmark v0 gates:

- `lll_valid`;
- `antisymmetry_valid`;
- `so3_equivariance_valid`;
- `l2_casimir_valid`;
- `fivefold_multiplet_valid`;
- `mc_error_valid`;
- `ed_crosscheck_valid` after reveal;
- `reproducible_run_valid`.

It must also pass:

- `scalable_path_valid`;
- `oracle_isolated` / `blind_training_valid` under the pipeline-blind
  definition;
- `resource_budget_valid`.

LLL and antisymmetry require a construction-level argument plus numerical
tests. A sampled residual alone cannot turn a non-LLL ansatz into a strict-LLL
one. The `L=2` state must satisfy `<L^2>=6` within the frozen uncertainty rule,
have variance compatible with zero, generate all five components, and meet the
frozen finite-rotation and multiplet-splitting criteria.

### Continuous metrics

Every route reports:

- `abs_gap_error` and combined-error-normalized `gap_z_score` after ED reveal;
- ground and excited variational energy errors;
- local-energy variance for `L=0` and `L=2`;
- `<L^2>` error, `Var(L^2)`, SO(3) residual, swap residual, and multiplet
  splitting;
- effective sample size, autocorrelation time, ESS/s, and estimator throughput;
- optimizer/seed spread;
- wall time, peak RSS, peak VRAM, checkpoint size, and device details;
- `N=8/N=6` smoke ratios for evaluator time and peak memory.

### Winner rule

Selection is lexicographic rather than a hand-tuned weighted score:

1. eliminate every route that fails a hard gate;
2. among survivors, minimize the median `abs_gap_error` across the frozen
   seeds; `gap_z_score` remains a diagnostic and cannot reward inflated error
   bars;
3. if gap errors are statistically tied under the frozen combined-error rule,
   prefer lower median excited-state local-energy variance, then lower seed
   spread;
4. if still tied, prefer better `N=8` smoke growth, then higher ESS/s and lower
   peak memory.

Exactly one survivor advances. If no route passes, Step 4 closes with a failure
comparison and Step 5 does not start. The evaluator may identify the strongest
failed route, but it is not called a winner and is not promoted to larger
systems.

## 8. Five research steps and attempt accounting

The project has **five research steps**, not five total attempts:

1. freeze the common oracle-isolated protocol, evaluator, schema, budgets, and
   failure-report format;
2. implement and evaluate the occupation-space autoregressive route;
3. implement and evaluate the continuous holomorphic route;
4. implement and evaluate the CF-Flow `L=2` route, then select the winner;
5. run the winner at `N=8`; after it passes, run `N=10` and `N=12` on SCNet.

Each step has its own attempt counter `a01` through `a05`. An attempt tests one
explicit technical hypothesis, receives at most 90 minutes of active
implementation time, and runs in its own branch and worktree:

```text
label:    scalable-v1-s02-a01
branch:   challenge/qmc-chiral-graviton-scalable-v1-s02-a01
worktree: D:/Playground/worktrees/quantum.harness/
          challenge-qmc-chiral-graviton-scalable-v1-s02-a01
```

The counter resets to `a01` at the next research step. `slice-pass`, `failed`,
and `inconclusive` closures consume an attempt; `step-pass` completes the step.
If `a05` closes without `step-pass`, all scalable-v1 implementation stops and a
five-attempt step report is produced. A later step never starts from an
incomplete prior step.

`step-pass` means that the step's evidence target is complete, not that a
candidate necessarily passed the physics gates. The exit criteria are:

- Step 1: the common protocol, evaluator, schema, and guard tests are committed
  and pass;
- Steps 2 and 3: the route produces a complete, reproducible evaluation with a
  decisive gate classification; a well-demonstrated hard-gate failure is a
  completed comparison result;
- Step 4: the CF-Flow route has the same decisive evaluation and the winner
  rule has been applied to all three routes;
- Step 5: `N=8` first closes as `slice-pass` after all non-ED physics and
  resource gates pass; the step reaches `step-pass` only after both `N=10` and
  `N=12` produce complete non-ED evaluation records on SCNet.

An optional post-freeze `N=8` ED check may be reported if it remains feasible,
but it is evaluator-only and is not required to unlock `N=10` and `N=12`.
At those larger sizes `ed_crosscheck_valid` is recorded as `not_applicable`, not
silently set to true.

An infrastructure retry with identical commit and configuration remains inside
the same attempt. It does not create a new attempt merely because a Slurm queue
or transport error required resubmission. The next implementation attempt must
change one named technical hypothesis, not only its random seed.

The design/specification work in this document occurs before Step 1 and does
not consume an implementation attempt.

## 9. Logging and failure handling

Each attempt has two evidence layers:

```text
tracked:
  tracks/qmc/solutions/BOTS-848/logs/scalable-v1/sXX-aYY.md

ignored raw artifacts:
  tracks/qmc/results/BOTS-848-scalable-v1-sXX-aYY/
    commands.log
    environment.txt
    stdout.log
    stderr.log
    training-manifest.json
    resource.json
    run.json
    checkpoints/
```

The tracked journal records the hypothesis, starting commit, physics contract,
budget, exact commands, exit codes, result classification, failure mechanism,
and the single changed assumption recommended for the next attempt. Raw logs
record progress and retain the last valid checkpoint.

NaN/Inf, complex local-energy drift, low ESS, failed symmetry gates, resource
exhaustion, timeout, and scheduler failure are explicit result states. The run
must flush progress, persist partial statistics, and preserve its last valid
checkpoint before closing whenever the process remains responsive. No password,
private key, token, full SSH configuration, or secret-bearing environment value
may enter either evidence layer.

## 10. Compute placement

- `N=6` development and comparison runs are local only when the cost estimate is
  below 10 minutes and 16 GB resident memory; otherwise they use SCNet.
- Every route instantiates its `N=8` shape through the same committed capacity
  mapping and performs the same fixed no-training smoke batch for growth
  evidence. No `N=6` checkpoint is assumed to be shape-compatible. Full `N=8`
  optimization is reserved for the selected winner and is placed locally or
  remotely from a fresh cost estimate.
- `N=10` and `N=12` production runs use the `scnet` Slurm profile. The current
  profile exposes `hx1hdnormal01` with 128 CPU cores, about 510 GB memory, and
  Hygon DCUs, but live partition state and the exact job request must be probed
  again before submission.
- The first implementation uses CPU-compatible kernels. DCU acceleration is an
  optional later attempt only after a compute-node device/runtime smoke test;
  CUDA compatibility is never assumed.
- Generated data and environments stay under `D:/Playground` locally and the
  declared remote project/results roots. No large artifact or tool installation
  is written to `C:`.

## 11. Verification strategy

Step 1 builds the verification harness before route implementation:

1. contract tests for `CandidateAdapter`, result schema, deterministic seeds,
   checkpoint hashing, and oracle-isolation guards;
2. tiny `N<=4` exact tests comparing sparse `local_energy`, ladder action, and
   `local_l2` against direct matrices;
3. route-specific LLL and antisymmetry construction tests;
4. numerical particle-swap and random finite-SO(3) tests;
5. `L=2` tower normalization, Casimir, variance, and fivefold-energy tests;
6. MC blocking, ESS, independent-seed, and error-propagation tests;
7. forbidden full-basis/projector/oracle dependency tests;
8. peak-resource capture and the common `N=8` smoke test;
9. a one-command frozen-checkpoint evaluation that writes the complete
   `run.json`.

A route cannot waive a failed gate by arguing that its energy is close to ED.
Conversely, a valid but inaccurate run is retained as evidence and classified
by the exact gate that failed.

## 12. Explicit non-goals

Scalable v1 does not yet implement:

- chiral metric operators `O_+`, `O_-`, weights, or helicity polarization;
- finite-`kappa` Landau-level-mixing scans;
- thermodynamic extrapolation or production sizes above `N=12`;
- the CF-Flow paper's `L=N` transport-gap figure;
- a universal benchmark leaderboard or weighted aggregate score;
- a new cluster environment before the winning route identifies its actual
  dependencies.

These are eligible only after the winning scalable route passes `N=8`.

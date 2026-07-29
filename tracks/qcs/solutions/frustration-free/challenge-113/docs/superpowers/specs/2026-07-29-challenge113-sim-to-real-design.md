# Challenge 113 Sim-to-Real Quantum-Gate Control Design

## Status and decision

This design implements the complete simulated core and the model-mismatch
failure study. Real hardware and a leakage-aware two-transmon model are
extensions after the simulated evidence chain passes.

The numerical core will use JAX with piecewise-constant controls and a product
of segment matrix exponentials. This preserves unitarity to numerical
precision, supports automatic differentiation and Hessian-vector products, and
avoids interpreting ODE-integrator drift as landscape curvature.

The official Colab notebook is authentication-gated. Stages 1 and 2 are
therefore reconstructed from the challenge text and the pinned author notebook,
not claimed as an exact reproduction of the Colab.

## Scientific claim

For phase-insensitive full-unitary synthesis on a controllable, over-resourced
closed system, the Hessian at a regular optimum has at most
\(d^2-1\) nonzero directions. A model-derived approximation to those directions
should reduce the number of expensive black-box queries needed to calibrate a
nearby true device.

The submission must establish both parts:

1. the observed local rank is consistent with the endpoint-map geometry; and
2. the model Hessian subspace provides a query advantage over both full-space
   search and uninformed dimensionality reduction.

The claim is falsified if a random subspace performs comparably, if the
endpoint Jacobian does not support the reported rank, or if the reduced
subspace cannot contain a correction that reaches the target.

## Scope

### Included

- One-qubit \(d=2\) gate synthesis, predicted maximal rank 3.
- Two-qubit \(d=4\) gate synthesis, predicted maximal rank 15.
- Structure-preserving differentiable propagation.
- Open-loop model optimization.
- Dense-Hessian validation and matrix-free Hessian-vector products.
- Endpoint-Jacobian and dynamical-Lie-algebra diagnostics.
- Opaque simulated devices with drift, gain, and unmodeled-term mismatch.
- Exact and finite-shot black-box observations.
- Full, top-\(k\), random-\(k\), and oracle-\(k\) closed-loop searches.
- Search-dimension, model-gap, shot-count, and seed sweeps.
- Failure diagnostics and independently validated target crossings.
- Reproducible, resumable artifacts and publication figures.

### Deferred

- Live cloud-hardware experiments.
- Leakage-aware coupled-transmon production studies.
- Device-driven subspace re-estimation.
- Bayesian optimization.
- Three-qubit \(d=8\) production sweeps.

These are extensions and must not delay the core result.

## Mathematical conventions

### Dynamics

For segment \(n\) of duration \(\Delta t\),

\[
H_n = H_0 + \sum_a u_{a,n} H_a,\qquad
U_{n+1} = e^{-i H_n\Delta t}U_n.
\]

All Hamiltonians are Hermitian and all amplitudes are real. The propagator is
the ordered product from the identity. JAX x64 is mandatory for rank and
curvature measurements.

### Objective

The phase-insensitive process infidelity is

\[
\mathcal L(U) =
1-\frac{|\operatorname{Tr}(U_\mathrm{target}^\dagger U)|^2}{d^2}.
\]

The squared trace is smooth at the optimum and has the same
\(\mathfrak{su}(d)\) dimensionality as the challenge's unsquared fidelity.
No fluence or smoothness penalty is included in the Hessian-rank objective,
because such penalties add artificial curvature to physically flat directions.
Amplitude limits are hard bounds.

The open-loop model gate must reach \(\mathcal L\le10^{-8}\). The black-box
calibration target is true-device infidelity \(\mathcal L\le10^{-3}\), confirmed
by a separate validation observation.

### Coordinates and rank

Control parameters are normalized by their declared amplitude scales before
forming Hessian directions. This prevents arbitrary unit choices from defining
the "top" subspace.

At an optimum, the control Hessian is checked against the endpoint Jacobian
from normalized pulse coordinates to a fixed orthonormal basis of traceless
Hermitian generators. Numerical rank uses a relative singular/eigenvalue
threshold of \(10^{-8}\), with threshold sweeps over \(10^{-6}\) through
\(10^{-10}\) included in diagnostics.

The implementation reports a rank plateau; it does not force exactly
\(d^2-1\). A lower rank is a scientific result if controllability, resource, or
regularity checks explain it.

## Systems

### One qubit

Use a nonzero drift proportional to \(Z\), independent \(X\) and \(Y\)
controls, and a noncommuting target gate. Use 12 segments per control
(\(p=24\)) so the pulse is clearly overparameterized relative to rank 3.

### Two qubits

Use a coupled drift containing \(ZZ\) and unequal local \(Z\) terms, with local
\(X/Y\) controls on both qubits. The target is CNOT up to global phase. Use
20 segments per control (\(p=80\)), well above rank 15.

Before optimization, compute the dynamical Lie closure and verify dimensions 3
and 15 respectively. Failure to reach the expected Lie dimension is a
configuration error, not an optimization result.

## Architecture

The implementation lives entirely under the Challenge 113 solution directory.

- `qcontrol/config.py`: closed, validated experiment dataclasses and canonical
  JSON serialization.
- `qcontrol/systems.py`: Pauli generators, one- and two-qubit systems, targets,
  Lie-closure diagnostics, and perturbation generation.
- `qcontrol/pulses.py`: normalized piecewise-constant parameterization,
  bounds, and subspace-coordinate maps.
- `qcontrol/propagation.py`: JAX matrix-exponential propagation and unitarity
  diagnostics.
- `qcontrol/objectives.py`: model loss, exact true loss, and fidelity
  conversions.
- `qcontrol/open_loop.py`: deterministic multistart L-BFGS-B optimization.
- `qcontrol/landscape.py`: dense Hessian, HVP operator, endpoint Jacobian,
  eigenspaces, rank, and principal angles.
- `qcontrol/device.py`: query-only device protocol, hidden truth model,
  finite-shot estimator, validation observations, and immutable ledger.
- `qcontrol/closed_loop.py`: common derivative-free search interface for all
  candidate spaces.
- `qcontrol/experiments.py`: trial generation and execution.
- `qcontrol/artifacts.py`: canonical hashing, JSON/JSONL schemas, atomic
  publication, locking, resume, and verification.
- `qcontrol/analysis.py`: aggregation, confidence intervals, target-query
  statistics, and figure-ready tables.
- `run.py`: explicit command-line entry point.

The dedicated environment is defined inside the challenge directory. Core
dependencies are JAX/JAXlib, NumPy, SciPy, Matplotlib, pytest, and `cma`.
No root lockfile is modified.

## Three-stage data flow

### Stage 1: open-loop model optimization

For each system and seed:

1. construct the model and target;
2. validate Hermiticity and Lie-algebra dimension;
3. run bounded multistart L-BFGS-B;
4. require model infidelity at most \(10^{-8}\);
5. save the normalized optimum, diagnostics, and source/config hashes.

The best pulse is selected by loss, then gradient norm, with deterministic
tie-breaking.

### Stage 2: landscape extraction

At the accepted optimum:

1. compute a dense Hessian for d=2 and the initial d=4 validation case;
2. verify HVPs against dense products;
3. compute leading eigenpairs matrix-free for production;
4. compute endpoint-Jacobian singular values;
5. compare Hessian and Jacobian ranks;
6. save top eigenvectors in normalized coordinates.

Degenerate eigenspaces are compared as subspaces, never by individual vector
signs or ordering.

### Stage 3: query-only calibration

The device accepts a complete pulse and returns only an observation plus query
metadata. Optimizers cannot access its Hamiltonian, exact fidelity, gradients,
or Hessian. Exact truth is exposed only to the offline evaluator.

Candidate spaces are:

- full \(p\)-dimensional normalized pulse space;
- model-Hessian top-\(k\) space;
- seeded random orthonormal \(k\)-space;
- true-device oracle top-\(k\) space, simulation-only.

All methods start from the same model-optimal pulse and use the same
derivative-free optimizer, amplitude constraints, query budget, stopping rule,
and validation policy. CMA-ES is the production optimizer because it is robust
to moderate observation noise. A deterministic Nelder-Mead smoke case checks
the noiseless interface.

## Simulated device

Truth-model perturbations are private and generated from:

- normalized drift perturbation;
- independent control-gain errors;
- one normalized unmodeled Hermitian term.

Gap magnitudes are relative to the model drift norm:
\(\varepsilon\in\{0,0.02,0.05,0.10,0.20\}\). Each nonzero magnitude uses
multiple seeded perturbation orientations.

The exact mode returns process fidelity without noise. The finite-shot mode
uses a binomial estimator whose success probability is the exact process
fidelity. This is an explicitly labeled abstract measurement model, not a claim
to implement randomized benchmarking. Shot settings are
\(N_\mathrm{shot}\in\{10^3,10^4\}\) per query.

A target crossing is provisional until an independent \(10^5\)-shot validation
query has a one-sided 95% confidence bound above fidelity 0.999. Validation
shots are included in total shot cost but not optimizer-query count.

## Experiment matrix

### Geometry acceptance

- d=2 with parameter counts 2, 4, 6, and 24.
- d=4 with parameter counts 8, 16, 32, and 80.
- At least five open-loop initializations per configuration.
- Report model fidelity, Hessian spectrum, endpoint-Jacobian spectrum,
  Lie-algebra dimension, rank-threshold sensitivity, and unitarity error.

### Headline calibration study

For d=4, p=80:

- \(k\in\{5,10,15,20,30,80\}\);
- all five gap magnitudes;
- exact, \(10^3\)-shot, and \(10^4\)-shot observations;
- top-\(k\), random-\(k\), full-space, and oracle-\(k\) methods;
- 20 independent trial seeds;
- a fixed optimizer-query budget of 2000.

Development runs use three seeds and a 200-query budget. They are never mixed
with production summaries.

### Invariant check

For d=2, compare \(k\in\{1,2,3,4,6,24\}\) under exact and \(10^3\)-shot
observations, using the same gap family and 20 seeds. The expected useful
dimension is near 3 rather than 15.

## Metrics and figures

Primary metrics:

- first optimizer query with independently validated target attainment;
- total shots to validated target;
- success probability within the fixed budget.

Secondary metrics:

- median best exact infidelity versus query count with bootstrap confidence
  bands;
- final infidelity under fixed budget;
- attainable noiseless fidelity floor within each subspace;
- principal angles between model and truth subspaces;
- Hessian eigenvalue gaps and effective ranks;
- amplitude-bound activity and propagation unitarity.

Required figures:

1. queries-to-target versus search dimension, with full/random/oracle
   baselines and confidence intervals;
2. success probability and query advantage versus model-gap magnitude;
3. model/true subspace principal angles and restricted fidelity floor versus
   gap;
4. d=2 and d=4 rank/invariant comparison;
5. one explicit failure case where the fixed model subspace loses its
   advantage.

## Fairness and failure policy

- All compared methods share the same device instances and trial seeds.
- Random subspaces are independently seeded and paired by device instance.
- Query and shot counters are monotonic and cannot be reset by optimizers.
- Optimizer compilation and model-only work never count as device queries.
- Noisy target crossings require independent validation.
- Failed or budget-exhausted trials remain in the dataset.
- If random-\(k\) matches top-\(k\), the reported conclusion is generic
  dimensionality reduction, not model-informed transfer.
- If oracle-\(k\) fails, diagnose optimizer/noise/constraints before blaming
  model-subspace rotation.
- If restricted noiseless optimization has a fidelity floor, report
  representational failure directly.
- Results are rejected if changing propagation resolution materially changes
  rank or headline conclusions.

## Artifacts and restartability

Each run uses a content-derived identifier and stores:

```text
results/<run-id>/
  config.json
  manifest.json
  open_loop.json
  landscape.npz
  trials/<trial-id>.json
  ledger/<trial-id>.jsonl
  summary.json
  figures/
```

Manifests bind source revision, lockfile hash, Python/JAX versions, device kind,
precision, system definition, optimizer settings, and input hashes.

Each trial publishes through a temporary file, fsync, and atomic rename.
Completed artifacts are immutable. Resume validates hashes and continues only
missing trials. A stale, malformed, or provenance-mismatched artifact fails
closed.

## Testing

### Unit tests

- Hamiltonians are Hermitian and dimensions agree.
- Lie closure returns dimensions 3 and 15.
- Propagation is unitary within \(10^{-12}\) in x64.
- Fidelity is invariant under global phase.
- JAX gradients agree with central differences.
- HVPs agree with dense Hessian products.
- Endpoint-Jacobian rank agrees with controlled analytic cases.
- Pulse normalization and subspace maps are inverse-consistent.
- Device observations are deterministic under fixed seeds.
- Device clients cannot retrieve truth internals through the public protocol.
- Query and shot counts are exact.
- Atomic publication preserves the previous valid artifact on failure.

### Integration tests

- d=2 open-loop optimization reaches \(10^{-8}\).
- d=2 Hessian rank is stable near 3 over threshold sweeps.
- A zero-gap device needs no calibration beyond validation.
- A small-gap top-3 search beats a paired random one in a deterministic fixture.
- Interrupted sweeps resume without duplicate trials or query-ledger mutation.

### Scientific acceptance

- Both system Lie dimensions pass.
- Dense and matrix-free leading eigenspaces agree.
- Rank conclusions survive timestep refinement.
- Headline summaries contain all methods, gaps, shot regimes, and 20 seeds.
- The main conclusion includes a paired uncertainty estimate and an explicit
  failure regime.

## Compute strategy

CPU is sufficient for unit tests, geometry validation, and development trials.
One GPU is used only after CPU correctness passes, primarily for batched
production seeds and repeated HVP/propagation calls. The runtime records compile
time separately from warm execution and fails if a requested GPU silently
falls back to CPU.

No cluster submission occurs until a local three-seed pilot estimates runtime,
memory, and projected total cost.

## Completion criteria

The simulated core is complete when:

1. all software and scientific acceptance tests pass;
2. d=2 and d=4 geometry diagnostics support the reported ranks;
3. the paired headline study demonstrates whether model-informed top-\(k\)
   directions beat random-\(k\) and full-space searches;
4. the model-gap crossover and at least one honest failure case are reported;
5. all figures derive from verified immutable artifacts; and
6. a fresh environment can reproduce the development study from documented
   commands.

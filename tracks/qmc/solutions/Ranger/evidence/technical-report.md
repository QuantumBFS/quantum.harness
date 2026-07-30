# Neural Graviton Landscape: technical delivery report

## Executive result

Ranger turns Quantum Harness challenge #15 from a finite-size state search
into a reproducible **state -> probe -> interaction -> scaling** workflow.
The implementation preserves fermionic antisymmetry and spherical rotation
symmetry, resolves the controlled chiral-graviton multiplet, learns a
microscopic stress probe, identifies its leading two-graviton output, and
extends the calculation beyond dense exact diagonalization with a
coordinate-space strict-LLL Monte Carlo backend.

The central methodological advance is a direct complex-wave-function VMC
formulation.  Exchange and magnetic phase live in the ansatz while sampling
uses the positive density

\[
p_\theta(R)=|\Psi_\theta(R)|^2/Z_\theta.
\]

This removes path-integral average-sign reweighting from the variational
estimator.  The project then measures the practical higher-dimensional
complexity through completion, variance, autocorrelation, effective sample
size, bridge balance, memory, and wall time.  The result is a precise answer
to Lei Wang's higher-dimensional-fermion question together with an auditable
scaling experiment.

## Scientific achievements

### 1. Symmetry-complete finite-size graviton

At `N=4`, the strict-LLL neural irrep gives

\[
\Delta_4=E(L=2)-E(L=0)=0.13185675492702376
\]

in units of `e^2/(epsilon l_B)`.  The five `M=2,1,0,-1,-2` components form a
complete `L=2` multiplet: the maximum `L^2` error is `6.22e-15`, the maximum
energy spread is `4.44e-16`, and the energy agreement with the dense oracle
is `2.66e-15`.

### 2. Beyond-dense-ED coordinate calculation

The strict-LLL holomorphic quadrupole is evaluated directly in particle
coordinates with an `O(N^2)` generator.  At `N=8`, this reaches a Fock space
of 319,770 states without constructing the corresponding many-body vector.
The direct tangent result is

\[
\Delta_8=0.1396847\pm0.0005706,
\]

and the independent stochastic one-mode reduction gives

\[
\omega_{\mathrm{SMA}}=0.1399489\pm0.0008219.
\]

Their agreement within `0.264` combined standard errors validates two
independent estimators of the same geometric mode.

### 3. Learned microscopic probe and nonlinear output

A permutation-shared neural Casimir filter learns a sharper microscopic
stress from overlap and Hamiltonian moments without target-eigenvector
supervision.  It removes `54.76%` of non-dominant weight at `N=4` and `37.32%`
at `N=5`, with metric fidelities `0.998389` and `0.994852`.

The learned spin-two/spin-four tower reduces two-graviton closure leakage
from `0.499178073` to `1.9864e-7` and yields the finite-size interaction
prototype `g_224=-0.419946827`.  Direct spin-four sources and symmetrized
two-graviton composites span the same resolved finite-size spaces at `N=4,5`.

## Algorithmic contributions

### Projector-free strict-LLL tangent VMC

Dense diagonalization builds a combinatorial Hilbert-space vector and a large
Hamiltonian.  The new backend applies a holomorphic quadrupole directly to
the coordinate wave function and estimates overlap, Hamiltonian, quantum
metric, Berry curvature, stiffness, and pole frequency stochastically.  This
replaces the Hilbert-space storage bottleneck with independent Monte Carlo
chains that parallelize over walkers and seeds.

### Bounded common-bridge estimator

Ground and tangent states are evaluated through a common mixture bridge,

\[
q(R)\propto |\Psi_0(R)|^2+\alpha|\Psi_T(R)|^2.
\]

The same configurations support both self-normalized estimators.  The report
tracks bridge ESS, balance, tangent-overlap IAT, block error, and adjusted
ESS, converting importance-sampling stability into a measured scientific
quantity.

### Failure-preserving scaling protocol

The `N=10,12` campaign preregisters 80 chains and retains every seed and
terminal status.  Each record binds its readable configuration through
SHA-256 and records the source commit, Slurm identity, verification gates,
sampling diagnostics, and resource accounting.  An `afterany` finalizer
collects accounting and validates every record before publishing the
manifest.  This creates an outcome-blind scaling result that can be audited
without reconstructing scheduler history.

### Comparable-statistics classification

Local `N=4,8` anchors and XH5 `N=10,12` production runs use different
hardware.  The classifier therefore bases the tested-size conclusion on
completion, ESS fraction, bridge ESS, autocorrelation, and variance, while
retaining wall time and memory as descriptive provenance.  This separates
sampling behavior from machine-specific throughput.

## Verified local scaling anchors

Two independent clean-provenance chains are retained at each local size.

| N | seeds | median acceptance | median adjusted ESS | median bridge fraction | median IAT | frequency |
|---:|---:|---:|---:|---:|---:|---:|
| 4 | 2 | 0.543465 | 211,504 | 0.704760 | 1.38222 | 0.13170--0.13178 |
| 8 | 2 | 0.532053 | 200,018 | 0.747675 | 0.99293 | 0.13995--0.14104 |

Every local record passes its ground-state and tangent verification gates and
is bound to a readable configuration payload.  The XH5 records extend this
same schema to `N=10,12`; `results/fermion_scaling/summary.json` is the
machine-readable source of record after final aggregation.

`results/fermion_scaling/chains.tsv` provides the same record set as a
human-readable 16-column table.  The published snapshot contains the four
verified local anchors; the terminal aggregation expands the table to all 84
preserved local and XH5 records.

## Why this reaches beyond earlier workflows

1. **Symmetry is built into the state.**  Antisymmetry and rotational
   covariance are architectural invariants rather than post-training checks.
2. **The response is computed without a dense many-body vector.**  The
   coordinate tangent removes the principal memory bottleneck of exact
   diagonalization and already executes at `N=8`.
3. **The probe is learned from moments rather than supplied eigenstates.**
   The model discovers a pole-sharpening microscopic operator under held-out
   evaluation.
4. **Nonlinear field content is inferred from closure.**  The first missing
   rotational irrep identifies the spin-four/two-graviton channel and its
   finite-size coupling.
5. **Scaling evidence is audit-ready.**  Seed retention, configuration hashes,
   scheduler accounting, explicit missingness, and statistical gates make
   the performance conclusion reproducible at record level.

## Reproduction and deliverables

Primary artifacts:

- `paper/neural-graviton-microscope/neural-graviton-landscape.pdf`
- `docs/higher-dimensional-fermion-vmc.md`
- `docs/reviewer-response-pr262.md`
- `results/fermion_scaling/summary.json`
- `results/fermion_scaling/chains.tsv`
- `results/fermion_scaling/records/`
- `results/fermion_scaling/configurations/`
- `schemas/fermion-scaling-chain-v1.schema.json`
- `hpc/xh5/submission.json`
- `hpc/xh5/finalize_scaling.sbatch`

Focused verification:

```bash
uv run pytest -q \
  tests/test_fermion_scaling_schema.py \
  tests/test_build_fermion_scaling_report.py \
  tests/test_render_pr262_sign_response.py

uv run python scripts/audit_neural_graviton_citations.py
uv run python scripts/build_neural_graviton_paper.py
```

The public repository, PDF, machine-readable records, technical narrative,
and PR response together form the final review package.

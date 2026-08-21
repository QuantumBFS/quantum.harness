# Phase 6 bounded DMRG optimization design

## Scope

Optimize the locked sigma=1.75 TeNPy workflow without changing the
Hamiltonian, Gamma grid, parity sectors, observables, fitting convention, or
numerical acceptance rules. No approximate MPO compression and no cluster
submission are allowed in this phase.

The local benchmark scope is:

- implementation and ED-backed tests at `L <= 12`;
- a forward/reverse continuation test at `L=16` around `Gamma=1.560` only
  when its measured local cost remains within the local budget;
- one optimized `L=32`, `Gamma=1.560`, `K=24`, `chi=128` timing benchmark;
- no full `L=32` continuation scan.

All ED-based acceptance gates stop at `L=12`. No exact diagonalization is
required or attempted at `L=16` or above.

## Components

### Exact zero-channel pruning

Before constructing the MPO graph, remove only entries whose fitted
coefficient is exactly equal to floating-point zero. Do not threshold small
positive coefficients. Lambda/coefficient ordering and the original fit hash
remain in provenance, together with the active-channel indices.

The current fit has three exact zeros, so the bulk MPO dimension should change
from 50 to 44. Coefficient reconstruction, dense-MPO equality, low-energy ED,
and correlation tests must pass before this graph is used in DMRG.

### Checkpoint format

Each converged state is saved atomically as:

```text
<cell>/state.h5
<cell>/checkpoint.json
```

`state.h5` uses TeNPy's HDF5 serialization for the complete MPS. The JSON
sidecar records:

- Hamiltonian/model hash;
- fit hash and active-channel indices;
- `L`, `Gamma`, `sigma`, `K`, `alpha`, and `r_fit`;
- parity sector;
- requested and reached chi;
- complete DMRG options;
- energy, variance, discarded weight, sweeps, and convergence status.

Loading rejects any mismatch in Hamiltonian, sector, physical sites, or
provenance. Writes use a temporary file followed by an atomic rename.

### Continuation

The DMRG sector runner accepts an optional checkpointed MPS instead of a
product state. Even and odd sectors have independent continuation chains and
checkpoints. Gamma values remain exactly the preregistered values.

At `L=16`, compute the target `Gamma=1.560` by:

```text
forward: 1.559 -> 1.560
reverse: 1.561 -> 1.560
```

Compare the two target states using:

- absolute energy difference `<= 1e-8` in each sector;
- relative gap difference `<= 1e-6`;
- variance and discarded-weight agreement, with both paths independently
  satisfying the locked numerical convergence rules;
- absolute `R_xi` difference `<= 1e-6`;
- maximum absolute full-correlation difference `<= 1e-6`.

There is no ED comparison at `L=16`. A failed forward/reverse criterion blocks
continuation from production use; it is not resolved by choosing the path
closer to an expected literature value.

Before starting the complete L=16 path pair, run a bounded timing probe and
estimate the remaining local work. If the estimate exceeds the harness local
budget, defer the L=16 continuation test until a cluster profile is available.
The L<=12 ED gates remain the required local qualification.

### Staged chi

The staged schedule is `32 -> 64 -> 128`. Each stage starts from the previous
stage's checkpoint in the same Hamiltonian and sector. DMRG convergence is
applied independently at every stage, and all stage diagnostics are retained.

Tests require non-increasing variational energy with increasing chi. At
`L <= 12`, the final staged state must agree with direct `chi=128` and ED
within the existing spectrum/correlation tolerances. The `L=32` benchmark
compares final energy, gap, `R_xi`, correlations, discarded weight, sweeps,
and wall time against the existing direct-`chi=128` baseline.

### Observable reuse

Observable and variance calculations load the converged checkpoint rather
than rerunning DMRG. The raw manifest continues to retain full `C(r)`,
`S(0)`, `S(k_min)`, `xi`, `R_xi`, variance, discarded weight, reached chi,
and sweep history.

## Test-first sequence

1. Checkpoint round-trip identity and provenance-mismatch rejection.
2. Exact zero-channel pruning and unchanged MPO/ED observables.
3. Warm-start continuation correctness in both parity sectors.
4. Staged-chi energy monotonicity and final-state agreement.
5. Cost-gated `L=16` forward/reverse DMRG-only qualification.
6. One bounded optimized `L=32` benchmark.
7. Full solution test suite and diff hygiene.

## Production estimate update

Use the measured ratio

```text
optimized L=32 base-cell time / original L=32 base-cell time
```

to update the fixed-chi base-grid estimate. Report higher-chi refinements
separately using measured staged behavior when available; do not present the
leading `chi^3` estimate as a measured runtime.

## Failure handling

- Corrupt or mismatched checkpoints are never silently reused.
- Interrupted checkpoint writes leave the previous successful checkpoint
  intact.
- Failed DMRG stages remain explicit and cannot seed later stages.
- Continuation disagreement blocks warm starts but leaves independent cold
  starts available.
- Approximate MPO compression is out of scope.

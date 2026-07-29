# VQETape Differentiation-Aware VQE Co-Design

**Date:** 2026-07-29

**Status:** Approved by the user after review of the measured spatial-transfer
results and the proposed next-stage research directions.

## Problem

VQETape now evaluates the exact one-dimensional TFIM VQE kernel

\[
\theta\longmapsto
\left(E(\theta),\nabla_\theta E(\theta)\right)
\]

with three progressively more structured representations:

1. state-vector execution;
2. one global bra–MPO–ket contraction;
3. an exact rolled spatial transfer with boundary
   \(D=3\cdot4^L\).

The spatial representation reduced the 100-call compile-plus-execute
objective by 4.31x at \(n=8,L=2\) and 8.45x at \(n=12,L=2\). It also reduced
compiler temporary memory and logical reverse-mode tape size. Its remaining
measured weakness is single-call throughput: the best spatial warm kernel is
about 1.26x slower than the best global MPO kernel on the audited CPU
workloads.

The next stage must improve that warm kernel without losing the rolled
program's compile and memory advantages. It must then extend the optimizer
from forward contraction paths to complete differentiated programs and from
a fixed VQE-call horizon to measured time-to-solution.

## Goal

Build an exact, reproducible VQE co-design system with four linked layers:

1. **Blocked spatial lowering:** contract multiple neighboring sites in one
   rolled spatial body while preserving the exact boundary.
2. **Differentiation-aware contraction planning:** score and select paths
   using forward work, reverse work, saved residuals, liveness, compiler
   complexity, and measured device behavior.
3. **Symmetry-aware execution:** identify exact conserved Abelian charges and
   eliminate forbidden spatial-boundary sectors without numerical
   approximation.
4. **End-to-solution VQE tuning:** select the execution program, optimizer,
   initialization, and ansatz growth rule by wall-clock time and memory needed
   to reach a target energy error.

The complete system remains exact within the configured floating-point
tolerance. Approximate tensor truncation is outside this design.

## Success criteria

### Exactness

- Every blocked, custom-adjoint, symmetry-aware, and VQE-training candidate
  agrees with the existing complex128 state-vector or global-MPO oracle where
  that oracle is feasible.
- Energy and complete-gradient checks remain mandatory before performance
  selection.
- Unused padded RZZ parameters continue to have exactly zero gradient.
- Symmetry compression removes only sectors proven unreachable by discrete
  charge propagation.

### Performance

- At \(n=12,L=2\), the best blocked spatial candidate targets at least a 20%
  reduction in warm value-and-gradient time relative to the current best
  spatial result.
- A promoted blocked spatial candidate must preserve a meaningful compile or
  compiler-temporary-memory advantage over the best exact global-MPO control.
- AD-aware path ranking must beat or match forward-only ranking on at least
  one holdout workload without regressing correctness.
- Large-chain checkpoint claims require measured device or compiler memory;
  logical tape and modeled boundary bytes remain separately labeled.

### VQE outcome

- Training reports the first iteration and wall-clock time at which
  \(E(\theta)-E_0\leq\epsilon\).
- Solver selection includes compile, all value-and-gradient calls, optimizer
  overhead, and recompilation caused by ansatz changes.
- A contraction-aware adaptive ansatz must be compared with a fixed ansatz
  and ordinary gradient-only adaptive selection under equal search budgets.

### Generality

- TFIM remains the exact small-system oracle and first performance workload.
- At least one holdout one-dimensional Hamiltonian or ansatz family must
  exercise a different MPO bond dimension or conserved charge.
- Results must distinguish fixed-depth one-dimensional scaling from generic
  VQE simulation.

## Architecture

### 1. Blocked spatial program

Replace the one-site recurrence

\[
B_{i+1}=F_i(B_i;\theta_i)
\]

with an exact block recurrence

\[
B_{q+1}
=
F^{(b)}
\left(
B_q;
\theta_{qb},\ldots,\theta_{qb+b-1}
\right).
\]

The planner partitions the existing operator-Schmidt bra–MPO–ket template
into first, repeated bulk-block, tail, and last programs. The current boundary
is an explicit operand of every bulk block and is never expanded into a
\(D\times D\) transfer matrix.

The external boundary remains

\[
\operatorname{shape}(B)
=
\underbrace{(2,\ldots,2)}_{2L}
\mathbin{\|}(3,),
\qquad
D=3\cdot4^L.
\]

For a block width \(b\), scan iterations fall from \(n-2\) to approximately
\(\lceil(n-2)/b\rceil\). The block-local graph grows with \(b\), exposing
additional fusion and contraction-order choices while keeping the rolled
body independent of total chain length.

`SpatialProgramConfig` gains `block_width`. Candidate generation searches:

\[
b\in\{1,2,3,4\},
\qquad
u\in\{1,2,4\},
\]

subject to workload size. First, block, tail, and last paths are serialized
once and reused by every AD policy for a fixed representation.

### 2. Differentiated contraction analysis

For every binary forward contraction

\[
C=\operatorname{contract}(A,B),
\]

the analyzer constructs the two reverse contractions

\[
\bar A=\operatorname{contract}(\bar C,B^*),
\qquad
\bar B=\operatorname{contract}(A^*,\bar C).
\]

It records:

- forward FLOPs and largest intermediate;
- reverse FLOPs and largest reverse intermediate;
- residual values required by the reverse graph;
- a deterministic reverse schedule;
- peak live residual elements under that schedule;
- estimated tensor read/write bytes;
- contraction and kernel count;
- StableHLO text size and operation counts when lowering succeeds.

The first static objective is

\[
\mathcal C_{\mathrm{AD}}(p)
=
\alpha F_{\mathrm{fwd}}
+\beta F_{\mathrm{bwd}}
+\gamma M_{\mathrm{live}}
+\delta B_{\mathrm{traffic}}
+\eta N_{\mathrm{contraction}}.
\]

Measured candidate data subsequently calibrates a hardware-specific linear
or log-linear surrogate. Static ranking reduces the number of expensive
fresh-process compilations but never replaces empirical selection.

### 3. Explicit block adjoint

The generic reverse-mode baseline remains available. A new custom VJP defines
the block map

\[
(B_q,\theta_q,\bar B_{q+1})
\longmapsto
(\bar B_q,\bar\theta_q)
\]

using the serialized differentiated contraction program.

The forward residual contains only values selected by the differentiated
planner. Gate matrices and inexpensive trigonometric values may be
recomputed. Forward and reverse contraction paths may differ.

Checkpoint policies compare:

- ordinary reverse mode;
- full block rematerialization;
- selective residual saving;
- segmented block checkpoints for large chains.

Segment length is not tuned further until a workload contains enough blocks
for its asymptotic storage benefit to be observable.

### 4. Exact symmetry sectors

The compiler represents each supported index by an Abelian charge and each
tensor by a charge-conservation rule. For TFIM:

\[
S=X^{\otimes n},
\qquad
[H,S]=0,
\qquad
[U(\theta),S]=0.
\]

The configured \(|+\rangle^{\otimes n}\) initial state is in the positive
\(\mathbb Z_2\) sector. RZZ Schmidt factors and MPO channels receive explicit
charges. Boundary assignments violating the local conservation rule are
excluded at planning time.

The first implementation uses a dense gather/scatter reference:

1. derive active flattened boundary positions;
2. expand a compressed carry only inside the reference transition;
3. contract with the verified dense column program;
4. gather the next active carry.

After correctness is proven, the production block program contracts only
charge-compatible blocks and does not materialize the dense carry. The
reference remains an oracle.

Symmetry metadata is part of the serialized program signature. A gate or
Hamiltonian that violates the declared symmetry disables compression rather
than silently producing a partial result.

### 5. Hardware execution and profiling

The JAX/XLA implementation remains mandatory and portable. Device reporting
records backend, device kind, JAX version, dtype, and synchronization method.

On GPU-capable environments the benchmark additionally records:

- device peak allocation when exposed by the backend;
- XProf trace location;
- executable temporary and argument bytes;
- optional kernel count and HBM traffic from an external profile.

A Pallas or cuTensorNet block backend is introduced only behind an optional
capability check. Absence of CUDA must skip the backend with an explicit
reason and must not invalidate CPU correctness tests.

### 6. End-to-solution VQE

Introduce a training workload:

```python
@dataclass(frozen=True)
class VQETrainingRequest:
    compile_request: CompileRequest
    optimizer: Literal["adam", "lbfgs", "natural_gradient"]
    target_energy_error: float
    max_steps: int
    ground_energy: float | None
    initialization: Literal["zeros", "random", "recycled"]
```

and a result:

```python
@dataclass(frozen=True)
class VQETrainingResult:
    program_label: str
    optimizer: str
    converged: bool
    steps: int
    compile_seconds: float
    optimization_seconds: float
    time_to_target_seconds: float | None
    peak_rss_bytes: int
    final_energy: float
    target_energy: float
    trace: tuple[VQEStep, ...]
```

The initial solver set is:

- deterministic gradient descent/Adam for compatibility;
- SciPy L-BFGS-B when the optional dependency is installed;
- a damped block-diagonal natural-gradient reference.

Parameter recycling maps a converged translation-invariant layer pattern from
one chain length, depth, or nearby coupling to a compatible target workload.
Every initialization is serialized with its provenance.

### 7. Contraction-aware ansatz growth

The first adaptive pool contains exact, local, symmetry-compatible operators
already supported by the tensor representation. For a candidate \(A\), the
selector records its energy-gradient signal, optional local metric, and the
predicted change in spatial and compiler cost.

The score is

\[
S(A)
=
\frac{|g_A|^2/(F_{AA}+\varepsilon)}
{1
+\lambda_D\Delta\log D_A
+\lambda_C\Delta T_{\mathrm{compile},A}
+\lambda_W\Delta T_{\mathrm{warm},A}
+\lambda_M\Delta M_A}.
\]

The comparison set includes:

- fixed RZZ–RX ansatz;
- gradient-only adaptive selection;
- contraction-aware adaptive selection.

Dynamic ansatz growth uses a structural cache key. Reusing an executable is
allowed only when topology, tensor shapes, dtype, compiler version, and
device signature match.

## Data flow

```text
VQE specification
    |
    v
Exact tensor template
    |
    +--> symmetry and operator-Schmidt analysis
    |
    v
Blocked spatial candidates
    |
    +--> forward contraction paths
    +--> differentiated contraction analysis
    +--> AD/checkpoint policies
    |
    v
Static pruning
    |
    v
Fresh-process compile and benchmark
    |
    v
Correctness filter + Pareto frontier
    |
    v
VQE optimizer / initialization / ansatz search
    |
    v
Time-to-target report
```

## Failure handling

- Invalid block widths, unroll factors, segment lengths, and path arities are
  rejected during configuration construction.
- A serialized path is replanned or rejected if operand shapes differ.
- Missing optional GPU or SciPy capabilities produce a structured skipped
  result, never a false pass.
- NaN/Inf energies, gradients, optimizer states, and metric solves invalidate
  the candidate.
- Natural-gradient solves add configurable damping and report conditioning or
  solver failure.
- Symmetry compression always checks the dense reference on small workloads;
  a nonzero supposedly forbidden sector is a hard error.
- Fresh-worker timeout and out-of-memory remain candidate failures and do not
  abort other candidates.

## Testing

### Unit tests

- block partition and tail handling for every \(n\bmod b\);
- exact block energy and complete gradient against the one-site program;
- boundary dimension and no-\(D^2\) invariants;
- differentiated FLOP/residual/liveness calculations on hand-checkable
  contractions;
- custom block VJP against `jax.vjp`;
- \(\mathbb Z_2\) charge propagation and forbidden-sector detection;
- VQE optimizer stopping, trace serialization, and parameter recycling.

### Integration tests

- fixed-path comparisons across default, remat, selective, and custom VJP;
- fresh-process blocked candidate search;
- global-MPO versus blocked-spatial Pareto selection;
- TFIM time-to-target using an exact ground-energy oracle;
- one holdout Hamiltonian or ansatz family;
- optional GPU capability and skip behavior.

### Regression tests

All existing state-vector, direct-TN, operator-Schmidt, MPO, spatial,
fresh-worker, and CLI tests remain green. Previous report schemas remain
readable.

## Staged delivery

The design is delivered as four independently testable subprojects:

1. blocked spatial execution and joint autotuning;
2. differentiated contraction analysis and explicit VJP;
3. exact symmetry-aware compression;
4. end-to-solution VQE and contraction-aware ansatz selection.

GPU profiling is integrated across the stages when a compatible device is
available. Each stage produces a raw JSON report, a human-readable findings
document, and a decision-gate audit before the next stage becomes the default.

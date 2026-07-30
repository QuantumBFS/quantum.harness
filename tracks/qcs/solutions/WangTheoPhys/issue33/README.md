# VQETape

VQETape is a research compiler prototype for exact classical simulation of the
core Variational Quantum Eigensolver kernel:

\[
\theta \mapsto \left(E(\theta), \nabla_\theta E(\theta)\right).
\]

It compares mathematically equivalent forward-control-flow and reverse-mode
residual schedules under a memory budget. The current oracle prototype supports
open-boundary 1D TFIM workloads and state-vector execution with JAX.

## Submission

| | |
|---|---|
| **Team** | Ranger |
| **Member** | Junkai Wang |
| **Challenge** | [QuantumBFS/quantum.harness #33](https://github.com/QuantumBFS/quantum.harness/issues/33), released by Shi-Xin Zhang |
| **Track** | Quantum circuit simulation (`qcs`) |
| **Status** | Completed exact research prototype with audited RTX 3090 validation, a same-machine TensorCircuit-NG threshold, and a correct Fig. 2 protocol/GPU smoke; the formal Fig. 2 scale run remains open |

The audited implementation jointly searches over tensor representation,
contraction path, reverse-mode program, checkpoint schedule, symmetry sector,
classical optimizer, initialization, and ansatz growth. On the recorded CPU
experiments:

- selected spatial-transfer programs reduced the
  \(T_{\mathrm{compile}}+100T_{\mathrm{warm}}\) objective by **3.66x** at
  \(n=8,L=2\) and **6.08x** at \(n=12,L=2\) against exact global-MPO
  controls;
- explicit contraction-tree VJPs reduced logical tape in every valid
  fixed-path comparison and occupied measured Pareto fronts;
- segmented state-vector adjoints reduced compiler-reported temporary memory
  by up to **62.4%** in the audited examples;
- a commutator-complete adaptive pool reached \(5.05\times10^{-11}\) energy
  error with 10 parameters, while the 14-parameter fixed control stopped at
  \(1.70\times10^{-7}\) under the same comparison budget.

The RTX 3090 validation additionally confirms statevector, direct-TN, and
spatial-transfer execution on JAX's CUDA backend. At `n=10,L=4`, the fixed
spatial representative reduces `compile + 100 warm` by **43.1%** relative to
the fixed statevector representative, while statevector remains the faster
warm kernel. The experiment also finds that platform-default GPU matmul
precision violates the declared exactness tolerance; fresh VQETape workers
therefore default to `JAX_DEFAULT_MATMUL_PRECISION=highest` unless explicitly
overridden.

The same RTX 3090 now also has an audited TensorCircuit-NG 1.8.0 baseline for
the identical RZZ/RX workload. TensorCircuit-NG records 18.2720 s for
`compile + first + 100 warm`; VQETape statevector records 29.4617 s and the
selected VQETape spatial representative records 16.7781 s. Thus spatial is
8.2% faster on the declared objective and uses 28.3% less host peak RSS, while
the sampled 272--274 MiB device allocations are tied at this size. This is a
real same-workload threshold, not a reproduction of the paper's larger
`N=32,L=16` SU(4) Fig. 2 protocol. See
[`outputs/tensorcircuit-ng-baseline-findings.md`](outputs/tensorcircuit-ng-baseline-findings.md)
for the matched comparison and precision audit,
[`outputs/vqetape-gpu-rtx3090-findings.md`](outputs/vqetape-gpu-rtx3090-findings.md)
for the complete GPU A/B evidence and
[`docs/vqetape-completion-audit.md`](docs/vqetape-completion-audit.md) for the
requirement-to-evidence matrix and interpretation boundaries.

The paper's larger Fig. 2 protocol is also executable through a separate,
safe-JSON find/execute CLI. An RTX 3080 `N=6,L=3` structural smoke passed a
direct value-gradient check at `2.38e-7` energy error and `3.29e-7` gradient
relative error. This closes the protocol-construction gate, not the formal
`N=32,L=16` H200-scale gate. See
[`outputs/tensorcircuit-ng-fig2-smoke-findings.md`](outputs/tensorcircuit-ng-fig2-smoke-findings.md).

## Reviewer Package

Start with the compact submission bundle rather than reconstructing the result
from individual experiment logs:

| Artifact | Purpose |
|---|---|
| [Technical report (PDF)](submission/output/pdf/vqetape-technical-report.pdf) | Seven-page visual report with protocol, performance plots, correctness, limitations, and reproduction |
| [Technical report (Markdown)](submission/vqetape-technical-report.md) | Searchable full narrative and exact commands |
| [Standalone HTML report](submission/report.html) | Browser-friendly executive review |
| [Matched benchmark TSV](submission/vqetape-matched-benchmark.tsv) | Four exact RTX 3090 comparison rows for downstream analysis |
| [Literal status text](submission/submission-status.txt) | Pass/fail/open statement with no implied claims |
| [Artifact manifest](submission/artifact-manifest.json) | SHA256 binding for the review artifacts and canonical evidence |

The matched result is deliberately split by criterion: VQETape spatial is
**8.2% faster** for `compile + first + 100 warm` and uses **28.3% less host
peak RSS**, but TensorCircuit-NG has the faster subsequent warm call and the
sampled GPU-memory peaks are tied. The literal challenge is therefore
partially, not fully, met.

Rebuild the complete package reproducibly from the committed JSON:

```bash
python scripts/build_submission_report.py
```

## Installation

Use Python 3.12:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
```

Install the independent comparison runner with the `baseline` extra:

```bash
.venv/bin/python -m pip install -e '.[test,baseline]'
```

Enable 64-bit JAX values when running `complex128` workloads:

```bash
export JAX_ENABLE_X64=1
```

Fresh benchmark, training, holdout, and ansatz workers default to full
32-bit matrix-product precision. An explicit environment value remains
authoritative:

```bash
export JAX_DEFAULT_MATMUL_PRECISION=highest
```

## Python API

```python
import jax.numpy as jnp

from vqetape import CompileRequest, TFIMVQESpec, compile_vqe

request = CompileRequest(
    spec=TFIMVQESpec(nqubits=4, depth=4),
    memory_budget_bytes=2 * 1024**3,
    expected_vqe_steps=100,
)
compiled = compile_vqe(request)
energy, gradient = compiled.executable(
    jnp.zeros(request.spec.parameter_shape)
)
print(compiled.selected.config.label, energy)
```

## Reproducible CLI Experiment

```bash
vqetape \
  --nqubits 4 \
  --depth 4 \
  --memory-budget-gib 2 \
  --expected-steps 100 \
  --warm-repeats 5 \
  --output outputs/vqetape-smoke-report.json
```

Run the matched TensorCircuit-NG threshold with:

```bash
vqetape-tc-baseline \
  --nqubits 10 \
  --depth 4 \
  --seed 33 \
  --warm-repeats 5 \
  --expected-steps 100 \
  --contractor omeco \
  --reference outputs/vqetape-gpu-rtx3090-statevector-n10-d4.json \
  --output outputs/tensorcircuit-ng-rtx3090-matched-n10-d4.json
```

Declare the formal Fig. 2 SU(4) protocol with:

```bash
vqetape-tc-fig2 manifest \
  --output outputs/tensorcircuit-ng-fig2-n32-l16-manifest.json
```

Run the direct bra-operator-ket tensor-network search with:

```bash
vqetape \
  --mode direct-tn \
  --nqubits 3 \
  --depth 2 \
  --memory-budget-gib 2 \
  --expected-steps 100 \
  --warm-repeats 3 \
  --output outputs/vqetape-direct-tn-report.json
```

Run the joint global-MPO and exact spatial-transfer search with:

```bash
vqetape \
  --mode spatial-transfer \
  --nqubits 8 \
  --depth 2 \
  --memory-budget-gib 2 \
  --expected-steps 100 \
  --warm-repeats 3 \
  --output outputs/vqetape-spatial-transfer-report.json
```

Run fixed-path dense/reference/native \(\mathbb Z_2\) symmetry triples with:

```bash
vqetape \
  --mode symmetry \
  --nqubits 8 \
  --depth 2 \
  --memory-budget-gib 2 \
  --expected-steps 100 \
  --warm-repeats 3 \
  --output outputs/vqetape-symmetry-report.json
```

Measure a complete VQE solve, including compilation and optimizer overhead:

```bash
vqetape-train \
  --nqubits 4 \
  --depth 2 \
  --program spatial \
  --block-width 2 \
  --optimizer lbfgs \
  --initialization random \
  --target-error 0.1 \
  --max-steps 80 \
  --seed 3 \
  --output outputs/vqetape-training-run.json
```

`adam`, `lbfgs`, and `natural-gradient` are supported. A recycled run accepts
the JSON from a previously converged solve through `--recycled-result`.
L-BFGS-B requires the `training` or `test` dependency extra.

Reproduce the fixed/gradient/contraction-aware ansatz comparison with:

```bash
vqetape-ansatz \
  --output outputs/vqetape-ansatz-report.json \
  --findings outputs/vqetape-ansatz-findings.md
```

The parameter layout is `(depth, 2, nqubits)`. In each layer, row zero stores
nearest-neighbor `RZZ` angles and its final element is unused padding; row one
stores all `RX` angles. The Hamiltonian convention is

\[
H=-J\sum_{i=0}^{n-2} Z_iZ_{i+1}-g\sum_{i=0}^{n-1}X_i.
\]

## Program Variants

- `unrolled-default`: Python layer loops are unrolled at JAX trace time.
- `scan-default`: the layer loop is represented by `jax.lax.scan`.
- `scan-remat`: the scan body is wrapped with `jax.checkpoint`.
- `scan-segmented`: a custom VJP saves segment-boundary states and recomputes
  one segment at a time during reverse mode.

Direct-TN mode compares two exact Hamiltonian programs:

- `pauli_sum`: contract one closed bra-product-operator-ket network for each
  of the \(2n-1\) TFIM Pauli terms;
- `mpo`: contract the complete energy once as a bra–MPO–ket network using the
  exact TFIM matrix-product operator with bond dimension \(\chi_H=3\).

The MPO tensors encode

\[
H=-J\sum_i Z_iZ_{i+1}-g\sum_i X_i
\]

without approximation. This shares circuit tensors and reverse-mode
residuals across all Hamiltonian terms. Both representations compare
`greedy`, `random-greedy`, and `auto-hq` opt_einsum paths.

The joint search includes two exact RZZ gate representations:

- `dense`: one rank-4 `(2, 2, 2, 2)` tensor;
- `operator_schmidt`: two rank-3 factors connected by a dimension-2 bond,
  using
  \[
  R_{ZZ}(\theta)
  =\cos(\theta/2)I\otimes I-i\sin(\theta/2)Z\otimes Z.
  \]

Every tape policy for one path receives the exact same serialized contraction
list. Gate and Hamiltonian representations are planned as separate tensor
programs because their equations and costs differ, but they use the same
search strategies and benchmark procedure. A positional path that remains
valid on another topology is fully replanned against that topology before its
cost is reported. This prevents stochastic path search from being
misinterpreted as a rematerialization or representation effect.

Direct-TN search also profiles JAX's actual VJP residuals. Contraction outputs
receive stable tape names, and residual-aware candidates save only a selected
byte budget of those names while exactly recomputing the rest. Complex
residuals are represented by named real/imaginary components to remain
compatible with JAX checkpoint policies.

Spatial-transfer mode lowers the exact operator-Schmidt bra–MPO–ket network
into first, repeated bulk, optional tail, and last programs. A cut retains
one ket and one bra RZZ Schmidt index per layer plus the MPO bond, so its
exact boundary is

\[
D=\chi_Hr^{2L}=3\cdot4^L.
\]

The current boundary is fused directly into each bulk contraction path; the
runtime never emits a full \(D\times D\) transfer tensor. Bulk columns execute
through `jax.lax.scan` and compare:

- default reverse-mode AD;
- `jax.checkpoint` rematerialization of the bulk transition;
- a segmented custom VJP that saves segment-boundary carries and recomputes
  one segment during the reverse pass;
- an explicit contraction-tree VJP that saves leaf tensors, reconstructs
  forward intermediates, and executes generated reverse einsums.

First/bulk/tail/last paths are searched once per strategy and block width,
then serialized into every corresponding AD/unroll candidate. The search
jointly selects among these spatial programs and exact global dense-MPO
controls.

The blocked spatial extension also plans exact multi-site bulk programs. For
block width \(b\), the incoming boundary and all tensors from \(b\)
neighboring sites participate in one contraction path, and only the outgoing
boundary is emitted. A shorter tail program handles
\((n-2)\bmod b\) interior sites. The default search compares widths one
through four and unroll values from \(\{1,2,4\}\) where applicable. Paths are
held fixed across AD schedules for every `(strategy, block_width)` pair.

For every spatial role, VQETape reconstructs the complete differentiated
contraction program. Reports separate forward/backward FLOPs, tensor traffic,
logical residual elements, and largest forward/reverse intermediates. The
initial deterministic AD score is recorded for research analysis but is not
used to prune candidates: on the audited workloads it did not rank warm
runtime better than forward FLOPs alone.

For the symmetric `plus`-state TFIM family, spatial programs can also use the
exact positive global-\(X\) \(\mathbb Z_2\) sector. The RZZ Schmidt and MPO
charges exclude exactly half of the boundary entries. `z2-reference`
expands the compressed carry inside each role and serves as an oracle;
`z2-native` uses BCOO input data and a sparse output selector, directly
carrying only active entries through the scan. Unsupported initial states are
rejected rather than silently compressed.

The time-to-solution layer compiles one exact value-and-gradient program and
then runs Adam, L-BFGS-B, or damped natural gradient until

\[
E(\theta)-E_0\leq\epsilon.
\]

The open-chain TFIM ground energy \(E_0\) is computed independently from its
\(2n\times2n\) Bogoliubov–de Gennes matrix. Every expensive objective call is
synchronized and traced. Random initialization is deterministic; recycled
initialization transfers overlapping layers/sites and fills newly introduced
parameters from source-layer means while preserving the unused RZZ padding.
The exact pure-state QGT used by natural gradient is intentionally limited to
audited small systems because its construction cost is included in wall time.

Adaptive ansatz growth starts from the same optimized depth-one RZZ–RX seed
and screens the same complete local pool at every round. In addition to the
original \(X_i\) and \(Z_iZ_{i+1}\) generators, the pool includes
\(Y_iZ_{i+1}\) and \(Z_iY_{i+1}\), the first local Lie-commutator closure.
These operators commute with global \(X\) and retain operator-Schmidt rank
two. They are necessary here: the original X/ZZ pool has vanishing insertion
gradients after the depth-one seed is optimized.

Gradient-only selection maximizes the exact metric-normalized insertion
signal. Contraction-aware selection divides the same signal by changes in
maximum spatial boundary dimension, compiler/execution proxies, and relative
boundary memory. Algebraically redundant candidates that can fuse through a
commuting suffix remain fully reported but cannot be selected. Every changed
structure is recompiled, and that cost is included in time to target.

The selected candidate minimizes

\[
T_{\mathrm{compile}} + K T_{\mathrm{warm}}
\]

over valid Pareto candidates within the configured memory budget.

## Measurement Meaning

- `compile_seconds`: lowering plus explicit compilation in a fresh worker.
- `first_execute_seconds`: first synchronized execution after compilation.
- `warm_seconds_median` and `warm_seconds_mad`: synchronized repeated calls.
- `peak_rss_bytes`: process peak resident memory, **not GPU peak memory**.
- `jax_memory_analysis`: compiler-reported executable fields when the current
  JAX backend provides them.
- `static_estimate.residual_profile`: byte-accounted logical values retained by
  JAX reverse mode; this is not a liveness-aware device peak.
- `static_estimate.modeled_checkpoint_bytes`: a boundary-count storage model
  for spatial reverse schedules, not measured device peak memory.

Candidates run in separate subprocesses to avoid sharing the in-memory JAX
compilation cache and allocator state. Worker environments default to
`JAX_DEFAULT_MATMUL_PRECISION=highest`; callers can override that environment
variable when intentionally studying the speed/accuracy tradeoff.

## Current Limitations

The repository now includes exact direct bra-product-operator-ket contraction,
explicit contraction-tree reconstruction, subtree checkpoint diagnostics, and
named residual-budget policies. It also compares dense and exact
operator-Schmidt RZZ gate representations, plus an exact bond-dimension-3 TFIM
MPO that shares the Hamiltonian-level VQE contraction and gradient. The same
MPO now supports exact carry-fused spatial scans, bulk rematerialization, and
a segmented custom carry adjoint. The training layer now compares Adam,
L-BFGS-B, exact natural gradient, deterministic initialization, and
continuation-based parameter recycling by synchronized time to an independently
verified energy target. It also includes exact Lie-closed adaptive ansatz
growth and contraction-aware gate ranking. It does not yet implement general
Pauli-to-MPO compression, cotengra slicing, cuTensorNet execution, noisy
circuits, sampling, approximate MPS, multi-GPU execution, arbitrary chemistry
operator pools, or large-system approximate quantum metrics.

All approved next-stage decision gates have now been evaluated. Candidates
that improve a measured frontier are retained in the search space; negative
results remain documented instead of being promoted as defaults.

See [the approved design](docs/plans/2026-07-28-vqetape-design.md) and
[implementation plan](docs/superpowers/plans/2026-07-28-vqetape-prototype.md).

The first direct-TN experiment found that path choice changed compiler
temporary memory, while checkpointing individual pairwise contractions did not
provide a meaningful fixed-path improvement. See
[the direct-TN findings](outputs/vqetape-direct-tn-findings.md). This negative
result motivates contraction-subtree/block scheduling rather than further
single-step threshold tuning.

The subsequent residual-aware experiment reduced the logical JAX VJP tape but
did not reduce compiler temporary memory on the small CPU workload. See
[the residual-aware findings](outputs/vqetape-residual-aware-findings.md).

The operator-Schmidt experiment eliminated dense RZZ `_diag` residuals and
reduced the default logical tape by 13–17%, but every Schmidt candidate was
dominated by a dense candidate in compiler temporary memory and warm runtime
on two CPU workloads. See
[the operator-Schmidt findings](outputs/vqetape-operator-schmidt-findings.md).

The exact TFIM MPO experiment removed repeated Hamiltonian-term circuit
contractions. MPO candidates occupied the complete measured Pareto front on
two workloads, reducing compile time, warm full-gradient time, compiler
temporary bytes, and logical tape relative to the horizon-optimal Pauli
controls. See
[the exact-MPO findings](outputs/vqetape-tfim-mpo-findings.md).

The exact spatial-transfer experiment kept the boundary at
\(D=3\cdot4^L\), reused one rolled bulk body, and reduced compile time and
compiler temporary memory relative to global MPO controls at eight and twelve
qubits. Global MPO remained faster for a single warm call, while spatial
remat won the 100-step VQE horizon. Segmented checkpointing reduced memory
relative to default AD but was dominated by ordinary rematerialization. See
[the spatial-transfer findings](outputs/vqetape-spatial-transfer-findings.md).

The blocked spatial experiment then fused two to four adjacent sites into one
exact carry-aware contraction. Width two improved the within-run best spatial
warm time by 5.6% at eight qubits, and width three improved it by 17.3% at
twelve qubits, but their additional compile cost kept width one as the
100-call default. Blocked execution remains on the search frontier while the
next phase adds differentiation-aware path ranking and explicit block VJPs.
See [the blocked spatial findings](outputs/vqetape-blocked-spatial-findings.md).

The differentiation-aware experiment generated exact reverse contractions
and compared them with JAX's default transpose on identical paths. Explicit
VJP reduced logical tape in every valid pair and usually reduced compiler
temporary memory, but made median warm runtime worse. It nevertheless
appeared on both multi-objective Pareto fronts and became the selected
100-call program at twelve qubits. The first static AD score failed its
runtime-ranking gate and remains diagnostic only. See
[the AD-aware contraction findings](outputs/vqetape-ad-aware-findings.md).

The exact symmetry experiment proved that the recurrent boundary and modeled
checkpoint bytes can be halved. JAX's sparse coordinates and reverse rules
made compiler temporary memory and logical tape larger in the median on CPU,
but native candidates remained on both multi-objective Pareto fronts and
occasionally improved warm time substantially. Native compression is
therefore retained as an optional search axis, not the default. See
[the symmetry findings](outputs/vqetape-symmetry-findings.md).

The end-to-solution experiment found a stationary-point failure for zero
initialization across all three optimizers. Recycling reduced target-workload
calls (for example, L-BFGS-B from 23 to 5), but its independently measured
source-solve cost prevents claiming a one-off wall-time win. Exact natural
gradient used only three to four value-gradient calls from nonzero starts, yet
QGT construction made it slower on the audited CPU workload. Statevector was
fastest at four qubits; scalable spatial and native symmetry programs remain
exact alternatives rather than being mislabeled as small-system winners. See
[the VQE time-to-solution findings](outputs/vqetape-training-findings.md).

The ansatz experiment rejected the original X/ZZ-only adaptive pool after it
stalled at a zero-gradient tangent space. Adding the symmetry-compatible YZ/ZY
commutator generators let both adaptive methods reach \(5.05\times10^{-11}\)
energy error with ten parameters, while the fourteen-parameter fixed RZZ–RX
control stopped at \(1.70\times10^{-7}\) under its budget. Gradient-only and
contraction-aware ranking selected the same three gates on this symmetric
workload, so the result supports the Lie-closed pool and adaptive parameter
efficiency but not a distinct contraction-aware speedup. See
[the adaptive ansatz findings](outputs/vqetape-ansatz-findings.md).

The generality holdout replaces TFIM with a longitudinal-field Ising chain and
uses a symmetry-breaking RZZ–RY–RX ansatz. Its independently diagonalized
ground energy was reached to the configured \(10^{-2}\) tolerance in 15
value-gradient calls. The measured global-X commutator norm is 5.6, so the
TFIM Z2-native compression is explicitly rejected for both Hamiltonian and
ansatz reasons. See
[the symmetry-breaking holdout findings](outputs/vqetape-holdout-findings.md).

## Completion Status

The completed exact one-dimensional prototype passes:

```text
389 passed, 6 skipped in 3715.35s (1:01:55)
```

The six skips are expected cases where the requested spatial block is wider
than the available interior. This clean-room regression used Python 3.12 with
JAX and jaxlib 0.11.0. The original local capability host exposes one CPU JAX
device and no GPU, so its process RSS is not presented as device memory. See the
[runtime capability report](outputs/vqetape-runtime-capabilities.md) and the
[complete requirement audit](docs/vqetape-completion-audit.md).

# VQETape Exact Spatial-Transfer Design

**Date:** 2026-07-29

**Scope:** Exact spatial-transfer lowering, rolled execution, and segmented
reverse-mode checkpointing for the current one-dimensional TFIM VQE family

## Problem

The exact global MPO phase replaces \(2n-1\) repeated Pauli-term contractions
with one bra–MPO–ket contraction:

\[
E(\theta)
=
\langle\psi(\theta)|H_{\mathrm{MPO}}|\psi(\theta)\rangle .
\]

That representation passed the executable decision gate, but it is still
lowered as one monolithic tensor graph. Increasing the number of qubits adds
more tensors and contraction steps to the compiled graph. This leaves three
important opportunities unused:

1. the circuit is one-dimensional and spatially repeated;
2. every RZZ gate has exact operator-Schmidt rank two;
3. the TFIM MPO has exact bond dimension three.

The next representation must expose this structure as a fixed-shape spatial
recurrence whose body is independent of chain length.

## Goal

Add an exact VQE program of the form

\[
B_1=F_{\mathrm{first}}(\theta_0),
\]

\[
B_{i+1}
=
F_{\mathrm{bulk}}
\left(B_i;\theta_{i-1,i},\theta_i,\theta_{i,i+1}\right),
\qquad 1\le i\le n-2,
\]

\[
E
=
F_{\mathrm{last}}
\left(B_{n-1};\theta_{n-2,n-1},\theta_{n-1}\right),
\]

and compute its complete reverse-mode gradient exactly.

The bulk recurrence must lower to `jax.lax.scan`; it must not construct or
retain all full \(D\times D\) transfer tensors before the scan.

## Non-goals

This phase does not add:

- approximate MPS/MPO truncation;
- two-dimensional circuits;
- arbitrary ansatz parsing;
- general Pauli-to-MPO compression;
- slicing, multi-GPU execution, or host offload;
- mixed precision;
- classical VQE optimizer or ansatz search;
- cuTensorNet-specific kernels.

Those remain separate compiler dimensions after the exact spatial program is
validated.

## Alternatives

### 1. Partition the verified operator-Schmidt MPO template — selected

Build the already tested
`operator_schmidt + mpo` bra–operator–ket template, assign every local tensor
to its physical site, and contract one site at a time while retaining only
cross-cut indices.

This reuses the exact gate, initial-state, bra/ket, and MPO conventions. The
global MPO remains an independent oracle for the spatial lowering.

### 2. Hand-code local transfer matrices

Direct formulas could make the scan body smaller, but they duplicate the RZZ
factorization, gate ordering, conjugation, and MPO sign conventions. That
creates a second semantic implementation and raises the risk of matching
energies while producing subtly incorrect parameter gradients.

### 3. Force the global tree into a spatial contraction order

This could demonstrate a spatial path without introducing column programs,
but it still emits a graph whose size grows with \(n\). It does not provide a
rolled recurrence or a natural custom adjoint over spatial carries.

## Spatial partition

The source topology is:

```python
build_mpo_expectation_template(
    spec,
    gate_representation="operator_schmidt",
)
```

The existing `TensorSlot.wire` has two meanings:

- for initial states, RX gates, and MPO tensors it is the physical site;
- for RZZ factors it is the left endpoint and parameter index of the bond.

Therefore spatial ownership is derived without changing parameter semantics:

```text
initial_ket, initial_bra, RX, MPO: site = slot.wire
RZZ left factor:                    site = slot.wire
RZZ right factor:                   site = slot.wire + 1
```

Dense RZZ tensors are not spatially local and are rejected by this lowering.

For a cut between sites \(i\) and \(i+1\), retain every index whose two
incident tensors belong to opposite sides of the cut. The cut contains:

- one ket Schmidt index for every layer;
- one bra Schmidt index for every layer;
- one Hamiltonian MPO bond.

Hence its exact shape is

\[
\underbrace{(2,\ldots,2)}_{2L\ \mathrm{entries}}
\mathbin{\|}(3,),
\]

and the flattened boundary dimension is

\[
\boxed{D=\chi_H r^{2L}=3\cdot4^L}.
\]

The compiler records the unflattened shape so contraction axes remain
explicit. It also reports `boundary_dimension=D` and
`boundary_bytes=D * dtype_bytes`.

## Column programs

Introduce a focused module, `vqetape.spatial_transfer`, containing immutable
planning records:

```python
@dataclass(frozen=True)
class SpatialColumnProgram:
    role: Literal["first", "bulk", "last"]
    equation: str
    path: tuple[tuple[int, ...], ...]
    slot_kinds: tuple[str, ...]
    input_shapes: tuple[tuple[int, ...], ...]
    carry_is_input: bool
    left_boundary_shape: tuple[int, ...]
    right_boundary_shape: tuple[int, ...]
    flops: int
    largest_intermediate_elements: int


@dataclass(frozen=True)
class SpatialTransferProgram:
    spec: TFIMVQESpec
    strategy: PathStrategy
    first: SpatialColumnProgram
    bulk: SpatialColumnProgram | None
    last: SpatialColumnProgram
    boundary_shape: tuple[int, ...]
    boundary_dimension: int
```

Planning proceeds from one complete global template:

1. map each slot to a physical site;
2. build the ordered cut-index list at every spatial boundary;
3. verify every cut has the same semantic shape;
4. form one einsum transition program per column role;
5. search and serialize an opt_einsum path for first, one representative
   bulk, and last;
6. verify all bulk columns have identical slot kinds, shapes, and local
   equations after index canonicalization.

The first program contains only site-zero tensors and outputs the right
boundary. A bulk program receives the current left boundary as its first
operand together with the current site's tensors and outputs only the right
boundary. The last program likewise receives the current boundary and
outputs a scalar.

The compiler must not first materialize an open \(D\times D\) transfer tensor.
Including the carry in the bulk contraction path lets the planner eliminate
left-cut indices while contracting the local network, so the required output
has only \(D\) elements. For `nqubits == 2`, `bulk` is `None`.

## Runtime binding

A column binder receives site-local parameter arrays rather than a dynamic
Python site:

```python
@dataclass(frozen=True)
class SpatialSiteParameters:
    left_rzz: Array
    right_rzz: Array
    rx: Array
```

Each field has shape `(depth,)`; absent boundary bonds use no placeholder
tensor and are not read.

Binding rules are:

```text
RX slot                   -> rx_matrix(rx[layer])
RZZ left factor           -> left factor of right_rzz[layer]
RZZ right factor          -> right factor of left_rzz[layer]
bra factor                -> conjugate of the corresponding ket factor
initial ket/bra            -> configured product-state vector/conjugate
first, bulk, last MPO slot -> exact role-specific TFIM MPO tensor
```

The local contraction executor applies the serialized column path using JAX
einsums. For bulk and last roles, the carry is operand zero. It exposes stable
names for optional residual profiling.

The bulk scan receives packed arrays:

```python
left_rzz = theta[:, 0, 0:-2].T
right_rzz = theta[:, 0, 1:-1].T
rx = theta[:, 1, 1:-1].T
```

with leading length `nqubits - 2`. Its body constructs only the current
column's small gate/MPO tensors, passes the current boundary into the
serialized transition contraction, and returns the next boundary. It never
materializes a \(D\times D\) transfer matrix.

## Exact execution modes

Add:

```python
SpatialAdjoint = Literal["default", "remat", "segmented"]


@dataclass(frozen=True)
class SpatialProgramConfig:
    path_strategy: PathStrategy
    adjoint: SpatialAdjoint
    unroll: int = 1
    segment_length: int | None = None
    column_paths: tuple[ContractionPath, ...] | None = None
    representation: Literal["spatial_transfer"] = "spatial_transfer"
```

`column_paths` contains `(first, last)` for two qubits and
`(first, bulk, last)` otherwise. Candidate generation searches these paths
once per strategy and serializes the same tuple into every corresponding
default/remat/segmented worker. This prevents stochastic path variation from
being attributed to an adjoint or unroll choice.

### Default

Use ordinary reverse-mode AD through the spatial `scan`. This is the runtime
and correctness baseline for the new representation.

### Remat

Wrap the bulk transition body in `jax.checkpoint`. This asks JAX to recompute
bulk-local values during the reverse pass. It may reduce column-local
residuals, but the measured result determines whether compiler temporary
memory improves.

### Segmented custom adjoint

Apply a custom VJP to only the shape-preserving bulk recurrence. The first and
last columns remain outside it, so standard AD computes their parameter
cotangents.

For \(m=n-2\) bulk columns and segment length \(s\):

1. pack bulk parameters into fixed-size segments;
2. pad the final segment and attach a validity mask;
3. forward-scan segments while saving only each segment's input boundary;
4. in reverse order, reconstruct one segment with `jax.vjp`;
5. return the left-boundary and bulk-parameter cotangents;
6. discard cotangents for padded transitions.

The expected carry-storage model is:

\[
M_{\mathrm{carry}}(s)
\approx
b_{\mathrm{boundary}}
\left(
\left\lceil\frac{m}{s}\right\rceil+s
\right).
\]

The default segment candidate is:

\[
s_\star=\max(1,\lfloor\sqrt m\rceil).
\]

This is a model, not a claimed device peak. The worker reports it separately
from JAX compiler temporary bytes, residual-profile bytes, and process RSS.

## Candidate search

The initial spatial search uses:

\[
\{\text{greedy},\text{random-greedy},\text{auto-hq}\}
\times
\{
\text{default-u1},
\text{default-u2},
\text{remat-u1},
\text{remat-u2},
\text{segmented-u1-}s_\star
\}.
\]

Duplicate configurations after clamping unroll to the number of bulk columns
are removed. For `nqubits == 2`, only default execution is emitted because
there is no bulk recurrence.

Within one path strategy, all adjoint and unroll candidates must report the
same first, bulk, last, and total forward FLOP counts.

Each fresh worker reports:

- first, bulk, and last path FLOPs;
- total forward energy FLOPs
  \[
  F_{\mathrm{first}}+(n-2)F_{\mathrm{bulk}}+F_{\mathrm{last}};
  \]
- boundary rank, dimension, and bytes;
- modeled checkpoint boundary count and bytes;
- JAX residual profile;
- compiler memory analysis;
- compile, first-execute, warm median/MAD, and process RSS.

The report includes an exact global-MPO control measured under the same seed,
dtype, hardware, and fresh-process protocol. Candidate selection still uses
the existing compile-plus-horizon objective and configured memory budget.

## Correctness

### Structural tests

For depths \(L=1,2,3\), verify:

- every source slot belongs to exactly one site;
- every nonlocal index is a nearest-neighbor spatial cut;
- every cut shape has \(2L\) dimensions of two and one dimension of three;
- every cut dimension equals \(3\cdot4^L\);
- first/bulk/last output indices match adjacent cuts;
- all canonical bulk programs are identical.

For depths \(L=1,2,3\), also require each bulk program's declared output size
to be exactly \(D\), rather than \(D^2\).

### Numerical tests

For `nqubits` in `2, 3, 4, 5`, depths in `1, 2`, both initial states, non-unit
\(J,g\), and both supported dtypes where practical, compare:

1. spatial-transfer energy;
2. spatial-transfer complete gradient;
3. global MPO energy and gradient;
4. state-vector energy and gradient.

The unused padding gradient
`gradient[:, 0, -1]` must remain exactly zero.

Compare default, remat, and segmented adjoints at identical parameters.

### Control-flow tests

Inspect lowered StableHLO text and require a `while` for at least four bulk
columns. Compare two chain lengths at fixed depth and record HLO text size;
the experiment must distinguish a rolled scan from Python unrolling, without
claiming perfectly constant total IR size.

## Error handling

Reject:

- non-operator-Schmidt source gates for spatial partitioning;
- non-MPO Hamiltonian source templates;
- a slot whose physical site cannot be derived;
- a cross-cut index that skips a site;
- inconsistent cut shapes;
- noncanonical bulk column topology;
- explicit paths invalid for their column;
- nonpositive unroll or segment length;
- segmented adjoints on a chain with no bulk columns;
- parameter arrays with the wrong shape or dtype.

## Decision gates

The spatial representation advances only if:

1. all structural, energy, and full-gradient tests pass;
2. the observed boundary dimension is exactly \(3\cdot4^L\);
3. lowered bulk execution contains rolled scan control flow;
4. at least one spatial candidate is nondominated by the global MPO control
   in warm time plus compiler temporary bytes on a workload with at least
   eight qubits;
5. the trend is checked at two chain lengths with fixed depth;
6. segmented checkpointing either reduces a measured/compiler memory metric
   or is recorded as a negative result without being made the default.

If spatial transfer is slower at small \(n\) but demonstrates improved
compile/memory scaling, both the crossover and the negative small-system
result are reported.

## Expected research contribution

This phase changes the compiler's optimization object from a global
contraction path to a differentiable spatial recurrence:

\[
\boxed{
\text{exact MPO representation}
+\text{column contraction programs}
+\text{rolled scan}
+\text{carry-aware custom adjoint}
}
\]

The scientific claim is deliberately limited to shallow, local,
one-dimensional VQE circuits. Fixed depth gives linear iteration count in
\(n\), while the exact boundary remains exponential in depth:

\[
T=O\!\left(n\,C_{\mathrm{column}}(L)\right),
\qquad
D=3\cdot4^L.
\]

This is the correct foundation for later generalized representation
selection, optimizer/ansatz co-design, and larger GPU experiments.

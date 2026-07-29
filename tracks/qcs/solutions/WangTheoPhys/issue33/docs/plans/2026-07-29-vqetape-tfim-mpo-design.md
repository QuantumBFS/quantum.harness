# VQETape Exact TFIM MPO Design

**Date:** 2026-07-29
**Status:** Approved
**Scope:** Exact global bra–MPO–ket contraction for TFIM VQE value and full gradient

## Motivation

The current direct-TN backend represents the TFIM Hamiltonian as \(2n-1\)
product-Pauli terms. Each term binds and contracts a complete copy of the
bra–operator–ket circuit network:

```text
for each Hamiltonian term:
    bind complete circuit and product operator
    contract one scalar
sum term scalars
differentiate the unrolled term loop
```

The circuit bulk is nearly identical across terms. The operator-Schmidt phase
showed that reducing gate-construction residuals alone does not improve the
lowered executable. Hamiltonian-level sharing is therefore the next measured
bottleneck.

## Goal

Add a mathematically exact TFIM matrix-product operator with bond dimension
\(\chi_H=3\), so that one bra–MPO–ket network computes the complete
Hamiltonian expectation:

\[
E(\theta)
=
\langle\psi_0|
U^\dagger(\theta)
H_{\mathrm{MPO}}
U(\theta)
|\psi_0\rangle.
\]

The compiler will jointly compare:

\[
\text{Hamiltonian representation}
\times
\text{contraction path}
\times
\text{reverse tape}.
\]

## Exact TFIM MPO

The Hamiltonian convention remains:

\[
H
=
-J\sum_{i=0}^{n-2}Z_iZ_{i+1}
-g\sum_{i=0}^{n-1}X_i.
\]

Use virtual states \(0,1,2\). The first-site tensor is:

\[
W^{[0]}
=
\begin{bmatrix}
-gX & -JZ & I
\end{bmatrix}.
\]

Each bulk tensor is:

\[
W^{[i]}
=
\begin{bmatrix}
I & 0 & 0\\
Z & 0 & 0\\
-gX & -JZ & I
\end{bmatrix},
\qquad 0<i<n-1.
\]

The final tensor is:

\[
W^{[n-1]}
=
\begin{bmatrix}
I\\
Z\\
-gX
\end{bmatrix}.
\]

With MPO indices ordered as left bond, right bond, bra physical index, ket
physical index, contraction of the virtual bonds produces exactly the TFIM
Hamiltonian.

Trivial dimension-1 exterior bonds are omitted:

- first tensor: `(right_bond, bra, ket)`, shape `(3, 2, 2)`;
- bulk tensor: `(left_bond, right_bond, bra, ket)`, shape `(3, 3, 2, 2)`;
- last tensor: `(left_bond, bra, ket)`, shape `(3, 2, 2)`.

## Alternatives Considered

### Global exact MPO contraction — selected

This changes only the Hamiltonian representation. It preserves the existing
contraction-path optimizer, explicit contraction program, residual profiler,
named tape, worker isolation, and Pareto selection.

### Spatial-transfer MPO scan

This would impose a sitewise recurrence and change both representation and
control flow. It may ultimately scale better, but including it now would make
MPO sharing, fixed contraction order, scan lowering, and carry checkpointing
inseparable.

### Shared prefix/suffix term environments

This retains Pauli-term semantics and manually caches common subexpressions.
It is useful as a later compiler rewrite, but less general and harder to
compare fairly with standard tensor-network programs than an explicit MPO.

## Compiler Configuration

Add:

```python
HamiltonianRepresentation = Literal["pauli_sum", "mpo"]
```

and:

```python
TensorProgramConfig.hamiltonian_representation
```

The default is `pauli_sum` for backward compatibility. The field participates
in validation, labels, JSON serialization, equality, fresh-worker transport,
and candidate generation.

The default experiment fixes `gate_representation="dense"`, because explicit
operator-Schmidt gate factors were rejected by the previous executable Pareto
gate. The API still permits combining MPO and operator-Schmidt gates for
diagnostics.

## Module Boundaries

Create `src/vqetape/tfim_mpo.py` with:

```python
def tfim_mpo_tensors(spec: TFIMVQESpec) -> tuple[Array, ...]
```

and a small-system test oracle:

```python
def dense_tfim_hamiltonian(spec: TFIMVQESpec) -> Array
```

The production function constructs the first, bulk, and last MPO tensors. The
dense helper uses explicit Kronecker products and is restricted to tests and
small-system correctness checks.

Add:

```python
def build_mpo_expectation_template(
    spec: TFIMVQESpec,
    *,
    gate_representation: GateRepresentation = "dense",
) -> TensorNetworkTemplate
```

The MPO template uses the same circuit-building routine as the Pauli-sum
template, then attaches one MPO operator tensor per site.

New slot kinds:

```text
hamiltonian_mpo_first
hamiltonian_mpo_bulk
hamiltonian_mpo_last
```

`TensorNetworkTemplate` records both:

```text
gate_representation
hamiltonian_representation
```

so an explicit path serialized for one topology cannot be reused for another.

## Energy Data Flow

### Pauli sum

1. Build one product-operator template.
2. Search one path reused across all product terms.
3. Bind and contract the template \(2n-1\) times.
4. Sum the real weighted expectations.
5. Differentiate the full unrolled term loop.

### MPO

1. Build one bra–MPO–ket template.
2. Search one path.
3. Bind circuit gates once and the \(n\) MPO tensors once.
4. Contract one scalar.
5. Differentiate that single contraction program.

Both return the same:

\[
\theta\mapsto(E,\nabla_\theta E).
\]

## Candidate Search

The default MPO experiment covers:

\[
\{\text{pauli-sum},\text{MPO}\}
\times
\{\text{greedy},\text{random-greedy},\text{auto-hq}\}
\times
\{\text{default},\text{named-empty},
\text{named-half},\text{named-full}\}.
\]

This yields 24 candidates with dense RZZ gates.

Within one Hamiltonian-representation/path pair, every tape receives the same
serialized explicit path. Paths are not shared across Hamiltonian
representations because the topologies differ.

Named tape budgets are generated independently from each contraction
program's output bytes.

## Static Metrics

The existing `path_flops` measures one network contraction. That is not a fair
energy-level comparison because Pauli sum executes it \(2n-1\) times.

Add:

```text
contractions_per_energy
network_tensor_count
bound_tensor_elements_per_network
estimated_energy_flops
estimated_energy_tensor_bindings
```

with:

\[
F_{\mathrm{energy}}
=
\begin{cases}
(2n-1)F_{\mathrm{network}},&\text{Pauli sum},\\
F_{\mathrm{network}},&\text{MPO}.
\end{cases}
\]

Logical residual bytes come from tracing the actual complete energy function,
not from multiplying a single-term residual estimate.

Dynamic metrics remain:

- compiler temporary bytes;
- process peak RSS;
- compile time;
- first execution time;
- warm median and MAD;
- energy and full-gradient errors.

## Correctness

### MPO algebra

For \(n=2,3,4\), contract the MPO to a dense matrix and compare it with the
explicit Kronecker TFIM Hamiltonian.

Cases:

- \(J=g=1\);
- non-unit \(J,g\);
- \(J=0\);
- \(g=0\);
- `complex64`;
- locally enabled `complex128`.

### VQE value and gradient

Compare Pauli sum, MPO, and state-vector oracle across:

- zero and plus initial states;
- depths 1 and 2;
- multiple \(J,g\) pairs;
- multiple parameter points;
- default and named tapes;
- complete padded gradients.

The final RZZ padding parameter in every layer must retain exactly zero
gradient.

### Topology

Verify:

- every index appears exactly twice;
- every internal MPO bond has extent 3;
- first, bulk, and last shapes match the specification;
- explicit positional paths are validated and fully replanned against the
  selected topology;
- configuration and results survive fresh-worker JSON round trips.

## Error Handling

Reject:

- unsupported Hamiltonian-representation names;
- an explicit positional path that is invalid for the selected topology;
- a named tape set generated for another contraction program;
- an MPO tensor count different from `nqubits`;
- inconsistent internal bond dimensions;
- physical shapes other than `(2, 2)`;
- dtype mismatches between circuit and MPO tensors.

## Decision Gates

MPO becomes the default only if:

1. dense MPO matrices, VQE energies, and complete gradients pass all
   correctness checks;
2. `contractions_per_energy` changes from \(2n-1\) to 1;
3. estimated energy FLOPs, logical tape, or compiler graph changes materially;
4. at least one MPO candidate is nondominated by all Pauli-sum candidates in
   compiler temporary memory and warm runtime;
5. the trend holds across at least two qubit/depth settings or Hamiltonian
   parameter settings;
6. no device-memory claim is inferred from CPU RSS.

If MPO reduces graph duplication but its bond-3 contractions are more
expensive, the failure is recorded without redefining success.

## Out of Scope

This phase does not simultaneously add:

- spatial-transfer scan;
- custom adjoint for sitewise carries;
- segmented MPO checkpointing;
- general Pauli-sum-to-MPO compression;
- slicing;
- mixed precision;
- approximate truncation;
- classical optimizer or ansatz search.

If global MPO passes the executable gate, the next phase lowers the same MPO
template to a spatial transfer recurrence and studies carry checkpointing.

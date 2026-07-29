# VQETape Operator-Schmidt Representation Design

**Date:** 2026-07-29
**Status:** Approved
**Scope:** Exact RZZ–RX TFIM VQE value-and-full-gradient programs

## Motivation

The current VQETape prototype jointly evaluates tensor-network contraction
paths and reverse-mode residual schedules. It can reduce the logical JAX VJP
tape using named checkpoint policies, but generic step, term, objective, and
subtree rematerialization have not reduced compiler temporary memory on the
small CPU workloads.

The residual profile identifies two remaining sources of avoidable structure:

1. dense RZZ gate construction through a 4-by-4 diagonal matrix; and
2. contraction paths chosen for rank-4 tensors that contain mostly zeros.

The next phase changes the tensor representation before path search. The
research question is whether an exact low operator-Schmidt-rank lowering
changes the best contraction path, reverse tape, and final executable
time–memory trade-off.

## Goal

Extend the optimization space from

\[
\text{contraction path}\times\text{AD tape}
\]

to

\[
\boxed{
\text{tensor representation}
\times
\text{contraction path}
\times
\text{AD tape}
}.
\]

The compiler will compare mathematically equivalent dense and
operator-Schmidt RZZ networks under identical VQE semantics and path-search
budgets.

## Exact Representations

### Dense

The existing representation binds one rank-4 tensor per RZZ gate:

\[
G_{o_1o_2i_1i_2},
\qquad
\operatorname{shape}(G)=(2,2,2,2).
\]

It is produced by reshaping a 4-by-4 diagonal matrix. It contains 16 complex
elements even though only four are nonzero.

### Operator Schmidt

Use the exact identity

\[
R_{ZZ}(\theta)
=
\cos\frac{\theta}{2}I\otimes I
-i\sin\frac{\theta}{2}Z\otimes Z.
\]

Introduce a Schmidt bond \(a\in\{0,1\}\) and two rank-3 tensors:

\[
R_{ZZ}
=
\sum_{a=0}^{1}
L_{o_1i_1a}(\theta)
R_{o_2i_2a},
\]

with

\[
L_0=\cos\frac{\theta}{2}I,\qquad
L_1=-i\sin\frac{\theta}{2}Z,
\]

\[
R_0=I,\qquad R_1=Z.
\]

This asymmetric factorization avoids square roots of complex coefficients,
branch choices, and the numerical instability that a balanced square-root
factorization could introduce. The bra network binds the exact complex
conjugates.

## Compiler Configuration

`TensorProgramConfig` gains:

```text
gate_representation:
    dense
    operator_schmidt
```

The field is part of serialization, equality, labels, fresh-process transport,
and candidate selection.

The tensor template builder accepts the same representation choice. Dense
RZZ gates retain one slot. Operator-Schmidt gates produce left and right
factor slots joined by a new dimension-2 internal index. RX, initial-state,
and observable slots are unchanged.

## Data Flow

For each representation:

1. build a closed bra–product-operator–ket topology;
2. bind the same parameters and Pauli term;
3. search a contraction path with the same strategy and search budget;
4. serialize the explicit contraction list;
5. reconstruct the contraction tree;
6. trace JAX's actual saved VJP residuals;
7. assign stable names to factor tensors and contraction outputs;
8. generate default and named residual-budget schedules;
9. benchmark each candidate in a clean process;
10. validate energy and the complete padded gradient against the state-vector
    oracle;
11. construct one Pareto frontier across both representations.

Dense and operator-Schmidt networks cannot reuse the same explicit path
because their topology differs. Fairness is defined by identical path-search
algorithm, search budget, workload, seed, tape-budget policy, and benchmark
procedure.

## Static and Dynamic Metrics

Each result reports:

- representation;
- tensor count;
- total bound tensor elements;
- path FLOPs;
- largest forward intermediate;
- contraction-step count;
- logical saved-residual count and bytes;
- residual bytes by source and name;
- compiler temporary bytes;
- process peak RSS;
- compile time;
- first execution time;
- warm median and MAD;
- energy and gradient errors.

The report explicitly distinguishes:

\[
M_{\text{input tensors}},
\qquad
M_{\text{logical tape}},
\qquad
M_{\text{compiler temp}},
\qquad
M_{\text{device peak}}.
\]

No one metric is used as a proxy for all four.

## Candidate Search

The initial joint search covers:

\[
\{\text{dense},\text{operator-Schmidt}\}
\times
\{\text{greedy},\text{random-greedy},\text{auto-hq}\}
\times
\{\text{default},\text{named-empty},\text{named-half},\text{named-full}\}.
\]

Existing diagnostic policies may remain callable, but the default
representation experiment excludes step, term, objective, and subtree remat
because previous fixed-path experiments rejected them.

Named budgets are generated independently for each explicit path from that
program's contraction outputs. A logical 50% budget means 50% of the sum of
candidate contraction-output bytes, not 50% of the number of steps.

## Error Handling and Invariants

The implementation rejects:

- unsupported representation names;
- representation/configuration mismatches;
- invalid tensor counts or shapes;
- inconsistent Schmidt bond dimensions;
- paths serialized for another topology;
- named tape values that do not belong to the selected program.

Required invariants:

1. the network is closed;
2. every index has a consistent extent;
3. dense and Schmidt energies agree;
4. dense and Schmidt complete gradients agree;
5. the unused final RZZ parameter in every layer has zero gradient;
6. bra factors are exact conjugates of ket factors;
7. candidate comparisons never re-search a path across tape policies.

## Testing

### Algebraic unit tests

- reconstruct dense RZZ from its two factors;
- test several angles including zero, small values, and values near \(\pi\);
- compare ket and bra factor contractions;
- verify `complex64` and locally enabled `complex128`.

### Template tests

- verify dense and Schmidt slot kinds and shapes;
- verify every network index occurs exactly twice;
- verify the Schmidt bond has extent 2;
- verify total tensor elements and tensor count.

### End-to-end correctness

Compare value and full gradient against the state-vector oracle across:

- at least two qubit/depth scales;
- zero and plus initial states;
- at least two \(J,g\) pairs;
- dense and Schmidt representations;
- default and named tapes.

### Search tests

- every representation/path pair reuses one explicit path across tapes;
- both representations appear in reports and Pareto selection;
- serialized configurations round-trip through fresh workers;
- incorrect cross-topology paths fail explicitly.

## Decision Gates

The phase is successful only if:

1. all energy and complete-gradient correctness checks pass;
2. the Schmidt representation eliminates dense `_diag` residuals;
3. at least one path or logical-tape metric changes materially;
4. at least one Schmidt candidate is nondominated against dense candidates in
   compiler temporary memory, warm runtime, or both;
5. the qualitative result holds on at least two workload scales and two
   Hamiltonian parameter settings.

If only the input tensor element count changes while contraction, tape, and
executable metrics do not improve, the result is recorded as negative.

## Out of Scope

This phase does not simultaneously add:

- a Hamiltonian MPO;
- shared environments across Pauli terms;
- slicing;
- mixed precision;
- approximate truncation;
- ansatz search;
- a classical optimizer.

Those features would confound attribution. The next phase will be selected
only after the representation experiment identifies whether gate lowering or
Hamiltonian-level sharing is the more important bottleneck.

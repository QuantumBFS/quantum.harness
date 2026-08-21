# Issue #147 Lazy Double-Layer Contraction Design

## Goal

Keep the exact relative Frobenius compression objective while removing the
explicit local double-layer tensor whose storage scales as D^8. The immediate
deliverable is a verified beta = 0.05 PEPO probe on SCNet before 20:00 on
2026-07-30. A full beta chain is optional and must not displace correctness
checks needed for the probe.

The fixed physical setup remains the 10x10 open-boundary transverse-field
Ising model

    H = -sum_<ij> Z_i Z_j - 3 sum_i X_i,

using Pauli operators, student bond D = 4, teacher bond D = 16, boundary bond
chi = 16, and delta_beta = 0.025.

## Problem

The current double-layer builder contracts the physical legs of the bra and
ket at every site before boundary contraction. An interior teacher site then
materializes an eight-virtual-leg array with D^8 entries. At D = 16 this makes
the beta = 0.05 initial diagnostic consume about 93 GiB and run for more than
an hour, so the planned 40-step chain is infeasible.

This is an evaluation-order problem, not a change to the Frobenius objective.

## Network Representation

Represent each lattice site with two tensors rather than one materialized
double-layer tensor:

- The bra and ket retain the common site tag `I{x},{y}`.
- They additionally carry distinct `BRA` and `KET` layer tags.
- Bra virtual indices use a `bra:` prefix and ket virtual indices use a
  `ket:` prefix, so spatial bonds connect only within their own layer.
- Every physical index name includes its site coordinates, preventing
  accidental inter-site contraction.

For `Tr(A^dagger B)`, conjugate the bra data and connect matching bra and ket
output legs and matching input legs. For `Tr(AB)`, leave the left data
unconjugated and exchange the right tensor's input and output index names.
These constructions preserve the current overlap and Hermiticity formulas
exactly.

## Boundary Contraction

Extend the scalar contraction wrapper with optional layer tags. Single-layer
partition-function and energy contractions retain their current behavior.
Double-layer contractions pass `("BRA", "KET")` to Quimb's
`contract_boundary` interface.

Quimb 1.12.1 supports multiple tensors carrying one site tag and contracts
specified layers into the boundary one at a time, compressing between layers.
This avoids materializing an interior D^8 site tensor. Open-boundary tensors
may still be locally combined at the initial edge, where their degree is lower;
the final exact contraction acts only on the remaining chi-compressed strip.

The numerical approximation remains the declared boundary-MPS truncation at
chi = 16. No local surrogate replaces the exact Frobenius expression.

## Interfaces and Validation

`_double_layer_network` becomes a structure builder: it copies tensor data,
renames indices, applies conjugation when requested, and adds layer tags. It
does not perform a local bra-ket einsum.

The builder rejects mismatched lattice extents and reports the coordinates of
any incompatible physical dimensions before contraction. NumPy and JAX arrays
continue through Autoray-compatible operations so diagnostics and automatic
differentiation share one implementation.

Before a remote probe, verify that SCNet's installed Quimb exposes the same
layered boundary-contraction behavior. Also inspect the built D = 16 network
and reject it if any construction-time tensor has the D^8 element count of an
interior materialized double layer.

## Tests

1. Compare lazy `Tr(A^dagger B)`, `Tr(AB)`, relative Frobenius loss, and
   Hermiticity residual with dense results on 1x1 and 2x2 networks, including
   complex non-Hermitian data.
2. Differentiate the lazy overlap and Frobenius loss with JAX and compare with
   finite differences on a small network.
3. Assert structurally that a D = 16 lazy network contains two tensors per
   site and no construction-time D^8 local allocation.
4. Run the focused PEPO tests, then the repository test suite.
5. Run the existing two-step SCNet probe through beta = 0.05 and require a
   completed checkpoint with finite diagnostics. Record elapsed time and peak
   memory against the current greater-than-one-hour, approximately 93 GiB
   failure mode.

## Failure and Deadline Policy

If the SCNet Quimb version lacks the layered interface, the structural gate
fails, the dense/JAX tests fail, or the beta = 0.05 probe still exceeds the
available memory or time, stop before launching the full chain and report the
evidence. Do not silently return to the explicit D^8 implementation.

A custom explicit layer-by-layer boundary sweep is a future fallback, not part
of the deadline scope. Before 20:00, a correct implementation plus a completed
two-step probe is preferred over a broader but insufficiently validated
implementation. If the probe succeeds with enough time remaining, resume from
the latest valid beta = 0.025 checkpoint with per-step checkpoints and flushed
progress; otherwise the completed probe and documented limitation are the
acceptable final result.

## Acceptance

The deadline-scoped work is accepted when:

- the exact Frobenius formula is unchanged;
- no interior D^8 local tensor is allocated during network construction;
- dense and JAX checks pass;
- the SCNet beta = 0.05 probe either completes with a valid checkpoint or
  yields a clearly recorded, non-silent failure before a full-chain launch.

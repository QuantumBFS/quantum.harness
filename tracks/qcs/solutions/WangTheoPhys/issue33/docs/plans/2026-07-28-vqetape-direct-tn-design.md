# VQETape Direct Tensor-Network Phase Design

**Date:** 2026-07-28

## Outcome

Add an exact direct scalar tensor-network representation of the same TFIM VQE
objective used by the state-vector oracle. The implementation must never
materialize the full output state as a program result. It must expose the
pairwise contraction program so reverse-mode rematerialization can be selected
per contraction step.

## Mathematical Network

For each product-Pauli term \(P_\alpha\),

\[
E_\alpha(\theta)
=
\langle\psi_0|
U^\dagger(\theta)P_\alpha U(\theta)
|\psi_0\rangle.
\]

The network contains:

- one initial-state vector per ket wire;
- one conjugate initial-state vector per bra wire;
- one tensor per ket gate;
- one conjugate tensor per bra gate;
- one rank-2 operator tensor connecting final bra and ket indices per wire.

All TFIM terms have identical topology because identity operator tensors are
inserted on wires outside each term's support. Only operator values differ, so
one contraction program can be reused for all \(2n-1\) Hamiltonian terms.

## Static IR

`TensorNetworkTemplate` stores:

- the einsum equation;
- ordered tensor slots and their shapes;
- the path-independent index topology;
- parameter-source metadata for every gate slot;
- final wire-operator slot positions.

`ContractionProgram` stores:

- path strategy and explicit path;
- opt_einsum contraction-list steps;
- FLOP estimate;
- largest-intermediate element count;
- per-step output byte estimates;
- rematerialized step indices.

## Runtime Binding

At execution time, the template binds:

- initial vectors;
- `RX` and `RZZ` tensors generated from `theta`;
- conjugate copies for bra slots;
- one batch of product-Pauli operator matrices.

The contraction program executes a trace-time-static Python sequence of
pairwise `jax.numpy.einsum` calls. A selected step is wrapped with
`jax.checkpoint`, allowing JAX reverse mode to recompute that step rather than
retain all of its linearization points.

## Initial Candidate Space

- path strategy: `greedy`, `random-greedy`, `auto-hq`;
- step rematerialization:
  - `none`;
  - `all`;
  - `output-ge-threshold`;
- threshold: distinct intermediate byte sizes from the selected path.

The initial search remains exact. Slicing, MPO Hamiltonians, shared
multi-output environments, and loop/block formation are subsequent extensions.

## Correctness

For `nqubits <= 8` and `depth <= 6`, direct-TN energies and full gradients must
match the state-vector oracle within the dtype tolerances already defined by
VQETape. Tests cover:

- zero parameters;
- deterministic nonzero parameters;
- every path strategy;
- every rematerialization policy;
- padding-parameter zero gradients.

## Falsifiable Phase Claim

This phase succeeds only if:

1. at least two valid contraction paths with different path metrics are
   generated for a nontrivial workload;
2. path choice changes measured compile time, warm time, or compiler temporary
   memory;
3. per-step rematerialization changes compiler temporary memory for at least
   one fixed path;
4. a joint path/rematerialization candidate is nondominated relative to both
   best fixed-path/no-remat and fixed-path/all-remat baselines.

If the final condition fails, VQETape must report that joint optimization is
not supported by the tested workloads rather than claim novelty.

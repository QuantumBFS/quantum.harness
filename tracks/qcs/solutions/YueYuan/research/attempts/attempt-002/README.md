# Attempt 002: Toy Two-Qubit Dynamics

## Status

Accepted by the public development validator on 2026-07-27.

Attempt 002 replaces attempt 001's direct surrogate with local NumPy quantum-control machinery:

- exact unitary propagation through small Hermitian generators;
- global-phase-invariant CZ gate infidelity;
- finite-difference Hessian at the model CZ optimum;
- rank-15 top-Hessian subspace in a 48-dimensional raw pulse vector;
- deterministic finite-shot query accounting for full, random, and Hessian subspaces.

## Model

The toy model treats the 48 raw pulse parameters as 4 controls over 12 segments. The model maps those controls into the 15 traceless two-qubit error-generator directions. The model optimum is the zero error pulse, so the Hessian rank is expected to be `d^2 - 1 = 15`.

The device gap perturbs the raw-to-error mixing and adds a small static error generator. Closed-loop rows solve the reachable correction inside each method's search subspace and then compute exact final CZ infidelity using the same unitary propagation path.

## Result

Public dev validator score: `3.031578947368421`.

| Gap | Median full queries | Median Hessian queries | Median random queries | Speedup |
|---:|---:|---:|---:|---:|
| `0.03` | `285` | `94` | `198` | `3.0319148936170213` |
| `0.08` | `288` | `95` | `200` | `3.031578947368421` |

Small Hessian subspaces `k = 0, 3, 8` are reported as failures/plateaus; `k = 15, 24, 48` pass the exact final guard.

## Caveat

This is a deliberately small toy quantum-control benchmark. It now computes propagation, infidelity, and Hessian geometry, but the query traces are still deterministic approximations to closed-loop Nelder-Mead behavior. Attempt 003 should replace that trace simulator with an actual derivative-free optimizer loop over the noisy scalar oracle.

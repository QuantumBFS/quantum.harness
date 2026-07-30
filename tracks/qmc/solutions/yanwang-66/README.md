# yanwang: dynamic atom reloading for loss-tolerant surface-code memory

## Team

| | |
|---|---|
| **Team name** | yanwang |
| **Members** | 王介人、何思成、赵志轩 |
| **Contributor for #66** | 何思成 |

## Challenge

| Row | |
|---|---|
| **Research question** | How much can active atom reloading improve logical surface-code memory under stochastic loss and Pauli noise? |
| **Catalog issue** | Addresses #66, released by Zhongyi Ni, HKUST(GZ) |
| **Track** | `qmc`, selected from the issue's "Quantum Circuit Simulation / Monte Carlo Simulation" method because the primary evidence is a paired circuit-level Monte Carlo campaign |

## Registered scope

We compare no reloading, immediate reloading, periodic reloading, and
missing-fraction-triggered reloading on the same rotated-surface-code circuits
and the same counter-addressed external noise streams. The submission will
report logical error, missing occupancy, reload overhead, independent-seed
confirmation, and a decoder-ready loss/reload data interface.

The implementation uses an erasure-aware MWPM baseline and preserves the
causal boundary that a policy may only observe loss detected up to the current
round. Training an AI decoder is intentionally outside this challenge.

## Verification boundary

The final delivery will separate provisional parameter-region signals from
claims that satisfy the registered stopping rule. Deterministic replay,
independent small-instance oracles, negative controls, immutable manifests,
and a sealed holdout gate are part of the acceptance path.

# frustration-free — Finite-temperature Anderson impurity solver

## Team

| | |
|---|---|
| **Team name** | frustration-free |
| **Members** | 蒋玮琪 (`jiangweiqi001`), 陈硕 (`ChS-YHWH`), 马追景 (`desitterf`) |

## Challenge

| Row | |
|---|---|
| **Challenge** | Build and independently validate a deterministically purified tensor-network solver for the continuous-bath spinful Anderson impurity model, then determine the coldest inverse temperature reachable with a controlled observable error budget. |
| **Catalog issue** | `Addresses #81` — “[challenge]: How cold can a purified tensor-network Anderson impurity solver go?”, released by Weiyi Guo, University of Amsterdam. |
| **Track** | `tracks/mps/solutions/frustration-free/` — selected from the issue’s `Method: MPS Based Algorithm` field. |

## Initial scope

The four-day acceptance target is:

1. fit and serialize the semicircular hybridization;
2. validate finite-bath \(n_d\), double occupancy, and \(G(\tau)\) against an independent exact-diagonalization oracle to \(10^{-6}\);
3. run a purified finite-temperature MPS baseline at \(\beta=16\) or \(32\);
4. report bath, chain-length, bond-truncation, and time-step/residual errors together with runtime, peak memory, and per-bond dimensions.

The implicit logarithmic integrator and residual-driven bond expansion are research extensions. The bosonic bath, DMFT self-consistency, real-time dynamics, analytic continuation, and METTS implementation remain out of scope.

## Reproducible references

Download the version-pinned papers and reference repositories into the
gitignored results tree:

```bash
python tracks/mps/solutions/frustration-free/references/download_references.py
```

Verify an existing download without network access:

```bash
python tracks/mps/solutions/frustration-free/references/download_references.py \
  --verify-only
```

`references/references.json` records immutable arXiv versions, file sizes,
SHA256 digests, and exact Git commits. These references are inputs for method
design and independent validation; they are not vendored into the submission.

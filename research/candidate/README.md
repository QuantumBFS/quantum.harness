# Automatic symmetry decomposition

Give the program a Hermitian Hamiltonian matrix and a symmetry name. It generates common tensor-product representations, verifies them with commutator residuals, and writes symmetry-reduced blocks.

## Quick start

Save the Hamiltonian as a NumPy array:

```python
import numpy as np

np.save("H.npy", H)
```

Run the decomposition from the repository root:

```bash
.venv/bin/python research/candidate/run.py H.npy \
  --symmetry su2 \
  --output result.npz
```

The input may instead be an `.npz` file containing an array named `H` or `matrix`.

## Built-in templates

| Name | Generated representation |
|---|---|
| `su2` | Total spin `Jₓ`, `Jᵧ`, `J_z` for identical local spins `s=(local_dim−1)/2` |
| `u1` | Total magnetization `J_z` for the same local-spin model |
| `z2` | Global spin flip `X⊗⋯⊗X`; currently restricted to `local_dim=2` |
| `translation` | Cyclic translation of identical sites |
| `auto` | Tries all templates and accepts only a unique match |

Without hints, the program factors the Hilbert-space dimension as `local_dim^sites`. Each candidate is accepted only if its normalized commutator residual is at most `--tolerance`, whose default is `1e-10`.

The matrix basis must use the same tensor-product ordering as repeated `numpy.kron`, with the leftmost site as the first tensor factor.

## Resolve an ambiguous match

A matrix dimension can have multiple tensor-product interpretations, and a Hamiltonian may preserve more than one listed symmetry. The program does not choose silently. Add either or both hints:

```bash
.venv/bin/python research/candidate/run.py H.npy \
  --symmetry su2 \
  --local-dim 2 \
  --sites 8 \
  --output result.npz
```

`--local-dim 2` means spin-½ for `su2` and `u1`. For a spin-1 chain, use `--local-dim 3`.

## Outputs

### NPZ

Use `.npz` when downstream code needs the complex basis and reduced matrices. The archive contains:

- `metadata`: JSON with the matched template, dimensions, sector labels, commutator residual, and spectrum reconstruction error;
- `sector_N_basis`: basis isometry for sector `N`;
- `sector_N_block`: reduced Hamiltonian block;
- `sector_N_eigenvalues`: eigenvalues of that block.

### JSON

Use a `.json` output suffix for a human-readable result:

```bash
.venv/bin/python research/candidate/run.py H.npy \
  --symmetry translation \
  --output result.json
```

Complex entries are encoded as `[real, imaginary]` pairs.

## What is automatic—and what is not

The program performs template matching, not unrestricted symmetry discovery:

1. infer dimension-compatible tensor-product models;
2. construct the requested standard symmetry operators;
3. verify `[H,G]≈0`;
4. decompose only a uniquely verified match.

Supplying only `H` cannot identify arbitrary physical group actions uniquely. A nonstandard basis, mixed local spins, fermionic conventions, or a custom group representation requires an explicit representation interface not provided by this command.

For SU(2), each reported block acts on the multiplicity space for total spin `S`; its eigenvalues occur `2S+1` times in the dense spectrum. The reported spectrum reconstruction error checks this multiplicity reconstruction.

## Legacy finite-Abelian corpus mode

The existing corpus interface remains available:

```bash
.venv/bin/python research/candidate/run.py \
  --input-dir research/benchmark/dev \
  --output candidate.json
```

Each corpus `.npz` supplies `matrix`, `generators`, and `moduli` explicitly.

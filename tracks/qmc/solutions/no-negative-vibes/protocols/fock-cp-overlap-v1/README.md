# Fock–CP overlap screen v1

This protocol tests whether natural finite-depth Klein–Hodge Fock transforms
can turn the six-mode overlapping-block quadratic basis into generators of a
completely positive semigroup.

## Grid

- transforms: identity and all contiguous Klein circuits of depth 1 or 2;
- transform count: 13;
- tensorizations: all 20 choices of three ket modes among six;
- families: number-conserving and BdG;
- support: rings plus two bridge edges;
- cells: `13 x 20 x 2 = 520`;
- conditional-CP random directions: 32 per cell after the exact linear
  Hermiticity-preserving gate.

## Run

From the solution directory:

```bash
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
python3 -u -m oracle.fock_cp_screen \
  --klein-depth 2 \
  --family number-conserving \
  --mask rings-bridges \
  --samples 32 \
  --seed 20260729

OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
python3 -u -m oracle.fock_cp_screen \
  --klein-depth 2 \
  --family bdg \
  --mask rings-bridges \
  --samples 32 \
  --seed 20260729
```

The command prints progress to stderr and the machine-readable payload to
stdout. Raw payloads belong under
`tracks/qmc/results/no-negative-vibes/fock-cp-overlap-v1/`.

## Outcome

All 520 cells have zero bridge directions in the
Hermiticity-preserving nullspace. The largest numerical bridge projection is
below `7.0e-15` at rank tolerance `1e-10`; consequently no SDP is needed for
this transform catalog. See `docs/FOCK_CP_SCREEN_RESULTS.md`.

# Tensor-square plaquette v1

This protocol verifies the arbitrary-depth tensor-square determinant theorem,
the exact four-mode positive-field decomposition, its split-orthogonal
reduction, and the direct product-lattice locality obstruction.

## Fixed physical point

```text
time_step = 0.2
hopping = 1.1
field_coupling = 0.6
```

The two noncommuting base fields are lifted as `X_s tensor X_s`. The Fock
average is compared against the exact symmetric Trotter sandwich. All binary
histories through depth 8 are enumerated as a regression check; arbitrary
depth follows analytically from Kronecker closure.

## Run

From the solution directory:

```bash
python3 -m pytest tests/test_tensor_square.py -q
```

## Outcome

- strict arbitrary-depth matrix theorem: proved and tested;
- exact four-mode repulsive HS gate: passed;
- ordinary TN/P0 reduction: excluded;
- four-mode novelty: reduced to known split `O(2,2)`;
- independent onsite fields: exact weight `-155085/32`;
- scalable direct product-lattice locality: failed because local base
  operations lift to system-size strips.

See `docs/TENSOR_SQUARE_RESULTS.md`.

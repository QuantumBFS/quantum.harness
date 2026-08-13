# Exact length-150 counterexample for seed 61

## Verdict

The candidate `exact5-shear-loop-pair:61` is not sign-free at arbitrary
depth.  The following 150-letter word has

```text
det(I + W) < 0
```

by a direct integer calculation:

```text
000000110010101100101011010101100101010101100101100101011001010100110100
110011010101001010101010110101010010110010101101010011010011010011010010
100000
```

The word SHA-256 is

```text
e36ea7ebf0c2038acc3f2a2e0cc97c5fed4a497c8fc9aafa12b61fb24ff4d072
```

This closes the seed-61 proof attempt: the candidate must not be promoted
to an arbitrary-history sign-free family.

## Exact acceptance gate

Let `B` be the positive gauge of the seed-61 atom and put `A=768 B`.
For the bit word above, bit zero selects `A`, bit one selects `A^T`, and

```text
M = A[w1] A[w2] ... A[w150].
```

Thus `W=M/768^150`, and no eigenvalue calculation is needed:

```text
det(I + W) = det(M + 768^150 I) / 768^750.
```

The denominator is positive.  Direct integer expansion of the `5 x 5`
numerator gives:

```text
sign:   negative
digits: 2223
SHA-256 of the signed base-10 numerator:
3ac8e5c102e147edfda33c646a43b1bef3118977f234f7c6a61996e056d69bfe
```

The oracle returns the complete integer numerator and denominator, so the
hash is only a compact frozen identity, not a substitute for recomputation.

## How the word was found

Ordinary double-precision eigenvalues become unreliable for these
ill-conditioned long products.  The search instead used the two compound
representations.  When the top spectral pair is real and negative,

```text
|lambda_3(W)| =
rho(Lambda^3 W) / rho(Lambda^2 W).
```

Products in the two ten-dimensional compound spaces keep this ratio
numerically stable.  Discrete word optimization reduced it through

```text
length 60:   2.1868118536...
length 80:   1.8501785912...
length 100:  1.5011051199...
length 150:  0.9805654650...
```

The last value indicated that one root had entered `(-1,0)`.  It was used
only to locate the word; the accepted result is the exact negative integer
determinant above.

As a diagnostic independent of the sign gate, 180-digit arithmetic gives

```text
lambda_1 =  2.4141640109867965... x 10^32
lambda_2 = -7.3734775481336463... x 10^27
lambda_3 = -0.9805654650228379987...
```

The existing exact stable-tail certificate applies from length 24 and
places the bottom pair strictly inside the unit disk.  Therefore its
quadratic factor is positive here, while the top-pair factor is negative,
consistent with the direct determinant sign.

## Reproduce

From `tracks/qmc/solutions/no-negative-vibes`:

```bash
PYTHONPATH=. python -c \
  "from oracle.exterior_seed61_counterexample import audit_seed61_exact_counterexample as a; print(a())"

PYTHONPATH=. python -m pytest \
  tests/test_exterior_seed61_counterexample.py -q
```

The implementation is
`oracle/exterior_seed61_counterexample.py`.  It uses only integer matrix
multiplication and an exact determinant for the acceptance result.

# Oddcycle robust candidate v1

This protocol freezes the independently promoted frontier point
`cell-4321`.  For

```text
B(p,q,r) =
[[0,0, 2,0,0],
 [2,0, 0,0,0],
 [0,2, 0,p,0],
 [0,0, 0,1,q],
 [0,0,-r,0,1]]
```

the four-letter alphabet is

```text
{
  B(1/2000,11/10,9/10),
  B(1/2000,11/10,9/10)^T,
  B(49/40,11/10,9/10),
  B(49/40,11/10,9/10)^T
}.
```

`frozen-certificate.json` contains only exact rational inputs:

- four path-metric numerator matrices over denominator `10^9`;
- four integer time vectors;
- four normalized Gordan--Stiemke dual multipliers, including their exact
  individual denominators.

The production verifier reconstructs every derived quantity.  It checks
four `(1,4)` inertias, all 16 positive-definite Stein gaps, coherent time
orientation, exact dual cancellation and normalization, multiplier
positivity, the 32-dimensional Fock transfer, real logarithms for all four
letters, and the non-Gaussian grade-two mismatch.

Run the one-command exact replay from the solution root:

```bash
python -m oracle.oddcycle_robust_certificate
```

Run the focused regression:

```bash
python -m pytest -q tests/test_oddcycle_robust_certificate.py
```

Neither command runs an SDP or scans parameters.  `cvxpy` and the discovery
artifacts are not needed once the frozen exact inputs are present.

The safe interpretation matches the main candidate: this alphabet is
sign-free at arbitrary auxiliary-field depth, is exactly separated from a
one-state common symmetric quadratic metric of the tested form, and has a
positive-field Hermitian interacting five-mode realization.  It does not
exclude a common nonquadratic cone or the full Wei/Majorana framework.

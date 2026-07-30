# Exact Hermitian interacting target for the leading oddcycle pair

Let

```text
B0 = B(1/1000, 1, 1)
B1 = B(4/5, 1, 1)
```

and let `Gamma` be the ordinary number-conserving exterior Fock lift.  On
the 32-dimensional five-mode Fock space define

```text
T = 37 I
  + Gamma(B0) + Gamma(B0)^T
  + Gamma(B1) + Gamma(B1)^T .
```

Exact row arithmetic gives a maximum diagonal-dominance requirement of
36.  Thus `T` is real symmetric, strictly diagonally dominant with minimum
row margin one, and positive definite.  The normalized transfer

```text
T / 41 = exp(-H)
```

defines a real Hermitian, number-conserving Hamiltonian
`H = -Log(T/41)`.

The five auxiliary fields are

```text
I, B0, B0^T, B1, B1^T
```

with strictly positive coefficients

```text
37/41, 1/41, 1/41, 1/41, 1/41.
```

Both one-particle atoms have determinant eight.  Their characteristic
polynomials evaluated at a negative real argument have only negative
coefficients (`p=1/1000` and `p=4/5` are both below eight), so they have no
negative real eigenvalue and admit real one-particle logarithms.

The transfer is genuinely interacting.  If it were a scalar Gaussian
lift, its vacuum, one-particle, and two-particle blocks would satisfy

```text
41 T2 = wedge^2(T1).
```

The exact difference has 58 nonzero entries; its `(0,0)` entry is 164.

This file closes the physical-realizability gate.  The separate exact
last-letter path-metric certificate proves `det(I+W)>0` for every word in
the same four nonidentity letters, so the resulting positive-field model
is sign free at arbitrary auxiliary-field depth.

Replay from `tracks/qmc/solutions/no-negative-vibes`:

```bash
PYTHONPATH=. python -m oracle.oddcycle_pair_physical
PYTHONPATH=. python -m pytest -q tests/test_oddcycle_pair_physical.py
```

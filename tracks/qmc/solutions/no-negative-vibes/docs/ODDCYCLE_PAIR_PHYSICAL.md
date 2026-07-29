# Exact Hermitian interacting target for the leading oddcycle pair

Let

```text
B0 = B(3/10, 1, 1)
B1 = B(5/2, 1, 1)
```

and let `Gamma` be the ordinary number-conserving exterior Fock lift.  On
the 32-dimensional five-mode Fock space define

```text
T = 45 I
  + Gamma(B0) + Gamma(B0)^T
  + Gamma(B1) + Gamma(B1)^T .
```

Exact row arithmetic gives a maximum diagonal-dominance requirement of
44.  Thus `T` is real symmetric, strictly diagonally dominant with minimum
row margin one, and positive definite.  The normalized transfer

```text
T / 49 = exp(-H)
```

defines a real Hermitian, number-conserving Hamiltonian
`H = -Log(T/49)`.

The five auxiliary fields are

```text
I, B0, B0^T, B1, B1^T
```

with strictly positive coefficients

```text
45/49, 1/49, 1/49, 1/49, 1/49.
```

Both one-particle atoms have determinant eight.  Their characteristic
polynomials evaluated at a negative real argument have only negative
coefficients (`p=3/10` and `p=5/2` are both below eight), so they have no
negative real eigenvalue and admit real one-particle logarithms.

The transfer is genuinely interacting.  If it were a scalar Gaussian
lift, its vacuum, one-particle, and two-particle blocks would satisfy

```text
49 T2 = wedge^2(T1).
```

The exact difference has 58 nonzero entries; its `(0,0)` entry is 196.

This file closes the physical-realizability gate.  Calling the model
sign-free still depends on the separate arbitrary-word theorem
`det(I+W)>0` for the four nonidentity letters.  No such theorem is assumed
by this certificate.

Replay from `tracks/qmc/solutions/no-negative-vibes`:

```bash
PYTHONPATH=. python -m oracle.oddcycle_pair_physical
PYTHONPATH=. python -m pytest -q tests/test_oddcycle_pair_physical.py
```

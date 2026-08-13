# Hodge reduction of the oddcycle grade-(3,4) sector

For either oddcycle atom let

```text
P = D wedge^4(B) D,  D = diag(1,1,1,-1,1).
```

For positive `p,q,r`, `P` is entrywise nonnegative.  In the
`q=r=1` family an exact signed-permutation matrix `H` satisfies

```text
wedge^2(P) = 8 H wedge^3(B) H^T.
```

The same `H` works for every positive `p` and for transpose atoms.  Exterior
multiplicativity therefore gives, for every length-`n` word,

```text
wedge^2(P_w) = 8^n H wedge^3(W) H^T.
```

Taking traces reduces the difficult sector pair to one nonnegative
five-state product:

```text
chi3(W) + chi4(W)
  = 8^(-n) [ e2(P_w) + 8^n trace(P_w) ].
```

Equivalently, the bracket is

```text
trace wedge^2(diag(P_w, 8^n)).
```

This does not by itself prove positivity, because a nonnegative matrix can
have negative second elementary symmetric function.  It is nevertheless a
strict reduction: the signed 10-dimensional grade-three dynamics is no
longer independent.  The remaining theorem can be sought as a
five-state path injection or as a 15-dimensional invariant-cone
certificate for

```text
wedge^2(diag(P_i, 8)).
```

Exact replay:

```bash
PYTHONPATH=. python -m pytest -q tests/test_oddcycle_grade34_hodge.py
```

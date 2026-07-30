# Exact full spin-axis permutation quotient

## Route

After V4 averaging and computational-basis conjugation, the fixed Challenge
88 relaxation is invariant under every permutation of the three spin axes.
For an axis permutation `p`, use the proper-rotation lift

```text
R(p) = sign(p) P(p).
```

Even permutations act by their permutation matrices. Odd permutations act by
the negative permutation matrix. This is a homomorphism from S3 into SO(3), so
it is implemented by global physical spin rotations and preserves the
isotropic Shastry--Sutherland Hamiltonian.

The conjugation-even, V4-invariant scalar moments have even X, Y, and Z
parity. Their total Pauli degree is therefore even, and the minus sign in an
odd lift cancels exactly. The action on all retained scalar moments is an
unsigned six-element axis-permutation orbit.

## Why the next model remains equivalent

The previously proved `X↔Z, Y↦−Y` model exactly parameterizes the feasible
functionals invariant under one order-two subgroup. Averaging any unrestricted
feasible functional over all six proper rotations gives a fully
S3-invariant feasible functional. Conversely, any fully invariant functional
is already invariant under the proved order-two subgroup.

It is therefore sufficient to quotient the current 8,803 moment coordinates
by their full S3 orbits while retaining every current PSD block. This changes
no cone or equality requirement and cannot weaken the finite relaxation.
Redundant S3-related cones may be removed only in a later, separately proved
block-congruence step.

## Truth gate

Before the orbit count is accepted, the implementation:

1. checks the Hamiltonian under all six proper-rotation lifts;
2. checks every upper-triangle coefficient of all V4 positive and facially
   reduced gap blocks under all six actions;
3. checks the complete V4 affine-equality row space;
4. checks closure of the complete conjugation-even moment inventory;
5. proves that every retained moment action has sign plus;
6. constructs the deterministic six-element orbit inventory.

The coefficient covariance check is deliberately performed before the
conjugation phase gauge. There the rotations are exact signed row
permutations, so no complex gauge relation is assumed.

# R01 candidate card — overlapping Klein/Fock circuit cone

Claimed by: Zibo

Claim date: 2026-07-28

Initial status: `claimed-design`

## Candidate definition

On four modes, let `u_K` act by the Klein–Hodge transform in the two-particle
sector and by identity elsewhere. On six modes use the fixed global circuit

```text
U_6 = u_(3456) u_(1234).
```

The candidate cone is the set of local real quadratic BdG operators `Q` for
which both parity blocks of `U_6 Q U_6^(-1)` are Metzler. The candidate is
interesting only if it contains a cross-cluster term and two noncommuting rays.

The physical weights under test are the even/odd Fock/Spin traces of arbitrary
products, not a square root chosen from a determinant.

## Why it may be nonnegative

A fixed Metzler basis makes each exponential entrywise nonnegative. Products
remain nonnegative and have nonnegative traces in each parity block. This is an
arbitrary-depth proof if the LP compiler exactly characterizes the cone.

## Novelty checks

Required checks:

- non-inducedness/Plücker decomposability;
- split and contraction metrics;
- Kramers, Majorana reflection, and MTR;
- diagonal Fock gauge and GF(2) coboundary;
- Jordan–Wigner exchange holonomy;
- disconnected block or open-path reduction.

The four-mode seed is high risk because of its relation to split `SO(3,3)`.

## Smallest experiment

Compile the exact six-mode parity-block inequalities. For each cross-cluster
coefficient and sign, fix that coefficient as an anchor and solve feasibility.
Extract two rays and test their commutator.

Success: exact cross-cluster, noncommuting, non-reduced cone.

Failure: exact Farkas certificate forces cross-cluster coefficients to zero or
to open-path/disconnected support.

## Physical route

If scalable, the same global Fock circuit becomes the common sign-free branch
certificate for overlapping plaquette HS gates. R02 tests the positive local
gate cone. Without R02, R01 remains a matrix theorem/no-go rather than a
challenge solution.

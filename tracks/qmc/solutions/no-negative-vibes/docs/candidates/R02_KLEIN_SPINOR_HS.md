# R02 candidate card — Klein–Spinor positive local HS cone

Claimed by: Zibo

Claim date: 2026-07-28

Initial status: `claimed-design`

## Candidate definition

On a four-mode plaquette use Gaussian branches

```text
Q = dGamma(A) + u P+ + v P-
```

whose fixed parity transforms are real Metzler. Search for a positive direct
sum or dagger-stable Gram decomposition of an analytic local gate
`E_X(dt)=exp(-dt h_X)` on an interval `0 < dt < dt_0`.

The target includes an interaction and at least one feature outside the simple
half-filled bipartite template: chemical potential, pairing, or ring exchange.

## Why it may be nonnegative

Every branch or fixed Gaussian micro-word lies in a common parity-positive
semigroup. Positive HS coefficients preserve the Monte Carlo sign. A Gram gate
`epsilon I + R^dag R` is Hermitian positive definite by construction and has a
positive expansion when the branch semigroup is dagger-stable.

## Novelty checks

- branch-by-branch parity/Spin lift;
- known Kramers/Majorana/split reductions;
- flavor doubling or hidden modulus square;
- locality and body order of `-log(E_X)/dt`;
- positive scalar HS prefactors;
- shared certificate under overlapping lattice tilings.

## Smallest experiment

Use a `16 x 16` exact Fock basis. Match the small-time moment equations with
`sqrt(dt)` symmetric-field scaling so quartic terms can appear at order `dt`.
First solve tangent/moment feasibility; only then fit finite-`dt` gates.

Success: analytic positive family with exact gate identity and a genuinely
interacting target.

Failure: an exact Hermitian separating functional for the chosen target cone,
or proof that the quartic tangent span is only a known model.

## Physical route

The decomposition itself is the local HS dictionary. A full result must state
the lattice Hamiltonian, tiling/Trotter order, field probabilities, every
branch generator, and why one global representation certificate covers all
placements.

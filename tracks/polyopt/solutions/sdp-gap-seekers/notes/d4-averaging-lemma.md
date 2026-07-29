# D4 averaging lemma — feasibility-equivalence of the D4-reduced relaxation

Date: 2026-07-29
Status: written to resolve advisor P0.4 / P0.3 (delivery-strategy stop-gate).
Computational support: the exact coefficient gates committed in
`evidence/d4-coefficient-gates-5f79c93/` (M/K/G covariance, off-irrep
cancellation). This note states the theorem, its assumptions, and the precise
scope of the conclusion. Conservative labelling is used wherever the scope is
narrower than a physical statement.

## What is averaged

The object averaged is a **relaxed state-polynomial functional** (a
pseudo-moment sequence) `L` on the finite truncated state-polynomial algebra —
i.e. the decision variable of the SDP relaxation. It is **not** a physical KMS
state. The relaxation is the finite-level feasibility problem defined in
`square-j1j2-gap-sdp-spec.md` §6.

## Definitions

Let the finite relaxation's feasible set at gap threshold `gamma` be

```text
F(gamma) = { L :
    L(1) = 1,                                    (normalization)
    L(zeta([H, q])) = 0  for every stationarity candidate q,   (stationarity)
    M_pos(L) = L(zeta(b_i* b_j))_ij  >= 0,       (positivity)
    M_gap(gamma)(L) >= 0 }                        (gap / covariance)
```

`F(gamma)` is convex: it is an affine subspace (normalization + stationarity)
intersected with the positive-semidefinite cone (a convex cone) in two
roles (positivity and gap).

The D4 group `G` (order 8) acts on functionals by `(g.L)(p) := L(g^{-1}.p)`,
where `g` acts on operators/state-polynomials by relabelling sites (the spatial
symmetry of the patch; Pauli axes are unchanged).

## Theorem (feasibility equivalence)

Under the assumptions below, `F(gamma)` is non-empty if and only if the
D4-invariant subset `F(gamma)^G = { L in F(gamma) : g.L = L for all g }` is
non-empty. Consequently the D4-reduced relaxation (moment-orbit quotient +
diagonal irrep blocks) has the **same** feasibility threshold in `gamma` as the
unrestricted finite relaxation.

## Proof

It suffices to exhibit, for every `L in F(gamma)`, a D4-invariant `L* in F(gamma)`.

1. **D4-stability of each constraint.** For every `g in G`:
   - Normalization: `(g.L)(1) = L(g^{-1}.1) = L(1) = 1`, since the identity
     operator is D4-fixed.
   - Stationarity: `(g.L)(zeta([H,q])) = L(zeta(g^{-1}.[H,q])) =
     L(zeta([g^{-1}H, g^{-1}q]))`. Because the Hamiltonian is D4-invariant
     (`g^{-1}H = H`, gate 1) and the stationarity candidate set is D4-closed
     (gate on the candidate inventory), `g^{-1}q` is again a stationarity
     candidate, so the value is `0`.
   - Positivity: `M_pos(g.L)_{ij} = (g.L)(zeta(b_i* b_j)) =
     L(zeta(g^{-1}.(b_i* b_j))) = L(zeta((g^{-1}b_i)*(g^{-1}b_j)))`. As a
     matrix this is `U(g^{-1})' M_pos(L) U(g^{-1})`, a congruence of a PSD
     matrix, hence PSD.
   - Gap: the gap matrix `M_gap(gamma)` is built from `K`, `G_moment`, and
     `G_product`. Gates 3-4 verify these coefficient maps are D4-equivariant, so
     `M_gap(gamma)(g.L)` is again a congruence `U(g^{-1})' M_gap(gamma)(L) U(g^{-1})`,
     PSD whenever `M_gap(gamma)(L)` is.

   Hence `g.L in F(gamma)`: `F(gamma)` is D4-stable.

2. **Averaging.** Define `L* := (1/|G|) sum_{g in G} g.L`. Because `F(gamma)` is
   convex and D4-stable, `L*` is a convex combination of points of `F(gamma)`,
   so `L* in F(gamma)`. For any `h in G`, `h.L* = (1/|G|) sum_g hg.L =
     (1/|G|) sum_{g'} g'.L = L*` (relabel `g' = hg`); so `L*` is D4-invariant.

Therefore `F(gamma) != {}  =>  F(gamma)^G != {}`. The reverse inclusion is
trivial. ▢

## Why the block model realizes `F(gamma)^G`

The moment-orbit quotient identifies variables `L(zeta(m))` and `L(zeta(g.m))`,
which is exactly the constraint `g.L = L` on functionals. Gate 3 (M covariance)
plus the symmetry-adapted basis `Q` (verified block-diagonal in
`check_d4_symmetry_basis.jl`) imply that for a D4-invariant `L` the matrix
`M(L)` commutes with every `U(g)`, so `Q' M(L) Q` is block-diagonal and the
single `M(L) >= 0` constraint is equivalent to its irrep diagonal blocks all
being PSD (Sylvester's law of inertia, `Q` invertible). Gate 6 (off-irrep
cancellation, sampled) confirms the off-diagonal blocks vanish in the quotient
variable space. Thus the emitted 5-block model is exactly the feasibility
problem on `F(gamma)^G`.

## Scope and limitations (conservative labelling)

- The theorem is about the **finite relaxation's** feasibility, which is what
  the `gamma`-scan measures. It is **not** a statement that averaging physical
  KMS states preserves a physical bulk gap.
- The relaxation's feasibility threshold is an upper bound on the physical
  bulk gap `Delta_bulk` only via the usual relaxation theory (a physical
  `gamma`-gapped KMS state yields a feasible `L`; the converse is not asserted
  at finite level). This caveat is **independent of D4** — it applies to the
  unrestricted relaxation equally.
- Remark 2.7 of `arXiv:2606.03836` concerns the non-convexity of the set of
  *physical* locally-non-degenerate gapped states: an average of
  symmetry-related pure gapped states can be a mixed, locally degenerate state.
  That subtlety lives at the physical-state level and does not affect the
  convex-functional averaging above; it is a caveat about the relaxation's
  tightness to the physical gap, not about whether D4 preserves the
  relaxation's answer.

Until the source-paper authors confirm the physical interpretation of the
linear invariance constraints, the recommended public label is:

> D4-averaged finite relaxation; feasibility-equivalent to the unrestricted
> finite relaxation by convex averaging; physical symmetry interpretation under
  review.

## Open follow-ups (not blocking the finite-relaxation claim)

- exhaustive (not sampled) off-irrep cancellation, or a general argument from
  gate 3 + representation theory that sampling is unnecessary;
- explicit stationarity-space covariance gate (currently implied by gate 1 +
  candidate closure, not asserted row-by-row);
- confirmation from the challenge authors on the Remark 2.7 reading.

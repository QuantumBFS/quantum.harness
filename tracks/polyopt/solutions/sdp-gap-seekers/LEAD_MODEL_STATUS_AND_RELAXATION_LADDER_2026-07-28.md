# Model status and a practical relaxation ladder

Date: 2026-07-28

Purpose: answer which examples already work, identify what the current SCNet
jobs are solving, and choose a smaller first Square J1-J2 relaxation before
spending a full node on the present formulation.

## Executive decision

Pause the proposed 486.4 GB Square retry.

The current Square configuration already uses the smallest non-vacuous patch
and degree, `(L,d)=(1,2)`, but it does **not** use the smallest sound basis. Its
`one_symbol_lift/v1` positive basis introduces 74,602 scalar moments and a
703-dimensional complex PSD constraint, which becomes a 1406-dimensional real
PSD constraint with 989,121 packed rows. Together with the 14-dimensional real
gap block, Mosek receives 989,226 affine-conic rows. Both 60.8 GB and 243.2 GB
jobs OOM before the first interior-point iteration.

The next scientific move should be a declared nested basis ladder at the same
physical point, starting with a much smaller principal-submatrix relaxation.
A loose, reproducible Square result is more valuable than immediately forcing
the largest current basis onto a full node.

## 1. Ising status

There is a working, fast legacy transverse-field Ising **gap calibration**:

```text
model       = 1D TFIM
N           = 9-site local-consistency window
g           = 0.5
d           = 2
state class = legacy sign-symmetric
solver      = Mosek 11.2.2
runtime     = approximately 4–25 seconds per recorded point
memory      = no recorded OOM at this configuration
```

The legacy scan changes flag between `gamma=0.25` and `gamma=0.26`. At
`gamma=0.26`, a candidate improving ray was exported and a standalone verifier
checked the declared affine identity, Gram PSD blocks, and deliberate
corruptions.

This is useful and substantially more mature than the Square solve, but
“has everything” is too strong:

- the raw termination is `SLOW_PROGRESS`, not a decisive
  `DUAL_INFEASIBLE`;
- the artifact is a numerically audited candidate, not a rational/interval
  certificate;
- the formulation manifest still needs to establish independently that the
  exported conic instance is exactly the intended TFIM hierarchy instance;
- the repository does not contain one unified, strict energy-plus-gap
  certificate bundle for TFIM. The ground-energy work is a separate
  QMBCertify track.

The important operational lesson is nevertheless valid: the hand-selected,
symmetry-reduced TFIM basis makes the end-to-end solver/certificate workflow
small and fast.

## 2. What the current jobs solve

Jobs `22986777`, `22986943`, and `22987149` solve the new direct-primal:

```text
model          = Square J1-J2 Heisenberg
J1             = +1 antiferromagnetic
g=J2/J1        = 1/2
L              = 1
outer / inner  = 9 / 1 sites
d              = 2
state          = unrestricted; no sector or imposed symmetry
positive basis = one_symbol_lift/v1, dimension 703, incomplete
gap basis      = one_symbol_lift/v1, dimension 7
stationarity   = bare_inner_pauli/v1, 3 nonzero equalities, incomplete
gamma          = 0 for the first smoke
target         = feasibility only
```

This is not Ising and not Kagome.

The scientific model and exact MOF are consistent and checksum-bound. The
failure is tractability of this particular finite relaxation:

| Job | Memory | Last trustworthy stage | Outcome |
|---|---:|---|---|
| `22986777` | 60.8 GB | `optimize!` started | OOM |
| `22986943` | 243.2 GB | `optimize!` started | OOM; peak about 221 GiB |
| `22987149` | 243.2 GB | explicit MOI attachment completed in 5.6 s at about 1.2 GiB; forced-dual Mosek presolve completed | OOM before first iteration; peak about 222 GiB |

The last job proves that model loading and MOI bridging are cheap compared
with interior-point factorization. Mosek reports:

```text
scalar variables   = 74,602
linear constraints = 4
affine conic rows  = 989,226 in two constraints
solve form         = forced dual
```

There is still no Square feasibility status and no Square gap bound.

## 3. Kagome and energy status

### Kagome gap

The project has a completed **legacy numerical reproduction**, not a completed
rigorous result:

```text
Kagome N=13, d=3:
legacy flag transition = 1.26 to 1.28
runtime                 = approximately 290 seconds
OOM                     = no at N=13,d=3
```

This reproduces the upstream `SpectralGap.jl` example and is therefore
calibration rather than the requested challenge novelty. It cannot currently
be called a certified bound. The later common-verifier work rejected the
reported Kagome high-side candidate on residual quality, so the honest status
is “legacy transition observed; rigorous gap conclusion not done.”

`N=27,d=3` is not done: it OOMed at 243 GB and then made no completed first
solve in 2 h 08 min on 486 GB. `N=13,d=4` is the same implemented SDP as
`d=3`, not a convergence test.

### Energy

The separate `feature/energy-cert-floor` branch contains numerical ground-state
energy lower bounds for **Square J1-J2**, including:

```text
g=0.5,   L=4, d-label=4, rdm=8: E0/N >= -0.5173, about 33 s
g=0.535, L=4, d-label=6, rdm=8: E0/N >= -0.5088, about 26 s
```

These are useful numerical SDP energy floors, but their current ledger
explicitly retracts the word “formally certified”: the scripts did not retain
enough solver-status/residual evidence, the raw results are off-branch, and
the runtime `QMBCertify` patch is not frozen cleanly. Increasing the energy
track's `d` label beyond four also does not enlarge its implemented basis.

There is no corresponding completed Kagome energy deliverable in this team
branch. Shastry-Sutherland energy and exact-gap calibration remain planned.

## 4. Which knobs are real?

For the direct Square gap hierarchy:

- `L` controls the local-consistency window;
- `d` controls the formal degree;
- the **basis family/subset** controls which sound finite principal
  submatrices are actually imposed;
- the stationarity selector controls which commutator equalities are imposed;
- `gamma` is the tested gap threshold, not an accuracy setting.

Reporting only `(L,d)` is insufficient because two basis rules at the same
`(L,d)` can differ by orders of magnitude.

### Why `L` and `d` cannot simply be lowered now

`L=1` is the smallest Square window with a one-layer interaction buffer for
the two-site J1/J2 Hamiltonian. Lowering it loses the intended local bulk
geometry.

At `d=1`, the gap basis has degree zero and contains only the identity.
The identity has zero excitation energy and zero covariance, so its gap
constraint is identically zero. That relaxation is feasible for every
`gamma` and cannot produce a gap threshold. Thus `d=2` is the smallest
non-vacuous degree.

The remaining useful reduction knob is the basis.

## 5. Recommended Square ladder

Every rung must have a versioned selector, explicit ordered entries, hashes,
exact assembly hash, MOF hash, and the same conservative result semantics.
Removing PSD rows/columns or stationarity conditions enlarges the relaxation's
feasible set. Therefore, an infeasibility result from a smaller sound rung is
still meaningful, although its resulting upper bound will generally be
weaker.

### Rung A — tiny end-to-end Square smoke

```text
physical setup     = unchanged Square g=1/2, L=1, d=2
positive basis     = identity + all one-site bare Pauli words on 9 outer sites
positive dimension = 1 + 9*3 = 28 complex
gap basis          = identity + X,Y,Z on the one inner site
gap dimension      = 4 complex
stationarity       = current three bare-inner equalities
suggested name     = bare_weight_one/v1
```

The real PSD embeddings have dimensions 56 and 8, only 1,632 packed
affine-conic rows in total. This should be a fast end-to-end correctness and
artifact test. It will be loose and must be labelled as such.

Run sequence:

1. `gamma=0` sanity;
2. one modest positive threshold;
3. one deliberately high threshold;
4. only if a status transition appears, bracket it coarsely.

### Rung B — bare degree-two Square relaxation

```text
physical setup     = unchanged
positive basis     = all bare outer-patch Pauli words through degree 2
positive dimension = 352 complex
gap basis          = bare inner-patch words through degree 1
gap dimension      = 4 complex
suggested name     = bare_operator/v1
```

Its real PSD embeddings have dimensions 704 and 8, approximately 248,196
packed affine-conic rows—about one quarter of the current 989,226. The linear
operator-word inventory through degree four is 12,826 before the few extra
covariance-product moments, versus the current 74,602 variables. This is the
best candidate for a first scientifically useful but loose Square threshold.

### Rung C — current one-symbol relaxation

```text
positive / gap dimensions = 703 / 7 complex
scalar moments             = 74,602
real affine-conic rows     = 989,226
```

Retain this rung as the stronger target after A and B work. Do not spend a
486.4 GB node on it before the smaller rungs establish:

- end-to-end solver behavior;
- gamma monotonicity;
- artifact/replay correctness;
- whether the weaker Square relaxation gives any finite transition worth
  tightening.

### Later rungs

Only after Rung C is understood should the project increase `L`, increase `d`,
or add larger nested state-symbol subsets. The exact count table shows that
`L=2,d=2` one-symbol already has dimension 5,551 and `L=1,d=3` one-symbol has
dimension 5,239, so either change is much larger than the current OOM case.

## 6. Recommended next action

Implement and export Rung A and Rung B without changing the physical
Hamiltonian, state class, or status/certificate policy. Run only Rung A
`gamma=0` first. If it returns coherently, proceed through its three-point
threshold smoke and then Rung B.

This is not abandoning accuracy. It is constructing a nested evidence ladder:

```text
small, loose, runnable Square result
    -> larger bare basis
    -> current one-symbol basis
    -> larger L/d only if justified
```

The correct headline, until witness replay passes, remains “numerical
transition candidate for a declared finite Square relaxation,” not “certified
physical bulk-gap bound.”

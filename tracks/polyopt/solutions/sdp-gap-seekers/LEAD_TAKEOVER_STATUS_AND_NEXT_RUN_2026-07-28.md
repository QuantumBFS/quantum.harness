# Lead takeover: verified status, implementation contract, and next run

Date: 2026-07-28

Branch: `challenge/polyopt-sdp-gap`

Review/implementation base: `8c1b58bdc9e17d2699a9ef51111e71601a5dd41a`

Mode: direct lead execution; the prior worker-advisor packet loop is paused

## Executive decision

The project remains on the expected scientific track, but two previously
interleaved tracks must be kept separate:

1. the legacy TFIM/Kagome certificate-audit track is useful calibration and
   infrastructure;
2. the Square J1-J2 challenge requires a direct state-polynomial primal model
   and cannot be obtained by relabelling a legacy Kagome certifier.

Sihan's structured-basis and legacy-inventory PRs were suitable prerequisites
and have been integrated. His later MOF/ray/verifier claims remain unavailable
for independent review. Work on Square J1-J2 should therefore continue through
the exact direct-primal implementation while retaining a clean integration
point for Sihan's artifacts if they become visible.

There is still **no Square J1-J2 gap result**. The current claim is only:

> a solver-independent exact coefficient assembler and a solver-free JuMP
> model adapter now exist and pass hand-checkable algebraic tests.

## 1. Repository state independently verified

### 1.1 Integrated visible work

The following visible Sihan branches were independently inspected in isolated
worktrees before ordinary merge commits:

- PR #3 / `feature/structured-basis-assembly`, source head
  `7bacf012e3e775a95e4c042bc088d05d158cfc56`;
- PR #4 / `fix/legacy-inventory-freeze-contract`, source head
  `46726ab73ea5f5accc5f557cf702fe22db71d245`.

They are integrated on this branch through:

- `710eb19f43186ad50a8eba3217d332cc0f955ceb`;
- `8c1b58bdc9e17d2699a9ef51111e71601a5dd41a`.

Both merge states passed the then-current Julia suite. The branch was pushed
to both GitHub over SSH and the SCNet remote without force.

### 1.2 Missing Sihan certificate artifacts

The four chat-reported commits remain unavailable:

- `b1a1cad`;
- `8c6106f`;
- `59f4b09`;
- `c1ae6f7`.

They were absent from:

- the local object database;
- the `iintSjds` GitHub fork;
- the `flyingwagner` GitHub fork;
- Sihan's visible PRs #1, #3, and #4.

A bot-authored request was sent to the Feishu `hackathon` group at 21:01,
message `om_x100b69becf41b8a0b21a6c714ae331e`. It requests a visible branch and
full successor SHAs, together with MOF, ray, machine-readable run metadata,
verifier source/tests/output, boundary-scan output, and SHA-256 values. No reply
had appeared at the time of this note.

### 1.3 The visible xH5 status branch does not unblock the audit

Sihan's fork exposes `feature/xh5-status-runner` at
`f9e2c6bb4803235f9ae06fe1293651b2ed63df10`. It is older than the claimed
certificate-audit work and contains a raw-status runner, not the missing MOF
pipeline. Its own `STATUS_RUNNER.md` says residual and witness fields are
explicitly unavailable. It therefore must not be mistaken for, or merged as,
the claimed later MOF/ray/verifier work.

### 1.4 SCNet access

The repository's standard Slurm wrapper works with the committed SCNet profile
when the system Python is selected:

```bash
PATH=/usr/bin:$PATH \
HARNESS_CLUSTER_PROFILE=scnet \
scripts/harness_slurm.sh precheck
```

The default shell currently resolves `python3` to a Python 3.10 environment
without `tomllib`; `/usr/bin/python3.12` avoids that unrelated wrapper failure.
No scientific job has been submitted during this takeover.

## 2. Mathematical contract implemented

The source of truth is `square-j1j2-gap-sdp-spec.md`, especially Sections 5–8.
The implementation does not call or modify `.external/SpectralGap`.

### 2.1 Exact scalar moments

For every canonical Hermitian Pauli word `w`, `ζ(w)` is a real commuting state
symbol. A scalar moment key is the sorted multiset

```text
ℒ(ζ(w1) ... ζ(wk)).
```

Identity symbols are removed using `ζ(I)=1`. Every coefficient is stored as
`Complex{Rational{BigInt}}`. Float input is rejected by exact assembly.

This distinction is enforced:

```text
ℒ(ζ(s†t))  !=  ℒ(ζ(s†)ζ(t)).
```

For example, with `s=X` and `t=Y`,

```text
ζ(s†t)    = i ζ(Z),
ζ(s†)ζ(t) = ζ(X)ζ(Y).
```

Multiplying the second expression as `XY=iZ` would destroy the variance term
and make the gap formulation wrong.

### 2.2 Positivity entry

For basis monomials `s,t`,

```text
M_pos[s,t] = ℒ(ζ(s†t)).
```

Only their operator words are Pauli-multiplied. Existing state-symbol factors
remain a commuting multiset.

### 2.3 Stationarity entry

For a test monomial `q`,

```text
stationarity(q) = ℒ(ζ([H,q])) = 0.
```

Complex expressions are split into real and imaginary equalities. Exact zeros
are removed. Nonzero equalities are normalized so their first canonical
coefficient is `+1`; duplicate scalar multiples are then removed
deterministically.

The current versioned selector is:

```text
family  = bare_inner_pauli
version = 1
rule    = all bare inner-patch Pauli words through degree 2d-2
```

This is a **sound but incomplete subset**. It omits stationarity equations
multiplied by nontrivial scalar state-symbol monomials. Any result must name
and hash this selector.

### 2.4 Gap entry

The implemented Hermitian energy term is

```text
1/2 ζ(s†[H,t] - [H,s†]t)
  = ζ(s†Ht) - 1/2 ζ(s†tH) - 1/2 ζ(Hs†t).
```

The complete entry is

```text
M_gap[s,t] =
    ℒ(1/2 ζ(s†[H,t] - [H,s†]t))
    - gamma (ℒ(ζ(s†t)) - ℒ(ζ(s†)ζ(t))).
```

No ground-state vector and no orthogonality constraint are introduced.

### 2.5 Deterministic assembly identity

The exact assembly records and hashes:

- the contextual problem SHA-256;
- positive and gap basis SHA-256 values;
- stationarity selector and candidate SHA-256;
- canonical nonzero real stationarity equalities and SHA-256;
- every scalar moment in deterministic degree/lexicographic order and SHA-256;
- the exact polynomial hash of every upper-triangular positivity and gap entry;
- one final assembly SHA-256 binding all of the above.

All emitted moments are checked to have degree at most `2d`. Matrix diagonals
must be exactly real, and off-diagonal entries are checked against the exact
adjoint entry before numerical conversion.

## 3. Numerical adapter contract

`PrimalGapJuMP.jl` converts one exact assembly into an empty, optimizer-free
JuMP feasibility model:

- one real JuMP variable per scalar moment;
- the identity moment is fixed to `1`;
- one real equality per canonical stationarity equation;
- one named `positive_psd` Hermitian PSD cone;
- one named `gap_psd` Hermitian PSD cone;
- no objective other than feasibility;
- no attached optimizer;
- no implicit state symmetry.

Exact rationals are converted to `Float64` only here. Overflow and nonzero
underflow are rejected. The returned model retains the exact assembly SHA-256.
JuMP/MOI represents each cone as
`HermitianPositiveSemidefiniteConeTriangle`, which MathOptFormat can serialize
without a hand-written real embedding.

This adapter is not yet a certificate verifier. A later exporter/verifier must
bind the MOF variable order, equality order, objective, affine columns, cone
order/dimensions/packing, model SHA-256, and exact assembly SHA-256.

## 4. Files added in this takeover

- `src/PrimalGapSymbolics.jl`
  - exact moments and affine polynomials;
  - positivity, covariance, stationarity, and gap entries;
  - deterministic canonical serialization.
- `src/PrimalGapAssembly.jl`
  - versioned stationarity selection;
  - duplicate removal;
  - exact moment inventory and assembly hashes.
- `src/PrimalGapJuMP.jl`
  - optimizer-free direct-primal JuMP model.
- `test/primal_gap_symbolics_tests.jl`
  - hand algebra, exactness, Hermiticity, deterministic assembly, and JuMP cone
    tests.
- `test/runtests.jl`
  - includes the new test file.

## 5. Verification performed

Command:

```bash
julia --project=julia-env \
  tracks/polyopt/solutions/sdp-gap-seekers/test/runtests.jl
```

Final result:

```text
569 passed, 0 failed, 0 errored
```

The new hand checks include:

- `XY=iZ` and `YX=-iZ`;
- positivity Hermiticity;
- `[Z,X]=2iY`;
- `1/2 (X[Z,X]-[Z,X]X)=-2Z`;
- variance `-gamma(1-ζ(X)^2)`;
- identity has zero energy and zero variance;
- exact gap Hermiticity across all entries of the 7-row Square gap basis;
- deterministic duplicate stationarity removal;
- a full one-site exact assembly built twice with identical hashes;
- changing `gamma` changes the problem, coefficient-map, and assembly hashes;
- the tiny JuMP model has the expected normalization, two stationarity
  equalities, and two named 7-by-7 Hermitian PSD cones.

One test attempt initially found a Julia name-shadowing bug in the canonical
serializer; it was fixed and the complete suite was rerun successfully. Two
later test assertions were corrected to inspect MOI's concrete Hermitian cone
set rather than JuMP's modelling wrapper. No physics formula changed in those
test fixes.

## 6. Reliability assessment and current limitations

### Supported by direct evidence

- Pauli multiplication and hand examples are exact.
- The positivity and gap maps satisfy entrywise Hermitian adjoint identities
  on the tested Square basis.
- The variance product is kept distinct from operator multiplication.
- Basis/problem/stationarity/moment/coefficient inventories are deterministic
  and hash-bound.
- The JuMP adapter emits the intended two Hermitian PSD constraint types
  without loading a solver.

### Not established

- No full Square `L=1,d=2` assembly has yet been generated.
- No Square MOF artifact has yet been written or independently replayed.
- No solver has been invoked on the Square direct-primal model.
- No feasible or infeasible Square threshold has been found.
- No Farkas ray has been extracted or verified.
- The `one_symbol_lift/v1` positive basis is incomplete.
- The `bare_inner_pauli/v1` stationarity set is incomplete.
- No convergence claim follows from these structured subsets.
- No state symmetry is implemented; symmetry metadata is rejected rather than
  silently ignored.
- Sihan's TFIM/Kagome MOF/ray claims remain unverified until their files are
  visible.

Therefore the code is reliable enough for a bounded structural smoke run, but
not yet reliable enough for a public gap bound.

## 7. Next execution sequence

### Gate A — user ratifies the exact Square setup

Proposed first structural run:

```text
Hamiltonian:
  H(g) = 1/4 sum_J1 (XX+YY+ZZ)
       + g/4 sum_J2 (XX+YY+ZZ)
  J1=+1, g=J2/J1=1/2 (antiferromagnetic)

Patch:
  outer Lambda_1 = {-1,0,1}^2, 9 sites
  inner I_1 = {(0,0)}, 1 site
  no physical OBC/PBC interpretation; local consistency window only

Sector/symmetry:
  no conserved-sector projection
  unrestricted state; no state-symmetry constraints

Hierarchy:
  d=2
  positive basis = one_symbol_lift/v1, dimension 703, incomplete
  gap basis = one_symbol_lift/v1, dimension 7, complete at this finite degree
  stationarity = bare_inner_pauli/v1 through degree 2, incomplete

Thresholds:
  gamma=0 and gamma=1/4

Target:
  feasibility only; no Neel observable objective
```

`gamma=0` is a numerical/pipeline sanity point. `gamma=1/4` is only a first
positive threshold, not an anticipated physical answer.

### Gate B — exact assembly and cost report, no solve

After ratification:

1. generate both exact assembly manifests;
2. report moment counts, equality counts, cone dimensions, exact hashes,
   construction wall time, and peak memory;
3. write MOF plus machine-readable run metadata;
4. independently reload the MOF and verify all declared counts, names, cone
   dimensions, and hashes;
5. estimate solve memory/wall time and select SCNet resources before
   submission.

If exact assembly or MOF replay disagrees, stop. Do not invoke Mosek.

### Gate C — bounded SCNet smoke solve

Only after Gate B passes:

1. submit `gamma=0` first;
2. retain raw MOI termination, primal and dual statuses;
3. retain objective/status availability and solver log;
4. do not translate every non-optimal status into infeasibility;
5. submit `gamma=1/4` only if the zero-threshold model behaves coherently;
6. retain model/run metadata and artifact SHA-256 values.

### Gate D — certificate path

For an infeasibility candidate:

1. export the exact solved MOF and solver ray in the same variable order;
2. verify equality residual, cone-dual membership, objective improvement, and
   every cone block independently;
3. use scale-normalized tolerances stated in metadata;
4. label a passing floating-point result only as an independently replayed
   floating-point conic-ray witness;
5. reserve a strict/certified claim for a rational or interval-validated
   certificate.

## 8. Repository hygiene

The following pre-existing dirty paths were deliberately preserved and are
not part of this takeover implementation:

- modified `Ion.lock`;
- untracked `ADVISOR_PROJECT_DIRECTION_AND_WORKER_PLAN_2026-07-28.md`;
- untracked `ADVISOR_RECHECK_2026-07-28_COMMIT_5a2425a.md`.

Do not stage them accidentally with a broad `git add`.

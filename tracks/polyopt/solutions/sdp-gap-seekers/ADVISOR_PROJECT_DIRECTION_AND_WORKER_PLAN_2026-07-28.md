# Project direction and gated worker execution plan

Date: 2026-07-28  
Branch snapshot reviewed: `challenge/polyopt-sdp-gap` at `5a2425a`  
Review mode: static repository review plus the reported Feishu updates; no Julia,
solver, verifier, or test execution

## Executive decision

The project is **methodologically on a plausible track but strategically behind
the challenge deliverable**.

The team has built useful prerequisites:

- a sound description of the state-polynomial bulk-gap logic;
- validated Square J1-J2 geometry and Hamiltonian enumeration;
- a substantially repaired numerical certificate-audit path on a TFIM
  calibration problem;
- an independent MOF/ray audit and boundary scan reported by Sihan;
- a useful negative example in which the Kagome candidate was rejected rather
  than promoted from an ambiguous solver status.

However, the official challenge is not to improve the TFIM or reproduce the
existing Kagome example. The requested order is:

1. Square-lattice J1-J2;
2. Shastry-Sutherland;
3. triangular-lattice J1-J2.

The current branch still has:

- no explicit runnable Square state-polynomial basis;
- no Square SDP assembly;
- no Square solver result;
- no Square gap upper-bound candidate;
- no Square Néel-observable interval;
- no Shastry-Sutherland model or exact-dimer calibration;
- no triangular model.

Therefore the project should now **stop polishing the private TFIM `.jls`
pipeline and stop further Kagome scans**. Use the TFIM/Kagome work as calibration
and regression evidence, unify it with Sihan's MOF path, and move immediately to
the smallest honest Square J1-J2 implementation.

This is a pivot in emphasis, not a rejection of the work already done. The
certificate work was necessary to expose several dangerous false-positive
paths. Its value is now realized by applying the lessons to the requested new
geometry.

## Authoritative target

The official issue is:

- [QuantumBFS/quantum.harness issue #88](https://github.com/QuantumBFS/quantum.harness/issues/88)

It requests, for Square J1-J2:

- gap upper bounds `Γ_(L,d)(g)` for several accessible levels at
  `g = 0, 0.50, 0.535`;
- certified bounds on the squared Néel order parameter at `g = 0.50, 0.535`
  conditional on `γ = 0, 0.05, 0.10`;
- precise reporting of model, symmetries, level, matrix size, status, runtime,
  gap/observable result, and trends with level.

It then requests Shastry-Sutherland at `g = 0, 0.80`, including the exact
decoupled-dimer benchmark `Δ_bulk = 1` at `g=0`, followed by triangular J1-J2.

The paper and issue describe finite-level infeasibility as the mechanism that
excludes a proposed gap:

- [Xu et al., *The bulk spectral gap is semi-decidable*](https://arxiv.org/abs/2606.03836)

The local authoritative mathematical specification remains:

- `square-j1j2-gap-sdp-spec.md`.

## Where we actually are

| Layer | Current state | Assessment |
|---|---|---|
| Mathematical semantics | Feasible/infeasible/unknown direction is now understood; covariance term is documented | Good prerequisite |
| Square geometry and Hamiltonian | Exact J1/J2 bond enumeration and `1/4` spin normalization exist and have solver-free tests | Good prerequisite |
| Explicit basis | Current branch has counts and a deliberately incomplete `:one_symbol` sizing baseline, but no explicit solver-ready Square basis manifest | Blocking |
| Square assembly | `SquareGapCertify.jl` is a Hamiltonian/geometry scaffold only | Blocking |
| Square numerical result | None | Blocking |
| Observable objective | Not implemented for the requested Néel bounds | Blocking after first Square solve |
| Local certificate path | TFIM `.jls` artifact is bound to one vector and passes the declared audit; still floating point and `SLOW_PROGRESS` | Useful calibration, not headline |
| Sihan certificate path | Reported MOF/ray replay is promising and rejects Kagome; commits/artifacts are not locally visible and the TFIM metadata report conflicts with its dimensions | Promising but not mergeable yet |
| Strict rigor | No rational/interval post-processing | Open |
| Shastry-Sutherland | Not implemented | Later target and exact calibration |
| Triangular J1-J2 | Not implemented | Stretch target |

In rough project terms, the team has developed much of the **method and
validation shell**, but very little of the **new-geometry scientific output**.
It would be misleading to call the project nearly complete.

## Interpretation of the two streams of work

### What the local worker accomplished

The worker materially repaired the most serious certificate-verifier defects:

- affine, objective, and cone checks now use one ray vector;
- the full declared cone-block inventory is required;
- malformed sizes, indices, versions, and non-finite values are rejected;
- actual affine constants are exported;
- `OPTIMAL` plus an improving ray is treated as a contradiction;
- the declared fourteen corruption cases are present.

This means the local TFIM artifact is a credible **floating-point candidate for
the exported conic instance**. It does not prove that the exported conic instance
faithfully represents the intended physical hierarchy, and it is not an exact
certificate.

The remaining local verifier issues are no longer the critical path. They can
be fixed later in a bounded hardening patch, but should not consume the next
research cycle.

### What Sihan appears to have accomplished

Sihan reported:

- a denser TFIM boundary scan;
- an MOF model plus ray consumed by a separate verifier;
- excellent numerical TFIM residuals;
- rejection of the Kagome candidate under the same verifier.

That is directionally strong. In particular, rejecting Kagome is evidence that
the verifier is not simply relabelling all solver rays as valid.

The report is not yet adoptable because:

- the message labels the TFIM instance `N=7,g=1,d=3`, while its reported
  dimensions match `N=9,g=0.5,d=2`;
- referenced commits `b1a1cad`, `8c6106f`, `59f4b09`, and `c1ae6f7` are not in
  the current local refs;
- the MOF, ray, run metadata, formulas, and hashes are not locally inspectable.

The likely best long-term direction is to use a standard MOF conic model plus a
versioned ray/run-metadata bundle instead of creating a second private Julia
serialization ecosystem. That decision must be made after inspecting Sihan's
actual commits, not from the chat summary alone.

## Claim ladder

Every result must be assigned exactly one of these levels.

### Level 0 — status-only scan

Evidence:

- solver termination/primal/dual statuses;
- no independently replayed witness.

Allowed language:

> numerical status transition

Not allowed:

> certificate, certified upper bound, excluded gap

### Level 1 — independently replayed floating-point conic witness

Evidence:

- frozen conic model;
- one ray bound to affine rows, objective, and every cone block;
- independent numerical residual/PSD audit;
- complete hashes and run metadata.

Allowed language:

> numerically audited conic-ray candidate for the exported relaxation

or:

> floating-point upper-bound candidate

Not allowed:

> formal proof, exact certificate, unconditional certified physical bound

### Level 2 — formulation-bound numerical witness

Level 1 plus:

- exact model/geometry/Hamiltonian manifest;
- exact ordered basis/support manifest;
- hashes binding those manifests to the exported conic model;
- a regression or independent assembly check establishing that the conic model
  represents the intended hierarchy.

Allowed language:

> numerically audited upper-bound candidate for the stated finite relaxation

Still distinguish floating-point evidence from a formal proof.

### Level 3 — rigorous certificate

Level 2 plus:

- exact rational/interval post-processing, or another rigorous residual/cone
  correction argument;
- strict positive separation where required;
- no ambiguous solver status is used as the logical basis.

Allowed language:

> certified finite-level upper bound excluding `gap ≥ γ`

Only Level 3 should be presented without a numerical caveat.

## Strategic priorities

### Priority A — make Sihan's work inspectable and choose one evidence contract

This is a short coordination gate, not a new infrastructure project.

Required:

1. Sihan pushes a visible branch or PR containing the referenced commits.
2. The exact TFIM configuration is read from machine-generated run metadata.
3. The MOF, ray, run metadata, and verifier report are available with hashes.
4. The MOF verifier is checked against the local one-vector requirements.
5. The team chooses one forward artifact contract.

Preferred decision if Sihan's implementation passes review:

- MOF model as canonical conic-instance representation;
- versioned JSON or another stable documented format for ray/run metadata;
- local `.jls` retained as historical TFIM evidence only;
- no new `.jls` certificate features.

### Priority B — first runnable unsymmetrized Square relaxation

This is the actual implementation bottleneck.

The first version must be:

- explicit;
- deterministic;
- unsymmetrized at the state level;
- small enough to inspect;
- manifest-driven;
- connected to the same three-way result and evidence pipeline.

Do **not** reuse `model="kagome"` and call it Square symmetry. The reviewed
legacy Kagome reducer does not implement Square translations, C4 rotations, or
mirrors, and is not a demonstrated full SU(2) irrep quotient.

Symmetry may be added later one generator at a time, with an automorphism test
and an explicit statement that the result is symmetry-restricted.

### Priority C — obtain the first Square result before optimizing

For the first successful new-geometry run:

- use the smallest accessible Square patch and basis level;
- use `g=0.50` first as the headline challenge point;
- also run `g=0` and `g=0.535` after the identical assembly path works;
- report dimensions and all statuses even if no high-side certificate is found.

A modest or loose Square result is more valuable than another polished TFIM or
Kagome result because it demonstrates the requested extension.

### Priority D — add observables, then expand models

After the Square gap pipeline is stable:

1. add the squared Néel objective at `g=0.50,0.535` for the issue's conditional
   `γ` values;
2. add Shastry-Sutherland, using `g=0` as an exact dimer calibration and `g=0.80`
   as the scientific point;
3. attempt triangular J1-J2 only after at least one earlier target is complete.

## Worker execution contract

The worker must execute **one work packet at a time** and stop for advisor
review at the stated gate. Do not implement later packets speculatively.

General rules for every packet:

1. Record the starting branch and full commit SHA.
2. Check and report the worktree before editing.
3. Preserve `Ion.lock` and every pre-existing user/other-agent change.
4. Do not edit outside `tracks/polyopt/solutions/sdp-gap-seekers/` or the
   explicitly pinned external SpectralGap patch without prior approval.
5. Use small, purpose-specific commits.
6. Do not combine infrastructure, physics, and numerical-result changes in one
   commit.
7. Do not run the SDP stack locally. Solver runs belong on SCNet.
8. Do not use an unseeded or random rank/filter heuristic.
9. Do not copy manually typed model parameters into result summaries. Generate
   summaries from the committed run metadata.
10. Never collapse solver outcomes into a Boolean flag.
11. Unknown, timeout, numerical error, iteration limit, and ambiguous status
    remain `unknown`.
12. Never bisect across an unknown point.
13. Every substantive status/requirement update goes in a Markdown note.
14. At each stop gate, report:
    - files changed;
    - commits created;
    - commands run;
    - tests actually run and their exact counts;
    - tests not run;
    - unresolved questions;
    - claim level reached.

## Work packet 0 — Sihan integration inventory

**This is the next immediate packet. Do not start Square solver code before this
packet is reviewed.**

### Inputs

- Sihan's visible branch/PR containing the reported commits;
- MOF model;
- ray;
- run metadata;
- verifier;
- verifier output;
- boundary-scan output.

If those inputs are not visible, stop. Do not recreate or guess them.

### Tasks

1. Resolve each referenced commit:

   ```text
   b1a1cad
   8c6106f
   59f4b09
   c1ae6f7
   ```

   Record the full SHA, branch, author, subject, and changed files.

2. Determine the TFIM configuration from the machine-readable artifact:

   ```text
   N
   g
   d
   lso
   gamma
   Hamiltonian normalization
   imposed state symmetry
   ordered basis/block dimensions
   nvars
   nconstraints
   ```

3. Explain the `N=7,g=1,d=3` versus `N=9,g=0.5,d=2` chat inconsistency. The
   artifact/run metadata wins over prose.

4. Record SHA-256 for:

   ```text
   MOF
   ray
   run metadata
   verifier source
   verifier output
   solver/export source
   ordered basis/problem manifest, if present
   ```

5. Statically inspect whether the verifier binds one ray ordering to:

   ```text
   all affine columns and constants
   the objective
   every declared PSD cone block
   exact block count and dimensions
   MOF/model hash
   ray hash
   run-metadata hash
   ```

6. Document the exact formulas for:

   ```text
   ray normalization
   affine residual normalization
   objective margin normalization
   PSD violation/block scaling
   acceptance tolerances
   ```

7. Check how malformed schema is handled and whether there are negative tests
   for missing blocks, reordered coordinates, wrong hashes, wrong lengths,
   NaN/Inf, and incompatible metadata.

8. Compare the Sihan contract with the local `.jls` contract. Recommend one of:

   ```text
   ADOPT_MOF
   KEEP_LOCAL_TEMPORARILY
   BLOCKED_ON_DEFECT
   ```

### Output

Create:

```text
SIHAN_MOF_INTEGRATION_REVIEW_2026-07-28.md
```

Do not modify the ledger, delete `.jls`, or merge/cherry-pick the implementation
in this packet.

### Stop gate

Stop after the review note. The advisor decides whether the MOF path becomes the
canonical contract.

## Work packet 1 — canonical run bundle

Start only after Work packet 0 is approved.

### Required bundle

Every new run should produce one immutable directory such as:

```text
evidence/<model>/<run-id>/
  runmeta.json
  problem_manifest.json
  model.mof.json.gz
  ray.json.gz
  verifier_report.json
  stdout.log.gz
  SHA256SUMS
```

Exact filenames may follow Sihan's implementation, but the content requirements
may not be weakened.

### `runmeta` minimum fields

```text
schema_version
run_id
UTC timestamp
hostname / scheduler job id
repository full SHA and dirty status
external SpectralGap SHA / patch SHA
Julia, MOI, JuMP, MosekTools, and Mosek versions
model name and exact rational couplings
L/patch, d, lso, gamma
Hamiltonian normalization
explicit state symmetry generators, or "none"
basis-family name and manifest hash
nvars, nconstraints, and every cone-block dimension
termination, primal, dual, result_count
runtime and solver limits
artifact hashes
verifier command/version
tolerance formulas and values
```

### `problem_manifest` minimum fields

```text
ordered site coordinates and ids
inner/outer patch membership
ordered interactions with exact coefficients
ordered basis entries for every role/block
state-polynomial/reduction rules
stationarity-row generation rule
objective definition
all enabled symmetries
hashes for every ordered component
```

### Acceptance tests

- Two constructions of the same problem produce byte-identical manifests and
  hashes.
- Changing `g`, `gamma`, basis family, patch, or symmetry changes the problem
  hash.
- A summary generated from `runmeta` cannot report parameters inconsistent with
  the model/ray.
- Raw logs are captured automatically; no line is manually replaced.
- Hash verification is one command and failure is fatal.

### Stop gate

Return the schema, one migrated TFIM calibration bundle, negative-test output,
and a concise migration note. Do not start broad model scans.

## Work packet 2 — explicit Square unsymmetrized MVP

Start only after the artifact contract is settled.

### Design constraints

1. Use the reviewed Square geometry/Hamiltonian code as the physics source.
2. Begin with **no state symmetry**.
3. Use an explicit ordered basis, not just a dimension counter.
4. Name the first family, for example:

   ```text
   square_unsym_v1
   ```

5. Define its positive, gap, and stationarity roles separately.
6. State exactly which family inclusions make later versions nested.
7. Save every explicit ordered list and its hash.
8. Use exact rational coefficients until the solver-export boundary.
9. No random monomial filtering.
10. Do not copy 150 lines from a legacy model-specific certifier without first
    extracting or reusing a generic assembly function.
11. Do not label Kagome reduction rules as Square spatial symmetry.

### Required tests before a solver run

#### Physics/geometry

- exact site, J1-bond, J2-bond, and Pauli-term counts;
- unique ordered supports;
- coefficients `1/4` for J1 and `g/4` for J2;
- interaction-buffer containment;
- exact change in manifest hash when `g` changes.

#### Basis

- deterministic byte-identical ordered manifests across repeated construction;
- no duplicates after canonical reduction;
- degree/support limits;
- every gap-basis word lies in the declared inner support;
- declared nestedness from `v1` to any later family;
- all block dimensions equal the actual manifest lengths.

#### Assembly

- Hermitian/symmetric block construction;
- exact affine constants;
- one variable ordering shared by affine map, objective, and cone maps;
- all declared blocks present, including legitimate zero-dimensional blocks;
- no missing/extra rows under serialization;
- a forced timeout maps to `unknown`;
- `gamma=0` is never treated as infeasible merely because of a non-optimal
  solver termination;
- one tiny hand-checkable/toy instance agrees coefficient by coefficient with
  its independently constructed reference;
- where a legacy wrapper is claimed equivalent, compare the complete ordered
  affine/cone inventory, not only dimensions or objective values.

### First SCNet smoke job

Use the smallest Square patch and lowest honest basis level. Run only:

```text
g = 0.50
gamma = 0
```

The purpose is to validate assembly, export, solver status, and replay—not to
claim a bound.

Required output:

- canonical run bundle;
- exact dimensions;
- three-way status;
- verifier result;
- no manually written model metadata.

### Stop gate

Stop after one successfully exported and replayable `g=0.50, gamma=0` Square
instance. Return it for review before scanning gamma.

## Work packet 3 — first Square gap scan

Start only after the Square smoke bundle is approved.

### Scan protocol

For each configuration:

1. Establish a decisive feasible low point.
2. Probe a coarse monotone grid:

   ```text
   gamma = 0, 0.05, 0.10, 0.20, 0.40, 0.80, 1.60
   ```

   Stop expanding after a decisive and independently audited high-side
   infeasibility candidate is obtained. Extend the grid only if every point is
   decisively feasible.

3. Classify every point as exactly:

   ```text
   FEASIBLE
   INFEASIBLE_CANDIDATE
   UNKNOWN
   ```

4. Do not interpret an unknown as a high-side bound.
5. Do not bisect across unknown.
6. Only bisect an interval whose lower endpoint is decisively feasible and whose
   upper endpoint has an accepted audited witness.
7. Generate tables from `runmeta`, not handwritten labels.

### Model order

1. `g=0.50`;
2. `g=0.535`;
3. `g=0`.

Use the identical patch/basis/assembly contract so the comparison is meaningful.

### Level expansion

After the smallest level works:

- increase one knob at a time;
- preserve the exact smaller basis as a subset;
- report matrix sizes and runtime;
- do not claim monotone convergence unless the actual relaxations are nested;
- an apparent reversal is a blocker requiring diagnosis, not a point to omit.

### Required result table

```text
model
g
patch / L
d and named basis family
symmetry (none or exact generators)
gamma
nvars / nconstraints / block dimensions
termination / primal / dual / result_count
runtime
verifier label
claim level
artifact hashes
```

### Stop gate

Stop after the first honest Square bracket or after a complete grid showing why
no bracket exists. Either is useful scientific information.

## Work packet 4 — Square Néel observable bounds

Start after the Square assembly and status semantics are stable.

Implement the issue's squared Néel observable from exact site coordinates.

Required points:

```text
g = 0.50, 0.535
gamma = 0, 0.05, 0.10
```

Requirements:

- define the finite `W_R` explicitly;
- include every coefficient and normalization in the manifest;
- solve min and max separately;
- retain raw statuses and primal/dual residuals;
- distinguish an optimal numerical interval from a rigorous certified interval;
- compare multiple `R` or levels only when their definitions are nested and
  directly comparable.

Do not infer phase conclusions from one small relaxation. Report what the
conditional interval permits or excludes.

## Work packet 5 — Shastry-Sutherland calibration and target

Add this only after the generic 2D assembly path works for Square.

### `g=0` exact checks

- each site belongs to exactly one designated diagonal dimer;
- Hamiltonian normalization matches the issue;
- the exact product-of-singlets moment assignment satisfies the represented
  constraints;
- singlet projector expectation is exactly `1`;
- a validated finite-level exclusion at `gamma <= 1` is a formulation or
  numerical red flag, because the exact model has `Δ_bulk=1`;
- a small finite relaxation is not required to become infeasible immediately
  above `1`, so failure to obtain `Γ≈1` is not by itself a bug.

Then study `g=0.80` and the requested observables using the same evidence
contract.

## Work packet 6 — triangular J1-J2

This is a stretch packet. Do not start it while Square lacks a result or while
Shastry integration reveals unresolved generic-assembly defects.

## Explicit non-goals for the next cycle

Do not spend the next cycle on:

- Kagome `N=27`;
- additional Kagome `d=3` versus `d=4` scans;
- tighter TFIM bisection;
- more custom `.jls` features;
- Clarabel cross-solver runs on the large legacy instance;
- broad refactoring unrelated to the first Square solve;
- claiming finite corruption tests prove general verifier soundness;
- adding Square translations/C4/mirrors before the unsymmetrized path works;
- energy-floor polishing as a substitute for issue #88 gap/observable output.

The energy work can remain a useful appendix or fallback demonstration, but it
does not satisfy the spectral-gap challenge.

## Remaining local verifier hardening

These issues are real but deferred from the critical path:

- make the CLI print `SCHEMA_FAIL` without accessing absent artifact fields;
- enforce symmetric index maps, not only symmetric reconstructed values;
- add end-to-end malformed-file CLI tests;
- replace “sound” with “all declared corruption tests pass”;
- use a stable format and scale-aware normalization;
- remove unseeded `filter_mons`;
- repair stale legacy driver APIs and provenance.

Fix them when integrating the canonical MOF path, or in one bounded cleanup
commit after the first Square result. Do not reopen a long TFIM-only hardening
loop.

## Definition of project success

### Minimum credible submission

- runnable deterministic Square J1-J2 state-polynomial relaxation;
- explicit basis/problem manifest;
- at least one new-geometry Square run at a requested `g`;
- complete statuses, dimensions, runtime, and immutable evidence;
- honest statement of whether the result is status-only, numerically audited,
  formulation-bound, or rigorous.

### Strong submission

- Square results for `g=0,0.50,0.535` at more than one nested accessible level;
- independently replayed high-side witness for at least one requested point;
- conditional Néel intervals at one or more requested `gamma`;
- Shastry `g=0` exact calibration.

### Ideal submission

- rigorous post-processed Square certificate;
- full requested Square observable table;
- Shastry `g=0.80` results;
- triangular pilot result.

## Required worker reporting style

Every worker handoff must begin with:

```text
Starting SHA:
Ending SHA:
Pre-existing dirty files preserved:
Work packet:
Stop-gate result:
Claim level:
```

Then provide:

```text
Files changed
Why each file changed
Commands actually run
Exact test/run outcomes
Evidence paths and SHA-256
Known failures/unknown statuses
What was deliberately not done
Decision requested from advisor
```

Avoid phrases such as:

```text
fixed everything
sound
certified
converged
pipeline validated end-to-end
```

unless each term is tied to the precise acceptance gate in this plan.

## Immediate instruction to the worker

Execute **Work packet 0 only**.

If Sihan's branch/artifacts are not visible, report that exact blocker in
`SIHAN_MOF_INTEGRATION_REVIEW_2026-07-28.md` and stop. Do not compensate by
editing more TFIM verifier code or beginning a competing Square/MOF
implementation.

Once Work packet 0 is reviewed, the advisor will authorize either:

- adoption of Sihan's MOF evidence contract and Work packet 1; or
- a narrowly specified repair if the MOF implementation has a blocking defect.

## Bottom line

We are not lost, but we have reached the point where continuing in the same
direction would put the project off track.

The local verifier and Sihan's independent audit together provide enough
calibration confidence to move forward. They do **not** constitute the requested
scientific extension. The next meaningful milestone is not a cleaner TFIM log
or a tighter Kagome scan; it is one deterministic, exported, independently
replayable Square J1-J2 relaxation.

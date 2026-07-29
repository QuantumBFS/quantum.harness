# Work packet 0 — Sihan MOF integration review (COMPLETED)

Date: 2026-07-29
Work packet: 0 (Sihan integration inventory) — executed after the blocker
(Sihan's evidence branch became visible, Feishu msg 41 @ 22:28, head `088513c`)
Review mode: pure local static review (no SCNet, no advisor) of the fetched branch
Previous note: `SIHAN_MOF_INTEGRATION_REVIEW_2026-07-28.md` (BLOCKED — now superseded)

```
Starting SHA: edfec4d  (challenge/polyopt-sdp-gap)
Ending SHA:   (this note only)
Work packet: 0
Stop-gate result: packet-0 inventory COMPLETE; recommendation = ADOPT_MOF
Claim level: N/A (contract review; no new scientific claim)
```

## Bottom line

The blocker is resolved. Sihan's evidence is on a visible branch
(`flyingwagner/quantum.harness` `evidence/challenge88-certificate-hardening`,
head `088513c92`, fetched via `gh api …/tarball`). The MOF + ray-replay verifier
(`scripts/verify_gap_ray.jl`) and the exact-rational post-processor
(`scripts/postprocess_gap_ray.jl` + `src/GapRayPostprocess.jl`) were statically
audited against the advisor's one-ray-binding, scale-aware-normalization, and
malformed-handling requirements.

**Recommendation: ADOPT_MOF** (rationale in §7). The MOF contract is structurally
stronger and more rigorous than the local `.jls` contract; the local `.jls` should
be retired to historical TFIM calibration evidence, as the project-direction plan
already anticipated.

## Task 1 — commit resolution

All four originally-referenced commits are present on the branch ancestry
(previously 404 only because the branch was pushed after my earlier check):

| ref | full SHA | subject | role |
|---|---|---|---|
| b1a1cad | `b1a1cad6f` | gap-status: export solver certificate audit artifacts | solver/export source |
| 8c6106f | `8c6106f95` | gap-status: load MOI through declared JuMP dependency | independent verifier |
| 59f4b09 | `59f4b091c` | gap-status: allow source-gated gamma scans | dense boundary scan |
| c1ae6f7 | `c1ae6f717` | gap-status: adapt dynamically loaded MOI statuses | baseline |

Branch HEAD lineage (newest first): `088513c92` (Square MGK core) ← `729b3959e`
(MOF A-B runner) ← `eaa479ce1` (Kagome dedup) ← `d3b9c5dbd` (TFIM exact cert) ←
`fb314c3d6` (harden ray replay) ← `8c6106f95` ← `453b29f00` (independently verify
conic rays) ← `b1a1cad6f` ← `59f4b091c` ← `c1ae6f717` ← … All attributable to
`flyingwagner` (Sihan) above the `Xiansheng` baseline commits.

## Task 2–3 — TFIM configuration and the metadata inconsistency

The instance data files (MOF/ray/runmeta) are **not committed** in the branch
(the reproduce paths in `STRICT_CERTIFICATE.md` are external, e.g.
`/path/to/tfim-0.25125/audit.mof.json.gz`). Configuration is therefore read from
the fail-closed structural assertions in `STRICT_CERTIFICATE.md` + the verifier
code, cross-checked against Sihan's Feishu runmeta report (msg 41):

```
N = 9, g = 1/2, d = 2, lso = 6, γ = 201/800 (=0.25125)
open boundary, sign-symmetric
variables = 23,949 ; affine equalities = 2,705
PSD block side-dimensions = 211, 50, 11, 14   (4 blocks)
coefficient inventory (exact rationals):
  -4, -2, -1, -201/400, -1/2, -201/800, 201/800, 1/2, 201/400, 1, 2, 4
```

**The N=7,g=1,d=3 vs N=9,g=0.5,d=2 inconsistency is settled: it is N=9,g=0.5,d=2.**
The block inventory `[211,50,11,14]` matches the pinned `get_basis`/`get_bulkbasis`
formulas for N=9,d=2; N=7,d=3 would give `[194,108]/[66,26]`. The N=7/g=1/d=3 label
in Feishu msg 38 was a chat-summary typo, corrected by Sihan in msg 41 and confirmed
here by the committed fail-closed assertions. The artifact wins over prose.

## Task 4 — SHA-256 (reported by Sihan; not independently recomputed)

The data files are external, so these are recorded from Feishu msg 41, NOT
recomputed in this review. They are the bundle-level integrity contract; the
verifier additionally enforces structural model-identity (variable names +
dimension inventory + coefficient inventory), so a wrong-model substitution is
fail-closed even without the hash.

```
TFIM export MOF       81fd38ffb09e9e456337947f5553b8baaaaeea019ccb63067233d9169c829e2f
TFIM floating ray     1050a479df73816d9c92b0468e4a0c486b629e502a5d8e5e7dde01c80de8210
TFIM runmeta          99b9e6c361531eb3ae3a05e95490095e78398a36a949e027df852fb41dc2c341
TFIM exact-ray        b62381f394bd4226a9ab3db2714f91618269455f6df720787aceeb34246d9e92
verifier source       scripts/verify_gap_ray.jl  @ 088513c92 (branch HEAD)
postprocessor source  scripts/postprocess_gap_ray.jl + src/GapRayPostprocess.jl
```

Open: a future bundle should commit `SHA256SUMS` covering the data files so the
hashes are machine-checkable in-repo, not chat-only.

## Task 5 — one-ray binding (static read of `verify_gap_ray.jl`)

The verifier reads the MOF via MOI's own reader
(`MOI.FileFormats.Model` + `read_from_file`), sorts variables by MOI index, then
binds the ray to the model by **three independent checks** (verify_gap_ray.jl:94-99):

1. ordinal position is canonical (`parse(Int,fields[1]) == expected_ordinal`, else
   "non-canonical ray ordinal");
2. `variable.value == moi_indices[ordinal]` (MOI index matches, else
   "model/ray MOI index mismatch");
3. `VariableName == "C$ordinal"` (generic name matches, else
   "model/ray generic-name mismatch").

A reordered, truncated, or permuted ray fails one of these. All subsequent
evaluation uses one `Dict(variable => value)` map (`ray`, line 100), so:

- **all affine equalities** (`EqualTo`, `Zeros`) → residual from the one ray;
- **all PSD cone blocks** (`PositiveSemidefiniteConeTriangle`) → triangle matrix
  rebuilt from the ray (structural symmetry via `MOIU.inverse_trimap`), `eigmin`
  checked;
- **all scalar cones** (`GreaterThan`/`LessThan`/`Interval`/`Nonnegatives`/
  `Nonpositives`) → checked;
- **objective** → evaluated as the recession direction (linear part only,
  lines 48-57 — correctly ignores constants for a homogeneous ray);
- **unsupported constraint sets → error** (fail-closed, line 184-185).

Crucially, the cone inventory is **read from the MOF itself**
(`ListOfConstraintTypesPresent` + `ListOfConstraintIndices`). The verifier cannot
"omit" a declared block — the @491083f defect class (a separately-supplied block
list that can lie) is structurally impossible here. Binding is by variable
identity, which is stronger than a hash check (catches reordering, not just
corruption). Hash binding itself is external (bundle `SHA256SUMS`).

## Task 6 — normalization formulas and tolerances (confirmed exactly)

From verify_gap_ray.jl:102-207 — matches Sihan's reported contract verbatim:

```
scale                 = max_i |x_i|                         (line 102; rejects zero ray)
normalized_tolerance  = absolute_tolerance/scale + relative_tolerance   (104-105)
equality  (accept)    = (max|Ax|)/scale  <= normalized_tolerance         (202,205)
cone      (accept)    = max(max_scalar_viol, max(0,-λ_min))/scale <= n_tol   (200,203,206)
objective (accept)    = (improving_objective)/scale >  normalized_tolerance   (204,207)
defaults              = absolute_tolerance = relative_tolerance = 1e-12
verdict               = accepted_floating_point_ray  iff  all three pass
```

This is the scale-aware normalization the advisor asked for and that the local
`.jls` verifier lacks (the `.jls` verifier uses a single absolute `1e-6` on an
unnormalized ray). The test suite explicitly asserts scale-invariance (a valid
ray scaled by 1e16 keeps the verdict, line 153-156).

## Task 7 — malformed-schema handling and negative tests

**Malformed handling** (verify_gap_ray.jl) — all fail-closed via `error()`:
bad ray header (13-14), malformed row (19), non-canonical ordinal (20-21),
variable-count mismatch (91-92), non-finite ray values (93), MOI-index mismatch
(95-96), generic-name mismatch (97-98), PSD triangle dim mismatch (29-30),
unsupported constraint set (184-185), non Max/Min objective sense (191-192).

**Negative tests** (`test/gap_ray_verifier_tests.jl`) — thorough on
accept/reject semantics and rigor:
- equality-residual reject; PSD/cone-violation reject; wrong-objective-sign
  reject (Max and Min senses);
- **scale-invariance** (1e16 scaling preserves verdict);
- **Kagome-style near-miss**: a 1e-10 *relative* equality defect rejects even
  when PSD/objective look clean post-normalization — this is exactly the
  mechanism that rejected Kagome γ=1.272 (residual 6.62e-11 > 1e-12);
- bad-tolerance `ArgumentError`;
- **exact-rational rigor**: rational-ray normalization, single-pivot residual
  correction, exact-zero residuals, objective improvement, `rigorous_psd_proof`
  (accepts a proved block, rejects an indefinite block, handles exact-zero rows);
- duplicate-equality deduplication (vector-Zero coordinate removed) — the Kagome
  4,887-duplicate fix.

**Gaps vs the advisor's task-7 list** (minor): the malformed-input error paths
(reorder / count-mismatch / NaN-Inf) are handled in code but not unit-tested
explicitly; the verifier `error()`s rather than returning a structured
`SCHEMA_FAIL` verdict (functionally fail-closed, but not the "structured failure,
not throw" the advisor preferred). No explicit test for a wrong-hash / mismatched
runmeta (those are bundle-level, outside the verifier's scope).

## Task 8 — contract comparison and recommendation

| Aspect | Sihan MOF contract | Local `.jls` contract |
|---|---|---|
| Model format | standard MOI/MOF JSON (portable, language-agnostic) | Julia `Serialization` `.jls` (opaque, Julia-version-bound) |
| Ray binding | variable identity: ordinal + MOI index + name `C$n` (3-way) | index maps rebuilt from one `x` (1-way) |
| Cone inventory | read from the MOF itself — cannot omit | declared in artifact — schema-validated after @491083f |
| Normalization | scale-aware: `…/max|x|`, `abs_tol/scale+rel_tol`, 1e-12 | single absolute `1e-6`, unnormalized ray |
| Malformed handling | `error()` (fail-closed, throws) | structured `SCHEMA_FAIL` (no throw) |
| Negative tests | accept/reject + scale-invariance + Kagome near-miss + **exact-rational PSD proof** | 14 binding/schema corruptions |
| Exact rigor | **YES** — exact-rational ray + directed-interval PSD proof (`STRICT_CERTIFICATE.md`) | NO — floating-point only |
| Hash binding | external (bundle `SHA256SUMS`) | internal (embedded in artifact) |

**Recommendation: `ADOPT_MOF`.** The MOF contract is stronger on every axis that
matters for certification: portable format, a structurally-unomittable cone
inventory, scale-aware normalization, and — decisively — an exact-rational rigor
path that the `.jls` contract has no analogue for. The `.jls` contract's only
edges are stylistic (structured `SCHEMA_FAIL`, embedded hashes) and minor. This
matches the project-direction plan's preferred decision ("MOF model as canonical
conic-instance representation; local `.jls` retained as historical TFIM evidence
only; no new `.jls` certificate features").

**Caveats / open gates (stated for the record):**
1. Data files (MOF/ray/runmeta) are not committed in the branch; SHAs in §4 are
   Sihan-reported, not independently recomputed. A future bundle should ship an
   in-repo `SHA256SUMS` over the data. The verifier's structural model-identity
   gate (variable names + dim inventory + exact coefficient inventory) makes a
   wrong-model substitution fail-closed regardless.
2. The formulation→MOF mapping (does the exported MOF faithfully represent the
   intended TFIM state-polynomial hierarchy?) remains an open gate — explicitly
   acknowledged by Sihan (msg 41). This is the Priority-3 manifest question and
   is common to BOTH contracts; it does not affect the ADOPT_MOF decision.
3. Minor: verifier throws rather than returns a structured verdict on malformed
   input; malformed-input paths are not unit-tested explicitly. Both are
   bounded cleanup items, not blockers.

## Stop

Packet 0 complete. Per the project-direction plan, the advisor decides whether to
authorize the MOF contract (→ Work packet 1: canonical run bundle) or require a
narrow repair first. The three noted caveats are small enough that no repair
blocks adoption.

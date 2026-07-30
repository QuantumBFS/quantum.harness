# 00:15 SMALL-N FREEZE REPORT (immutable; filed unconditionally
# 2026-07-30 00:15 +08; method evidence only — the N=200 release/block
# decision is NOT in this document and will be filed separately as
# N200_RELEASE_BLOCK_SUPPLEMENT.md when the probe reaches terminal state)

## Selection (frozen before holdout; untouched since)

- S* = {B_bond_edge, B_half}; Score = +3.820e-9/site
- Runner-up {B_bond_half, B_half, B_pair_edge} (+3.907e-9); within ε_cmp
  → TIE-BREAK RULE (b) FIRED (lower gamma2_dim; declared blind at 17:19
  with ≤9/28 subsets complete) — the mechanical rule chose the smaller
  model over the nominally higher score.
- FROZEN_SELECTION.json SHA256 =
  e13ed241003eb65a0229ae610e2d4420ee076a811174c8d0a37bd6209b4d0783
- Enumeration: EXACT_ALL_SUBSETS_LE3, 28/28 joint rows (14 subsets × 2
  training N) + 2 base; wall median 344 s, max 476 s; training.csv full.
- Training landscape (honest): all subset scores at e-9 = inside the
  solver-noise band. Clean measurement: on the training sizes, no bundle
  in the declared pool produces resolvable constraint power — exactly
  the pre-named training-domain limitation (sep-25/100 objects have no
  room at N=10/12), and exactly why the pre-registration designates the
  N=200 pair as the real experiment.

## Gate table as of 00:15

| gate | status | key numbers |
|---|---|---|
| G0/G1/G1b/G1c | PASS | identity |Δ|=0; neutrality |Δ|=0; rows=r(N)+Σcl exact |
| G2 (a/b/c) | PASS | oracle 2.78e-10; compat 1.14e-16; sandwich holds, ε=6.7e-8 |
| G3 | PASS | orderings 28/28 ok; nesting ok; freeze done |
| G4 arms (split-proc) | PASS (numbers) | base −0.44740635087 (23.3 s) · sel −0.44740635091 (12.0 s) · rg −0.44740634776 (381.4 s) · joint −0.44740634533 (368.0 s) |
| G4 classification | unresolved-null (pre-registered) | Δ_joint = +5.5e-9 vs ε_cmp ~1.5e-7; orderings within ε; ≤ E_ED ✓ |
| G4 α_time anchor | RECORDED | max solve/build multiplier from joint arm ≈ 15 (368 s wall, build ~23 s) |
| G4b space-equivalence | PASS | V_pool ≡ V_{S*} at N=14: |dE|=0.00e+00, signatures equal |
| vcheck V1 | PASS | Γ eigmin +0.353; ω herm ≤2.1e-17; links 1.7e-15/768 rows |
| vcheck V2 | PASS | 28 blocks eigmin ≥ −3.9e-10; 1174 equalities ≤ 4.2e-7; N=10 winner also PASS |
| vcheck V3 (strengthened) | INCOMPLETE_AT_FREEZE | run in progress at filing; last durable artifact: /tmp/vcheck_final.log (V1 section complete); no verdict recorded |
| vcheck V4a (link-sign mutation) | INCOMPLETE_AT_FREEZE | same run; prior (pre-strengthening) V4a evidence exists but is not carried as a verdict |
| probe memory/time gates | PENDING PROBE | see status below |

## Probe & pair status AS OF 00:15 (status only, no ruling)

- n200probe (23009659, 128c): PD, AssocGrpCpuLimit.
- n200probe64 (23013383, 64c fallback): RUNNING 28 min on a01r02n07.
- n200pair (23009660): HELD (JobHeldUser), snapshot cebb8da, untouched.
- e49p0v2 (22994754): RUNNING 10h11 (passive harvest lane).

## Scientific rationale (arbiter ruling 5, verbatim)

The frozen selected bundles are scale-covariant. At N=200 they probe
separations 25 and 100 beyond the r=24 base, so the target-scale pair
tests directed long-range tightening in a regime not represented by the
small-N gain landscape. This is consistent with, but does not identify
or replace, the independent reach effect measured in Route A.

## Claim sentence (in force)

Single implementation, gate-chain validated on tested small-N paths;
the N=200-only newwords path remains unexercised (V3 strengthening in
flight at freeze).

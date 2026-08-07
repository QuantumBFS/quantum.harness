# PLAN_OF_RECORD — joint method (ACTIVE instructions only; history in
# PLAN_HISTORY.md, ARCHIVE ONLY). T0 = 2026-07-29 ~18:10 (+08).

Two-level functional-RG specialization × fixed-cardinality moment-bundle
selection, ONE code path: N∈{10,12} training → N=14 strict holdout →
ONE N=200 pair. Do not disturb: stock lane, Route-A cells, DMRG, 2D,
agent-2/fline. LAW.md governs terminology/ε_cmp/sign rules.

## Frozen configuration
BASE_CONFIG.json (hash 483a3f713d24a267…): rdm=8, pso=0, lso=true, d=4,
ρ_deploy=0.24 ⇒ r(N)=max(2, round(0.12N)): r=2 at N∈{10,12,14}, r=24 at
N=200; extra=r−1. Same covariant config at every N.

## Candidate pool (canonical common non-mandatory over N={10,12,14,200};
pool + hash immutable after G0; no pullback bundles this run)
  B_pair_edge : σᵃᵢ σᵃᵢ₊ₛ,  s = r(N)+1
  B_half      : σᵃᵢ σᵃᵢ₊⌊N/2⌋
  B_bond_edge : bᵢ bᵢ₊ₛ,   s = r(N)+1,   bᵢ = Σₐ σᵃᵢσᵃᵢ₊₁
  B_bond_half : bᵢ bᵢ₊⌊N/2⌋
M=4 (not forced). Collapse/duplicate checks against ALL mandatory
families (1-, 2-body sep≤r, 3-body three_type, 4-body a2) are
CODE-ASSERTED at pool build and printed to results/gates.json.
Closure per bundle: translation, reflection, Hermitian conjugation,
spin-component orbit, Pauli quotient; Γ blocks are built over the
PRODUCT-SPAN closure of §V_pool, never raw words; closed-variable
counts asserted at G3.

## Coefficient spaces
V_pool(N) (small N only) = span{u†v : u,v ∈ mandatory ∪ ⋃ all bundle
closures}/ideal, built ONCE after pool freeze; all four arms at
N∈{10,12,14} share it. After S* freezes: V_{S*}(200) = span over
mandatory ∪ S*-closures only; BOTH N=200 arms run on V_{S*}(200).

## Model and arms (four-arm contract, explicit)
L(N,S) = min c'y s.t. y ∈ F_base(N) [on the arm's coefficient space];
optional blocks:
  [SEL]  Γ_{2,S}(Q₂y) ⪰ 0        (level-2 selected moment blocks)
  [RG]   Γ₃(x³) ⪰ 0 with x³ compressed level-3 variables, and the
         link  B₂ Q₂ y = T₃ x³
Arms: Base = neither; Selection-only = [SEL] only (no x³, no link);
RG-only = [RG] only (no selected level-2 blocks); Joint = both.
Orderings (violation beyond ε_cmp = bug, STOP): L_base ≤ L_RG ≤
L_joint; L_base ≤ L_sel ≤ L_joint; L_joint ≤ E0 (ED, N≤14).
Report Δ_RG, Δ_sel, Δ_joint, Δ_int = L_joint−L_RG−L_sel+L_base (no
prescribed sign), g = E_Bethe − L_joint.

## Selection
SELECTION_PROTOCOL.json committed before any search. Training N={10,12};
Score(S) = ½ Σ_N [L_joint(N,S) − L_base(N)]/N (per-site improvement).
Search = EXACT enumeration of all |S| ≤ 3 subsets (M=4 → 14 evals per
training N); PT is OUT of the critical path. S* → FROZEN_SELECTION.json
IMMEDIATELY after training, before any N=14 run; holdout never retunes;
selected_bundles.json = identical S* + appended holdout metadata.

## Maps
Lossless oracle: explicit invertible relabeling; L_RG,lossless =
L_uncompressed-level-3 within 1e-8. Physical: the validated D=4
parity-resolved VUMPS map (vumps_A_D4.json) UNMODIFIED; re-verify gauge
residual, parity-flow identity, map hash, energy sanity, compatibility
‖B₂C₁T₃ − T₃′C₂‖max ≤ 1e-12. fline cross-check: non-gating, only if
fline artifacts appear (PORT_CONTRACT.md then records same-maps proofs).

## Gates (each reported: name/PASS-FAIL/commit/values/residuals/files/
blocking issue/next — nothing else)
G0 (T0+45m): this file, BASE_CONFIG, THEOREM_CONTRACT_RG_SELECTION.md,
  SELECTION_PROTOCOL.json, bundle definitions+dimension formulas,
  production complexity statement. Pool hash frozen.
G1 (T0+2h, blocking): new builder, RG off + selection off, on the STOCK
  coefficient space: N=10 objective ≤1e-8 vs existing adapter; N=14
  structural signatures equal (coeff-basis hash, Gram signature,
  PSD-cone signature, row count, objective hash). First row = family
  birth (22:00 law extended by arbiter — logged).
G1b NEUTRALITY (blocks N=200): on V_pool with S=∅, optimum equals the
  stock adapter within 1e-8.
G1c ORBIT COMPLEXITY (blocks N=200): builder counters prove canonical-
  representative orbit handling; materialized objects scale with rep
  count, never ×N; code-generated assertion.
G2 (T0+3.5h, self-contained): lossless oracle equality; compatibility
  ≤1e-12; D=4 sandwich L_base ≤ L_RG,D4 ≤ L_level3 ≤ E_ED.
G3 (T0+5h): enumeration at N=10,12; orderings + S⊆S′ monotonicity
  within ε_cmp; closed-variable assertions; FREEZE S*.
G4 (T0+6h): four arms at N=14 with frozen S*; L_joint ≥
  max{L_RG,L_sel}−ε_cmp and ≤ E_ED+ε_cmp; classify resolved-positive/
  unresolved/null/invalid. NULL → arbiter rules at 00:15 (selection-only
  baseline value stands regardless).

## N=200 (after G4, commit-frozen worktree)
Build-only probe on V_{S*}(200): block sizes, scalars, affine rows,
nnz, build time/RSS. Memory gate: projected solve = build RSS × the
N=14-measured solve/build multiplier; if unavailable, build RSS < 40%
of node memory. Slurm prefix = N=14 frozen-basis self-test at the same
commit (failure exits). Then exactly ONE pair in ONE allocation, same
builder, same space: L_base(200) + L_joint(200,S*). Report Δ_joint(200),
g₂₀₀. All four outcomes reportable. No second subset. No re-runs.

## Clocks (arbiter-held)
22:00 status line · 00:15 G3+G4 freeze report (+null ruling if needed)
· 01:00 probe done + pair submitted (ONE ≤90-min extension iff all
green, else kill switch: freeze small-N study as the method chapter) ·
Thu 09:00 no new method features · Thu PM report only.

## Language
Permitted: "numerical SDP lower bound", "two-level functional-RG
specialization", "fixed-cardinality moment-bundle selection",
"target-scale evaluation". Banned: "first implementation", "full
implementation of Sec. III-D-2", "first numerical study" (struck — no
literature audit), "certified", "scalable" without measured scaling,
"globally optimal basis" beyond the declared pool, any success claim
before the row exists.

## Provenance
Every formal row: commit, git_diff_empty(-uno), script SHA, Manifest
SHA, QMBCertify commit, Julia/MOSEK versions, base config hash, bundle
IDs+pool hash, RG-map hash, solver status+residuals, build/solve times,
peak RSS, result SHA. Commit after every green gate.

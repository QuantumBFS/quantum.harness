# PLAN — active directives (Wed 2026-07-29 afternoon)

Arbiter: 张彦白 (user). Builder: agent. External audits: Codex (structure),
GPT (plan). Frozen rules live in LAW.md; superseded scheduling in HISTORY.md.

## Route A — reach-hypothesis test (ACTIVE, stock lane only)

H_reach: the N=100 deficit (gap 2.364e-5 vs the paper's 8.3e-6) is basis
undercoverage — CONFIG A pins two-body reach r=extra+1=5; the paper's local
basis reaches r≈⌈N/2⌉. v100e8hi2 / v200e8 rows reinterpret as r=9 points.

- **Step 0 (local; PASS = (i) E(e6) tighter than E(e4) beyond ε_cmp AND
  (ii) m strictly increases 4→6).** Historical −0.4473967065 is DIAGNOSTIC
  only (arbiter amendment ~12:50; unverified provenance). 0b ceiling probe
  extra=13 at N=14: record wrap/cap semantics (silent saturation expected
  from source: smod ring wrap + reduce! collapse).
- **Step 1 (SCNet screen):** N=100, J2=0, rdm=8, d=4, pso=3, lso=true,
  extra ∈ {4,14,24,34,49}; sizes: e∈{4,14} 32c/110-cap, e∈{24,34,49}
  64c/230-cap; a breach IS a datum. Degrade by dropping extra=34 first.
  Quota probe before submission. Deliverable: Δ_r(r)=E_{8,r}−E_{8,5},
  m(r), RSS(r).
- **Step 2 (mechanical):** r* = min r with Δ_r(r) ≥ 0.9·Δ_r(50). Δ_r(50)
  not resolved-positive → H_reach REJECTED at rdm=8, stop, report, WAIT.
  Price confirm cell: 113 GB × (m_{10,r*}/m_{10,5})²; construction-only run
  if m_{10,r*} unknown; > 245G → price report, WAIT for GO.
- **Step 3 (ONE confirm cell, post-arbiter):** N=100 rdm=10 extra=r*−1.
  Readout gap vs 8.3e-6. Consistency-only language (LAW.md).
- **Stop lines:** no N=200 large-reach without GO; no Route B; reach-curve
  tables under Thursday freeze rules.
- **Report points:** (i) Step 0 one-liners; (ii) Step-2 table + r* + price;
  then WAIT.

## Track 2 — M2 in progress (gates were green before the 13:00 deadline)

- D=2 verdict recorded: ΔCG8 = +3.7/6.7/7.0e-9 (n=6/9/13) vs ε_cmp ≈
  1.4-2.6e-7 → unresolved; monotone PASS; n*≤6 saturated; Δreplace −1.41e-5.
- D=4 arms running on SCNet (m2d4). Verdict on landing:
  resolved-positive → §T tiers apply tonight; unresolved/null → F0
  (hybrid scale OFF; F0 becomes the method narrative, reported as measured).
- F0 triggers (any): ΔCG null · deadline missed · contract cannot close.

## §T tonight tiers (only if ΔCG8 resolved-positive)

| tier | content | condition |
|---|---|---|
| must-run | N=20/40 rdm=8 pairs | ΔCG8 resolved-positive |
| big point | ONE large pair (100/200 by Target-1 state) | rungs green |
| expensive | ONE rdm=10+CG | clear target value |
| hatch | +1 big pair / 2nd expensive | measured cost allows AND both target plays live |

## In-flight (touch nothing)

v200hi (N=200 frontier test @460), v140hi2, v100e8hi2 (r=9 lever), v120hi,
v160hi, 2D L=8 probe, m2d4. Remark 6.1 control: verdict recorded
(infeasible ≤230G, inconclusive) — no fat-node retry while verdict cells run.

## DMRG (today) & Thursday

DMRG probe order J2 = 0.5 → 0.2 → 1.0; 0.4/0.6/0.8 released one by one on
measured cost. Thursday: no new experiment families; red-cell reruns →
freeze → all tables from CSV → claim audit per LAW.md → push before 20:00.
Audit package for Codex: run inventory, gate results, provenance proofs,
claim-tier draft (first-review §11 format; user re-pastes spec if exact
format required). Codex replies GO/NO-GO + BLOCKING FIXES + CLAIM
RESTRICTIONS only.

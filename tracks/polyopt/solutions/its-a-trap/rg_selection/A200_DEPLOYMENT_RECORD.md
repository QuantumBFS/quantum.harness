# A200 DEPLOYMENT RECORD (Amendment 4 + 4A + 4B + 4C)

Builder log of record for the N=200 adaptive-only deployment. All times CST
(UTC+8), 2026-07-30. Claim boundary: deployment/resource/lower-bound
statements only; no fixed-budget superiority claim (P200 intentionally not
run).

## Old-job states at execution start (4B.6 / 4C §4 — recorded, NOT cancelled)

| time | job | name | state | elapsed | node |
|---|---|---|---|---|---|
| 10:05 | 23009659 | n200probe (128c) | RUNNING | 4:23:09 | a01r03n03 |
| 10:05 | 23009660 | n200pair | RUNNING | 1:30:48 | a01r04n03 |

## Fresh-selection timer (4B.3 + 4C §3)

- Protocol: immutable pool {B_bond_edge, B_bond_half, B_half, B_pair_edge},
  N=10 on the replacement chassis (d=4, rdm=false, pso=0, lso=false), all
  subsets |S| ≤ 2 in deterministic lexical order (BASELINE + 4 singletons +
  6 pairs), score [L(Core+RG+S) − L(Core+RG)] (per-site E from the builder).
- 10:07 attempt 1: all 11 arms died at load — `ulimit -v` (virtual-address
  cap) is incompatible with Julia's address-space reservation. 14 s.
  Evidence: results/fresh_selection_attempt1_ulimit_failure.txt
- 10:11 attempt 2: cgroup cap adopted (systemd-run MemoryMax=18G, the correct
  RSS-scope implementation of the 18 GiB law); all arms died at load —
  missing JULIA_PROJECT (env: ~/code/qh-method/julia-env). 15 s.
  Evidence: results/fresh_selection_attempt2_noproject_failure.txt
- 10:16:43 attempt 3 launched (JULIA_PROJECT fixed, cgroup cap active).
- Strict cumulative expiry (30 min TOTAL incl. diagnosis, from ~10:07): 10:37.
- OBSERVATION 10:21: BASELINE arm RSS 16.9 G under the 18 G cap — the
  rdm=false + lso=false chassis admits far more genuinely-new seam words at
  N=10 than the training chassis; arms are an order heavier than projected.
- OUTCOME 10:23:28 — STOPPED by arbiter checkpoint mechanical ruling:
  completion mathematically impossible in-window (10/11 arms unstarted,
  single arm > 6 min at ~17 G RSS). No row accepted; per 4C §3 NO choice
  from partial enumeration. FROZEN: {B_bond_edge, B_half} =
  **A200_FIXED_BUNDLE_PILOT** (frozen chain-selection S*, never described
  as newly optimized on the rdm=false chassis). No further selection
  diagnosis.

## Release gates (R1 + R2 + R3 + R4 + R4b + R4c)

Ran staged, one heavy solve per process (first single-process attempt was
OOM-killed at the 18 G scope during R4b, 10:27 — journalctl evidence; staged
rerun from 10:31). From results/a200_release_gates.csv:

- R1 PASS 10:31–10:35 — Core(rdm=false,lso=false) N=10 E=−0.451549606105 ≤
  E0/N=−0.451544635449, pfeas 5.6e-09 dfeas 7.7e-09.
- R2 PASS — V1 ED substitution (Γ + all ω blocks + 768 link rows, worst
  residual 5.6e-16).
- R3 PASS — link-sign mutation on the rdm=false chassis went red
  (mutated E=+0.0102 ≫ E0/N).
- R4b PASS 10:46 — auto = pool = −0.451549597105, |dE| = 0.0 ≤ ε_cmp=5.0e-07,
  block-level semantic hashes equal, counts auto ≤ pool (scal 19431=19431),
  Γ(y_ED) eigmin +3.5e-01. Note seam_newwords = 0 at N=10 (ring-wrap windows
  cover all product classes at this size — consistent with the V3 N=10
  observation of record).
- R4c — STARTED 10:47 (exact `run_n200.jl --mode a200 --manifest
  A200_CONFIG_N10test.json`), KILLED 10:50 mid-run by the arbiter override.
  NOT completed. R4 (snapshot) never made.

## OUTCOME — A200 CANCELLED (arbiter override, ~10:49)

Arbiter override of record: "A200 is CANCELLED. No snapshot, no ship, no
HELD submit, no handoff." All A200 processes killed 10:50:17. No A200 job
was ever submitted to SCNet. Jobs 23009659 (n200probe) and 23009660
(n200pair) were left in their prior RUNNING states (no cancellation was
ordered). The read-only diagnostic extract (9 build-only rows, sections
1–5) was delivered to the arbiter 10:56–11:00; its raw numbers are the
findings of record for the selection-arm memory observation. Fresh
replacement-chassis selection ended with NO accepted row; the pilot label
{B_bond_edge, B_half} = A200_FIXED_BUNDLE_PILOT remains the frozen wording
for any retrospective description of the cancelled deployment.

## Post-cancellation passive harvest (revision data)

- 11:42 job 23009659 (128c V_{S*}(200) construction probe) ended TIMEOUT at
  its 6 h sbatch template limit (requested wall in template, not a partition
  cap — 23009660 holds 1-00:00:00). sacct: State TIMEOUT, Elapsed 06:00:03,
  MaxRSS 174040728K (~166 GiB). n200_probe.json absent; state file stage
  stopped at spec-built → the whole 6 h was inside build_rg_selection_model.
  Frontier pair of record: 64c TIMEOUT 6 h @ 182 GB; 128c TIMEOUT 6 h @
  174 GB, both pre-solve.
- 23009660 (base/joint pair, 24 h wall) at 11:45: RUNNING 3 h 19 m, stage
  arm:base since 08:36.

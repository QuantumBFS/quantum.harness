# HISTORY — superseded scheduling sections (audit chain; moved intact from
# the plan file on Wed 2026-07-29 ~13:20 per arbiter's three-document split)

# ROUTE A DIRECTIVE — reach-hypothesis test (user-authored Wed ~12:30,
# ACTIVE; TARGETS lane, stock code path only)

H_reach: the 2.364e-5-vs-8.3e-6 deficit at N=100 is basis undercoverage —
CONFIG A pins r=extra+1=5 while the paper's local basis reaches r≈⌈N/2⌉.
v100e8hi2 / v200e8 rows are reinterpreted as r=9 reach-curve points.

## Reality deltas (verified read-only before adoption)

1. [AMENDED by arbiter Wed ~12:50] The historical −0.4473967065 is
   DIAGNOSTIC only (unverified provenance). Step 0 PASS =
   (i) E(extra=6) tighter than E(extra=4) beyond ε_cmp AND
   (ii) m strictly increases 4→6. Which-knobs-reproduce-it is reported as a
   provenance note on the Tuesday scan, never as a gate. 0b unchanged.
2. `extra` semantics read from source (basic_function.jl chain branch):
   2-site words at separations s+1, s=0..extra, smod ring wrap → beyond
   ⌈N/2⌉ wrapped pairs collapse under reduce! → SILENT saturation expected;
   Step 0b measures it (m flat 6→13 at N=14 = confirmation).
3. m is printed per cell as "SDP size: n, m" in cell logs → Step 0c/1 m
   extraction is a log grep; m recorded per row in the reach table.
4. Memory sizing for the screen (pso=3+lso=true at rdm=8, N=100 — never run
   before): extra∈{4,14} at 32c/~122G (MAX_RSS 110); extra∈{24,34,49} at
   64c/~245G (MAX_RSS 230). A breach IS a datum (RSS(r) curve); degradation
   order drops extra=34 first (directive).
5. Quota: assoc has no explicit TRES caps; AssocGrpJobsLimit throttles
   concurrent jobs (~7) — screen cells queue behind running verdict cells;
   probe re-run before submission (directive).

## Execution (stock lane: MAIN checkout, pinned commit, wrapper-only;
`extra=` is an existing GSB kwarg already plumbed through parsecell)

- **Step 0 (local, ~10 min, ALL green before any screen cell):**
  0a fingerprint N=14 rdm=8 extra=6; 0b ceiling N=14 rdm=8 extra=13 —
  record no-op/error/equal-to-r=7; 0c m strictly increasing extra 4→6
  (from logs); flat → STOP + report + await arbiter.
- **Step 1 (SCNet screen):** N=100, J2=0, rdm=8, d=4, pso=3, lso=true,
  extra ∈ {4, 14, 24, 34, 49}; per-cell outdirs (CSV row + cell log = the
  per-task record); deliverable Δ_r(r)=E_{8,r}−E_{8,5}, m(r), RSS(r).
- **Step 2 (mechanical gate):** r* = min r with Δ_r(r) ≥ 0.9·Δ_r(50);
  Δ_r(50) not resolved-positive under ε_cmp → H_reach REJECTED at rdm=8,
  stop, report, wait. Price the confirm cell from measured m(r):
  113 GB × (m_{10,r*}/m_{10,5})²; if m_{10,r*} unknown, construction-only
  run to get it; projection > standard big node (245G) → price report and
  WAIT for arbiter GO.
- **Step 3 (ONE confirm cell, after arbiter sees the Step-2 report):**
  N=100, rdm=10, extra=r*−1, CONFIG A knobs; readout gap vs 8.3e-6;
  pre-written consistency-only language (never "identified the config").
- **Step 4 stop lines:** no N=200 large-reach cell without arbiter GO;
  no Route B work; reach-curve table family under Thursday freeze rules.
- **Report points:** (i) after Step 0 — fingerprint + ceiling, one line
  each; (ii) after Step 2 — Δ_r/m/RSS table + r* + confirm price. Then WAIT.
- Running jobs untouched (v200hi, v140hi2, v100e8hi2, v120/160hi, 2D L8,
  m2d4 all proceed in parallel).

---

# FINAL NIGHT PLAN (v3, user-authored 2026-07-28 ~23:20 — supersedes the
# scheduling sections below; science content, gates, sign rules, claim
# ladder and terminology sections below remain in force)

The user's final plan is adopted verbatim, with the reality deltas in §R
(verified read-only before adoption). The "10-条 markdown 指令块" = the ten
blocking corrections already adopted throughout this file; amendments (A)–(F)
are folded in below. Arbiter: the user. Builder: this agent. Audits: Codex
(structure), GPT (plan) — external, user-operated.

## §R Reality deltas (verified 23:20)

1. **Incident pre-check: CLEAN.** Queue v3's inputs (`targets_queue3.sh`,
   `overnight_harness.jl`) last modified 22:33:53 / 20:41 (committed e286276
   20:43), both before the 22:34:05 launch; `git status` empty on both. No
   provenance annotation needed. Recorded in run LOG.
2. **Nothing submitted to SCNet yet** (bootstrap still precompiling) — the
   staging becomes first-submission-clean: `sbatch --hold` the whole array,
   then immediately `scontrol release` the small/trusted tasks; the big ones
   (v120, v140, v160, v200, v100e8, v200e8) stay held for the morning
   reconciliation. No scancel/re-submit ever needed.
3. **v14 fingerprint cell was missing** from cells.txt — added (cell 23,
   released immediately): CONFIG A N=14 on a COMPUTE node; morning trust
   chain = v14 → 7-digit match vs local row & Table 3, then v100 vs 8.3e-6.
4. **j2v3_1.0 landed** (exit 0, 39 min, 19G budget) — the local N=40 J2 lane
   is viable; SCNet j40_* cells become cross-machine validation rows.
5. **Worktree caveat:** julia-env/Manifest.toml pins QMBCertify by RELATIVE
   path `../.external/QMBCertify`, and `.external/` is untracked — the method
   worktree gets a symlink `.external -> <main>/.external` (dev clone is
   read-only by standing rule, so sharing is safe).
6. **"Stock lane freeze" precise meaning:** queue v3's input files in the
   main checkout are untouched until v3 finishes. ALL new code (M0-C runner,
   tower harness passthrough, 2D cellspec support, m2_arms.jl) happens in
   worktree-method on a pinned commit; every NEW cell (local M0-C tail, SCNet
   2D chain) launches from that pinned commit via absolute path and its row
   records git_commit / git_diff_empty / script_sha256 / manifest_sha256 /
   qmbcertify_commit (several already in the CSV schema; git_diff_empty is
   the addition).
7. **2D chain runs from a second remote dir** (`~/qh-method`, rsynced from
   the method worktree) so the stock `~/quantum.harness` tree's provenance
   stays single-commit. Chain: L=4 canary (encoding/normalization; the
   square-lattice recon is read from source BEFORE the canary is written —
   Phase-3 blocking recon stands) → afterok → L=6 (held) → fit-check job
   (reads L6 JSON: config/status/RSS/walltime; exit code is the verdict) →
   afterok → L=8. L=10 only if two-point margins are clear. 2D J1-J2 cells,
   if ever reached, carry lso=0 pso=0 (Remark 6.1).
8. **MOSEK concurrency, technical half:** the licence FEATUREs are
   `uncounted` (PTS/PTON, HOSTID=DEMO, TS_OK) — no technical limit on
   concurrent solves. The CONTRACTUAL confirmation remains the user's item
   (flagged, non-blocking tonight).
9. **Quota/billing probe** runs tonight via the profile's `quota_command`
   (sacctmgr assoc) before any big-cell release; note DefMemPerCPU=3800M —
   a 120G cell may be billed as ~32 cores; morning release is conditioned
   on the measured balance.

## §N Tonight (delta on the original queue; order matters)

1. Worktree surgery FIRST (before any further edit): create worktree-method
   pinned at HEAD (9c229f9+), symlink .external, verify
   `julia --project=julia-env -e 'using QMBCertify'` resolves inside it.
2. SCNet: on BOOTSTRAP OK → `sbatch --hold --export=ALL,RUN_NAME=scnet-<ts>`
   (23 cells incl. v14) → release everything except {v120, v140, v160, v200,
   v100e8, v200e8} → post `squeue` detail to the user → arm overnight
   monitor (first-cell early-output check for compute-node env failures;
   fix in place if any).
3. Quota probe + record; licence concurrency note to LOG.
4. 2D recon (source read, method worktree) → write 2D chain scripts →
   submit chain to `~/qh-method` with L=4 canary released, L=6/L=8 held+
   dependent. If recon surfaces an unresolvable knob ambiguity, the chain
   waits for morning — do NOT guess knobs.
5. Local serial tail (strictly after queue v3 finishes): M0-C 4 cells from
   the method worktree pinned commit (CONFIG A N=10/14 ~34 min each, rdm=8
   N=10/14 fast) with the new provenance columns; then M1 gates re-run for
   row provenance. No Julia compute concurrent with v3 — writing/coding only.
6. Then sleep. No new list items may be invented tonight.

## §W Wednesday morning (sequence = dependency)

Bethe battery (already green; re-verify checksums only) → SCNet trust chain
(v14 fingerprint 7-digit; v100 vs 8.3e-6) → quota check → release held big
cells → M0-C structural signature table + objective double-validation →
THEOREM_CONTRACT review → M1 gates. All green before any M2 arm.

Target-1 verdict (three branches, mechanical):
- v200 alone ≤ 1e-5 → MET, freeze; e8 rows: keep as tightening if already
  running, cancel if still held.
- v200 miss but v200e8 ≤ 1e-5 → "extra=8 configuration meets the target",
  report BOTH rows honestly.
- both miss → frontier + N* where 1e-5 last holds.
Freeze cancels only never-started low-priority cells; near-complete jobs run
out.

## §D Wednesday 13:00 hard deadline

M0-C + THEOREM_CONTRACT + M1 all green by 13:00 → M2 runs. Mechanical bug
(<1 h est.) → one fix-and-rerun round. Not green by 13:00 → F0: large-scale
hybrid OFF, machine time to Targets/2D. F0 triggers (any of three): ΔCG
null · deadline missed · contract cannot close. No unlimited seam-fixing.

## §T Wednesday night tiers (replaces the full-ladder idea)

| tier | content | condition |
|---|---|---|
| must-run | N=20/40 rdm=8 pairs | ΔCG8 resolved-positive |
| big point | ONE large pair (100 or 200, chosen by Target-1 state) | all rungs green |
| expensive | ONE rdm=10+CG | clear target value |
| hatch | +1 big pair / 2nd expensive | measured per-cell cost allows AND both Target-1 & Target-2 plays are simultaneously live |

ΔCG null → zero scale cells; F0 becomes the method narrative, reported as
measured.

## DMRG (Wednesday, corrected release logic)

Mandatory probe order J2 = 0.5 (MG sanity) → 0.2 (critical side) → 1.0
(strong frustration). 0.4/0.6/0.8 released one by one on measured cost of
the first three. "Release the whole gapped side" is dead.

## Thursday

No new experiment families. Red-cell reruns → data freeze → all tables from
CSV → claim audit (tier sentences copied verbatim, terminology grep,
per-number provenance) → push before 20:00.

## Builder-instruction mapping

- The ten blocking corrections: already law throughout this file.
- (A) worktree per §N1/§R5-6 incl. incident check (§R1: clean).
- (B) SCNet staging per §R2 (--hold at submit), 2D chain head = L=4 canary.
- (C) tier hatch clause per §T.
- (D) manifest += mosek_ver/julia_ver (already CSV columns); three checks:
  quota, fat-node billing rate, MOSEK concurrency terms (§R8/§R9).
- (E) F0 = three triggers (§D).
- (F) Morning audit package for Codex in first-review §11 format; if the
  exact §11 spec is needed verbatim, user re-pastes it in the morning —
  default contents: run inventory, gate results, provenance proof
  (diff-empty per row), claim-tier draft. Codex replies GO/NO-GO +
  BLOCKING FIXES + CLAIM RESTRICTIONS only.

## Verification (tonight's additions)

- worktree: `using QMBCertify` loads; pinned commit recorded; main checkout
  `git status` unchanged w.r.t. v3 inputs until v3 ends.
- SCNet: squeue shows 23 tasks with exactly the six big ones in JobHeldUser;
  v14/v50 first-output sanity within minutes of start.
- 2D: canary JSON row exists and its encoding matches the source-read
  expectation before L=6 is ever released.
- Morning: every verdict in §W is a comparison of numbers already on disk.

---

# Plan (of record): two tracks, PR ready Thursday 20:00

**Track 1 — targets (unchanged):** user-authored strategy, adopted verbatim.
Push stock CONFIG A (`d=4, extra=4, rdm=10, pso=3, lso=true`) to the
challenge Target sizes and map the accuracy frontier honestly. Tonight's
stock queue is UNCHANGED by anything in Track 2.

**Track 2 — method (Plan v2, user-authored):** NPA + ω-tower hybrid,
supersedes the cancelled method plan. Gated M0–M3 below, after Track 1's
phase sections. Six external-review corrections adopted; not re-litigated.

Why credible: construction cost is N-independent (~34 min measured),
post-symmetry block sizes are N-independent, N=10/14 reproduce Table 3 to
7 digits. Nobody has published N>100.

Terminology (correction 10 — per-source, once, everywhere):

| output | mandated term |
|---|---|
| SDP results | "numerical SDP lower bounds" |
| DMRG results | "variational upper bounds" |
| Bethe results | "high-precision Bethe references" |
| MG point J2=0.5, −0.375/site | may be called **exact** |

Primary Target metric (correction 7): **absolute per-site signed reference
gap** — `gap = E_Bethe − E_LB` (Bethe-referenced rows) or
`bracket_width = E_DMRG_upper − E_LB` (DMRG-referenced rows). Relative error
is supplementary only. Both columns in every CSV row and table.

Priority: **Target 1 > Target 2 > Target 4 > Target 3.**
Budgets: MAX_WALL_S = 7200 per 1D cell (construction alone ~2050 s),
MAX_RSS_GB = 18 [SUPERSEDED — laptop-era; local J2 lane runs 18.5/19G, SCNet 110/120G], fail-fast on process-group swap. Provenance: the
overnight-harness cfg-NamedTuple pattern, one CSV row per run —
**no row, no claim**.

---

## Phase 0 — close-out + references (Tuesday daytime)

**0a.** Reproduction close-out (docs only, ~1 h): fill
`tracks/polyopt/results/20260727-203050-*/run.json` honestly (stage 1 N=14
reproduced via CONFIG A with knob changes recorded; stage 2 N=50 not run at
CONFIG A), rebuild report (`build_report.py` → `render_report.py`),
**push #1** to PR #193 (content preview first).

**0b.** Bethe reference solver (`bethe_ref.jl`, standalone): ground-state
Bethe equations for the PBC Heisenberg chain, logarithmic form, N/2 real
roots, Newton. **Validation battery (correction 8):** (i) ED cross-check at
small even N (XDiag, N = 8, 10, 12); (ii) Bethe-equation residuals reported
per root; (iii) root-count and quantum-number checks (N/2 real roots, the
ground-state I_j set); (iv) high-precision stability: BigFloat re-solve at
2× precision agrees to well beyond the quoted digits; (v) matches Table 3
DMRG column to 7 digits for N = 10…100. Product terminology: a
**"high-precision numerical Bethe reference"** — never "exact numerical
value". It is the reference of record for Target 1 at any N — no PBC DMRG
needed for the J2=0 chain.

**0c.** Interface recon (read, don't guess): GSB's `J2` argument and 2D
`lattice="square"` path — exact argument names, expected Hamiltonian encoding
for the J1-J2 chain (`supp=[[1,4],[1,7]]`, `coe=[3/4, 3/4*J2]` per the repo
example — verify) and the square lattice (what `L` means, basis knobs).
Log the call signatures into the run log.

## Phase 1 — tonight's merged queue (Target 1 ladder + Target 2 SDP cells)

**Amendment 2 (user):** Phase 1 alone (~4 cells ≈ 5 h) leaves half the night
idle; the six Target-2 J₂ SDP cells depend on no daytime decision (DMRG
references can be computed Wednesday), so they run tonight. ~11 cells ≈ one
full night. Insurance: whatever happens Wednesday, Target 2's SDP numbers are
already on disk.

**Amendment 1 (user) — memory, not time, is the N=200 risk.** Interior-point
Schur complement is m×m dense: with m ≈ 8716 + 290·(N−14),
N=100 → m≈33.7k → ~9.1 GB dense Schur (+factor workspace) — **already near
the 18 GB budget**; N=200 → m≈62.7k → **~31.4 GB, over budget**. (Mosek may
exploit sparsity and land below the dense estimate — the probe decides, the
dense number is the planning basis.) Therefore:
- N=100 and N=140 are **memory probes**, not just validation: fit peak-RSS
  vs m, project N=200 before it runs.
- **Queue is memory-ascending with truncation-after-death** [SUPERSEDED — laptop-era; SCNet staging replaces this]: N=200 cells sit
  last; an OOM kill burns only the tail, never the night.

**Amendment 3 (user) — Remark 6.1:** the paper itself removes PSD state
optimality for the J₁-J₂ chain at 0.1 ≤ J₂ ≤ 0.9 (documented solver
failures). All J₂ cells therefore run **pso=0**, recorded per-row as
"CONFIG A minus pso, per Remark 6.1". One control cell (J₂=0.2, pso=3) is
kept to observe what the authors saw.

**Tonight's queue (correction 4 — priority order, one process per cell,
serial, flush per cell):**

| # | cell | config | role |
|---|---|---|---|
| 1 | N=100, J₂=0 | CONFIG A | **validation + memory probe** (paper: gap 8.3e-6) |
| 2 | N=140, J₂=0 | CONFIG A | memory probe #2 |
| — | **RSS gate** | linear fit RSS(m) from cells 1–2, project N=200 | decision, logged |
| 3 | N=200, J₂=0 | CONFIG A | **CONDITIONAL** on RSS gate ≤ 18 GB; else SKIP with projection logged |
| 4 | N=100, J₂=0.5 | CONFIG A, pso=0 | J1-J2 core — **exact MG reference** −0.375 |
| 5 | N=100, J₂=0.2 | CONFIG A, pso=0 | J1-J2 core |
| 6 | N=100, J₂=1.0 | CONFIG A, pso=0 | J1-J2 core |
| 7–9 | N=100, J₂ ∈ {0.4, 0.6, 0.8} | CONFIG A, pso=0 | fill-if-room |

**Conditional diagnostics — NOT initial queue cells:** N=200 `extra=8`
(only per the Wednesday decision rule) and the J₂=0.2 pso=3 Remark-6.1
control (only if a slot is genuinely free). Each cell is its own Julia
process (bash driver), so an OOM at cell 3 cannot take down cells 4–9.
The J1-J2 core set {0.5, 0.2, 1.0} is the minimum source-of-record set:
J₂=0.5 has the exact MG reference tonight; 0.2/1.0 get DMRG variational
upper bounds Wednesday; the fill set extends the frontier if the night
allows.

Per row: opt (=E_LB), E_ref where available, **signed gap** (correction 7:
`gap = E_Bethe − E_LB` / `bracket_width = E_DMRG_upper − E_LB`; MG row:
`gap = −0.375 − E_LB`), supplementary relative error, construction_s,
solve_s, peak RSS, limit_hit, full provenance.

**Harness edits tonight (wrapper-side only):** float parsing in `parsecell`
(J₂ values are non-integer), a `model=j1j2` cellspec override switching
supp/coe, signed `gap`/`bracket_width` + supplementary `rel_err` columns,
queue truncation on memory death
(ordering already makes stop-on-frontier equivalent).

**Decision rule (Wednesday morning; gap = E_Bethe − E_LB, per-site):**
- gap(200) ≤ 1e-5 → **Target 1 MET. Freeze.**
- 1e-5 < gap(200) ≤ 3e-5 → near miss: ONE lever run Wed night — larger
  `extra` only (rdm=11 does not exist in QMBCertify; hard-coded 8/9/10),
  or the Track-2 M3 Target-1 play if its gates are green.
- gap grows faster → report the measured (N, gap) frontier and the N* where
  1e-5 last holds. Complete, publishable answer.
- [SUPERSEDED — laptop-era; N≥50 moved to SCNet, .wslconfig branch dead] **N=200 died on memory** and RSS-vs-m projection says 26–28 GB suffices →
  contingency: bump `.wslconfig` (Windows side, machine has 32 GB physical)
  to 26–28 GB **for Wednesday night only**, rerun N=200, revert Thursday
  morning. NOTE: applying `.wslconfig` requires `wsl --shutdown` — kills all
  sessions/tmux — so it is strictly a between-runs daytime action, never a
  mid-queue one.

## Phase 2 — Target 2 references + gap analysis (Wednesday daytime)

**2a.** PBC DMRG references (ITensors), N=100,
J2 ∈ {0.2, 0.4, 0.5, 0.6, 0.8, 1.0}, converged to ≤ 1e-4/site (all a 1e-3
target needs). Sanity: J2=0.5 must give the exact MG value −0.375/site.

**2b.** (moved to tonight — see Phase 1 queue.) Wednesday only fills in
`bracket_width = E_DMRG_upper − E_LB` (plus supplementary relative error)
once 2a lands, plus any red-cell reruns.

Deliverable: the **J2-frontier table** — where |dev| ≤ 1e-3 holds at N=100 and
where it fails, both metrics. Partial credit is the honest outcome; the
frustrated side will likely miss, exactly as the paper's N=40 numbers predict.
The pso control cell gets one sentence: did Remark 6.1's failure reproduce?

## Phase 3 — 2D recon gate (Wednesday, timeboxed ~2 h wall)

**Pre-run resolution (correction 9, blocking):** before ANY 2D cell, resolve
from source and the paper — Lx, Ly, N_sites (N = L² for `lattice="square"` —
verify in code), boundary conditions, and the **exact source-of-record
configuration** (which d/extra/three_type/rdm/pso/lso the paper's 2D tables
correspond to, as far as determinable; where indeterminable, record "chosen
by us" per knob). The phrase "CONFIG-A-equivalent" is **banned**; every 2D
cell names its full knob vector.

One cell: 2D Heisenberg **L=6** (resolved config), budgets 7200 s / 18 GB.
Record construction_s, solve_s, RSS.

- L=6 fails budgets → Targets 3 AND 4 **conceded on hardware grounds**; one
  honest paragraph citing the paper's 32-core/1-TB setup. Stop.
- L=6 fits comfortably → **one point can reject scaling but cannot justify
  extrapolation** (correction 9): run L=8 as a second scaling point; only a
  two-point (L=6, L=8) measurement may project L=10. If L=10 projects inside
  budgets, launch Wednesday night: 2D J1-J2 10×10 at J2 = 0.2 and 0.5
  (references = paper Table 10; J2=0.2 already meets 1e-2 in the paper —
  likeliest scored point). **Per Remark 6.1: 2D J1-J2 cells run with BOTH
  lso=0 and pso=0** — baked into the cellspec now.
  16×16 (Target 3) only if the measured L-scaling says it fits — expected:
  it does not.

Target 4 controversy note: with bounds at ~1e-2 looseness, discriminating the
2602.21468 intermediate-phase claim is unlikely; the honest sentence is "our
lower bounds bracket the published variational energies and exclude none" —
unless a published energy falls **below** our bound, which would be
reportable immediately.

## Phase 4 — freeze and write (Thursday)

- AM: final reruns of red cells, **data freeze**, all tables generated from
  CSV (no hand-copied numbers).
- PM: report only. One table per Target — achieved size, measured deviation,
  config, cost; the (N, dev) frontier plot for Target 1; the J2 frontier for
  Target 2; the hardware-concession paragraph for whatever 2D didn't run.
  `/challenge-report`, final push before **20:00**. (PR #193 is already
  non-draft, so "ready" = final push + body update, not `gh pr ready`.)

## Standing rules (Track 1)

- QMBCertify unmodified; wrapper scripts only. (Track 2's single fork
  function is the one sanctioned exception — see patch discipline below.)
- Never quote a number without its CSV provenance row.
- A measured miss is a result; an unmeasured claim is not. The report's spine
  is the frontier tables, whichever way each target lands.

---

# Track 2 — Plan v2: NPA + ω-tower hybrid (method track)

Corrections adopted from external review — **do not re-litigate**:
1. GSB is the dual/SOHS side, **confirmed from source at commit be63c27**:
   `bound_gsp.jl:601` `mvar = -dual(con) # extract moments`; the
   coefficient-matching equality family is `bound_gsp.jl:579`
   `@constraint(model, con, cons==zeros(length(tsupp)))`. M0 is no longer a
   which-side recon — these verbatim refs seed RECON.md.
2. D=2 is "the lowest-cost initial accuracy setting" — D affects BOTH cost
   and bound quality. Never described as a pure cost knob.
3. No hardcoded resource constants. Equality counts, map ranks, nnz are
   code-generated outputs, never assumptions. The "~136 eqs/ω" figure is dead.
4. `n_tower` comes from measured saturation, never a literature heuristic.
5. Scaling climbs a gated ladder. No N=14 → 200 jump.
6. Efficiency claims follow the tier ladder. Nothing is pre-written.

## M0 — dual extension seam (30–60 min, blocks all coupling code)

- **M0-A** Pin QMBCertify commit (`be63c27…`, already pinned by the dev
  checkout); verify reviewed structures at that commit: Gram PSD variables,
  coefficient-matching equalities (`:579`), `mvar = -dual(con)` (`:601`).
  Record verbatim refs in `cg_hybrid/RECON.md`.
- **M0-B** Seam inventory in RECON.md: coefficient basis + monomial index
  map (`tsupp`/`bfind`); coefficient-matching constraint refs; Gram maps;
  Hamiltonian coefficient vector; insertion points for the tower adjoints
  B*, T*; the new PSD dual blocks; tower-link multipliers.
- **M0-C** **BLOCKING regression gate:** rebuild the SAME model through the
  adapter with NO tower. Require |E_adapter − E_GSB| ≤ 1e-8 at N=10 and
  N=14, for both CONFIG A and the rdm=8 variant. No tower coupling runs
  until green. (CONFIG A arms cost ~34 min construction each — budget ~1.5 h
  of Wednesday morning for this gate.)
- **Patch discipline:** one fork function (`GSB_cg`, copied from GSB with
  the seam) committed as a diff; stock GSB and every Track-1 baseline row
  untouched.

## M1 — tower module (parallel to M0, independent)

Gates: n=4 lossless ≤ 1e-8 — **the lossless oracle uses an explicit unitary
map (χ=4 unitary W constructed and verified W†W = 𝕀), never the VUMPS D=2
tensor** (correction 6); n=5 flow composition; commuting-identity residual
≤ 1e-12; translation-averaged ED ground-state moments feasible ≤ 1e-10 with
objective = E0 (XDiag, N=8/10).
D=2 fixed as **the lowest-cost initial accuracy setting** (correction 2 of
Plan v2: D moves BOTH cost and bound quality; never a pure cost knob).
EVERY run emits, code-generated: `omega_side, omega_real_variables,
tower_equalities, tower_map_rank, tower_nnz, T_build, T_solve, peak_RSS`.

## THEOREM_CONTRACT.md — blocking artifact BEFORE M2 (correction 2)

`cg_hybrid/THEOREM_CONTRACT.md` must exist and contain, before any M2 arm
runs — numerical gates do NOT replace this proof:
1. **Shared primal baseline**: the primal moment SDP whose dual GSB solves
   (variables = moments over `tsupp`; PSD via the coefficient-matching
   equalities at `bound_gsp.jl:579`; moments recovered at `:601`).
2. **F_physical ⊆ F_hybrid**: every physical TI ring state's moment vector
   satisfies the base constraints AND the ω-tower constraints (marginals of
   TI ring states satisfy chain-LTI; images of valid states under CP coarse
   maps are valid) — stated and proved, with the M1 ED-feasibility gate
   cited as its numerical echo, not its substitute.
3. **E_base ≤ E_hybrid ≤ E0** derived from (2): adding valid constraints to
   a relaxation can only raise its optimum, and it stays a lower bound.
4. **Duality**: the implemented SOHS/dual extension (new PSD dual blocks +
   tower-link multipliers at the `:579` seam) is the dual of that primal
   tower; weak duality suffices for soundness of every reported bound.

## ε_cmp — comparison tolerance (correction 3; replaces every bare 1e-8 in
Δ classification)

For runs a, b:
`ε_cmp(a,b) = (g_a + g_b) + κ·(pfeas_a + dfeas_a + pfeas_b + dfeas_b) + (s_a + s_b)`
where g = solver duality gap (MU), pfeas/dfeas = feasibility residuals,
κ = problem-scale factor recorded per run (from the model's coefficient
norms, code-generated), s = model/map assembly residuals (commuting-identity
residual, adapter-rebuild residual). All terms live in the CSV row.
Classification of any Δ: `Δ > ε_cmp` resolved-positive; `|Δ| ≤ ε_cmp`
unresolved; `Δ < −ε_cmp` → see the per-quantity sign rules below.

## M2 — N=14 core experiment (Wednesday)

Arms:
| arm | config |
|---|---|
| B8 | rdm=8, fresh baseline (8 s construction) |
| A_n | rdm=8 + CG(n), n = 6, 9, 13 |
| B10-E | **energy value** reused from the provenanced overnight CONFIG A row |
| B10-C | **cost baseline** = the fresh, isolated CONFIG-A no-tower run from M0-C (correction 5: the overnight row's RSS came from the broken @async monitor and its timing environment differed — it must not support any memory/time claim) |
| C | rdm=10 + CG(n*) — ONLY if the A_n family shows a resolved positive gain |

Named quantities (exactly these symbols everywhere), **with sign logic
(correction 1)**:
- `ΔCG8 = E(A_{n*}) − E(B8)` — **≥ 0 in exact arithmetic** (tower adds valid
  constraints to the same base). `ΔCG8 < −ε_cmp` = bug: stop, fix, no scale
  runs.
- `ΔCG10 = E(C) − E(B10-E)` — **≥ 0 in exact arithmetic**, same rule.
- `Δreplace = E(A_{n*}) − E(B10-E)` — **no sign constraint** (neither
  feasible set contains the other); a negative value is a valid result, not
  a bug. Report signed.

Monotonicity gate (correction 6): enforce `E_6 ≤ E_9 ≤ E_13` within ε_cmp
(nested towers). Saturation: per-added-level gains
`g_n = (E_{n+Δn} − E_n)/Δn`, take the smallest n with g_n below threshold on
**two consecutive intervals** (threshold `max(5e-8, 0.05·(E_n − E(B8)))`).
No saturation observed → say so in the log; no sufficiency claim.
**Timing hygiene:** Tier-1 claims compare T(A) vs T(B10-C) — timed M2 cells
run serially and alone; Track-1 DMRG jobs pause during timed cells.

## M3 — gated scale ladder (Wednesday evening/night, conditional on M2)

Mandatory rungs: N = 20, 40 as CHEAP rdm=8 pairs (stock rdm=8 vs
rdm=8+CG(n*)) — tests scaling machinery and the ΔCG8-vs-N trend at 8 s
construction per arm.
Per-rung gates: solver status acceptable; Δ ≥ −ε; peak RSS within budget;
wall-time extrapolation to next rung acceptable.
All rungs green → **ONE big run**, chosen from tonight's stock CSV:
- Target-1 play (stock N=200 missed 1e-5): rdm=10 + CG(n*) at N=140 or 200.
- Target-2 play (stock met 1e-5): N=100, J2 ∈ {0.6, 0.8}, pso=0 per
  Remark 6.1, coarse tensor from VUMPS on the J1-J2 MPO.
Ladder failure at any rung → record the resource frontier, stop climbing.
"ΔCG grows with N" is a hypothesis under test: it may appear in the report
only next to its measured values, never in conclusions as established.

**Wednesday-night compute arbitration** (both tracks want the machine; the
`.wslconfig` bump, if triggered, kills all sessions and therefore runs FIRST,
before any queue): single serial queue ordered by the Track-1 priority rule
(Target 1 > 2 > 4 > 3). M3's big run IS a target play, so it slots by the
target it plays for; 2D cells (if the L=6 gate passed) slot as Target 4/3.
Memory-ascending within equal priority.

## Claim ladder for the efficiency result (report uses highest tier EARNED, verbatim)

Energy comparisons against B10-E; time/memory comparisons against **B10-C**
(the fresh M0-C cost baseline — correction 5); all thresholds are ε_cmp,
never a bare solver parameter (correction 3).

| tier | condition | permitted sentence |
|---|---|---|
| 1 | E(A) ≥ E(B10-E) − ε_cmp AND T(A) < T(B10-C) AND M(A) < M(B10-C) | "the CG tower replaces the rdm=10 constraint family at lower cost" |
| 2 | E(A) < E(B10-E) but meets the relevant target accuracy | "the CG tower provides a cheaper target-sufficient alternative" |
| 3 | E(A) > E(B8) + ε_cmp only | "the CG tower tightens the rdm=8 baseline" |
| below | — | report the signed numbers and claim nothing |

## Report language (fixed)

- "certified" remains banned; every number is a "numerical SDP lower bound".
- The tower is never "a synergistic moment set"; permitted phrase:
  **"constraint-family complementarity hypothesis"**. The 2×2 interaction
  ablation (rdm ∈ {8,10} × r ∈ {5,7},
  Δint = (E₁₀,₇ − E₁₀,₅) − (E₈,₇ − E₈,₅)) is OPTIONAL — only if a queue slot
  is genuinely free.
- arXiv:2607.14755 gets ONE paragraph, exactly four clauses: moment
  contributions are non-uniform and non-additive; it shows directly on the
  1D Heisenberg chain (N=9, 10) that the local basis is compressible but not
  globally optimal; this motivates budget-aware selection over local cones
  as a future direction; this work implements none of PT/RBM/BO and computes
  no marginal synergy. (Optional during execution: `/download-ref`
  2607.14755 for citation fidelity; the paragraph content is fixed above
  either way.)

## Track 2 files

| path | role |
|---|---|
| `tracks/polyopt/solutions/its-a-trap/cg_hybrid/RECON.md` | M0-A/B seam inventory with verbatim refs |
| `tracks/polyopt/solutions/its-a-trap/cg_hybrid/gsb_cg.jl` | the ONE fork function + adapter |
| `tracks/polyopt/solutions/its-a-trap/cg_hybrid/tower.jl` | M1 ω-tower module + gates |
| `tracks/polyopt/solutions/its-a-trap/cg_hybrid/m2_arms.jl` | M2 runner (provenance rows incl. the code-generated resource fields) |
| reuse | overnight harness row pattern; MPSKit VUMPS (left gauge); XDiag; Bethe ref from Track-1 0b |

---

## Execution notes (operational risk register — no strategy changes)

1. **Solve time at N≥100 under rdm=10 is unmeasured.** Constraint count grows
   ~290/site (m=8716 @ N=14 → 19156 @ N=50 → ~62k projected @ N=200); the
   N=100 validation cell exists precisely to measure this before N=200 runs.
   If N=100 solve alone approaches 7200−2050 s, the ladder auto-reports the
   frontier instead of silently dying — the harness records `limit_hit`.
2. **`rdm=11` does not exist** in QMBCertify (hard-coded 8/9/10) — the Phase 1
   near-miss lever is `extra` only. Noted inline above.
3. **Bethe-vs-DMRG 7th-digit ties:** if 0b matches to within ±1 in the 7th
   digit for some N, flag that N in the log rather than silently passing or
   blocking — Table 3's DMRG is itself a converged variational number.
4. Killed/failed cells inherit the overnight lesson: status fields of a cell
   that never reached MOSEK are recorded as N/A, never "OPTIMAL".

## Files

| path | role |
|---|---|
| `tracks/polyopt/results/20260727-203050-*/run.json` | 0a fill + report rebuild |
| `tracks/polyopt/solutions/its-a-trap/bethe_ref.jl` | 0b reference solver |
| `tracks/polyopt/solutions/its-a-trap/overnight_harness.jl` | reused runner (cellspec overrides already support `extra=`, `J2=`… via parsecell; 2D needs `lattice=square` passthrough — verify in 0c, extend cellspec parser if needed, wrapper-side only) |
| `tracks/polyopt/solutions/its-a-trap/dmrg_ref_j1j2.jl` | 2a ITensors PBC DMRG refs |
| new results dir `tracks/polyopt/results/targets-<ts>/` | all CSV + logs |
| `tracks/polyopt/solutions/its-a-trap/RESULTS.md` + report | Phase 4, generated from CSV |

## Verification

- 0b gate: printed table N=10…100 Bethe vs Table-3 DMRG, 7-digit agreement.
- Phase 1: every row has full provenance with **signed gap (primary) and
  relative error (supplementary)**;
  N=100 dev reproduces ~8.3e-6 before N=140/200 are trusted; decision rule
  applied to CSV values only; RSS-vs-m fit from cells 1 and 9 logged before
  cell 10's outcome is interpreted. [SUPERSEDED — laptop-era cell numbering; the fossil the user flagged Tuesday morning]
- **Tonight's success criterion (user):** by Wednesday morning the CSV holds
  the complete Target-1 ladder AND all Target-2 SDP numbers, plus the N=100
  vs 8.3e-6 reconciliation. If reconciled → Wednesday is harvest; if not →
  a full day to debug instead of half.
- Phase 2: MG sanity −0.375 exact; DMRG convergence evidence (χ, sweeps,
  energy drift) logged per J2 point; pso-control cell status reported.
- Phase 3: timebox enforced by harness budgets, not by hand; 2D J1-J2 cells
  carry lso=0 pso=0.
- Phase 4: rebuild all tables from CSV in one command; grep the report for
  "certified"/"exact" — must appear only in the mandated phrase
  "numerical SDP lower bounds".
- Track 2: M0-C adapter regression green (4 cells, ≤1e-8) before any coupled
  run; **THEOREM_CONTRACT.md exists and covers its four mandated sections
  before any M2 arm** (correction 2); M1 gates green before M2 (lossless
  oracle = explicit unitary, W†W = 𝕀 asserted); M2 sign rules per quantity
  (ΔCG8/ΔCG10 ≥ −ε_cmp mandatory, Δreplace unconstrained); E_6 ≤ E_9 ≤ E_13
  within ε_cmp; every quoted Δ carries its ε_cmp(a,b) value and components
  in the CSV; cost claims cite B10-C, never the overnight row; the report's
  efficiency sentence is copy-pasted from the earned tier, and the
  2607.14755 paragraph contains exactly the four mandated clauses.
- Terminology audit at freeze: grep the report — SDP rows say "numerical SDP
  lower bounds", DMRG rows "variational upper bounds", Bethe rows
  "high-precision Bethe references"; "exact" appears only for the MG value;
  "certified" appears nowhere.

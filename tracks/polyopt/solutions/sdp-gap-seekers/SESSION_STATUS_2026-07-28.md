# Session status & review request — sdp-gap-seekers / challenge #88

> ## ⚠️ SUPERSEDED — see `ADVISOR_REVIEW_2026-07-28.md`
>
> This was the **input** to the advisor review. Several of its claims are
> **overstated/wrong** and have been corrected by the advisor (P0/P1 findings)
> and in the ledgers: the gap values are numerical transition candidates (NOT
> "two certified upper bounds"); the "d-convergence" is an implementation
> artifact; kagome is calibration (the #88 target is square J1-J2, then
> Shastry-Sutherland, then triangular); the §8 Farkas framing read the wrong
> conic side. Read the advisor review for the authoritative assessment + the
> corrected ledgers (`gap-cert-ledger.md`, `energy-cert-ledger.md`).

> **Purpose:** a self-contained snapshot for a fresh advisor session to review
> our position and give strategic/technical advice. Written 2026-07-28 after a
> long working session. Read this, then the referenced files, then tell us where
> we're wrong / what to prioritize / what we're missing.
>
> Team: **sdp-gap-seekers** — Xiansheng Cai (蔡贤盛, xcai, this session) + Sihan Hu
> (胡思寒, "Sihan"/flyingwagner). Challenge: **#88** (polyopt track) — certified
> bulk spectral-gap bounds for frustrated spin-1/2 models, via the state-
> polynomial γ-feasibility SDP hierarchy of **arXiv:2606.03836**.

## TL;DR — what we have

- **Energy-cert floor (safety-net deliverable): COMPLETE + ledgered.** Certified
  lower bounds E₀/N for 2D square J1-J2, L=4–10, full E₀(g) phase diagram,
  d-converged, reference-matched (L=8 Heisenberg ≥ −0.6805 vs paper −0.676370,
  0.61%). Ledger: `feature/energy-cert-floor` → `energy-cert-ledger.md` (27 rows).
- **Gap-cert (the actual #88 target): TWO certified upper bounds on Δ, both as
  γ-scan "flag-transition candidates":**
  - **1D TFIM** N=9 g=0.5 d=2 sign-symmetric → **Δ ≤ 0.26** (matches example.jl
    0.258). Pipeline calibration / Gate 5.
  - **Kagome Heisenberg** (frustrated, #88-relevant) N=13 d=3 → **Δ ≤ 1.28**
    (matches example.jl). **d-converged** (d=3 = d=4 = 1.28).
- **Gap-cert pipeline VALIDATED end-to-end** (`ncpoly` → `certify_*_gap` →
  γ-scan transition). Ledger: `challenge/polyopt-sdp-gap` → `gap-cert-ledger.md`.
- **Square J1-J2 (the SPEC's original target): scaffolded, not yet runnable.**
  Validated H construction + a `get_square_basis` interface spec; blocked on a
  structured basis (PR #3 provides a generic one — see open questions).

## The toolchain (key discovery of the session)

The repo carries a **local dev copy of `SpectralGap.jl`** at `.external/SpectralGap/`
(gitignored; upstream `wangjie212/SpectralGap` @ `a1171c9` — Jie Wang is one of
the #88 challenge authors). It exposes **turnkey γ-feasibility certifiers**:
- `certify_Ising_gap(N, H, gamma, d; lso, QUIET)` — 1D TFIM.
- `certify_Heisenberg_kagome_gap(N, H, triples, edges, inner_triples, inner_edges, gamma, d; lso, QUIET)` — kagome.
- `ncpoly(supp, coe)` — the Hamiltonian encoding (site `i` → `3i-2=X, 3i-1=Y, 3i=Z`).

These implement exactly the SPEC §6 SDP (positivity block + gap block with the
`−γ·c + γ·mirror` covariance term + `lso` stationarity). **No square J1-J2
certifier exists** — that's the custom-build gap. We did NOT need to implement
the hierarchy from scratch; we drive the turnkey functions.

We **patched** SpectralGap (documented, recomputable): the certify functions now
return raw `(flag, termination, primal, dual, objective)` instead of the legacy
collapsed `flag`, plus an optional Farkas/dual-moment extraction. The pinned
patch is checked in: `spectralgap_a1171c9.patch` (base `a1171c9` + patch →
sdp.jl SHA `1e13b401…`, recomputable). See `GAP_RUN_PROVENANCE.md`.

## Methodology — γ-scan to localize Δ

`certify_*(…, gamma, d)` returns a status; we scan γ upward:
- `flag=1` (OPTIMAL) → γ feasible → Δ could be ≥ γ.
- `flag=0` (non-OPTIMAL) → treated as infeasible → Δ < γ (candidate).
- **largest feasible γ\* = certified upper bound on Δ** (the hierarchy is
  non-increasing in L,d; converges from above).

⚠️ The legacy `flag=(status==OPTIMAL?1:0)` collapses ALL non-OPTIMAL to flag=0
(no raw status/residual/witness). We patched this (status gate, see §8 below).

## Open problems — WHERE WE WANT ADVICE

### Q1. §8 rigor: how to actually get a certified (not "candidate") bound?

The SPEC §8 requires "a primal-infeasibility/Farkas witness extracted and
independently validated" to call a bound certified. We tried two paths, both
hit walls:

- **Farkas extraction via JuMP `dual()`:** at γ=0.26/0.30, Mosek reports
  `primal_status = INFEASIBILITY_CERTIFICATE` (it asserts a certificate exists),
  BUT `termination = SLOW_PROGRESS` + `dual_status = NO_SOLUTION`, so JuMP's
  `dual(con_eq)` is **not populated** — the reconstructed dual moment matrix is
  degenerate (all-zero). The witness exists in Mosek's state but isn't exposed
  via the standard JuMP API. Real extraction needs Mosek's
  `MSK_IPAR_INFEAS_REPORT_AUTO` low-level API (uncertain integration via Mosek.jl).
- **Cross-solver (Clarabel, pure-Julia SDP solver):** Clarabel is **impractically
  slow** on this complex certify SDP — stuck >11 min on TFIM N=9 d=2 (Mosek does
  it in 25s), and ignores the 120s `time_limit`. So no independent-solver
  agreement.

**Where we landed:** status gate closed (raw status retained); Mosek asserts
`INFEASIBILITY_CERTIFICATE`; but the witness is not extracted and no independent
solver confirms. **Is "Mosek INFEASIBILITY_CERTIFICATE + SLOW_PROGRESS" an
acceptable rigor level for the hackathon, or must we extract the Farkas ray?**
Is there a better §8 path we're missing (COSMO? SDPA? a Mosek setting that
yields a clean INFEASIBLE + populated dual)?

### Q2. Kagome bound Δ ≤ 1.28 at N=13 — competitive, or do we need N=27?

The bound is **d-converged at N=13** (d=3 = d=4 = 1.28; mirrors the energy side's
d-convergence). Tightening needs the L (system-size) knob:
- **N=27 d=3 OOM'd at 64 cpus (243 GB)**, then **ran 2h08m on 128 cpus (486 GB)
  with ZERO progress** (Mosek grinding on a huge SDP) — killed. N=27 d=3 is
  effectively intractable-in-practice on this hardware.
- example.jl's reference for N=27 d=3 is ~1.15.

**Is Δ ≤ 1.28 (N=13) a respectable #88 result, or is N=27 required to be
competitive?** Any way to make N=27 tractable — symmetry reduction (the kagome
certifier already uses sign symmetry), sparser formulation, different solver
settings, or a bigger machine? The SCNet nodes cap at 128 cpus / ~500 GB.

### Q3. Square J1-J2 — build it on PR #3's generic basis, or hand-craft?

SpectralGap has **no square certifier**. We established:
- The reduction rules (`model="kagome"` = SU(2) spin-rotation) REUSE for square
  Heisenberg. The SDP assembly copies cleanly.
- The only missing piece is `get_square_basis`. PR #3 (Sihan's structured-basis)
  provides a **geometry-generic** `basis_manifest(problem, role)` with a
  `:one_symbol_lift` family — usable for square, BUT with **no symmetry quotient**
  → much larger SDP (looser/slower) than a hand-crafted SU(2)-reduced basis.

**Build `certify_Heisenberg_square_gap` on PR #3's `:one_symbol_lift` (valid but
loose, fast to try), or invest in a hand-crafted SU(2)/C4-reduced square basis
(tighter, days of work)?** Spec'd in `SQUARE_BASIS_SPEC.md`.

### Q4. Strategic: is kagome the right #88 target, or square J1-J2?

Challenge #88 is "frustrated spin-1/2 models." Kagome Heisenberg IS frustrated
and turnkey → fast results. Square J1-J2 is the SPEC's choice but needs custom
code. We agreed (A-primary/B-preserved): kagome is the main result, square is
stretch. **Is that the right call for "winning" #88?** What's the likely bar
(other teams — `wangfh5` has open upstream PRs #219 NPA-cert + #221 kagome
energy bracket)?

### Q5. The d-convergence pattern — are we at the hierarchy's limit?

Both energy AND gap sides show **d-convergence at small L** (energy: d=4=d=6=d=8;
gap: d=3=d=4). Bound quality is set by **rdm/L**, not d. For the energy side,
rdm=8 is optimal (rdm=16 is looser). **Is this expected for this hierarchy, or a
sign we're missing a knob (the SPEC's "structured basis" completeness, or a
symmetry sector)?** Does this limit how tight our bounds can get?

## Coordination state (Sihan / flyingwagner)

- **PR #1** (square J1-J2 foundation): MERGED.
- **PR #2** (xcai: legacy inventory oracle): OPEN, Sihan reviewed CHANGES_REQUESTED
  (Gate-S items: commit artifact+SHA, strict verifier, SCNet evidence). I'm addressing.
- **PR #3** (Sihan: structured-basis manifests): xcai APPROVED. Provides the
  geometry-generic `basis_manifest` + `:one_symbol_lift` family (unblocks square,
  loosely).
- **PR #4** (Sihan: stacked Gate-S freeze-contract fix — independent verifier):
  xcai APPROVED.
- Sihan has SCNet access; will independently reproduce TFIM + kagome once the
  source/status gates closed (source gate: DONE — patched SpectralGap pinned;
  status gate: DONE — raw status retained). Both gates closed this session.
- Agreed split: Sihan owns generic/structured/assembly; xcai owns
  legacy/reference/solver.

## Infrastructure notes (for the advisor)

- **SCNet** (`ssh scnet`, partition `xhacnormalb`, 128-cpu/~500GB nodes): fully
  operational + git-tracked (bare repo `~/quantum.harness.git`; `git push scnet
  <branch>` / `git pull` workflow). All SDP compute runs here.
- **⚠️ HARD CONSTRAINT: the local laptop is sanity-check ONLY (<1 min, <1 GB).**
  WSL OOM-killed (twice) on loading SpectralGap+MosekTools+Clarabel (~15 GB RSS).
  Never run the SDP stack locally.
- **Block-buffering:** Julia stdout redirected to a file is block-buffered;
  certify's internal prints don't flush. Rely on per-γ results FILES (written
  with flush-on-close), not stdout, for progress.
- Mosek license on SCNet: `~/mosek/mosek.lic`. Env: `PATH=$HOME/julia-1.11.5/bin:$PATH`,
  `MOSEKBINDIR=$HOME/mosek/mosek/11.2/tools/platform/linux64x86/bin`,
  `LD_LIBRARY_PATH=$HOME/julia-1.11.5/lib/julia`.

## Key artifacts (all on `challenge/polyopt-sdp-gap` unless noted)

| file | what |
|---|---|
| `gap-cert-ledger.md` | the gap-track results table (TFIM, kagome) + §8 status |
| `GAP_RUN_PROVENANCE.md` | frozen run provenance: SpectralGap pin, H conventions, commands, γ-scan results |
| `spectralgap_a1171c9.patch` | the recomputable SpectralGap patch (status-return + Farkas scaffold) |
| `SQUARE_BASIS_SPEC.md` | interface spec for the square certifier's missing basis |
| `src/SquareGapCertify.jl` | validated square-J1-J2 ncpoly H construction (the done half) |
| `scripts/gap_tfim_validate.sh`, `gap_kagome*.sh` | the γ-scan SLURM scripts |
| `scripts/gap_cross_solver.sh` | the (failed) Mosek-vs-Clarabel cross-solver attempt |
| `energy-cert-ledger.md` (feature/energy-cert-floor) | the energy floor results |
| `square-j1j2-gap-sdp-spec.md` | the original from-scratch SPEC (666 lines; partly superseded by the turnkey path) |

## What we'd like from the advisor

1. **Prioritization:** given limited remaining hackathon time, rank: (a) extract
   the Farkas witness (Mosek API), (b) push kagome to N=27 or a tighter bound,
   (c) build the square certify on PR #3, (d) something else.
2. **§8 reality check:** is our "Mosek INFEASIBILITY_CERTIFICATE" level
   defensible, or genuinely short of "certified"? Cheapest path to a real witness?
3. **Kagome N=27 tractability:** any technique we're missing?
4. **Square vs kagome:** right #88 target?
5. **Anything we're doing badly** — methodology, the patch-the-upstream-package
   approach, the d-convergence interpretation, the division of labor.

Raw session detail: the Feishu group `oc_97429633afc6af23f4674228abc6b04b` has
the full xcai↔Sihan thread. Commits this session: `71a9506..44bdb2c` on
`challenge/polyopt-sdp-gap` (~25 commits).

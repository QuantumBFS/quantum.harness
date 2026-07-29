# Worker γ=1/4 attempt, solver-config findings, and Feishu landscape

Date: 2026-07-29
Author: local worker (xcai's agent)
Status: STOPPED — documenting findings + own recommendation (advisor temporarily unavailable)

## Worker handoff header

```
Starting SHA: edfec4d  (challenge/polyopt-sdp-gap)
Ending SHA:   edfec4d  (no new commit; this is a note only)
Work packet: Rung A γ=1/4 probe (lead's LEAD_RUNG_A…NEXT_PROBES packet)
Stop-gate result: NOT REACHED — the run did not produce a usable γ=1/4 result
Claim level: N/A (no scientific claim; two process/solver findings)
```

## 1. What I attempted and what actually happened

I tried to execute the lead's next probe (Rung A, γ=1/4) from the
LEAD_RUNG_A_GAMMA_ZERO_RESULT_AND_NEXT_PROBES packet.

**Job 22990714 did NOT run γ=1/4. It ran γ=0.** Root cause is my own process
error: I submitted while the SCNet **working clone** was still at `ea07011`
(one commit behind `edfec4d`). The `ea07011` batch script hardcodes
`SOURCE_POINT=…square-rung-a-g0-20260728-r1/gamma-0` and does **not** read
`RUNG_A_POINT`/`RUNG_A_GAMMA_CANONICAL`, so my `--export=RUNG_A_POINT=gamma-0p25…`
was silently ignored and the run-dir came out as `square-rung-a-smoke-22990714`
(no point label). This is exactly the "push to bare ≠ working clone current"
trap I documented in `notes/scnet-job-submission.md`. I then pushed `edfec4d`
to the bare repo and pulled the working clone; it is now correct (whitelist
gate, point-label run-dir, r2 bundle, expected-gamma contract all verified
on disk).

## 2. Solver-config findings (independent of the wrong point)

The wrong-point run happened to be γ=0 — the **same** point the lead solved in
**1.5 s** on job 22987727 at the same commit `ea07011`. Yet 22990714 **timed out
at the 10-min wall** (Slurm SIGTERM at 10:23, MaxRSS 167 MB — no OOM). So
something nondeterministic makes this tiny problem hang.

Two concrete defects, either of which dooms a slow solve to be uninformative:

1. **Forced `MSK_IPAR_INTPNT_SOLVE_FORM = MSK_SOLVE_DUAL` is nondeterministically
   pathological.** The lead's own γ=0 note flags that 22987727 "solved problem:
   the primal" (Mosek overrode the dual request after presolve) and "must not be
   cited as evidence the solve-form always forces the logged form." When Mosek
   instead actually goes dual, it appears to hang past the wall — and it ignored
   the 600 s solver time-limit (killed at 10:23, not 10:00). Prime suspect for
   the 1.5 s → >10 min regression.
2. **Solver time-limit == slurm wall (both 600 s): zero capture slack.** The
   script sets `--time-limit-seconds 600` and `--time=00:10:00`. On any slow
   solve Slurm SIGTERMs julia mid-`optimize!`, before the post-solve capture
   code runs, so **no `result.toml` / `mosek.log` is ever written.** A slow
   solve therefore yields zero diagnostic output.

## 3. Feishu landscape (messages 36–42, group oc_97429633…)

Reading the team chat materially changes the picture. Highlights:

- **Message 41 (Sihan, 22:28):** the TFIM metadata is confirmed **N=9, g=0.5,
  d=2, lso=6, γ=0.25125, open boundary, sign-symmetric** (the N=7/g=1/d=3 was a
  chat typo). The evidence is now on a **visible branch**
  `evidence/challenge88-certificate-hardening` (head `088513c92`), with MOF
  SHA `81fd38ff…`, fp-ray SHA `1050a479…`, runmeta SHA `99b9e6c3…`, plus an
  **exact-rational ray** (SHA `b62381f3…`). Sihan's verifier normalization is
  the scale-aware form the advisor asked for: `max|Ax|/max|x|`,
  `max(0,-λ_min)/max|x|`, `c·x/max|x|`; gate `abs_tol/max|x| + rel_tol`,
  both `1e-12`; binds MOF var order/names + objective + all affine columns +
  all PSD cone maps, fails closed on ray-order mismatch. Kagome γ=1.272 had
  **4,887 duplicate equalities** (15,671→10,784 deduped); old ray still
  rejected. **Square J1-J2: exact M/G/K core built (247,456 positive pairs,
  28 gap pairs) but no complete MOF solve yet.**
- **Message 42 (main agent, 09:58 today):** the main agent **took over and
  stopped the two remote research agents**, and published two branches on the
  flyingwagner fork: **Kagome strict Δ_bulk ≤ 1.272** (within the
  symbol/cyclic-spin-symmetry-restricted infinite-volume KMS class — *not*
  unrestricted) on `challenge/polyopt-kagome-strict-certificate` (head
  `1dbbb9fa0`); and **Shastry–Sutherland exact-equivalence reduction**
  (d=2, γ=½ finite-level feasible; 9 real PSD blocks, 3,250 vars; ~39.1× RSS /
  ~52.2× solve-time reduction vs the raw Hermitian bridge) on
  `challenge/polyopt-ss-exact-reduction` (head `ee9fedf92`). A rational-witness
  job (22990727) was PENDING under the shared account's `AssocGrpJobsLimit`.
  iintSjds/quantum.harness returns 403 for Sihan's GitHub identity, so all
  Sihan/main-agent work lands on the flyingwagner fork.

All three branches confirmed visible via `gh api`. SCNet queue is empty at the
time of writing (the AssocGrpJobsLimit appears to have cleared).

## 4. What this means for the open gates

- **Work-packet-0 blocker is RESOLVED.** Sihan's evidence branch (`088513c92`)
  is now inspectable; the MOF/ray/runmeta/verifier/exact-rational inventory the
  advisor's packet-0 asked for can finally be executed as a pure local static
  review (no SCNet, no advisor needed). This was the gate for choosing the shared
  artifact contract, and Sihan's contract already meets the scale-aware +
  one-ray-binding requirements.
- **The Rung A path may be superseded.** Message 42 says the main agent
  "stopped the two remote research agents"; Sihan's Square M/G/K
  symmetry-restricted core (247,456 positive pairs) is far more challenge-aligned
  than the unrestricted Rung A smoke (28 positive / 4 gap). It is unclear
  whether the lead's Rung A plan is still the wanted Square route.

## 5. My recommendation (advisor unavailable — my own judgment)

Ranked by value-to-risk:

1. **Execute packet-0 against Sihan's now-visible evidence branch** (zero SCNet,
   zero advisor). Fetch `evidence/challenge88-certificate-hardening` @ `088513c92`,
   statically audit the MOF/ray/verifier + exact-rational post-processing against
   the one-ray-binding and scale-aware-normalization requirements, record SHAs,
   and recommend ADOPT_MOF / KEEP_LOCAL. This is the highest-value zero-risk
   action and unblocks the shared-contract decision.
2. **If the Rung A γ=1/4 data point is still wanted**, two small fixes would very
   likely yield a clean result: (a) **drop the forced `MSK_SOLVE_DUAL`** (Mosek
   overrode it to primal on the fast run anyway; it is the prime hang suspect);
   (b) **give capture slack** — keep solver `--time-limit-seconds 600` but submit
   with `sbatch --time=00:20:00` so a slow solve still captures `SLOW_PROGRESS`
   + `mosek.log`. Both are one-line changes; (b) needs no script edit (submission
   override). Recommend confirming with the main agent / lead first, since msg 42
   may have redirected the Square effort to Sihan's M/G/K core.
3. **Do not fight `AssocGrpJobsLimit`.** Sequence SCNet submissions; the shared
   account saturates. Check `squeue`/`AssocGrpJobsLimit` before each submit.
4. **Reconcile the Square strategy explicitly** before more Square compute:
   unrestricted Rung A (lead's MVP, weak) vs Sihan's M/G/K symmetry-restricted
   core (more aligned, incomplete). They are different relaxations and should not
   both be pushed in parallel.

## 6. What I deliberately did NOT do

- Did not re-run γ=1/4 (user said stop + document; high chance of another
  no-output timeout under current config).
- Did not edit the lead's solver/batch scripts (forced-dual / wall-time changes
  are the advisor's call; flagged for authorization).
- Did not send any Feishu message (no instruction to; the clarifications already
  sent are in messages 39–40).
- Did not fetch/audit Sihan's evidence branch yet (that is recommendation #1,
  not executed — awaiting the user's go-ahead).

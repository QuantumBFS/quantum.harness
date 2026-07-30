# B0 Thread Status: Hard Goal Scientific Design

## Thread identity

- Thread: B0
- Date closed: 2026-07-28
- Scope: Issue #28 Hard Goal Stage 0 (design) and Stage 1 (conceptual
  self-review)
- Branch observed: `challenge/issue28-pure-neural`
- Starting HEAD: `a734162e0e75098fd9326e0aeb45e9ae3247b0f5`
- Primary artifact: [`HARD_GOAL_DESIGN.md`](../../HARD_GOAL_DESIGN.md)
- State: complete for B0

Post-thread update: on 2026-07-28 the user accepted all five Stage 2 choices.
Stage 3 planning proceeds in the B1 thread; the exact Stage 7 scheduler request
remains subject to its required pre-submission confirmation.

## Completed in this thread

1. Read and applied the repository-root `AGENTS.md`; no more-specific
   `AGENTS.md` exists under `tracks/mps/DMRG/`.
2. Audited Issue #28 and PR #154. They specify a 45^3 three-dimensional spin
   glass but do not uniquely define the Hamiltonian or bond distribution. PR
   #154's existing XY/LTRG work is unrelated to the Hard Goal.
3. Re-derived the VMCRG functional, gradient sign, target condition, and
   `H'_overlap=-V*+constant` recovery for a uniform target from Wu and Car,
   arXiv:1707.08683.
4. Audited primary three-dimensional spin-glass references:
   - Katzgraber-Koerner-Young, arXiv:cond-mat/0602212;
   - Hasenbusch-Pelissetto-Vicari, arXiv:0809.3329;
   - Hukushima-Nemoto, arXiv:cond-mat/9512035.
5. Read the challenge design, current MPS track plans, active Slurm profile,
   qdeshell/scnet cluster cards, and the Slurm mechanism contract.
6. Audited reusable code. The existing implementation supplies tested 2D MPS
   contraction/gradients/canonicalization, local incremental sampling,
   optimization controls, IAT/statistics patterns, atomic artifacts, and
   Slurm manifests. It does not supply the required 3D disorder-conditioned
   overlap/PT implementation.
7. Wrote the independent Hard Goal design covering:
   - provisional physical model and alternatives;
   - two-replica overlap and 3x3x3 RG;
   - VMCRG functional and effective-Hamiltonian interpretation;
   - Routes A/B/C and four local stencil choices;
   - exact Z2, cubic, and local gauge symmetry;
   - unbiased and biased parallel tempering;
   - equilibration, disorder averaging, FSS, Tc fitting, and error budget;
   - compute/Slurm design, success criteria, and downgrade paths.
8. Completed Stage 1 self-review and incorporated the corrections into the
   design. The main corrections include fixed-J disorder conditioning,
   gauge-canonical J features, full biased swap acceptance, fail-closed
   reweighting, odd-periodic update coloring, neural-bias conflict coloring,
   quenched bootstrap units, correction-aware crossings, and the distinction
   between the overlap effective Hamiltonian and the original Hamiltonian.

## Key design decisions

- **Model remains provisional:** iid equal-probability +/-J Edwards-Anderson
  Ising spins, `H_J=-sum_<ij> J_ij s_i s_j`, cubic PBC, zero field, `|J|=1`,
  beta=1/T. The literature benchmark is Tc around 1.11, not a fit prior.
- Literal exact-half +/-J disorder is impossible at L=45 because the lattice
  has 273,375 bonds. Any constrained alternative needs a new nearest-balanced
  definition and label.
- **Main neural route:** Route C, a gauge-invariant disorder-conditioned finite
  linear VMCRG baseline plus a conditioned local TT residual.
- **Scientific fallback:** Route B, a direct disorder-conditioned shared TT if
  the residual decomposition is unstable. Route A (q only) is an ablation and
  cannot support the fixed-J Hard Goal claim.
- **First template benchmark:** a 2x2x2 q cube plus five independent
  gauge-fixed chord/loop bits, compared with a centered 3D cross. Mandatory
  ranks are chi=2,4,8; chi=16 is extension-only.
- **Final Tc evidence:** separate unbiased two-ladder PT, using correction-aware
  xi_L/L and Binder finite-size analyses. Neural RG flow is independent
  consistency evidence, never the sole Tc estimator.
- **Candidate sizes:** `{6,9,12,15,18,24,27,45}`, with L=36 added only if pilot
  correction/parity fits require it.
- **Provisional disorder floors:** 8,192 for L<=12; 4,096 for L=15,18; 2,048
  for L=24,27; and 1,024 for L=45. Stage 6 must replace these placeholders
  with a measured power/resource decision.
- A Slurm cell owns a complete PT temperature ladder. Temperatures are not
  split into independent jobs.
- The active qdeshell card imposes one-node, 24-hour, array-200 limits and at
  least one A800 per job. SCNet is an unconfirmed compatibility/budget option.

## Test and review results

| Check | Result |
|---|---|
| `git diff --check -- HARD_GOAL_DESIGN.md` | PASS |
| Focused MPS model/sampler/optimizer/observable tests | `10 passed in 2.94s` |
| All existing `tests/*mps*.py` tests | `24 passed in 4.06s` |
| Stage 0/1 scientific compute | Not run by design |
| Production Slurm submission | Not performed |

One initial focused pytest command named a nonexistent
`tests/test_autocorrelation.py`; pytest collected no tests. It was corrected
to existing files, producing the passing results above. The full repository
suite was not run because B0 changed documentation only and the shared
worktree contains unrelated in-progress implementation changes.

## Not completed

- At B0 closure, no Stage 2 model, budget, route, sample-count, or Tc-contract
  confirmation had been received. The post-thread update above records its
  later resolution.
- No Stage 3 implementation plan has been written through `writing-plans`.
- No Hard Goal production module, test, config, report, or Slurm run spec has
  been implemented.
- No 2D Stage 4 regression was newly executed for this Hard Goal.
- No 3D validation, pilot, L=45 production, or FSS fit has been run.
- No commit, push, branch switch, PR update, or cluster submission was made.

## Required Stage 2 confirmation

The next thread must present and obtain an explicit answer on one decision
set before implementation:

1. iid +/-J versus exact-half/nearest-balanced +/-J versus Gaussian disorder;
2. Route C main and Route B fallback;
3. final Tc contract based on unbiased xi_L/L plus Binder, with independent RG
   compatibility;
4. candidate sizes and power-gated sample schedule; and
5. authorized accelerator-hour/storage budget and qdeshell versus SCNet scope.

After confirmation, open a new B1/Stage 3 thread, invoke `writing-plans`, and
write that thread's completed work, tests, decisions, and next step to its own
progress status before ending.

## Cross-thread handoff: Stage 6 adaptive readout, 2026-07-29 22:04 CST

The latest Stage 6 result-reading thread is recorded in
[`B4_STATUS.md`](B4_STATUS.md). Both L=24 and L=27 paired adaptive arrays
completed operationally and passed complete artifact/hash verification, but
all four candidates recorded zero minimum complete temperature round trips.
Both selectors therefore returned `RECALIBRATE`; Stage 6 remains no-go for
freeze, and Stage 7/L=45 remain blocked. The next task is the reviewed,
parent-hash-bound checkpoint extension protocol described in the B4 handoff.

Post-handoff update: the extension protocol and four 8,192-sweep packages are
implemented and locally verified. All four continuation jobs are now submitted:
`5315277` (L24 A035), `5315301` (L24 A040), `5315302` (L27 A035), and `5315303`
(L27 A040). The one-time startup check found all four `PENDING (Priority)`.
See `B4_STATUS.md` for hashes, tests, and the remaining Stage 6 gate.

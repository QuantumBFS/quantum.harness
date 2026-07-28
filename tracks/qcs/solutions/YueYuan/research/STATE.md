# Autoresearch State

- stage: run               # topics | db | validator | run | done
- topic: minimal-hessian-subspace-calibration-demo
- batch_size: 10           # attempts per cycle
- time_limit_seconds: 300  # hard wall-clock limit per scored run
                           # (default 5 min; user-confirmed, and
                           # adjustable, at the validator stage)
- authorized_attempts: 0   # attempts the loop may run without user review
- next_attempt: 5          # next .worktrees/attempt-NNN number
- next_cycle: 1            # next reflection cycle number
- gates:
  - survey_gate: passed 2026-07-27  # pending | passed YYYY-MM-DD
  - validator_gate: passed 2026-07-27  # pending | passed YYYY-MM-DD
- validator_env: fallback (Docker unavailable; local Python 3.11 subprocess sandbox with static source scan and timeout)
- overrides:
  - 2026-07-27: User asked Codex to "start automatic research" and set goal "Use Karpathy's autoresearch scheme to deal with the 113rd challenge"; proceeded with the previously recommended issue-113 topic and recorded its strict acceptance gate in topics.md.
  - 2026-07-27: Autoresearch-db normally asks the user to select insight areas after distillation; because the user requested automatic research, selected the core implementation insights and shelved the optional theory/hardware extensions without pausing.
  - 2026-07-27: User approved the validator bar; created GOAL.md, public dev split, sealed gitignored holdout split, validate.py, manifest, and negative controls. Validator self-test passed without using holdout.
  - 2026-07-27: Started run stage with attempt-001, a local rank-15 surrogate candidate. Public dev validator accepted it with score 2.9263157894736844. Treat as run-loop smoke evidence, not final physics evidence.
  - 2026-07-27: Attempt-002 replaced the direct surrogate with local toy two-qubit unitary propagation, finite-difference Hessian geometry, and exact final infidelity checks. Public dev validator accepted it with score 3.031578947368421. Next gap: real derivative-free closed-loop optimization traces.
  - 2026-07-27: Attempt-003 replaced deterministic query formulas with a pure-NumPy noisy-oracle simplex optimizer. Public dev validator accepts the stabilized version with score 2.4615384615384617. Next gap: per-query trace artifacts and research-grade plots/tables.
  - 2026-07-28: Attempt-004 full checklist package implemented locally. Local tests, smoke sweep, figure generation, and validator self-test passed. HPC verification remains a separate resource-gated step.

## Challenge 113 Full Checklist Memory

Source: `/Users/yueyuan/Downloads/challenge_113_codex_spec.md`.

Success criterion:

> Demonstrate, with fair baselines and honest query/shot accounting, that a low-dimensional subspace derived from the differentiable model Hessian can reduce the experimental cost of noisy black-box quantum-gate calibration in the regime where the model and true device remain sufficiently aligned, and clearly identify the regime where that advantage fails.

Final acceptance checklist:

- [ ] Differentiable model implemented.
- [ ] Open-loop pulse optimization works.
- [ ] Gradient validated against finite differences.
- [ ] Hessian or HVP implemented.
- [ ] Leading Hessian eigenspace extracted.
- [ ] Strict query-only true device implemented.
- [ ] Finite-shot noise implemented.
- [ ] Query and shot counters implemented.
- [ ] Model-only baseline implemented.
- [ ] Full-space black-box baseline implemented.
- [ ] Random-subspace baseline implemented.
- [ ] Hessian-subspace method implemented.
- [ ] Search-dimension sweep completed.
- [ ] Model-truth gap sweep completed.
- [ ] Shot-budget sweep completed.
- [ ] At least two system sizes tested.
- [ ] Multiple seeds and error bars reported.
- [ ] Queries-to-target headline plot produced.
- [ ] Total-shots-to-target reported.
- [ ] At least one failure case analyzed.
- [ ] Reproducible configuration and instructions provided.
- [ ] Short report or notebook completed.
- [ ] Pull request updated with the final artifact.

Execution note:

- Attempt 004 is the active full-checklist target. Consult `docs/superpowers/specs/2026-07-28-yueyuan-full-checklist-attempt-004-design.md` and `docs/superpowers/plans/2026-07-28-yueyuan-full-checklist-attempt-004.md` before reviewing completion or starting new work.
- Generated data and figures stay under ignored `tracks/qcs/results/YueYuan/attempt-004/`.
- HPC verification and scans must stay within 200 concurrent CPU cores and 1 concurrent GPU, and credentials must never be committed or echoed into logs.

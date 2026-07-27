# Autoresearch State

- stage: run               # topics | db | validator | run | done
- topic: minimal-hessian-subspace-calibration-demo
- batch_size: 10           # attempts per cycle
- time_limit_seconds: 300  # hard wall-clock limit per scored run
                           # (default 5 min; user-confirmed, and
                           # adjustable, at the validator stage)
- authorized_attempts: 0   # attempts the loop may run without user review
- next_attempt: 3          # next .worktrees/attempt-NNN number
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

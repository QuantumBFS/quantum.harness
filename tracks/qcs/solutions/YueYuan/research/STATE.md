# Autoresearch State

- stage: validator         # topics | db | validator | run | done
- topic: minimal-hessian-subspace-calibration-demo
- batch_size: 10           # attempts per cycle
- time_limit_seconds: 300  # hard wall-clock limit per scored run
                           # (default 5 min; user-confirmed, and
                           # adjustable, at the validator stage)
- authorized_attempts: 0   # attempts the loop may run without user review
- next_attempt: 1          # next .worktrees/attempt-NNN number
- next_cycle: 1            # next reflection cycle number
- gates:
  - survey_gate: passed 2026-07-27  # pending | passed YYYY-MM-DD
  - validator_gate: pending  # pending | passed YYYY-MM-DD
- validator_env: (unset)   # docker | fallback (<reason>)
- overrides:
  - 2026-07-27: User asked Codex to "start automatic research" and set goal "Use Karpathy's autoresearch scheme to deal with the 113rd challenge"; proceeded with the previously recommended issue-113 topic and recorded its strict acceptance gate in topics.md.
  - 2026-07-27: Autoresearch-db normally asks the user to select insight areas after distillation; because the user requested automatic research, selected the core implementation insights and shelved the optional theory/hardware extensions without pausing.

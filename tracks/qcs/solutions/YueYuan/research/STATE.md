# Autoresearch State

- stage: topics            # topics | db | validator | run | done
- topic: (unset)           # slug of the chosen topic once stage >= db
- batch_size: 10           # attempts per cycle
- time_limit_seconds: 300  # hard wall-clock limit per scored run
                           # (default 5 min; user-confirmed, and
                           # adjustable, at the validator stage)
- authorized_attempts: 0   # attempts the loop may run without user review
- next_attempt: 1          # next .worktrees/attempt-NNN number
- next_cycle: 1            # next reflection cycle number
- gates:
  - survey_gate: pending     # pending | passed YYYY-MM-DD
  - validator_gate: pending  # pending | passed YYYY-MM-DD
- validator_env: (unset)   # docker | fallback (<reason>)
- overrides: (none)        # every user-approved protocol deviation, dated

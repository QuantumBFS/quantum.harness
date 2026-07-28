# Autoresearch State

- stage: done
- topic: finite-abelian-invariant-hermitian-reduction
- batch_size: 10
- time_limit_seconds: 8
- authorized_attempts: 0
- next_attempt: 1
- next_cycle: 1
- gates:
  - survey_gate: passed 2026-07-28
  - validator_gate: passed 2026-07-28
  - goal_gate: passed 2026-07-28 (30 development + 20 sealed private instances)
- validator_env: fallback (locked project .venv; lightweight NumPy prototype, subprocess timeout and Python I/O/network/process guards)
- final_report: docs/discussion/issue-229-final.html
- overrides: 2026-07-28 scope narrowed with user approval to finite abelian symmetry; permutation and SU(2) are deferred. The prototype validates invariant Hermitian block reduction as a precursor to, not a replacement for, general moment-SDP construction.

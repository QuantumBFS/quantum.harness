# Autoresearch State

- stage: run
- topic: finite-abelian-invariant-hermitian-reduction
- batch_size: 10
- time_limit_seconds: 8
- authorized_attempts: 0
- next_attempt: 1
- next_cycle: 1
- gates:
  - survey_gate: passed 2026-07-28
  - validator_gate: passed 2026-07-28
  - precursor_gate: passed 2026-07-28 (finite-dimensional invariant-Hermitian character decomposition only)
  - issue_229_gate: pending (NC word basis, affine moment SDP, and dense/reduced optimum equivalence not yet implemented)
- validator_env: fallback (locked project .venv; lightweight NumPy prototype, subprocess timeout and Python I/O/network/process guards)
- precursor_report: docs/discussion/issue-229-final.html
- overrides: 2026-07-28 scope narrowed with user approval to finite abelian symmetry; permutation and SU(2) are deferred. 2026-07-28 review corrected an overclaim: the implemented invariant-Hermitian character decomposition is only a reusable backend precursor; it does not satisfy issue #229 without NC word/moment construction and dense-vs-reduced SDP optimum equivalence.

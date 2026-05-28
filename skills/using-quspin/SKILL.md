---
name: using-quspin
description: Use when choosing or running QuSpin as the Python fallback for exact diagonalization, spin-chain ED examples, or QuSpin setup failures.
---

# QuSpin

Use QuSpin only as the declared Python fallback for ED workflows, especially when an existing QuSpin example matches the target model.

## Sources

- Stack contract: `skills/using-quspin/stack.toml`
- Method card: `skills/method-ed/SKILL.md`
- ED interview notes: `docs/ed/interview.html`
- ED review notes: `docs/ed/review.html`
- Install target: `make install quspin`
- Smoke test: `.venv/bin/python -c 'import quspin; print(quspin.__version__)'`

## Workflow

1. Prefer `/using-xdiag` unless the protocol or method card declares QuSpin as the fallback.
2. Confirm basis, symmetries, boundary, and operator conventions before code.
3. Record whether the run is full-spectrum, sparse, or selected-state ED.
4. Do not replace QuSpin with generic NumPy/SciPy ED unless the protocol records that deviation.

## Parameter setup

Use this section as the source for QuSpin-specific reproduction knobs unless the paper or official code fixes a value. QuSpin is a fallback: use it for Python-first workflows, matching official examples, spin-chain quick starts, or custom constrained bases through `user_basis`.

- Route reason: official QuSpin code/example, custom `user_basis`, Python workflow requirement, or XDiag blocker. Otherwise recommend `/using-xdiag`.
- Basis: QuSpin basis class, `user_basis` precheck when constrained, site ordering, boundary convention, and state-index map.
- Sectors: particle number / `Sz`, momentum, parity/inversion, spin inversion, particle-hole, and any paper-used sector QuSpin cannot express cleanly.
- Operators: operator strings, coupling lists, static/dynamic terms, dtype, sign convention, normalization, boundary terms, and momentum phases.
- Solver policy: full dense spectrum, sparse eigensolve, time evolution, selected-state overlaps, or level statistics. State whether the result is full-spectrum exact within a sector or selected-state ED.
- Diagnostics: basis dimension, sector label, term count, Hermiticity error, residuals, tiny dense brute-force comparison, and `/using-xdiag` comparison when feasible.

## Time estimate

Estimate from the QuSpin basis/block dimension `D` after all constraints and sectors are fixed.

- Dense full-spectrum: memory starts at `8 D^2` bytes for a real dense matrix, plus eigenvectors/workspace; wall scales as `D^3`.
- Sparse eigensolve: memory is sparse operator storage plus Krylov vectors; wall is `matvec_cost * iterations * requested_states`, with Python/basis construction overhead paid before the eigensolver.
- Time-dependent runs scale as `matvec_cost * time_steps * solver_substeps`; include observable-evaluation cost when it is not cheap.
- First estimate paper size and the largest local-PC-in-15-min size. If the route is slower, memory-heavier, or less expressive than `/using-xdiag`, say so before asking the user to choose.

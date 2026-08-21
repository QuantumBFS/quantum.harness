# Human-report table plan

> Planning and provenance file. Every reviewer-facing table is rendered
> directly in `../main.md`; this directory is reserved for optional CSV copies.

## Table 1 — Method settings

- Framework, boundary/coupling convention, K, α, r_fit, χ policies, parity
  sectors, variance/discarded-weight criteria, and maximum L.
- Exclude machine paths, code hashes, and per-cell runtimes.

## Table 2 — Validation benchmarks

- Nearest-neighbor: Γx crossings, Γ=1 gaps, gap-based pairwise `z_eff`, and
  direct z.
- σ=2/3: external Γc, gaps, gap-based pairwise `z_eff`, direct z, and
  power/log sensitivity.
- Include a compact convergence-status column.

## Table 3 — Long-range dynamical scaling

- Rows for σ=7/4 and σ=1.8.
- Fields: critical-field role and value, size range, direct z, power-coordinate
  z, log-coordinate z, and Shiratani–Todo comparison.
- Keep self-consistent and external-field σ=7/4 branches visibly distinct.
- Preserve published uncertainties for σ=1.8:
  `z_power=0.93(2)`, `z_log=1.00(3)`.

## Table 4 — Numerical uncertainty budget

- MPO coupling reconstruction and K=24→32 observable shifts.
- One χ=128→256 row at the largest validated size L=128, reporting the maximum
  absolute gap shift.
- Critical-field sensitivity and scope limitations.
- Do not repeat the finite-size correction-coordinate comparison already
  presented in Sections 3.1–3.2.

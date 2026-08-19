# Rung A gamma scan result — relaxation too weak to bound the gap

Date: 2026-07-29
Jobs: 22987727 (γ=0, lead), 22991825 (γ=1/4), 22992596 (γ=2)
Config: Rung A — Square J1-J2, g=1/2, L=1, d=2, unrestricted, bare_weight_one
basis (28 positive / 4 gap), 352–358 moments, 4 PSD blocks.

## Result

| γ | job | classification | termination | solve_wall |
|---|---|---|---|---|
| 0 | 22987727 | feasible_candidate | OPTIMAL | 1.5 s |
| 1/4 | 22991825 | feasible_candidate | OPTIMAL | 1.95 s |
| 2 | 22992596 | feasible_candidate | OPTIMAL | 2.25 s |

All three feasible. **Rung A cannot exclude a gap of even γ=2** (very large on the
J1=1 scale).

## Interpretation

Per the lead's `LEAD_RUNG_A_GAMMA_ZERO_RESULT_AND_NEXT_PROBES` §7: when both γ=1/4
and the high probe are feasible, *do not scan blindly upward*; first determine
whether the relaxation admits an unbounded-in-γ pseudo-moment construction. The
fact that feasibility does not tighten from γ=0 → γ=1/4 → γ=2 (all OPTIMAL, all
~2 s, objective unchanged) is strong numerical evidence that Rung A's gap basis
(4-dimensional) is too small to constrain the gap direction — i.e., the feasible
set is essentially unbounded in γ. A rigorous analytic/numerical unbounded-in-γ
construction was not produced here, but the scan answers the practical question:
**Rung A is too weak to produce a Square gap upper bound at any γ.**

## Conclusion — the Rung A path is exhausted for bounding

Rung A successfully exercised the full Square pipeline end-to-end (geometry →
basis → MOF → Mosek → result) and delivered a clean negative: the smallest
unrestricted relaxation cannot bound the gap. This is useful (it sets a floor on
how weak a relaxation can be) but it is not a #88 gap bound.

The strong Square result — the actual #88 deliverable — needs the bigger
relaxation: Sihan's M/G/K structured core (703 positive / 7 gap, 247,456 pairs)
wired into a conic assembly (the `SquareGapConic.jl` piece both Sihan's
`SQUARE_CORE_MGK.md` and the SS branch's `PrimalGapAssembly.jl` point at). That is
the next substantive engineering item.

## Solver-config fix that unblocked this scan

The earlier γ=0 re-run (22990714) timed out at 10 min because the forced
`MSK_IPAR_INTPNT_SOLVE_FORM = MSK_SOLVE_DUAL` hung nondeterministically past its
own time-limit. Fix (commit `f37864e`, verified in preopt metadata of 22991825):
the forced-dual form is now opt-in via env var `RUNG_FORCE_DUAL_SOLVE_FORM`
(default off → Mosek chooses; it freely chose dual on 22991825 and solved in
1.95 s). Capture slack added (solver `--time-limit-seconds 480` within the 10-min
wall) so a slow solve still writes its result. With these, γ=1/4 and γ=2 each
solved in ~2 s.

## Evidence

- `evidence/square-rung-a-gamma-0p25-22991825/result.toml` (+ SHA256SUMS)
- `evidence/square-rung-a-gamma-2-22992596/result.toml` (+ SHA256SUMS)
- γ=0: lead's `LEAD_RUNG_A_GAMMA_ZERO_RESULT_AND_NEXT_PROBES_2026-07-28.md`

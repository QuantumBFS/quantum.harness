---
name: scaling-fit
description: Use when the user has a size-indexed (and optionally parameter-indexed) data set and wants to fit a finite-size scaling form — power law, log, polynomial, or universal data-collapse — and extract exponents with uncertainty. Generic over the observable and the form.
---

# scaling-fit

Fit a finite-size scaling form to a size-indexed (and optionally parameter-indexed) observable. Produce fitted exponents with bootstrap or jackknife error bars, a quality-of-fit report, and an auto-generated diagnostic plot (residuals + collapse). Generic over the observable and the model.

## When to activate

- User has a `(L, observable)` or `(L, parameter, observable)` table and wants exponents.
- `/parameter-scan` flagged a critical-like / extremum / crossing label and exponents are wanted.
- A `physics/*` skill needs an exponent to compare against universality-class expectations (`physics/criticality`, `physics/magic`, `physics/confinement`).

## Inputs

- A data table: `(L, [parameter,] observable, uncertainty)` from `results/<run>/`.
- A *fit form* — picked by the calling skill, the user, or this skill's defaults:
  - `power-law` — `obs(L) ~ L^{-α}`. For gap-closing, correlation-length, and order-parameter scalings.
  - `log-L` — `obs(L) ~ A log L + B`. For 1D CFT entanglement, long-range magic at criticality, and similar.
  - `polynomial` — fixed-degree polynomial in `1/L`. Standard for energy-per-site extrapolation to the thermodynamic limit.
  - `data-collapse` — `f(L^{1/ν} (h − h_c))` with `obs · L^{γ/ν}` collapsed across sizes; extracts `(h_c, ν, γ/ν)`. The standard finite-size-scaling form.
- Optional pinned values (e.g., user fixes `h_c` from prior work; this skill fits only the exponents).

## Workflow

1. Load the table; verify size and uncertainty columns.
2. Pick the fit form (default or as instructed). For `data-collapse`, both axes are scanned over `(h_c, ν, γ/ν)` to minimize collapse residual; for `power-law` / `log-L` / `polynomial`, weighted least-squares.
3. Estimate uncertainties via bootstrap (resample data points with their uncertainties; refit; quantile error bars).
4. Plot the residuals and (for collapse) the collapsed curves; save to `results/<run>/scaling-fit.png`.
5. Report fitted parameters with uncertainties, the quality-of-fit (`χ²/ν` for least-squares; collapse-residual norm for data-collapse), and a one-line interpretation if the calling skill provided a universality-class anchor.
6. Hand back the report to the caller.

## Output

- `results/<run>/scaling-fit.csv` — fitted parameters, uncertainties, quality-of-fit.
- `results/<run>/scaling-fit.png` — collapse / residual plot.
- 2–3-line report: fitted exponent(s) with uncertainty, fit quality.
- `scripts/<run>/scaling-fit.jl` (or `.py`) — reproducible script.

## Quality-of-fit interpretation

- For weighted least-squares: `χ²/ν ≈ 1` is consistent with the model; `χ²/ν ≫ 1` means either the fit form is wrong or uncertainties are underestimated; `χ²/ν ≪ 1` means uncertainties are overestimated.
- For data-collapse: a small residual *with* visually clean collapsed curves is the meaningful signal. A small residual with visually scattered curves means the fit is over-fitting noise.

## Composition

- Pairs with `/parameter-scan` (data input — single- or multi-axis).
- After this skill runs, common follow-ups (offered via `AskUserQuestion`):
  - `/cross-method-check` — verify the fitted exponent against an independent method or observable on the same data (Recommended when the result will be reported).
  - Extend the scan range — when the fit is poor at the boundary of the swept range.
  - Compare to a literature *range* — through `physics/criticality` (or the calling physics skill).
  - Done.

## Notes

- This skill is *content-agnostic*: it does not know whether the exponent is `ν`, `γ`, or `c`. The calling skill provides the label and interpretation. Universality-class comparison happens in the calling skill, citing `knowledge-base/benchmark-numbers.md` or `knowledge-base/magic-benchmarks.md`.
- For contested universality classes the result should be presented as a range with the harness's value sitting inside the literature range, not as a definitive identification. The calling skill enforces this; this primitive just produces the fit.

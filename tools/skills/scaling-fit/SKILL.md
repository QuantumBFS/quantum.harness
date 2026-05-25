---
name: scaling-fit
user-invocable: false
description: Use when the user has L-indexed or size-indexed data and wants finite-size scaling — phrases like "fit a power law", "data collapse", "extract the critical exponent", "finite-size extrapolation", "extrapolate to the thermodynamic limit", "fit log L", "polynomial fit in 1/L", or "collapse these curves".
---

# scaling-fit

Fit a finite-size scaling form to a size-indexed (and optionally parameter-indexed) observable. Produce fitted exponents with bootstrap or jackknife error bars, a quality-of-fit report, and an auto-generated diagnostic plot (residuals + collapse). Generic over the observable and the model.

## Audience / scope (binding)

<audience>
This primitive is content-agnostic. It receives a typed data table from the calling skill (a model card, a physics card, `/reproduce-paper`, or `solve` chained from `/parameter-scan`) and returns a fit plus a diagnostic plot. The calling skill consumes the fitted parameters; the user reads the 2–3-line report.

This skill MUST NEVER name the physical exponent (ν, γ, c, etc.) or identify a universality class. Labels and interpretation belong to the calling skill.
</audience>

## When to activate

- User has a `(L, observable)` or `(L, parameter, observable)` table and wants exponents.
- `/parameter-scan` flagged a critical-like / extremum / crossing label and exponents are wanted.
- A physics card needs an exponent to compare against universality-class expectations (`.knowledge/physics/criticality/PHYSICS.md`, `.knowledge/physics/magic/PHYSICS.md`, `.knowledge/physics/confinement/PHYSICS.md`).

## Inputs

- A data table: `(L, [parameter,] observable, uncertainty)` from `results/<run>/`.
- A *fit form* — **exactly one** of the four below, picked by the calling skill, the user, or this skill's defaults. The skill does NOT auto-cycle through forms; the caller commits to one form per run.
  - `power-law` — `obs(L) ~ L^{-α}`. For gap-closing, correlation-length, and order-parameter scalings.
  - `log-L` — `obs(L) ~ A log L + B`. For 1D CFT entanglement, long-range magic at criticality, and similar.
  - `polynomial` — fixed-degree polynomial in `1/L`. Standard for energy-per-site extrapolation to the thermodynamic limit.
  - `data-collapse` — `f(L^{1/ν} (h − h_c))` with `obs · L^{γ/ν}` collapsed across sizes; extracts `(h_c, ν, γ/ν)`. The standard finite-size-scaling form.
- Optional pinned values (e.g., user fixes `h_c` from prior work; this skill fits only the exponents).

## Workflow

1. Load the table; verify size and uncertainty columns are present and non-empty for **every** row. If any row is missing one of the columns, stop with a one-line `blocked:` report naming the missing column; do NOT silently impute.
2. Pick the fit form (default or as instructed). For `data-collapse`, both axes are scanned over `(h_c, ν, γ/ν)` to minimize collapse residual; for `power-law` / `log-L` / `polynomial`, weighted least-squares.
3. Estimate uncertainties via bootstrap: resample the data points with their uncertainties **N times** (default N=1000), refit on **every** resample, and report quantile error bars from the resulting distribution. Cover **every** declared bootstrap resample; do NOT drop resamples for which the fit failed to converge silently — surface them in the report as `failed_resamples = N` so the caller can assess fit stability.
4. Plot the residuals and (for collapse) the collapsed curves; save to `results/<run>/scaling-fit.png`.
5. Report fitted parameters with uncertainties, the quality-of-fit (`χ²/ν` for least-squares; collapse-residual norm for data-collapse), and a one-line interpretation if the calling skill provided a universality-class anchor. When no anchor is provided, omit the interpretation line — do NOT fabricate one from this skill's prior knowledge of common exponents.
6. Hand back the report to the caller.

## Output

- `results/<run>/scaling-fit.csv` — fitted parameters, uncertainties, quality-of-fit.
- `results/<run>/scaling-fit.png` — collapse / residual plot.
- 2–3-line report: fitted exponent(s) with uncertainty, fit quality.
- `scripts/<run>/scaling-fit.jl` (or `.py`) — reproducible script.

## Quality-of-fit interpretation

<checklist name="qof">

- `χ²/ν ≈ 1` → fit is consistent with the model.
- `χ²/ν ≫ 1` → either the fit form is wrong OR uncertainties are under-estimated.
- `χ²/ν ≪ 1` → uncertainties are over-estimated.
- Data-collapse + visually clean collapsed curves → meaningful signal.
- Data-collapse + visually scattered curves → noise (over-fit); a small residual number alone is NOT signal.

</checklist>

## Composition

- Pairs with `/parameter-scan` (data input — single- or multi-axis).
- After this skill runs, common follow-ups (offered via `AskUserQuestion`):
  - `/cross-method-check` — verify the fitted exponent against an independent method or observable on the same data (Recommended whenever the exponent will leave this session — run report, paper figure, declared entry, or message to the user).
  - Extend the scan range — when the fit is poor at the boundary of the swept range.
  - Compare to a literature *range* — through `.knowledge/physics/criticality/PHYSICS.md` (or the calling physics card).
  - Done.

## Notes

**Binding.** This skill MUST NOT label the fitted parameter with a physics name (ν, γ, c, etc.). The calling skill provides labels.

**Explanatory.** Universality-class comparison happens in the calling skill, citing `.knowledge/benchmark-numbers.md` or `.knowledge/magic-benchmarks.md`. For contested universality classes the result should be presented as a range with the harness's value sitting inside the literature range, not as a definitive identification. The calling skill enforces this; this primitive just produces the fit.

## Anti-patterns (auto-reject)

#### Inventing the physics label

<example name="label bad">
Fit gives exponent = 0.63 ± 0.02 — this is ν, the Ising-class correlation-length exponent.
</example>

<example name="label good">
Fit gives exponent = 0.63 ± 0.02. The calling skill names this against its physics card; this skill stays generic over the physics label.
</example>

#### Auto-cycling through fit forms

<example name="cycle bad">
Power-law fit had χ²/ν = 12. Trying log-L instead... still poor. Trying polynomial...
</example>

<example name="cycle good">
Power-law fit χ²/ν = 12 (poor). Stopping. The caller committed to power-law for this run; trying a different form is a separate invocation, not a silent fallback.
</example>

#### Reporting χ²/ν without the bootstrap confidence interval

<example name="qof bad">
χ²/ν = 0.7. Fit quality is good.
</example>

<example name="qof good">
α = 0.51 (95% CI: 0.47–0.56 from N=1000 bootstrap resamples, 23 failed). χ²/ν = 0.7.
</example>

#### Suppressing visually scattered collapse curves behind a low residual

<example name="collapse bad">
Collapse residual = 0.04 (low). Universality class consistent.
</example>

<example name="collapse good">
Collapse residual = 0.04, but the visual collapse in `scaling-fit.png` is scattered — three sizes diverge at high `h − h_c`. Reported as tentative.
</example>

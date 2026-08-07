# G5 active feasibility analysis protocol

This protocol was fixed before inspecting any `49x1296` BP-TN pilot result.
Its purpose is to prevent a favorable or unfavorable pilot from changing the
go/no-go rule after the fact.

## Required grid

- circuit: Tracker Git blob `829be362d1526ea9afe8e13fe1594e2e00eaa2e2`;
- raw perturbation: δ=0.15;
- deterministic seed namespace: `issue119-ole-v1`, seed IDs 1–20;
- BP-TN bond dimensions: χ=64,128,192;
- expected cells: 60, each with its own success manifest.

Any missing, failed, or duplicate cell fails `complete_grid`. A failed cell can
be retried without changing the run specification, but the gate is evaluated
only after all 60 declared cells have a success manifest.

## Numerical stability checks

Every sample must be finite and satisfy `|xᵢ|≤1+10⁻⁶`. Every barrier layer must
have a finite BP residual no larger than the configured tolerance `10⁻⁸`; any
non-converged layer fails `bp_stable`.

For common seeds define the paired mean drifts

```text
Δ₆₄→₁₂₈  = mean(xᵢ,₁₂₈ − xᵢ,₆₄)
Δ₁₂₈→₁₉₂ = mean(xᵢ,₁₉₂ − xᵢ,₁₂₈).
```

The finite-χ trend is classified as non-diverging only when

```text
|Δ₁₂₈→₁₉₂| ≤ max(2|Δ₆₄→₁₂₈|, 3 SE(Δ₁₂₈→₁₉₂), 10⁻³).
```

This is a feasibility rule, not a proof that χ=192 is converged.

TNQS local-tensor normalization is kept identical to the baseline and discards
the global scale needed for an independent norm defect. The analyzer must
therefore report `norm=unavailable_by_normalization`; it must not manufacture
a zero defect or silently change normalization. BP residuals, sample bounds,
truncation indicators, and paired drift are the available G5 stability
evidence. G6 adds the δ=0 control.

## Empirical resource model

For each χ, take the maximum wall time and maximum peak RSS across all 20
seeds. Fit each resource independently to

```text
resource(χ) = a χᵖ
```

by linear regression in log space. Because a negative cost exponent is not a
safe extrapolation, clamp `p≥0`. Predictions for χ=256,384,512 are the larger
of the fitted value and the largest observed value, multiplied by a fixed 1.2
safety factor.

The active production scan is feasible only when the χ=512 prediction obeys:

```text
predicted peak RSS ≤ 0.8 × batch node memory
predicted wall time ≤ 0.7 × declared partition wall cap.
```

For the current `batch` profile these limits are 80% of 1,500,000 MiB and 70%
of the 24-hour harness cap.

## Gate decision

G5 returns `GO` only if all checks pass:

1. complete 60-cell grid;
2. finite, bounded samples and positive finite resource measurements;
3. no BP-nonconverged layer;
4. non-diverging paired χ drift;
5. χ=512 memory prediction inside the 80% limit;
6. χ=512 wall prediction inside the 70% limit;
7. unique per-cell identifiers sufficient for selective retry.

Machine-readable results, the observed/predicted resource table, and the plot
are produced by `scripts/analyze_active_g5.py`. `NO-GO` stops the production
scan and becomes the documented G5 result; it must not be overridden merely
because more cluster capacity is available.

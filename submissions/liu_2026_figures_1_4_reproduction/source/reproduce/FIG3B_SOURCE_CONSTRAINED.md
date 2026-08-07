# Figure 3(b) source-constrained backend

This update extends the existing Figure 2–4 workflow; it does not replace or
fork the original command-line program.  The default `spline` and `time_bin`
backends remain unchanged.  A separate configuration opts into the new
`source_phase` backend.

## Why this is an integration rather than a copied implementation

The new path reuses the existing model, propagators, optimizer stages,
serialization, adaptive verification, plotting, and `input.in` contract.
Only the control parameterization and the first-order robustness residual are
selected differently.

| Existing seam | Default behavior | `source_phase` behavior |
|---|---|---|
| `OptimizerConfig` | spline/time-bin amplitude and phase | fixed envelope, 400 phase bins |
| `make_basis` | existing `WaveformBasis`/`TimeBinBasis` | `SourceConstrainedPhaseBasis` |
| `JaxControlKernels` | echoed channel-root residual | common-α state-vector residual |
| `save_waveform` | existing NPZ keys | same keys and cache/config checks |
| CLI and `input.in` | existing interfaces | unchanged |
| Figure 3(b) rendering | stored intensity and phase | intensity plus continuous phase |

## Source-fixed facts and reconstruction choices

The method cited by Liu et al. describes:

- a constant Ω₀ plateau with sinusoidal rising and falling edges;
- N=400 piecewise-constant phase intervals;
- the first-order condition ψq⁽¹⁾ = iαψq⁽⁰⁾ for
  q∈{|00⟩,|01⟩,|11⟩}; and
- a phase regularizer proportional to Σₙ(φₙ₊₁−φₙ)².

The paper does not publish the 400 optimized phase values, the smoothness
coefficient, the exact edge duration, or the optimizer seed.  This
implementation therefore declares Δᵣtᵣ=10 and a smoothness weight of 10⁻⁶ as
reconstruction choices.  Neither the pulse nor those choices are obtained by
fitting or digitizing Figure 3(b).

The phase is non-unique: 400 controls are constrained by a much lower-rank
terminal map.  A converged pulse is an equivalent numerical reoptimization,
not the authors' phase array.  Visual agreement of φ(t) is not an acceptance
criterion.

Sources:

- Liu et al., arXiv:2606.05060: <https://arxiv.org/abs/2606.05060>
- RobustGRAPE method, arXiv:2506.13724: <https://arxiv.org/abs/2506.13724>

## Run

```bash
.venv/bin/python liu_2026_fig234_reproduction.py \
  --standard \
  --config liu_2026_fig3_source_constrained_config.json \
  --stage optimize \
  --run-dir results/fig3b-source-constrained
```

The usual `robust_waveform.npz` and optimization summary are retained.
Running a downstream plotting stage additionally writes
`figs/fig3b_source_constrained_waveform.png`.

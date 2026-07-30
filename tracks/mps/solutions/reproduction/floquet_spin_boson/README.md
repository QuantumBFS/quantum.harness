# Floquet spin-boson reproduction

This directory implements the single-spin calculations for *Exact Floquet
dynamics of strongly damped driven quantum systems* (arXiv:2511.08754v3).
It extends PR #207 without treating the reduced 4×4 density-matrix channel as
a non-Markovian Floquet map.

## Physics and conventions

Ω=1, S=σz, and Hsys(t)=σx/2+Hdrive(t). Longitudinal driving uses
Hdrive=εd cos(ωd t)σx; transversal driving uses
Hdrive=εd cos(ωd t)σz. The bath is J(ω)=αω exp(−ω/ωc), with α=0.05,
ωc=2.5, εd=1, and temperature zero. Every Floquet period is discretized as
T=M dt with integer M; no closing-step interpolation is used.

## Environments and accuracy levels

- `envs/current`: pinned, runnable Julia environment using the recorded
  UniformTEMPO revision.
- `envs/paper`: provenance placeholder. The exact paper-era UniformTEMPO
  revision is unknown, so this environment must not be presented as resolved.
- `quick`: smoke tests only; reduced rank and grids.
- `validation`: development-scale numerical checks.
- `production`: paper-scale settings, permitted only after all seven
  convergence axes are recorded in a complete evidence file.

The uniform influence-functional cache key includes bath settings, exact `dt`,
compression controls, Julia version, and UniformTEMPO revision. Cache files are
validated before reuse and replaced atomically.

## Commands

From the repository root:

```bash
PROJ=tracks/mps/solutions/reproduction/floquet_spin_boson
julia --project="$PROJ/envs/current" "$PROJ/test/runtests.jl"
julia --project="$PROJ/envs/current" "$PROJ/scripts/reproduce_fig2.jl" \
  "$PROJ/configs/fig2.toml" /path/to/fig_2 output/fig2
julia --project="$PROJ/envs/current" "$PROJ/scripts/reproduce_fig3.jl" \
  --parallel phases --resume --reference-dir /path/to/fig_3 \
  "$PROJ/configs/fig3.toml" output/fig3
julia --project="$PROJ/envs/current" "$PROJ/scripts/reproduce_fig5.jl" \
  --parallel frequencies --resume --reference-dir /path/to/fig_5 \
  "$PROJ/configs/fig5.toml" output/fig5
julia --project="$PROJ/envs/current" "$PROJ/scripts/run_convergence.jl" \
  output/convergence
julia --project="$PROJ/envs/current" "$PROJ/scripts/benchmark.jl" \
  benchmark 32 20
python "$PROJ/scripts/plot_results.py" fig2 \
  --result-root output/fig2 --output output/fig2_comparison.png
python "$PROJ/scripts/plot_results.py" fig3 \
  --result-root output/fig3 --reference-root /path/to/fig_3 \
  --output output/fig3_comparison.png
python "$PROJ/scripts/plot_results.py" fig5 \
  --result-root output/fig5 --reference-root /path/to/fig_5 \
  --output output/fig5_comparison.png
```

Use `--rebuild-cache` only when the uniform influence tensor must be rebuilt.
`--resume` accepts a checkpoint only when its complete configuration and source
fingerprints match; incompatible partial output fails closed.

## Outputs and validation

Fig. 3 writes configuration, steady state, Floquet spectrum, micromotion,
correlation and its periodic/decaying split, continuous heat current, separate
delta-peak weights, diagnostics, and timing for each drive/frequency point.
Fig. 5 writes one resumable manifest per point plus total current and
period-averaged drive power. Delta peaks are compared by integrated weight,
never by an arbitrary plotted height. `plot_results.py` fails closed on
missing paper points or incomplete Fig. 5 rows; use
`--allow-validation-subset` only for an explicitly labeled Fig. 3 validation
checkpoint.

Production evidence must cover `dt`, compression/rank, eigensolver tolerance,
τmax, Δω, ωmax, and nmax. The benchmark report records matrix-free allocation
and runtime; the original PR #207 baseline remains under
`tracks/mps/results/20260728-floquet-task1-quick/output/baseline/`.

Known limitation: the implementation and tests are complete through the
validation workflow, but paper-precision Fig. 3/Fig. 5 numerical artifacts
require a cluster run and convergence evidence. They must not be described as
reproduced until those jobs finish and pass the physical diagnostics.

## Recorded checkpoints

- [`validation/20260730-fig2/`](validation/20260730-fig2/) records the complete
  two-panel Fig. 2 transient reproduction at strict `1e-10` compression.
- [`validation/20260729-fig3-longitudinal-wd5/`](validation/20260729-fig3-longitudinal-wd5/)
  records the first strict Fig. 3 validation point. The longitudinal
  `ωd=5Ω` spectrum passed all configured diagnostics and overlaps the Zenodo
  reference.
- [`validation/20260730-fig3-transversal-wd1/`](validation/20260730-fig3-transversal-wd1/)
  records the strict 8192-lag transversal `ωd=1Ω` validation point and a
  two-point visual checkpoint. Both recorded points pass the configured
  diagnostics; the other four Fig. 3 frequencies remain pending.

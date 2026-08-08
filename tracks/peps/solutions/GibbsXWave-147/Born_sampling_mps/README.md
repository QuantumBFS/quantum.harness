# Born-sampling TFIM comparison figure

This directory is a self-contained plotting bundle for
`tfim_open_10x10_h3_born_sse_comparison.png`.

## Contents

- `tfim_open_10x10_h3_born_sse_plot_data.csv` contains every plotted energy,
  absolute-error, and specific-heat point, including the statistical errors and
  the metadata needed to distinguish thermal and Born-sampled segments.
- `plot_tfim_open_10x10_h3_born_sse_comparison.jl` validates the CSV, rebuilds
  the original gnuplot data blocks, and renders the three-panel figure.
- `born_sampling_mps_overview.tex` and the compiled PDF briefly describe the
  stochastic-trace estimator, sequential purification Born snapshots, the
  $Z_2$ symmetry convention, and the numerical comparison.

The source paths retained in the CSV are provenance metadata only. The plotting
script does not read those paths, the original JLD2 files, or an external SSE
file.

## Reproduce the figure

Requirements:

- Julia 1.11 or another recent Julia release;
- gnuplot with the `pngcairo` terminal;
- Times New Roman installed for identical typography.

From the parent `Z2transverseIsing/` directory, run:

```bash
julia Born_sampling_mps/plot_tfim_open_10x10_h3_born_sse_comparison.jl
```

When already inside `Born_sampling_mps/`, the equivalent command is:

```bash
julia plot_tfim_open_10x10_h3_born_sse_comparison.jl
```

The script resolves its input and default output relative to its own location,
so it also works from another directory when invoked with the corresponding
absolute or relative script path.

The default output is
`Born_sampling_mps/tfim_open_10x10_h3_born_sse_comparison.png`. An optional
output path may be supplied as the only positional argument.

The plotting data and visual style reproduce the original figure in `../data/`.
The bundle labels the three sampling switch points by inverse temperature,
`β₀ = 0.25, 0.5, 1`, while retaining the provenance labels `T0=4,2,1` in the
CSV-facing series identifiers.

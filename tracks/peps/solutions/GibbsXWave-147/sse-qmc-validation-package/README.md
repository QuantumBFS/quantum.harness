# SSE-QMC validation package

This directory is the self-contained SSE-QMC handoff prepared for the
Harnessing Quantum 2026 coordination repository.

## What is included

- `plots/qmc-validation/tfim-sse-validation-note.tex` and the compiled PDF;
- the original, cited crop of Sandvik Fig. 3(b);
- the final `2×2` ED/SSE/tanTRG and `4×4` SSE/tanTRG SVG figures;
- Julia code and frozen input tables needed to regenerate both figures;
- compact CSV tables used by the PGFPlots figures in the TeX note;
- a snapshot of the necessary Julia SSE implementation, runner, environment,
  and test suite.

The physical convention is

```text
H = -J sum_<ij> sigma_i^z sigma_j^z - h sum_i sigma_i^x
```

with Pauli eigenvalues `±1` and open boundaries in the displayed benchmarks.

## Disclosure and scope

The current Julia SSE baseline was written mainly with AI assistance. The
project owner used the implementation, derivations, and benchmark discussion
to learn the basic ideas of fixed-length SSE, diagonal updates, linked
vertices, cluster updates, and expansion-order estimators. This is not a claim
of an independent from-scratch rewrite.

The implementation has passed the recorded deterministic, exact-small,
sampling, and cross-method benchmarks. Those tests support correctness in the
tested regime; they are not a proof for arbitrary Hamiltonians or parameters.
The stronger subsequent tests and independent comparisons were completed by
Jianxin Gao and Chuanshu Xu.

## Provenance

- coordination repository source branch: `main`;
- QMC source snapshot:
  `QuantumMC-Methods` commit
  `a0ca9c024316669d2fc01f7261ac4cc9e737df3f`;
- Julia: `1.11`;
- algorithm: fixed-length SSE with the TFIM-specific all-cluster update;
- `2×2` benchmark: `J=1`, `h=0.5`, `beta=1,...,10`, OBC;
- `4×4` comparison: exact common beta points only, without interpolation.

The SSE code is included as a source snapshot. It was not re-run while this
handoff directory was assembled.

## Rebuild the figures and note

From this directory:

```bash
julia plots/qmc-validation/build_energy_comparison_figures.jl \
  --require-l2-tantrg
julia plots/qmc-validation/build_sse_validation_note_data.jl
cd plots/qmc-validation
latexmk -xelatex -interaction=nonstopmode -halt-on-error \
  tfim-sse-validation-note.tex
```

The Julia plotting code uses only standard libraries, checks the hashes of the
frozen source tables, compares exact common beta points, and does not
interpolate.

## SSE source snapshot

The package-compatible source is under:

```text
QuantumMC-Methods/code/validation/julia/
```

It includes the transparent SSE kernel, constant-deflated estimators, exact
small-system routines, diagnostics, the Carlo adapter, a job runner, and the
original test suite. The associated commands are documented in that
directory's README; they are provided for later use and were not executed
during packaging.

## Sandvik Fig. 3(b)

`plots/qmc-validation/sandvik-2019-fig3b.pdf` is a vector crop of panel (b)
from `fig3.pdf` in the arXiv source package for:

> A. W. Sandvik, *Stochastic Series Expansion Methods*,
> arXiv:1909.10591 (2019).

Only the bounding box was changed. The crop source is
`plots/qmc-validation/extract_sandvik_fig3b.tex`.

Source `fig3.pdf` SHA-256:

```text
fe6f7e832d69b95f2876e87b79ff072c572511dc64afdca71329fe8edd3993a5
```

Packaged crop SHA-256:

```text
2180e495255538d0a7d46b62133203ce9829fe595b244c2cf30d92971185dc5c
```

To recreate it, download the arXiv source archive, extract `fig3.pdf` beside
the crop TeX file, and run:

```bash
cd plots/qmc-validation
xelatex -interaction=nonstopmode -halt-on-error \
  -jobname=sandvik-2019-fig3b extract_sandvik_fig3b.tex
```

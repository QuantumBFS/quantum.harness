# Integrated three-model central-charge report

This package builds detailed English and Simplified Chinese reports for
university students from three already completed Challenge #122 studies:

- clean Ising: `tracks/qmc/results/clean-ising-20260729-120302`;
- ordinary quenched Nishimori Ising:
  `tracks/qmc/results/nishimori-ising-20260729-refinement1`;
- weak self-dual Majorana network:
  `tracks/qmc/results/weak-self-dual-20260729-154737`.

The generator performs no Monte Carlo calculation. It validates frozen JSON,
CSV, manifest, gate, and PNG artifacts; derives four cross-model comparison
figures; and renders the same report model to HTML and PDF.

## Build

```bash
make setup
make test
make build
make build-en
make build-zh
make build-all
```

The stable outputs are:

- `output/html/three-model-central-charge-report.html`;
- `output/pdf/three-model-central-charge-report.pdf`;
- `output/html/three-model-central-charge-report-zh.html`;
- `output/pdf/three-model-central-charge-report-zh.pdf`.

`make build` remains an alias for the English build. `build-en` and `build-zh`
publish one locale, while `build-all` rebuilds both editions from the same
frozen source state. A Chinese-only build cannot replace either English
artifact.

The HTML is self-contained: all charts are embedded as base64 image data and no
network stylesheet, font, script, or image is required. The PDF uses an A4
publication layout and is verified for a 25-35 page range, required sections,
headline values, and embedded images. The Chinese PDF allows 25-45 pages for
natural CJK reflow and fails explicitly if no supported CJK font can be found.

All 21 reader-facing figures in the Chinese edition are regenerated with
Simplified Chinese titles, axes, legends, and annotations from the same frozen
CSV/JSON values. Rust and Python code listings remain unchanged so they can be
matched directly to executable source.

## Architecture

- `analysis/sources.py` adapts and validates the three different result schemas.
- `analysis/report_model.py` contains the common scientific narrative and
  format-independent block model.
- `analysis/report_model_zh.py` contains the contextual Simplified Chinese
  narrative while reusing the same block types and model results.
- `analysis/locale.py` contains fixed renderer labels and output metadata.
- `analysis/comparison_plots.py` generates the four synthesis charts.
- `analysis/source_plots_zh.py` reconstructs the 17 model-specific plots with
  Chinese labels without running Monte Carlo.
- `analysis/html_renderer.py` creates the offline responsive HTML.
- `analysis/pdf_renderer.py` creates the A4 PDF with ReportLab.
- `analysis/verify_outputs.py` checks both final artifacts.
- `build_report.py` performs an atomic build and confirms that source hashes do
  not change while rendering.

## Scientific safeguards

Every headline value is loaded from a processed artifact rather than typed into
the report prose as an independent value. A build stops if a required file or
figure is missing, a confidence interval is malformed, a benchmark target
conflicts with its gate file, or a required scientific gate has failed.

The clean Ising chapter reports both the deterministic transfer-matrix result
and the Monte Carlo thermodynamic-integration result. The Nishimori chapter
explicitly treats the ordinary quenched target near 0.464, not the distinct
Born/higher-replica value near 0.522. The weak self-dual chapter documents
state-conditioned Born sampling and the Rao-Blackwellized conditional-entropy
estimator.

The current Nishimori evidence uses only
`L = 4, 6, 8, 10, 12, 14`. Proposed larger-width simulations are not part of
this frozen report and are not implied by either language edition.

## Testing

The tests cover:

- frozen-source schema and headline-value loading;
- confidence intervals, parameters, figures, gates, and provenance hashes;
- required report sections and explanatory content;
- deterministic comparison-plot generation;
- embedded offline HTML;
- PDF page count, text extraction, A4 media boxes, and image coverage;
- stable end-to-end output paths.
- bilingual locale labels, CJK extraction, and output coexistence;
- deterministic generation of all 21 Chinese figures;
- isolation of English artifacts during a Chinese-only build.

Generated comparison figures live under the ignored local `generated/`
directory. `make clean-generated` removes only those figures and temporary PDF
page renderings; it does not remove frozen results or either final report.

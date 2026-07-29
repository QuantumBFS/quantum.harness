# Integrated three-model central-charge report

This package builds one detailed English report for university students from
three already completed Challenge #122 studies:

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
```

The stable outputs are:

- `output/html/three-model-central-charge-report.html`;
- `output/pdf/three-model-central-charge-report.pdf`.

The HTML is self-contained: all charts are embedded as base64 image data and no
network stylesheet, font, script, or image is required. The PDF uses an A4
publication layout and is verified for a 25-35 page range, required sections,
headline values, and embedded images.

## Architecture

- `analysis/sources.py` adapts and validates the three different result schemas.
- `analysis/report_model.py` contains the common scientific narrative and
  format-independent block model.
- `analysis/comparison_plots.py` generates the four synthesis charts.
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

## Testing

The tests cover:

- frozen-source schema and headline-value loading;
- confidence intervals, parameters, figures, gates, and provenance hashes;
- required report sections and explanatory content;
- deterministic comparison-plot generation;
- embedded offline HTML;
- PDF page count, text extraction, A4 media boxes, and image coverage;
- stable end-to-end output paths.

Generated comparison figures live under the ignored local `generated/`
directory. `make clean-generated` removes only those figures and temporary PDF
page renderings; it does not remove frozen results or either final report.

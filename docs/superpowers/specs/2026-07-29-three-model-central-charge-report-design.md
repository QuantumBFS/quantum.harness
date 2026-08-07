# Three-Model Central-Charge Report Design

## Purpose

Build a detailed English technical report for university students that integrates
the clean Ising, Nishimori random-bond Ising, and weak self-dual Majorana-network
studies. The report must explain the physics, numerical reasoning, implementation,
parameter choices, uncertainty analysis, and validation principles behind all
three calculations. It must be delivered as matching HTML and PDF documents.

The report reuses frozen simulation data and existing charts. It does not rerun
Monte Carlo calculations or alter any source result.

## Audience and Scope

The primary audience is university students with introductory statistical
mechanics, linear algebra, probability, and programming experience. The report
will introduce specialized concepts before using them while retaining enough
technical detail for a reader to reproduce the analysis or audit its assumptions.

The PDF target is 25-35 A4 pages. The HTML contains the same substantive content
in a responsive screen-oriented layout.

## Frozen Data Sources

The generator consumes these result directories:

| Model | Result directory | Principal benchmark |
|---|---|---|
| Clean Ising | `tracks/qmc/results/clean-ising-20260729-120302` | Exact \(c=1/2\) |
| Nishimori Ising | `tracks/qmc/results/nishimori-ising-20260729-refinement1` | \(c_{\mathrm{eff}}=0.464\) |
| Weak self-dual | `tracks/qmc/results/weak-self-dual-20260729-154737` | \(c_{\mathrm{eff}}=0.447\) |

All headline numbers, confidence intervals, fit diagnostics, parameter values,
and validation outcomes are loaded from the JSON and CSV artifacts in these
directories. Existing figures are reused at native resolution. The only new
figures are cross-model comparisons calculated from the processed artifacts.

## Scientific Narrative

The clean Ising calculation establishes the baseline. It introduces finite-size
free-energy scaling and validates the computational pipeline against the known
central charge \(c=1/2\), including a transfer-matrix reference and Monte Carlo
thermodynamic integration.

The Nishimori calculation then adds quenched bond disorder. It explains the
Nishimori-line relation, why disorder averaging changes the estimator and
uncertainty structure, how Lyapunov/free-energy quantities are accumulated, and
why the Nishimori energy identity and negative-bond frequency are strong physical
oracles.

The weak self-dual calculation extends the comparison to a Born-correlated
Majorana measurement network. It explains Gaussian covariance evolution,
conditional binary entropy, Rao-Blackwellization, electric and magnetic vortex
statistics, and the role of weak self-duality.

The synthesis emphasizes that the three models share a finite-size/Casimir
inference pattern but do not share an identical microscopic observable or
sampling distribution. Comparisons must therefore distinguish universal scaling
logic from model-specific estimators.

## Report Structure

1. Executive summary and headline result table.
2. Conceptual foundation: criticality, conformal finite-size scaling, Casimir
   terms, central charge, effective central charge, quenched disorder, and
   self-duality.
3. Shared computational architecture: Rust simulation, Xoshiro256++ random
   streams, Python aggregation, fitting, bootstrap analysis, and plotting.
4. Clean Ising model: definition, critical parameters, exact and Monte Carlo
   methods, integration, scaling fit, diagnostics, and results.
5. Nishimori random-bond Ising model: disorder law, Nishimori constraint,
   transfer/Lyapunov method, disorder averaging, bootstrap, diagnostics, and
   results.
6. Weak self-dual Majorana network: covariance dynamics, Born sampling,
   Rao-Blackwellized entropy rate, vortex observables, scaling fit, diagnostics,
   and results.
7. Cross-model comparison: common principles, non-equivalent quantities,
   estimator design, computational cost, precision, and scientific gates.
8. Error and sensitivity analysis.
9. Implementation principles, code organization, reproducibility, and testing.
10. Conclusions, equation glossary, complete parameter tables, validation-gate
    tables, provenance, and implementation pseudocode.

## Explanatory Requirements

For each model, the report must state:

- the physical degrees of freedom and critical-point definition;
- the calculated observable and its relation to central charge;
- why that observable and estimator are appropriate;
- the simulation and analysis data flow;
- the role and meaning of every production parameter;
- the random-stream and reproducibility strategy;
- the fitting equation, correction terms, and fit-window choice;
- the bootstrap or uncertainty procedure;
- exact, analytic, structural, or symmetry-based oracles;
- statistical and systematic limitations;
- the final estimate, interval, target, and validation outcome;
- code ideas and implementation principles, illustrated with compact
  pseudocode rather than large source listings.

## Data and Figure Policy

The report model is populated from source artifacts, not manually copied
numerical prose. It validates that required files and fields exist before
rendering. Derived differences, normalized errors, interval widths, and runtime
comparisons are recomputed during the report build.

Existing figures are organized by purpose:

- finite-size scaling and central-charge extraction;
- convergence and effective sample size;
- fit-window and correction-model stability;
- physical-oracle and symmetry checks;
- residual and replica diagnostics.

Four cross-model figures are generated:

1. central-charge estimates with 95% confidence intervals;
2. measured estimates versus benchmark targets;
3. normalized precision and runtime comparison;
4. required validation-gate summary.

Every figure caption explains the plotted quantity, the intended inference, and
the inference that the figure alone cannot support. Measured values, targets,
exact references, and diagnostic-only fits use distinct and consistent visual
styles.

## Error Analysis

The report treats the following uncertainty sources separately:

- finite Monte Carlo and disorder-sample noise;
- autocorrelation and effective sample-size loss;
- numerical integration error in the clean Ising workflow;
- finite-size and neglected-correction bias;
- fit-window and correction-model sensitivity;
- paired-bootstrap uncertainty and replica dependence;
- quenched-disorder fluctuations in the Nishimori calculation;
- Gaussian invariant drift and trajectory sampling error in the weak self-dual
  calculation;
- discrepancy between statistical confidence and broader model/systematic
  uncertainty.

Confidence intervals will not be described as proof of exact equality. Passing a
target-containment gate means consistency at the stated resolution, not an exact
measurement of the benchmark value.

## Implementation Architecture

Create `tracks/qmc/solutions/卧龙凤雏/integrated-report/` with focused modules:

- `sources.py` declares source paths and required artifacts.
- `data.py` loads and validates JSON/CSV inputs.
- `model.py` constructs a format-independent report model.
- `comparison_plots.py` creates the four derived synthesis plots.
- `html_renderer.py` renders the responsive self-contained HTML.
- `pdf_renderer.py` renders the matching A4 PDF.
- `build_report.py` validates, builds, and verifies both artifacts.
- `tests/` checks loaders, derived values, content coverage, and output integrity.

Final files:

- `output/html/three-model-central-charge-report.html`
- `output/pdf/three-model-central-charge-report.pdf`

Temporary PDF renderings are placed under `tmp/pdfs/` and removed after final
visual verification.

## Presentation Design

The HTML provides a table of contents, clear section anchors, responsive figures,
print-friendly colors, and compact result cards. It must remain readable without
network access.

The PDF uses an A4 publication layout with a title page, abstract, numbered
sections, equations, tables, captions, headers, footers, and page numbers. Page
breaks keep headings with their opening paragraphs and avoid splitting small
tables or figure captions from their figures.

Notation is defined before use. Parameter tables contain the symbol, value,
units or normalization, computational role, and sensitivity. Equations are
numbered when later sections refer back to them.

## Validation and Failure Behavior

Generation stops with a source-specific error when:

- a required artifact or field is absent;
- a confidence interval is malformed or excludes its reported estimate;
- target values conflict across source artifacts;
- a required scientific gate is false;
- a referenced figure is unreadable.

Verification includes:

- unit tests for data loading and derived comparisons;
- exact comparisons between displayed values and source values;
- checks for every required section and figure reference;
- local-link and embedded-image checks for HTML;
- PDF text extraction to confirm section and headline-number coverage;
- PDF page-count validation against the 25-35 page target;
- PNG rendering and visual inspection of every PDF page;
- visual inspection of the final HTML;
- a provenance appendix containing source paths and SHA-256 hashes.

## Success Criteria

The work is complete when:

1. both stable output paths exist and open successfully;
2. both formats contain the same scientific claims and headline numbers;
3. all three models receive complete conceptual, implementation, parameter, and
   uncertainty treatment;
4. all figures and tables are legible and correctly captioned;
5. the HTML works offline and the PDF has no clipping, overlap, broken glyphs, or
   poor section transitions;
6. all automated report tests pass;
7. every PDF page and the complete HTML layout pass visual inspection;
8. the source simulations and frozen result directories remain unchanged.

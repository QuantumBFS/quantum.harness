# PRB Four-Model Paper Design

## Purpose

Create a submission-style Physical Review B Regular Article that turns the
four frozen Challenge #122 studies into one coherent scientific paper. The
paper will be written in American English and typeset with REVTeX 4.2 using
the `prb` journal option. The reader-facing deliverable is a polished PDF;
LaTeX, BibTeX, scripts, and copied figure assets remain in the repository to
make that PDF reproducible.

The manuscript is not a concatenation of the existing reports. Its narrative
progresses from three validated benchmarks to a deliberately conservative
test of the open learning-induced metal-insulator transition.

## Authorship

- Authors: Xu Tian and Huidan Tan
- Affiliation: Department of Physics, School of Science, Westlake University,
  Hangzhou 310030, China
- Contact author: Xu Tian, tianxu@westlake.edu.cn

## Article Type and Official Formatting

The manuscript is a PRB Regular Article rather than a Letter. It has no hard
word limit and is expected to occupy approximately 14--18 typeset pages,
including appendixes. It will use a two-column REVTeX 4.2 layout, numbered
sections, APS-style citations, American English, and reference titles as
required by PRB.

The format is based on the current APS author guidance:

- https://journals.aps.org/prb/authors
- https://journals.aps.org/revtex
- https://journals.aps.org/prb/about

## Working Title

**Effective Central Charges across Clean, Disordered, and Monitored
Criticality: Benchmarks and an Exploratory Learning-Induced Metal--Insulator
Transition**

## Scientific Thesis

The paper argues that a validation hierarchy built from exact benchmarks,
finite-size scaling, correlation-preserving resampling, numerical invariants,
and predeclared gates can recover established effective central charges in
three progressively more difficult critical systems. The same hierarchy then
shows why the current learning-induced metal-insulator-transition calculation
does not yet support a universal effective central charge.

The three benchmark results are:

1. Clean Ising Monte Carlo:
   \(c=0.4987390623\), standard error \(0.0052247817\), with transfer-matrix
   value \(0.4994244024\), consistent with \(c=1/2\).
2. Nishimori random-bond Ising:
   \(c_{\mathrm{eff}}=0.4564694008\), standard error \(0.0081805213\), and
   95% interval \([0.4400639148,0.4723035402]\), consistent with \(0.464\).
3. Weak self-dual Majorana network:
   \(c_{\mathrm{eff}}=0.4441066355\), standard error \(0.0042401493\), and
   95% interval \([0.4357488246,0.4524943542]\), consistent with \(0.447\).

The open-study result is frozen at the pre-refinement candidate
\(\phi/\pi=0.30\). The entanglement estimator gives
\(c_{\mathrm{eff}}=3.0607395131\) with standard error \(0.7597477321\), while
the Casimir estimator gives \(c_{\mathrm{eff}}=12.5799328431\) with standard
error \(0.9898055467\). The manuscript must not publish either number as a
universal central charge because the DIII transition is not bracketed, the
anisotropy estimate is unstable, and the two estimators disagree.

## Manuscript Structure

### I. Introduction

Motivate central charge and effective central charge as finite-size probes of
clean, quenched-disordered, and monitored critical matter. Introduce the main
question: can a numerical workflow validated on known universality classes
make a defensible statement about a learning-induced transition?

### II. Models and Universal Observables

Define the common cylindrical geometry and the finite-size Casimir relation

\[
f(L)=f_\infty-\frac{\pi c_{\mathrm{eff}}}{6L^2}+\cdots .
\]

Then define the clean Ising model, the ordinary quenched Nishimori
random-bond Ising model, the Born-correlated weak self-dual Majorana network,
and the XY validation line plus generic-DIII cut used in the learning-induced
study. The distinction between the ordinary Nishimori value near \(0.464\)
and the separate Born/higher-replica value near \(0.522\) must be explicit.

### III. Numerical Methodology and Validation Hierarchy

Explain that Rust performs all Monte Carlo, random-transfer, and Gaussian/Born
trajectory sampling. Python validates frozen artifacts, performs fits and
bootstraps, generates figures, and builds the manuscript. Describe
Xoshiro256++, Wolff cluster updates, common-disorder pairing,
Rao--Blackwellization, block construction, paired bootstrap units, and exact
or small-system oracles. Explain why each model requires a different
resampling unit and why increasing Monte Carlo steps does not remove
finite-size or model-form bias.

### IV. Benchmark Central Charges

Present the three established systems as a sequence of increasing difficulty:

\[
\text{clean}\longrightarrow\text{quenched disorder}
\longrightarrow\text{Born-correlated monitored dynamics}.
\]

Each subsection reports the estimator, finite-size fit, uncertainty,
stability variants, exact or physical oracles, and the comparison with its
literature target.

### V. Exploratory Learning-Induced Metal--Insulator Transition

First reproduce the known XY transition window. Then present the generic-DIII
scan, the pre-refinement candidate-selection rule, entanglement chord-length
fits, Casimir-amplitude fits, and spatial-temporal anisotropy calibration.
Treat estimator disagreement as the principal scientific result of this
section and as evidence that the present calculation is inconclusive.

### VI. Cross-Model Discussion

Compare sampling error, numerical error, finite-size corrections, disorder
covariance, and model-identification error across the four systems. State
which failure modes are helped by more samples and which require larger
widths, an independent anisotropy estimator, or a genuinely bracketed
transition.

### VII. Conclusion

Summarize three successful benchmarks and one open result. Give concrete next
steps without implying that the current DIII candidate is a confirmed
critical point.

### End Matter and Appendixes

Include a Data Availability Statement, Author Contributions,
Acknowledgments, and appendixes covering coupling maps, Gaussian covariance
updates, resampling details, fit-window variants, and the complete validation
gate table.

## Figures

The paper will contain eight compact, publication-style multipanel figures:

1. Four-model workflow and validation hierarchy.
2. Clean Ising free-energy scaling and transfer-matrix/Monte Carlo comparison.
3. Nishimori free-energy fit, bootstrap distribution, and window stability.
4. Weak self-dual scaling, residuals, self-duality, and convergence.
5. Benchmark effective-central-charge comparison.
6. XY validation and generic-DIII phase scans.
7. Entanglement chord-length fit and infinite-width extrapolation at
   \(\phi/\pi=0.30\).
8. Casimir fit, anisotropy stability, and the two incompatible
   effective-central-charge estimates.

Figures must remain intelligible in grayscale and for readers with common
color-vision deficiencies. Meaning must be encoded by markers and line styles
as well as color. Axis labels and legends must remain readable at final
two-column size.

## Tables

1. Four model definitions, geometries, widths, sampling methods, and primary
   observables.
2. Benchmark estimates, standard errors, 95% intervals, targets, and
   agreement diagnostics.
3. Learning-induced-transition estimators, anisotropy result, and failed
   scientific gates.
4. Cross-model error sources and the validation mechanism used for each one.

## Data and Build Architecture

Create a focused paper package under
`tracks/qmc/solutions/卧龙凤雏/prb-paper/`. It will contain the REVTeX source,
BibTeX database, a deterministic data-extraction and figure-preparation
script, tests, and a build entry point. The package reads only these frozen
sources:

- `tracks/qmc/results/clean-ising-20260729-120302`
- `tracks/qmc/results/nishimori-ising-20260729-refinement1`
- `tracks/qmc/results/weak-self-dual-20260729-154737`
- the learning-MIT result selected by
  `tracks/qmc/solutions/卧龙凤雏/learning-mit/FROZEN_RESULT`

No Monte Carlo is rerun. Headline values are loaded from JSON/CSV rather than
duplicated as independent constants in prose. Existing result figures may be
combined or replotted from frozen data, but their numerical content must not
change. The stable reader-facing artifact is
`output/pdf/effective-central-charges-prb-paper.pdf`.

## Literature Policy

Use primary research papers and authoritative method references. Every DOI,
author list, title, journal, volume, page or article number, and year must be
verified against a publisher page, Crossref record, arXiv metadata, or another
primary bibliographic source. PRB reference titles are mandatory. The paper
must contain no invented citations, unresolved citation keys, or placeholder
references.

## Validation and Visual QA

The build must fail when:

- a frozen source or required field is missing;
- a learning-MIT summary hash differs from `FROZEN_RESULT`;
- a reported confidence interval is malformed;
- a benchmark headline value changes unexpectedly;
- a citation or cross-reference is unresolved;
- LaTeX reports an overfull box beyond the declared tolerance;
- the generated PDF is missing required sections, figures, tables, or
  embedded fonts.

Tests will compare all manuscript headline values with their frozen sources.
The final PDF will be rendered page by page and visually inspected for clipped
text, overlapping panels, unreadable labels, broken equations, bad page
breaks, and reference defects. The abstract, results, discussion, captions,
and conclusion must consistently distinguish validated benchmark claims from
the exploratory learning-MIT evidence.

## Acceptance Criteria

- A single polished PRB-style PDF is present at the stable output path.
- The byline and contact information match the approved author metadata.
- All four frozen studies appear in one coherent benchmark-to-frontier story.
- The three benchmark estimates and uncertainty intervals match their source
  artifacts.
- The learning-MIT section reports both estimators and all three reasons that
  prevent publication of a universal central charge.
- All automated scientific, citation, compilation, and PDF checks pass.
- Page-by-page visual inspection finds no layout or rendering defects.

# PRB Paper Depth and Vector-Figure Revision Design

## Purpose

Revise the existing Physical Review B manuscript so that its figures remain
sharp under magnification and its scientific narrative is broad, deep,
accessible to university-level readers, and academically rigorous. The
revision preserves all frozen numerical results and the conservative claim
boundary for the learning-induced metal-insulator transition.

The final reader-facing artifact remains:

`output/pdf/effective-central-charges-prb-paper.pdf`

There is no hard page limit. Completeness and clarity take priority; the
expected outcome is approximately 16--20 PRB pages.

## Approved Approach

Use data-native vector redrawing and systematic manuscript expansion.

Every scientific panel will be regenerated directly from existing CSV, JSON,
bootstrap, and hash-selected summary data. The current approach of wrapping
pre-rendered PNG images in PDF containers will be removed. This provides true
vector curves, markers, error bars, labels, and legends.

The manuscript will be expanded as a coherent whole. The Introduction will
establish the broad physical context, while Models, Methods, Results,
Discussion, and Appendices will add the explanations needed to make the
analysis understandable without weakening its scientific precision.

The revision will not rerun Monte Carlo simulations, alter fitted values, or
change frozen source artifacts.

## Figure System

The paper retains eight principal figures, but their panels are rebuilt as
native Matplotlib vector graphics.

1. **Validation hierarchy:** Reformat the workflow with larger typography,
   less empty space, and an explicit progression from exact clean benchmarks
   to claim gates for the monitored model.
2. **Clean Ising:** Show free-energy finite-size scaling, fit residuals, and
   exact-versus-Monte-Carlo central-charge estimates.
3. **Nishimori RBIM:** Show the quenched free-energy fit, the hierarchical
   bootstrap distribution, and fit-window stability.
4. **Weak self-dual model:** Show finite-size scaling, studentized residuals,
   the electric-magnetic self-duality diagnostic, and sampling convergence or
   effective sample size.
5. **Benchmark comparison:** Compare the three benchmark estimates, 95%
   confidence intervals, reference values, and standardized deviations.
6. **Phase scans:** Compare the bracketed XY validation transition with the
   unbracketed generic-DIII scan, marking the candidate point and scan
   boundary.
7. **Entanglement analysis:** Show the chord-length fit, width-dependent
   coefficients, large-width extrapolation, and model-weight information.
8. **Learning-induced MIT diagnostics:** Show the Casimir amplitude fit,
   anisotropy estimates across admissible windows, estimator disagreement, and
   the three claim-gate outcomes.

All scientific data marks, text, and axes must be vector objects. Rasterized
PNG panels are forbidden. The exported PDFs may contain Form XObjects but no
Image XObjects.

The common visual standard is:

- colorblind-safe palette;
- line style plus marker shape, never color alone;
- explicit `(a)`--`(d)` panel labels;
- minimum effective text size of approximately 8.5 pt;
- legends that do not obscure data;
- readable axis units and mathematical notation;
- widths matched to REVTeX single- or double-column geometry;
- consistent uncertainty representation and caption terminology.

## Introduction Structure

The Introduction will be expanded from four short paragraphs into a complete
scientific narrative with the following eight layers.

### 1. Critical phenomena and universality

Introduce the diverging correlation length, scale invariance, renormalization
group flow, relevant and irrelevant perturbations, and universality classes.
Explain why microscopically different lattice models can share continuum
critical behavior.

### 2. Two-dimensional conformal field theory and central charge

Explain the Virasoro central extension, conformal anomaly, finite-size Casimir
term, and the interpretation of central charge as a measure of critical
degrees of freedom. Connect the cylinder free energy and entanglement entropy
formulas to numerical observables.

### 3. From clean to disordered critical points

Distinguish quenched from annealed averaging and explain why the quenched
observable involves the disorder average of `ln Z`. Introduce the effective
central charge and the statistical consequences of correlated disorder.

### 4. Nishimori-line criticality

Explain the gauge structure and exact identities on the Nishimori line, its
multicritical role, and the ordinary quenched reference near
`c_eff = 0.464`. Explicitly distinguish this observable from the
Born-weighted or higher-replica quantity near `0.522`.

### 5. Self-duality and Born-weighted criticality

Explain why duality constraints can identify candidate critical manifolds and
how sequential Born sampling correlates the disorder with the evolving
Gaussian state.

### 6. Measurement-induced transitions and disordered topology

Introduce nonunitary trajectories, measurement-induced entanglement
transitions, free-fermion network descriptions, Altland-Zirnbauer class DIII,
and the possibility of a two-dimensional disordered metallic phase separating
localized phases.

### 7. Numerical inference risks

Explain finite-size bias, autocorrelation, common-disorder covariance,
fit-window selection, anisotropy calibration, and disagreement between
independent universal estimators. Distinguish regression precision from the
validity of the physical observable mapping.

### 8. Contributions and paper organization

Present the four models as a validation ladder rather than four unrelated
calculations. State the three benchmark outcomes and the conservative,
inconclusive monitored-model conclusion. Summarize the paper structure.

## Expansion of the Remaining Manuscript

### Models and observables

Define each model, probability distribution, geometry, partition function or
trajectory weight, observable, and finite-size mapping. Explain the meaning of
every parameter used in the numerical analysis.

### Numerical methods

Explain the Rust simulation kernels, Xoshiro256++, Wolff cluster updates,
Rao-Blackwellization, thermodynamic integration, transfer products, Gaussian
covariance evolution, bootstrap units, common-disorder pairing, correction
terms, and fit-window strategy. Each method must state why it is used and what
error it controls.

### Results

For every figure, the prose follows four questions:

1. What is plotted?
2. Why is this calculation performed?
3. What does the result support?
4. What does the result not establish?

Parameter settings, confidence intervals, fit diagnostics, and systematic
checks are stated explicitly.

### Discussion

Compare the four models, classify statistical and systematic errors, explain
the distinct roles of more Monte Carlo steps and larger system sizes, clarify
the `0.464` versus `0.522` distinction, and specify the decisive next
calculations for the learning-induced transition.

### Appendices

Retain the reproducibility derivations and add a notation guide, details of
fit-model selection, resampling formulas, and exact claim-gate definitions.

## Literature Standard

Add approximately 15--25 core references beyond the existing bibliography.
Use original research papers and authoritative reviews wherever possible.
Coverage includes:

- renormalization group and universality;
- two-dimensional conformal field theory;
- finite-size scaling and entanglement;
- quenched disorder and random critical points;
- Nishimori-line identities and multicriticality;
- measurement-induced phase transitions;
- fermionic Gaussian-state methods;
- Altland-Zirnbauer symmetry classes;
- disordered topological metals and metal-insulator transitions.

Historical and quantitative claims require nearby citations. Literature
results, calculations performed in this work, and inferences from those
calculations must be linguistically distinct. Every bibliography entry must
include a title and a DOI, ISBN, or arXiv identifier.

## Frozen-Data and Claim Boundaries

The revision consumes only existing result artifacts:

- clean Ising processed CSV files and manifest;
- Nishimori processed CSV/bootstrap files and manifest;
- weak-self-dual processed CSV files, diagnostics, and manifest;
- the hash-selected learning-MIT production-v2 summary and block data.

No Monte Carlo job is rerun and no reported value is changed.

The accepted benchmark conclusions remain:

- clean Ising passes against `c = 1/2`;
- ordinary quenched Nishimori passes against `c_eff = 0.464`;
- weak self-dual passes against `c_eff = 0.447`.

The learning-induced MIT values remain conditional diagnostics. They do not
constitute a universal-central-charge estimate because:

- the DIII transition is not bracketed;
- the anisotropy calibration is unstable;
- the entanglement and Casimir estimators disagree.

The paper must state that more Monte Carlo steps reduce sampling uncertainty
but cannot repair transition mislocation, finite-size bias, an unstable
anisotropy mapping, or estimator-definition mismatch.

## Data Flow and Code Boundaries

`paper_data.py` remains the hash-gated scientific data contract.

A new focused vector-data layer will parse the existing processed tables and
learning summary into immutable, plot-oriented records. It will validate
column names, finite numerical values, matching widths, bootstrap sample
counts, and the frozen summary hash.

`build_figures.py` will construct only native Matplotlib artists from those
records. It will no longer import or call `matplotlib.image`.

`paper.tex` will consume the generated vector PDFs and expanded bibliography.
Generated numerical headline macros remain source-derived.

## Testing and Acceptance

Automated tests must verify:

- all eight figures are deterministic and publication-sized;
- no generated figure PDF contains an Image XObject;
- every expected panel is backed by validated numeric data;
- the Introduction covers all eight approved conceptual layers;
- every manuscript citation has a complete bibliography entry;
- all existing frozen values and claim boundaries remain unchanged;
- the compiled manuscript contains no unresolved references, citation
  warnings, overfull boxes above 1 pt, placeholders, or missing fonts;
- the final PDF uses US-letter geometry and contains all figures and tables.

Visual verification must:

- render every page at 180--200 dpi;
- inspect every page and all figure panels;
- confirm readable labels at 100% scale;
- confirm no clipping, overlap, missing glyphs, or ambiguous panel ordering;
- confirm that the learning-MIT figures and captions visibly identify the
  result as exploratory;
- repeat after every material layout correction.

The final stable PDF must be byte-identical to the most recently verified
package build.

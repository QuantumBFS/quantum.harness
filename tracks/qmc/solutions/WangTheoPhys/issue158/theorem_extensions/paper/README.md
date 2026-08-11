# Manuscript build

This directory contains three independently compilable APS drafts:

- `main.tex`: the XY massless-phase classification, finite-size mechanism,
  and numerical interpretation;
- `supplement.tex`: the complete XY proof, massless comparison, and
  reproducibility details;
- `main_on.tex`: the separate hard-spin \(O(n)\) theorem.

From the parent `theorem_extensions` directory, run:

```bash
mkdir -p paper/output
latexmk -pdf -interaction=nonstopmode -halt-on-error \
  -output-directory=paper/output paper/main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error \
  -output-directory=paper/output paper/supplement.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error \
  -output-directory=paper/output paper/main_on.tex
```

Validated on July 30, 2026:

- `main.pdf`: 6 pages;
- `supplement.pdf`: 19 pages;
- `main_on.pdf`: 11 pages;
- no undefined citation or cross-reference;
- no overfull box;
- all pages rendered and visually inspected.

The theorem scopes are deliberately separate.  The hard-spin \(O(n)\)
article excludes vector LRO under its infrared hypotheses and derives a
quantitative marginal finite-size upper envelope; it does not establish
masslessness for \(n\ge3\).  The low-temperature non-exponential lower bound
and massless-phase classification in the XY article and supplement are
\(O(2)\)-specific and do not select BKT versus logarithmic asymptotics.

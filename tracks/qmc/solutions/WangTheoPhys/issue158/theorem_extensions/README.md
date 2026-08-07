# Theorem extensions and manuscript sources

This directory records two post-submission strengthenings of the Issue #158
audit:

1. a finite-volume infrared theorem for classical hard-spin \(O(n)\)
   ferromagnets with finite \(n\ge2\), including the marginal finite-size
   envelope \(\langle|M_L|^2\rangle=O((\log\log L)^{-1/2})\); and
2. an XY-specific comparison theorem that, together with the no-LRO result,
   rigorously classifies a low-temperature massless, nonmagnetic regime.

These results have different scopes.  The \(O(n)\) theorem excludes vector
long-range order when its regulated infrared integral diverges.  The
low-temperature massless comparison uses classical Ginibre monotonicity and
Theorem 1(ii) of van Engelenburg and Lis, and is established here only for
the XY/\(O(2)\) model.  Neither result decides whether the remaining XY
massless regime is ultimately BKT or genuinely logarithmic.

The sources were frozen from the research repository after the proof and
scope audits.  The finite-size envelope is an asymptotic upper bound, not an
exact decay rate or a sharp prediction at accessible sizes.  Compact-model
pilot code and finite-volume sampling results are intentionally not included
in this extension.

## Contents

- `PROOF_AUDIT.md`: full XY finite-volume proof and the massless comparison;
- `ON_PROOF_AUDIT.md`: complete hard-spin \(O(n)\) proof;
- `artifacts/`: deterministic proof and infrared-regime certificates;
- `scripts/`: certificate generators;
- `tests/`: focused algebra, scope, and reproducibility tests;
- `paper/main.tex`: six-page XY article;
- `paper/supplement.tex`: nineteen-page Supplemental Material;
- `paper/main_on.tex`: ten-page independent \(O(n)\) article.

## Verify the proof certificates

From this directory:

```bash
PYTHONPATH=. python3 -m pytest -q
```

Regenerate the theorem records with:

```bash
PYTHONPATH=. python3 scripts/massless_phase_audit.py \
  --output artifacts/massless_phase_audit.json
PYTHONPATH=. python3 scripts/on_theorem_audit.py \
  --output artifacts/on_theorem_audit.json
PYTHONPATH=. python3 scripts/on_infrared_regimes.py \
  --output artifacts/on_infrared_regimes.json
```

The numerical certificates are regression checks.  The analytic arguments
in the two proof-audit documents establish the theorems.

## Compile the manuscripts

From this directory:

```bash
mkdir -p paper/output
latexmk -pdf -interaction=nonstopmode -halt-on-error \
  -output-directory=paper/output paper/main.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error \
  -output-directory=paper/output paper/supplement.tex
latexmk -pdf -interaction=nonstopmode -halt-on-error \
  -output-directory=paper/output paper/main_on.tex
```

The PDFs are build products and are not committed.  The five vector figures
required by the manuscripts are versioned under `paper/figures/`.

## Scope boundary

The \(O(n)\) result is not a theorem for arbitrary continuous field theories.
It assumes compact unit-vector spins, bilinear translation-invariant
ferromagnetic pair interactions, finite positive temperature, a uniform
kernel limit, and a divergent regulated infrared integral.  It does not
cover unbounded soft spins, arbitrary target manifolds, gauge theories,
multibody interactions, frustrated couplings, or quantum systems without
new arguments.

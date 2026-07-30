# DFPT_research

Research proposal for QuantumBFS `quantum.harness` Issue #35: a physics-first
explanation of the practical success and limitations of DFPT, followed by a
testable design for a next-generation electron--phonon method.

## Central claim

The size of a beyond-DFPT correction is not determined by a material-wide label
such as "strongly correlated" or by the quasiparticle weight alone. It depends on
which low-energy operator a phonon modulates (charge, orbital, hopping,
hybridization, interaction, and so on), the susceptibility in that channel, and
the relevant frequency and momentum scales.

The proposed method keeps DFPT as the baseline, decomposes each perturbation in a
localized low-energy basis, and applies only the channel-specific correction that
is required by a risk diagnostic. The method is explicitly allowed to abstain when
its uncertainty is not controlled.

## Build

Requirements: XeLaTeX, `latexmk`, BibTeX, and Poppler.

```bash
make
make check
make render
```

The submission artifact is `main.pdf`. Source provenance and claim-level source
notes are in `provenance/sources.md` and Appendix D.

## Project structure

- `main.tex`: document entry point
- `sections/`: scientific narrative and proposed method
- `appendices/`: derivations, evidence matrix, two-day protocol, and claim ledger
- `figures/`: TikZ source for the method schematic
- `references.bib`: validated bibliographic metadata
- `provenance/sources.md`: source URLs, access dates, and usage notes

## Current scientific status

The equations defining standard DFPT, Hedin response quantities, and the Ward
identity are established theory. The finite-momentum electron-gas relation and the
channel-resolved correction architecture are working hypotheses that must be
tested against the benchmark matrix before they are presented as a predictive
theory.

The repository now includes a coefficient-space response-matrix fitter, a
synthetic held-out software contract, and explicit comparisons with DFPT-only and
dense higher-level costs. These make the proposed interface executable but do not
establish real-material accuracy or a measured speedup. The correction layer
still needs DFPT coefficients at every target point, so it is not cheaper than
DFPT alone; its possible saving is relative to evaluating the higher-level vertex
everywhere. Beating DFPT would require an additional surrogate and a separate
test against a modern DFPT interpolation baseline.

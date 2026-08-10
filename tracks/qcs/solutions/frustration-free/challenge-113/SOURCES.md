# Challenge 113 source bundle

## Official materials

- Challenge specification: `CHALLENGE.md`, captured from
  [QuantumBFS/quantum.harness#113](https://github.com/QuantumBFS/quantum.harness/issues/113).
- Official starting notebook:
  [Google Colab](https://colab.research.google.com/drive/1T0_sJMwmk7rbpxHMcBZwdD9pnYZx93oh).
  The file currently requires an authenticated Google session, so it could not
  be exported by the unattended downloader.

## Downloaded code

The `code/` directory contains two pinned differentiable-Schrödinger notebooks
from the challenge author's
[`wangleiphy/ml4p`](https://github.com/wangleiphy/ml4p) repository:

- `inverse_schrodinger_reference.ipynb`
- `neural_schrodinger_reference.ipynb`

Their source revision is recorded in `code/ml4p_commit.txt`. These are reference
implementations, not substitutes for the inaccessible official starting
notebook.

## Papers

`references/ref.bib` records all 14 references listed by the challenge:

- GRAPE, CRAB, discrete adjoints, adaptive hybrid control, and randomized
  benchmarking calibration;
- control-landscape topology, Hessian rank, and dynamic dimensionality;
- the neural-network Hessian analogy, glassy control, barren plateaus, and
  quantum-network overparameterization.

The nine arXiv papers and the open GRAPE paper were downloaded and rendered to
searchable Markdown under `references/rendered/`. Four closed DOI-only papers
have metadata entries but no local full text. Raw PDFs are intentionally
gitignored; `SHA256SUMS` records their checksums.

Verify tracked notebooks and local PDFs from this directory with:

```bash
sha256sum -c SHA256SUMS
```

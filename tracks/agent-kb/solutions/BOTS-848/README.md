# BOTS:848 — A Channel-Resolved DFPT Research Agent

## Team

| | |
|---|---|
| **Team name** | BOTS:848 |
| **Members** | Shaojie Tai, Huanjing Gong, Bohan Jia |

## Challenge

| Row | |
|---|---|
| **Challenge** | Investigate why DFPT remains effective across diverse materials and develop an AI-agent-guided, faster, more transparent framework for predicting electron-phonon interactions without substantial loss of accuracy. |
| **Catalog issue** | Addresses #35 — released by Kun Chen (Chen Kun), Institute of Theoretical Physics, Chinese Academy of Sciences. |
| **Track** | `agent-kb` |

## Result

We do not claim that charge conservation or a numerical cancellation proves DFPT universally. We propose a narrower, testable physical hypothesis:

> The leading error of static DFPT is controlled by which low-energy operator a phonon changes, the many-body susceptibility in that operator channel, and the momentum-frequency path of the response. Strong correlation changes the answer mainly when a mode has appreciable weight in an unprotected internal, nonlocal, interaction-modulation, or dynamic channel.

The submission turns that hypothesis into an AI-for-science artifact:

`literature -> typed claim ledger -> operator decomposition -> sparse anchors -> held-out error and cost gate -> falsifying calculation`

- `agent/` contains a reusable Agent Skill with explicit inputs, claim statuses, stop rules, and output contract.
- `knowledge/` contains source-traceable claims and material-mode cases in JSON-compatible YAML.
- `src/` contains a dependency-free prototype that decomposes a Hermitian DFPT perturbation, fits a small channel-response matrix from supplied anchors, scores held-out coefficient vectors, and compares DFPT-only, dense higher-level, and sparse-correction workflow costs.
- `eval/` measures decision accuracy, claim-status accuracy, citation coverage, and unsupported claims.
- `report/` contains the physics derivation, evidence matrix, two-day exploration protocol, source ledger, source LaTeX, and final PDF.

Reviewer entry points:

- [Reproduce the submission](REPRODUCE.md): fresh-checkout requirements, exact commands, expected outputs, PDF verification, and evidence-audit procedure.
- [Read the result argument](RESULTS.md): the physical picture, usefulness, correctness checks, limitations, and falsification tests in one short file.
- [Read the full scientific report](report/main.pdf): definitions, derivation, primary-source evidence, and the proposed validation program.

## What the Prototype Predicts

For localized site blocks, it constructs

```text
D = D_charge + D_internal + D_nonlocal
```

It can project these channels into a chosen low-energy basis, measure their normalized weights, apply one transparent static kernel per channel, and return one of:

- `dfpt-safe`: charge-dominated adiabatic calibration candidate;
- `static-correction`: appreciable internal or nonlocal weight;
- `dynamic-correction`: phonon and electronic relaxation scales are not well separated;
- `abstain`: sources, reference state, energy scale, or signal are insufficient.

The thresholds are declared calibration parameters, not universal accuracy bounds. Interaction-parameter derivatives such as dU/du remain outside the executable prototype.

## What the Sparse-Anchor MVP Adds

For coefficient vectors in a fixed, declared operator basis, the new response
model fits

```text
c_reference = K c_DFPT + residual
```

from supplied anchors. Diagonal entries of `K` rescale channels and off-diagonal
entries represent channel mixing. The bundled case trains on four transparent
synthetic anchors and predicts two synthetic held-out vectors. It verifies the
fitting and scoring software; it is not evidence of accuracy for a real material.

The current response model still consumes `c_DFPT` at every predicted point. Its
cost module therefore compares DFPT alone, DFPT plus a higher-level calculation
at every point, and DFPT plus four higher-level anchors and inexpensive inference.
Under the declared normalized inputs those costs are `100`, `600`, and `122`, so
the dense higher-level path costs `4.918` times as much as the corrected path, but
more expensive than DFPT alone. This is not a measured runtime speedup and it is
not evidence that the executable model is faster than DFPT.

## Quick Start

Only Python 3 is required for the prototype:

```bash
cd tracks/agent-kb/solutions/BOTS-848
make check
```

Expected summary:

```text
Ran 48 tests ... OK
BOTS:848 evaluation: 14/14 cases passed
decision_accuracy: 1.000
citation_coverage: 1.000
unsupported_claim_rate: 0.000
held-out synthetic: relative_rmse=2.711e-16
declared cost model: dfpt_only=100.000, dense_high_level=600.000, corrected=122.000, speedup_vs_dense_high_level=4.918, is_faster_than_dense_high_level=True, is_faster_than_dfpt=False, measured_runtime=False
physical_accuracy_established=False
```

Run the two channel-classification toys and the separate sparse-anchor software
contract:

```bash
python3 examples/run_example.py
python3 examples/run_sparse_anchor.py
```

Rebuild and inspect the research report when XeLaTeX, latexmk, BibTeX, and Poppler are installed:

```bash
make report-check
open report/main.pdf
```

## Evidence Included

The compact knowledge base routes to the primary sources and keeps their conventions separate:

- uniform electron gas: finite-q comparison through 2 k_F, including the difficult backscattering region;
- SrVO3: M-point Jahn-Teller 44 -> 87 meV and R-point breathing 58 -> 50 meV at omega=0 in the cited convention;
- CaCuO2: half-breathing 70 -> 76 meV, full-breathing 53 -> 45 meV at U=3.1 eV, plus strong frequency dependence at U=4.7 eV;
- CoO: a reference-state and Hubbard-occupation-response failure of ordinary DFPT;
- Ba1-xKxBiO3: a nonlocal GW perturbation-theory correction route.

These numbers are not compared across papers without checking basis, phonon eigenvector normalization, units, momentum, frequency, and observable. Exact source locations and limitations are stored in `knowledge/material_cases.yaml`.

## Verification and Limits

The unit suite checks exact reconstruction, traceless on-site internal blocks,
Hermiticity, local-unitary invariance, identity-kernel recovery, response-matrix
fitting and channel mixing, held-out scoring, cost break-even behavior, invalid
inputs, toy classifications, and evidence-driven abstention. The current
evaluation is a deterministic contract test of the included reference
implementation; it is not an end-to-end benchmark of an external language model,
a measured DFPT runtime comparison, or a real-material physical-accuracy result.

The first final physical test remains a held-out finite-momentum uniform-electron-gas benchmark. The hypothesis must be revised if channel weights fail to correlate with beyond-DFPT corrections, charge-dominated modes show large unexplained errors, every matrix element needs its own kernel, or dynamic effects eliminate a useful static regime.

## File Map

| Path | Purpose |
|---|---|
| `REPRODUCE.md` | Fresh-checkout reproduction guide and expected outputs |
| `RESULTS.md` | Human-readable argument for usefulness, credibility, and limits |
| `agent/SKILL.md` | Short discoverable Agent Skill |
| `agent/workflow.md` | Detailed scientific input/output and abstention contract |
| `knowledge/schema.yaml` | Machine-readable record schema |
| `knowledge/claims.yaml` | Typed claim ledger |
| `knowledge/material_cases.yaml` | Source-routed benchmark cases |
| `src/` | Channel decomposition, correction and response models, cost accounting, and decision gate |
| `tests/` | Numerical invariants and grounding contracts |
| `eval/` | Evaluation cases, runner, and recorded result |
| `examples/` | Common-shift and orbital-splitting toys plus a sparse-anchor synthetic contract |
| `report/main.pdf` | Full scientific report |
| `docs/superpowers/` | Approved design and executable implementation plan |

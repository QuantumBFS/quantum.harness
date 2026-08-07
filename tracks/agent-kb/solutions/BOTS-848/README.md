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

> The leading error of static DFPT is controlled by which low-energy operator a phonon changes, the many-body susceptibility in that operator channel, and the momentum-frequency path of the response. Strong correlation changes the answer mainly when a mode has appreciable weight in an unprotected `site_charge`, `internal`, `nonlocal`, separate two-body interaction-modulation, or dynamic channel.

The submission turns that hypothesis into an AI-for-science artifact:

`literature -> typed claim ledger -> operator decomposition -> sparse anchors -> held-out error and cost gate -> falsifying calculation`

- `agent/` contains a reusable Agent Skill with explicit inputs, claim statuses, stop rules, and output contract.
- `knowledge/` contains source-traceable claims and material-mode cases in JSON-compatible YAML.
- `src/` contains a dependency-free prototype that decomposes a supported Hermitian DFPT perturbation into four one-body channels, fits a small response matrix from supplied fixed-basis one-body anchors, scores held-out coefficient vectors, and compares DFPT-only, dense higher-level, and sparse-correction workflow costs.
- `eval/` measures decision accuracy, claim-status accuracy, citation coverage, and unsupported claims.
- `report/` contains the physics derivation, evidence matrix, two-day exploration protocol, source ledger, source LaTeX, and final PDF.

Reviewer entry points:

- [Reproduce the submission](REPRODUCE.md): fresh-checkout requirements, exact commands, expected outputs, PDF verification, and evidence-audit procedure.
- [Read the result argument](RESULTS.md): the physical picture, usefulness, correctness checks, limitations, and falsification tests in one short file.
- [Read the full scientific report](report/main.pdf): definitions, derivation, primary-source evidence, and the proposed validation program.

## What the Prototype Predicts

For localized site blocks, it constructs four mutually Hilbert--Schmidt-orthogonal
one-body channels:

```text
D = D_global_charge + D_site_charge + D_internal + D_nonlocal
```

- `global_charge` is the single identity operator inside the complete declared
  projection basis. It is an algebraic channel, not automatically the conserved
  total-charge direction of the full electronic Hilbert space.
- `site_charge` contains site/block identity shifts relative to that global
  average.
- `internal` is traceless inside every site block.
- `nonlocal` contains the inter-site blocks.

The Ward anchor is allowed only when the original, unprojected perturbation is
verified to be a strict uniform `q=0` common shift under a declared energy-zero
and chemical-potential convention. Finding `P_c D P_c` proportional to identity
is insufficient because the omitted and cross-subspace blocks can differ; the
gate therefore also requires `full_space_common_shift: true`. `site_charge` is a
correction-risk channel even though it is locally proportional to identity. The executable Hermitian API accepts a real-space
displacement derivative, a Gamma perturbation, or a real standing-wave
combination of `q` and `-q`. A general fixed-`q` perturbation instead obeys
`D(q)^dagger = D(-q)` and is outside this API.

The prototype can project the four channels into a chosen low-energy basis,
measure their normalized weights, apply one transparent finite real static kernel
per channel, and return one of four outputs:

- `dfpt-safe`: `global_charge` dominated, explicitly verified strict uniform
  `q=0` full-space common shift, and adiabatic calibration candidate;
- `static-correction`: appreciable `site_charge`, `internal`, or `nonlocal`
  weight;
- `dynamic-correction`: phonon and electronic relaxation scales are not well separated;
- `abstain`: sources, reference state, energy scale, or signal are insufficient.

The thresholds are declared calibration parameters, not universal accuracy bounds.
Interaction-parameter derivatives such as `dU/du` and `dJ/du` are two-body
vertices in a separate operator space; they are not components of this one-body
decomposition and remain outside the executable prototype.

## What the Sparse-Anchor MVP Adds

For coefficient vectors of a one-body inverse-Green-function vertex in one fixed,
declared operator basis, the response model fits

```text
c_reference = K c_DFPT + residual
```

from supplied anchors. Diagonal entries of `K` rescale channels and off-diagonal
entries represent channel mixing. Quasiparticle external-leg factors
`Z^(1/2)` and quasiparticle-state rotations are separate transformations; they
must not be silently included in some anchors but omitted from others. The
bundled case trains on four transparent
synthetic anchors and predicts two synthetic held-out vectors. It verifies the
fitting and scoring software; it is not evidence of accuracy for a real material.
Its three coefficients are labeled `global_charge`, `internal`, and
`nonlocal`; `site_charge` is zero/omitted by construction, so this example is
not a complete four-channel physical validation.

The current response model still consumes `c_DFPT` at every predicted point. Its
cost module therefore compares DFPT alone, DFPT plus a higher-level calculation
at every point, and DFPT plus four higher-level anchors and inexpensive inference.
Under the declared normalized inputs those costs are `100`, `600`, and `122`, so
the dense higher-level path costs `4.918` times as much as the corrected path,
while the corrected path remains more expensive than DFPT alone. This is not a measured runtime speedup and it is
not evidence that the executable model is faster than DFPT.

## Quick Start

Only Python 3 is required for the prototype:

```bash
cd tracks/agent-kb/solutions/BOTS-848
make check
```

Expected summary of the bundled software contract (not a material calculation):

```text
Ran 82 tests ... OK
BOTS:848 evaluation: 14/14 cases passed
decision_accuracy: 1.000
citation_coverage: 1.000
unsupported_claim_rate: 0.000
held-out synthetic: relative_rmse=2.653e-16
declared cost model: dfpt_only=100.000, dense_high_level=600.000, corrected=122.000, speedup_vs_dense_high_level=4.918, is_faster_than_dense_high_level=True, is_faster_than_dfpt=False, measured_runtime=False
physical_accuracy_established=False
```

The 82-test and 14-case counts, the synthetic RMSE, and the normalized cost
numbers establish only the declared software behavior. They do not provide a
real-material response matrix `K`, physical held-out accuracy, or measured
acceleration.

Run the two channel-classification toys and the separate sparse-anchor software
contract:

```bash
python3 examples/run_example.py
python3 examples/run_sparse_anchor.py
```

Rebuild and inspect the research report when XeLaTeX, latexmk, BibTeX, and Poppler are installed:

```bash
make report-check
open report/build/main.pdf
```

## Evidence Included

The compact knowledge base routes to the primary sources and keeps their conventions separate:

- uniform electron gas: finite-q comparison through 2 k_F, with backscattering the least-controlled exception; in the report convention the complete ratio is
  `K_total = z Gamma_rho [1-(v+f_xc)chi_s]/[1-v P_MB]`, and the cited scalar
  matching gives `K_total approximately 1` rather than a second `P_MB/chi_s`
  factor to multiply onto screened DFPT;
- SrVO3: M-point Jahn-Teller 44 -> 87 meV and R-point breathing 58 -> 50 meV at omega=0 in the cited convention; the finite-R breathing mode is `site_charge`-like only in the paper's 2x2x2 real-displacement supercell/standing-wave representation, where V-site blocks alternate in phase;
- CaCuO2: half-breathing 70 -> 76 meV, full-breathing 53 -> 45 meV at U=3.1 eV, plus strong frequency dependence at U=4.7 eV;
- CoO: a reference-state and Hubbard-occupation-response failure of ordinary DFPT;
- Ba1-xKxBiO3: a nonlocal GW perturbation-theory correction route.

These numbers are not compared across papers without checking basis, phonon eigenvector normalization, units, momentum, frequency, and observable. The
Abramovitch values are controls within that paper's declared setup, not independent
cross-code accuracy benchmarks. Exact source locations and limitations are stored
in `knowledge/material_cases.yaml`.

## Verification and Limits

The unit suite checks exact four-channel reconstruction, orthogonality, traceless
on-site `internal` blocks, Hermiticity in the supported input domain,
local-unitary invariance, identity-kernel recovery, response-matrix
fitting and channel mixing, held-out scoring, cost break-even behavior, invalid
inputs, toy classifications, and evidence-driven abstention. The current
evaluation is a deterministic contract test of the included reference
implementation; it is not an end-to-end benchmark of an external language model,
a measured DFPT runtime comparison, or a real-material physical-accuracy result.

The first final physical test remains a held-out finite-momentum uniform-electron-gas benchmark of the complete physical-to-DFPT ratio. It is a theory/data
calibration until a paired `q/-q` or real-space interface exists, not an executable
continuous-fixed-`q` claim. The hypothesis must be revised if channel weights fail
to correlate with beyond-DFPT corrections, nonuniform density modes show large
unexplained errors, every matrix element needs its own kernel, or dynamic effects
eliminate a useful static regime.

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
| `examples/` | Strict common-shift and orbital-splitting toys plus a sparse-anchor synthetic software contract |
| `report/main.pdf` | Full scientific report |
| `docs/superpowers/` | Approved design and executable implementation plan |

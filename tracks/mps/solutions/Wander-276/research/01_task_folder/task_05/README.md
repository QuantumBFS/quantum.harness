# Task 05 — Protected Response Complex and Geometric ETH

This task asks a falsifiable question inside an exactly degenerate manifold: after matching registered two-point response data, does a gauge-invariant four-channel statistic follow a Gaussian Wick law? Across the completed finite-size $N=8$--$14$ sequence, the answer is no for both preregistered separable covariance nulls.

## Physics Object

For a protected projector (P(\lambda)), define (X_a=(1-P)\partial_aP). Then

$$\mathcal Q_{ab}=X_a^\dagger X_b,\qquad g_{ab}=\tfrac12(\mathcal Q_{ab}+\mathcal Q_{ba}),\qquad F_{ab}=i(\mathcal Q_{ab}-\mathcal Q_{ba}).$$

The (\mathcal N=2) SYK supercharge (Q=\sum_{i<j<k}C_{ijk}\psi_i\psi_j\psi_k) obeys (Q^2=0). In a fixed charge sector, its BPS fiber is harmonic cohomology and its parameter response splits exactly as

$$X=-H_\perp^+(Q\,\delta Q^\dagger+Q^\dagger\delta Q)P=X_-\oplus X_+,qquad X_-^\dagger X_+=0.$$

This exact/coexact decomposition is independent of the one-sided (H=B^\dagger B) Laughlin parent response.

## Registered Design

| Stage | Sizes | Role |
|---|---|---|
| Sequential pilot | (N=8,10,12) | Fix observable, covariance signatures, controls, and inference branches |
| Held out | (N=14) | Freeze predictions from safe covariates, seal them, then explicitly unseal outcomes |

Each size contains central/adjacent charge sectors and sparse/isotropic eight-channel tangent panels. The primary held-out pair is the central/adjacent sparse pair; the isotropic pair is secondary and cannot change the selected branch.

The frozen branches are: both covariance nulls cover; only the Hodge null covers; both reject with reproducible response memory; the generic response is indistinguishable from the structured control; or feasibility failure. Independent seal validation and explicit opening select `cohomological_non_gaussian_class`.

## Held-Out Result

| $N=14$ sparse sector | Physical median (95% bootstrap) | Collapsed null (97.5% prediction) | Hodge null (97.5% prediction) |
|---|---:|---:|---:|
| Adjacent | 0.301529 [0.291527, 0.312061] | [0.111789, 0.111852] | [0.112344, 0.112513] |
| Central | 0.374993 [0.368980, 0.380473] | [0.111338, 0.111353] | [0.111333, 0.111348] |

The result identifies structured four-point response memory beyond the frozen separable collapsed/Hodge null family. It does not establish intrinsic non-Gaussianity after complete nonseparable entrywise covariance matching.

## Minimal Verification

```bash
cd script
PYTHONPATH=. pytest -q $(rg --files tests | rg 'v7\.py$')
python generate_susy_hodge_controls_v7.py
python verify_susy_hodge_delivery_v7.py
python verify_susy_hodge_manuscript_v7.py
```

## Build the Delivery

```bash
cd script
bash run_susy_hodge_delivery_v7.sh
```

The script merges the pilot, generates the final result figure and report from frozen artifacts, activates result macros only after the audits pass, compiles the Letter and Supplemental Material, copies the exact PDFs into `script/output/`, and verifies their hashes and render state.

## Artifact Map

| Artifact | Meaning |
|---|---|
| `output/susy_hodge_v7_outcomes_pilot_combined.json/.npz` | Complete (N=8,10,12) pilot |
| `output/susy_hodge_v7_N14_covariates.json` | Outcome-free held-out covariates |
| `output/susy_hodge_v7_N14_prediction.json/.npz/.sha256` | Frozen numerical predictions and seal |
| `output/susy_hodge_v7_N14_unsealed.json/.npz` | Explicitly opened outcome payload |
| `output/susy_hodge_v7_N14_inference.json` | Frozen-branch decision |
| `output/susy_hodge_v7_controls.json` | Analytic and synthetic controls |
| `output/figure_susy_hodge_geometric_eth_v7.*` | Main data figure and provenance manifest |
| `output/response_complex_memory_v7.pdf` | Final Letter |
| `output/response_complex_memory_supplement_v7.pdf` | Final Supplemental Material |
| `output/susy_hodge_delivery_audit_v7.json` | Scientific/provenance audit |
| `output/susy_hodge_manuscript_audit_v7.json` | Paper/PDF audit |

## Interpretation Boundary

The operational label `cohomological_non_gaussian_class`, if selected, means four-point response memory beyond the frozen separable collapsed and Hodge covariance nulls. It does not establish failure of every fully nonseparable Gaussian covariance model. No (N=8\)–(14) result is presented as asymptotic Geometric ETH.

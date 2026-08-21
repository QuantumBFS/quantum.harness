# PR submission draft

The live target is the existing Quantum Harness Issue #276 and its open PR #283; no duplicate issue is needed.

## PR title

```text
🌠Wander: Issue #276 Exactly Degenerate Quantum Chaos and Geometric Response
```

## PR body

Related issue: `#276`

This PR delivers two back-to-back, independently audited manuscripts on quantum chaos in exactly degenerate state spaces.

Paper I, *Exactly Degenerate Quantum Chaos: Non-Abelian Quantum Geometry as a Probe*, asks what remains measurable when the connected energy spectral form factor vanishes identically. Across frustration-free Laughlin/FCI parents, Moore–Read clustering, supersymmetric cohomology, and stabilizer controls, it separates protected intrafiber degeneracy from off-fiber projector motion. The result is finite-size and mechanism resolved: local geometric correlations can be random-matrix-like while global covariance, topology, and protection mechanism retain structure.

Paper II was prospectively result-gated. It proves an exact weighted-channel fourth-cumulant identity under independence, centering, deterministic weights, finite fourth moments, and a common response space. A sealed chiral-index calculation then tests the parameter-free (N_{\mathrm{eff}}) specialization. The random-channel values (1.2903, 1.3650, 1.4814) lie above the registered simultaneous band ([0.4476,1.2352]). The selected branch is therefore `random_channel_failure`, and the delivered title is the bounded *Geometric Response of Exactly Degenerate Quantum State Bundles*. The PR does not claim an established asymptotic or universal Geometric ETH.

## Delivered artifacts

| Item | Result |
|---|---|
| Paper I main / supplement | 23 / 11 pages; seven vector figures; delivery audit passed |
| Paper II main / supplement | 18 / 8 pages; six vector figures; delivery audit passed |
| Paper I archived PDF SHA-256 | `257b1c10e75f7104d4a70afbd3b9c9056e197036a5f4c216f3789af8c513746a` |
| Paper II archived PDF SHA-256 | `45984eed2daa8df1c741a5924287664a3c0b9508389be8681232a91ed54c0d20` |
| Cross-paper manifest | `01_task_folder/task_05/script/output/two_paper_delivery_v14/two_paper_manifest_v14.json` |
| Claim boundary | finite-size Paper I; conditional theorem and failed prospective closure in Paper II |

## Reproduction

```bash
bash 01_task_folder/task_05/script/run_paper1_prb_delivery_v13.sh
bash 01_task_folder/task_05/script/run_geometric_eth_theory_delivery_v14.sh
python3 01_task_folder/task_05/script/verify_two_paper_delivery_v14.py
```

Each paper has an independent source tree, evidence or literature registry, generated assets, figure manifest, tests, archived PDFs, and fail-closed delivery audit. The delivery commands rebuild both manuscripts from frozen numerical evidence; the reproducibility note separately gives the non-overwriting Paper II scientific recalculation. The combined verifier checks both delivery audits, all four PDF hashes, the Paper II failure branch and fallback title, the planning-contract hashes, and the shared nonclaims.

## Reviewer route

1. Read the two abstracts and Paper I Fig. 1.
2. Inspect Paper I Figs. 4 and 7 for channel separation and mechanism dependence.
3. Read Paper II Theorem 1 and the assumptions immediately preceding its (N_{\mathrm{eff}}) corollary.
4. Inspect Paper II Fig. 6 and confirm that the failed random-channel test is reported before its interpretation.
5. Run the three commands above and compare the manifest hashes.

## Team

| Field | Value |
|---|---|
| **Team name** | Wander |
| **Members** | Chenxi Wan, Yedi Shen, Junkai Wang |
| **Contact email** | WangTheoPhys@outlook.com |

## Checklist

- [x] Two independent REVTeX source trees and supplements
- [x] Exact-degeneracy, gap, gauge, covariance, and claim-boundary gates
- [x] Primary-source citation audits
- [x] Vector figures with source hashes and 300-dpi previews
- [x] Deterministic archived PDFs and page-level visual checks
- [x] A failed positive-title gate reported without refitting or renaming it as success
- [x] Bind the package to live Issue #276
- [x] Push the final package and update open PR #283 against `QuantumBFS/quantum.harness:main`

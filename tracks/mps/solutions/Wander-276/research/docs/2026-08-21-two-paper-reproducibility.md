# Reproducing the two-paper exact-degeneracy release

Run from the repository root with the Python and LaTeX dependencies already used by the task-local delivery scripts.

## Frozen-artifact manuscript rebuilds

```bash
bash 01_task_folder/task_05/script/run_paper1_prb_delivery_v13.sh
bash 01_task_folder/task_05/script/run_geometric_eth_theory_delivery_v14.sh
```

The commands regenerate the registered manuscript assets and figures, run the paper-level test suites, compile the main text and supplement, inspect LaTeX logs and PDF structure, render every page, and compare the archived PDFs with clean rebuilds. They verify the sealed numerical artifacts but deliberately do not overwrite and recompute the Paper II prediction, production outcomes, or inference files. They contain no upload, push, or journal-submission action.

## Paper II scientific recalculation

The prospective calculation can be repeated into a temporary directory without changing the canonical seal. This path takes longer than the manuscript rebuild:

```bash
recalc_dir="$(mktemp -d)"
python3 01_task_folder/task_05/script/derive_geometric_eth_channel_theory_v14.py \
  --output "${recalc_dir}/channel_theory_v14.json"
python3 01_task_folder/task_05/script/seal_chiral_kernel_prediction_v14.py \
  --channel-theory "${recalc_dir}/channel_theory_v14.json" \
  --prediction "${recalc_dir}/chiral_prediction_v14.json" \
  --sidecar "${recalc_dir}/chiral_prediction_v14.sha256" \
  --outcomes "${recalc_dir}/chiral_outcomes_v14.json"
python3 01_task_folder/task_05/script/run_chiral_kernel_geometric_eth_v14.py \
  --prediction "${recalc_dir}/chiral_prediction_v14.json" \
  --sidecar "${recalc_dir}/chiral_prediction_v14.sha256" \
  --output "${recalc_dir}/chiral_outcomes_v14.json"
python3 01_task_folder/task_05/script/analyze_chiral_kernel_geometric_eth_v14.py \
  --prediction "${recalc_dir}/chiral_prediction_v14.json" \
  --sidecar "${recalc_dir}/chiral_prediction_v14.sha256" \
  --outcomes "${recalc_dir}/chiral_outcomes_v14.json" \
  --output "${recalc_dir}/chiral_inference_v14.json"
```

The production runner uses 64 base matrices, 16 tangents, three tangent classes, and three validation sizes. The checked-in paper delivery treats the resulting seal and outcomes as immutable evidence and revalidates their hashes and branch logic.

## Cross-paper integrity check

```bash
python3 01_task_folder/task_05/script/verify_two_paper_delivery_v14.py
PYTHONPATH=01_task_folder/task_05/script python3 -m pytest -q \
  01_task_folder/task_05/script/tests/test_two_paper_delivery_v14.py
```

The verifier checks:

- both paper-level delivery audits are passed;
- all four archived PDFs exist and match their registered SHA-256 values;
- Paper II remains on `random_channel_failure`;
- the positive Paper II title gate remains false;
- the fallback title has not been replaced by *The Geometric ETH*;
- the shared asymptotic, universal, independent-ensemble, and black-hole nonclaims remain false;
- the two-paper design and both implementation plans retain their registered hashes.

## Canonical documents

| Document | Pages | SHA-256 |
|---|---:|---|
| Paper I main | 23 | `257b1c10e75f7104d4a70afbd3b9c9056e197036a5f4c216f3789af8c513746a` |
| Paper I supplement | 11 | `63d20a5149fd3f7f85c9f0a2e3b7c3be2025d1699508be7c14760a234af909a1` |
| Paper II main | 18 | `45984eed2daa8df1c741a5924287664a3c0b9508389be8681232a91ed54c0d20` |
| Paper II supplement | 8 | `ab98b5a39117c7f412df4e62c0b76eb7e31e85ac6911af7c7ff0039fd83d18c9` |

## Expected scientific branch

Successful reproduction does not mean that the proposed Geometric ETH closure passed. It means the calculation and its negative branch reproduce exactly. Paper II must end with:

```text
selected_branch = random_channel_failure
positive_title_gate = false
selected_title = Geometric Response of Exactly Degenerate Quantum State Bundles
```

Any run that silently changes those values, drops the third complex Wick pairing, rewrites the prospective seal, or presents the failed closure as an established law is not this release.

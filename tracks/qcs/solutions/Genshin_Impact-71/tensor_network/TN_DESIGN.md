# Issue 71 tensor-network arm: preregistered pilot

## Security and evidence boundary

- Only official `train.csv` files are read by training and rank diagnostics.
- Strict ASCII/shape validation rejects malformed CSV rows and duplicate inputs.
- Training code contains no `eval`, `exec`, subprocess, shell, network, pickle,
  or dynamic import path.
- No competitor PR prose or code is consumed.
- Full arithmetic truth is isolated in `tn_truth.py`; `train_mps.py` and
  `rank_diag.py` never import it. `audit_mps.py` imports it only after a model
  artifact and SHA-256 are frozen.

## Pilot hypotheses

1. LSB-interleaved order should expose a lower train-unfolding completion rank
   and better low-bond MPS generalization for addition than blocked order.
2. Even the 4-by-4 multiplication warmup should require a larger effective
   bond than addition, foreshadowing the known one-dimensional MPS/OBDD
   bottleneck for multiplication.
3. A continuous MPS can be a useful hypothesis-discovery diagnostic, but a
   thresholded continuous fit is not by itself a legal small Boolean circuit.

## Algorithms

- Rank proxy: for every order/cut/output bit, fit real low-rank matrix
  completions at ranks 1, 2, 4, and 8 using only an 80% split of official
  training coordinates. Report held-out sign accuracy, RMSE, and category
  coverage. This is explicitly a proxy, not an exact hidden-rank certificate.
- MPS baseline: one scalar real MPS per output bit, one-site alternating ridge
  least squares, QR gauge transport, deterministic PCG inner solves, root seed
  42, and an 80/20 train-only split.
- Pilot sweep: both warmups, blocked-LSB and interleaved-LSB order, maximum bond
  2 and 4, ridge 1e-5, at most 6 sweeps, patience 2.
- Audit: exhaustive 256-input evaluation after each frozen model. Exact
  full-target Boolean and signed TT ranks are computed only as audit diagnostics.

## Promotion criteria

The full A/B/C/D sweep is promoted only if the pilot:

- completes without non-finite values or parser/audit failures;
- shows at least one configuration above chance on held-out rows;
- writes complete JSON reports, model hashes, and a completion sentinel.

The full sweep will compare all four fixed variable orders and bonds
2, 4, 8, and 16. No full-domain metric will select a hyperparameter.

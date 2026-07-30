# Issue 71 tensor-network arm: promoted full sweep (v2)

Pilot job 42645 met the preregistered promotion criteria. The full sweep uses
only official training coordinates and self-written, audited code.

## Fixed matrix

- 16 train-only unfolding-rank cells: four mystery instances by four fixed
  orders, completion ranks 1, 2, 4, 8, and 16, eight ALS iterations.
- 64 train-only MPS cells: four instances by four fixed orders by maximum bond
  2, 4, 8, and 16, ridge 1e-5, six sweeps, patience two, root seed 42.
- Every MPS cell freezes a model and SHA-256 before launching the independent
  full-domain audit process.
- Model choice inside each instance/order uses validation exact accuracy, then
  validation bit accuracy, then lower validation RMSE, then smaller bond.
  Full-domain metrics never select a model or hyperparameter.

## Resource estimate

The warmup pilot completed 8 MPS configurations and 4 rank diagnostics in
about 84 seconds on 4 requested CPU cores. The promoted instances have at most
2000 samples, 16 sites, 12 outputs, and maximum bond 16. The largest one-site
feature block is at most about 1000 by 256 float64 values (about 2 MiB);
rank-factor arrays and 256 by 256 audit matricizations are also small. Each
independent task requests 1 CPU and 4--6 GiB, with at most 16 concurrent tasks.
The 1 h rank and 2 h MPS limits are conservative relative to the pilot.

## Interpretation guardrail

A continuous thresholded MPS with any full-domain mismatch is not exact Boolean
recovery and is not a legal candidate circuit, regardless of its bit accuracy.

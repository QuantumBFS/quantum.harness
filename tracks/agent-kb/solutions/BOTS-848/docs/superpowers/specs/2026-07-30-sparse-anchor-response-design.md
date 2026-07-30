# Sparse-Anchor Channel Response Design

## Objective

Extend the BOTS:848 channel-resolved DFPT prototype into an honest quantitative
software MVP.  The extension must learn a small response matrix from supplied
channel-coefficient anchors, predict held-out coefficients, report numerical
error, and state explicitly whether a sparse workflow is cheaper than its
declared dense-DFPT baseline.

The extension does not claim validated accuracy for a real material.  Its bundled
dataset is a transparent synthetic contract case that verifies the fitting,
prediction, held-out scoring, and cost-accounting path.  Physical accuracy remains
a separate experiment requiring convention-matched DFPT and beyond-DFPT data.

## Scientific Claim

For a fixed localized, symmetry-adapted operator basis, let `x_s` contain the DFPT
coefficients for anchor `s` and let `y_s` contain reference coefficients obtained
from a declared higher-level calculation or experiment-linked inference.  The
minimum static hypothesis is

```text
y_s = K x_s + residual_s,
```

where `K` is a small channel-response matrix shared only inside a declared
calibration domain.  Diagonal entries rescale a channel; off-diagonal entries
represent channel mixing.  `K = I` recovers the DFPT coefficient vector.

This is a stronger and more falsifiable statement than the existing manual scalar
kernel interface.  It does not imply that the full electron-phonon matrix element
is globally low rank, that all electrons feel the same potential shift, or that a
Ward identity constrains non-charge channels.  A real-material application must
separate analytic long-range fields from localized short-range operators before
fitting and must define the operator basis, gauge, momentum, frequency, and
normalization convention.

## Software Architecture

### Response fitting

Create `src/response_model.py` with three public functions:

- `fit_response_matrix(inputs, targets, ridge=0.0)` validates rectangular numeric
  samples and solves the multi-output ridge problem using standard-library complex
  arithmetic and Gaussian elimination;
- `predict_coefficients(model, inputs)` applies the fitted matrix to one or more
  coefficient vectors;
- `error_metrics(predicted, reference)` returns root-mean-square error, relative
  root-mean-square error, and maximum absolute error.

The fitted model is a JSON-serializable dictionary containing the response matrix,
channel count, anchor count, ridge strength, and training error.  A singular
unregularized fit must fail with a useful error instead of silently inventing a
solution.

### Cost accounting

Create `src/cost_model.py` with `compare_sparse_to_dense(...)`.  It compares:

```text
dense_cost = campaigns * full_points * dfpt_cost_per_point

sparse_cost = training_cost
            + campaigns * (
                anchor_points * dfpt_cost_per_point
                + high_level_anchors * high_level_cost_per_anchor
                + (full_points - anchor_points) * inference_cost_per_point
              ).
```

The output reports both totals, `speedup = dense_cost / sparse_cost`, and a boolean
`is_faster`.  No documentation may claim a speedup unless the supplied parameters
make `is_faster` true.  The comparison is an accounting model, not a measured
runtime benchmark; a future physical benchmark must compare against a converged,
symmetry-reduced DFPT plus interpolation workflow.

### Reproducible example

Add one JSON-compatible YAML case with a known three-channel response matrix,
separate training and held-out coefficient vectors, and explicit cost assumptions.
The example runner must fit without reading the hidden matrix, predict the held-out
targets, print error metrics, print the dense and sparse costs, and print whether
the declared case is faster.

## Documentation Contract

The reviewer-facing documents and report must distinguish three claims:

1. the existing operator decomposition and new fitting/cost paths are executable
   and reproducible;
2. the bundled synthetic held-out result verifies software behavior only;
3. physical accuracy and real speedup over modern DFPT plus interpolation remain
   unproven until measured on convention-matched material data.

The report must replace any blanket statement that the method is faster than DFPT
with a conditional amortization statement.  It may say that the correction layer
can be much cheaper than evaluating a beyond-DFPT vertex everywhere, and that a
sparse surrogate can beat dense DFPT only when the number of anchors is small
enough to overcome fitting and inference overhead.

## Verification

- Unit tests must demonstrate response-matrix identity recovery, off-diagonal
  mixing recovery, held-out prediction, shape/type validation, singular-fit
  failure, cost break-even behavior, and rejection of invalid costs.
- `make check` must run the new example in addition to all existing tests,
  evaluation cases, and knowledge parsing.
- `make report-check` must rebuild the PDF with no unresolved references or
  overfull boxes.
- Every PDF page must be rendered and visually inspected after the final build.
- The final git diff must remain inside `tracks/agent-kb/solutions/BOTS-848/`.

## Non-goals

- No production Quantum ESPRESSO, EPW, ABACUS, or Wannier parser.
- No claim that synthetic held-out accuracy transfers to a material.
- No learned frequency dependence, uncertainty calibration, active learning, or
  interaction-modulation channel in this minimum extension.
- No replacement of the mature DFPT phonon calculation in a one-off small job.

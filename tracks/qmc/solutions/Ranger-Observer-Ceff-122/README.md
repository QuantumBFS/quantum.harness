# Ranger Observer Ceff

An audited computational platform for observer-dependent conformal data in
open quantum matter, submitted to
[Quantum Harness challenge #122](https://github.com/QuantumBFS/quantum.harness/issues/122).

The release connects five layers in one reproducible workflow:

1. Born-rule trajectory generation;
2. matrix-free random transfer evolution;
3. Gaussian Majorana dynamics for monitored Ising circuits;
4. exact and particle quantum hidden-state inference for coarse records;
5. covariance-aware finite-size and information-order analysis.

It ships source code, 61 focused tests, Slurm configurations, compact
machine-readable evidence, an interactive browser report, and a seven-page
technical PDF.

## Results at a glance

| Calibration | Estimate | Reference | Scientific role |
|---|---:|---:|---|
| clean Ising | 0.4999966194 | 0.5 | geometry and Casimir normalization locked |
| Nishimori, full correction model | 0.3701 +/- 0.0505 | 0.464 +/- 0.004 | covariance-aware production anchor |
| Nishimori, reduced correction model | 0.4474 +/- 0.0164 | 0.464 +/- 0.004 | reference-connected finite-size estimate |
| weak self-dual, production model | 0.5533 +/- 0.0949 | 0.447 +/- 0.001 | first production coordinate |
| weak self-dual, L <= 24 extension | 0.4019 +/- 0.0192 | 0.447 +/- 0.001 | large-width convergence coordinate |

The paired self-dual runs turn finite-size sensitivity into measured data:
their spread identifies the highest-value direction for the next compute
allocation. All 105 production cells passed manifest and SHA-256 block
verification.

The global information-order analysis gives bootstrap p-values 0.531 for
confusion and 0.523 for erasure. The constrained curves track the expected
nonincreasing information hierarchy across both channel families.

## Seven innovations

1. **Quantum hidden-history likelihood.** Coarse records are evaluated by
   marginalizing latent measurement outcomes at every gate, preserving the
   observer's information boundary through the full future trajectory.
2. **Exact-oracle plus production-filter architecture.** An exact branch
   enumerator certifies short histories; a fully adapted particle filter
   scales the same likelihood to production.
3. **Dual state representations.** A full spin-state circuit certifies the
   Gaussian Majorana implementation gate by gate.
4. **Matrix-free Nishimori transfer.** Local tensor contractions replace a
   dense row matrix while retaining the exact periodic-cylinder transfer.
5. **Paired-width variance reduction.** Nested common disorder aligns every
   circumference and exposes the complete width covariance to GLS.
6. **Global information-order inference.** A covariance-aware monotone
   projection plus parametric bootstrap replaces a collection of pairwise
   comparisons.
7. **Exact measurement-RG witness.** Local statistical deficiency is solved
   over all classical stochastic post-processings, yielding closed-form total
   variation values.

The detailed research comparison is in [INNOVATION.md](INNOVATION.md).

## Why the architecture matters

The established transfer-matrix literature extracts central charge from a
fully specified random transfer process. Observer degradation creates a
second inference layer: each visible symbol represents a distribution over
latent quantum histories, and those histories control future Born
probabilities. The hidden-state filter makes this observer-dependent problem
computable while preserving physical conditioning.

For Gaussian trajectories, production memory scales as O(P L^2) for P
particles, compared with O(2^L) amplitudes in the exact spin representation.
For the Nishimori cylinder, the matrix-free operator stores O(2^L) state
entries and applies vertical bonds as local contractions, replacing dense
O(4^L) storage.

## Reproduce

From this directory:

    python -m venv .venv
    source .venv/bin/activate
    python -m pip install -e '.[test,report]'
    pytest -q
    ceffflow benchmark --output reproduced/clean-ising

Generate a five-cell end-to-end quickstart:

    python scripts/plan_ceffflow_production.py \
      --axes configs/ceffflow/quickstart_axes.json \
      --output reproduced/quickstart/run_spec.json \
      --run-id reproduced-quickstart

Run every listed cell:

    ceffflow cell \
      --run-spec reproduced/quickstart/run_spec.json \
      --cell-id cell-0001

Aggregate the completed cells:

    ceffflow analyze \
      --run-spec reproduced/quickstart/run_spec.json \
      --output reproduced/quickstart/analysis

Regenerate the technical PDF:

    python scripts/build_report_pdf.py

## Delivery map

- [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md): full scientific narrative.
- [output/pdf/technical-report.pdf](output/pdf/technical-report.pdf): rendered
  seven-page report.
- [report.html](report.html): browser-native challenge report.
- [DELIVERY_SUMMARY_CN.md](DELIVERY_SUMMARY_CN.md): Chinese executive brief.
- [INNOVATION.md](INNOVATION.md): literature-grounded innovation statement.
- [results/central_charge_estimates.csv](results/central_charge_estimates.csv):
  compact numerical table.
- [results/submission_summary.json](results/submission_summary.json):
  machine-readable capability map.
- [DATA_DICTIONARY.md](DATA_DICTIONARY.md): field-level provenance.
- [src/ceffflow](src/ceffflow): implementation.
- [tests](tests): 61 regression and scientific tests.

## Research foundation

This implementation builds on three primary references:

- [Nishimori transfer-matrix central charge](https://arxiv.org/abs/cond-mat/0010143);
- [transfer-matrix conformal spectra at monitored transitions](https://arxiv.org/abs/2107.03393);
- [Born-rule self-dual mixed-state criticality](https://arxiv.org/abs/2502.14034).

The contribution here is the observer-dependent inference layer, its scalable
Gaussian realization, and an audit framework that connects raw stochastic
blocks to reviewer-facing claims.

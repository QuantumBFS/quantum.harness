# Reproduce the BOTS:848 Submission

This guide reproduces the executable result, the recorded evaluation, two
channel-classification toys, one sparse-anchor synthetic held-out prediction,
the declared cost comparison, and the human-readable report. The software path
uses only the Python standard library. It does **not** rerun the external DFPT,
DFT+DMFT, DFPT+U, GWPT, or diagrammatic Monte Carlo calculations cited by the
report.

## 1. Requirements

For the executable checks:

- Git;
- GNU Make or a compatible `make`;
- Python 3.10 or newer.

No third-party Python package is required. Files ending in `.yaml` use the
JSON-compatible YAML subset and are read with Python's standard-library
`json` module; PyYAML is not needed.

For rebuilding and checking the PDF, also install XeLaTeX, `latexmk`, BibTeX,
and Poppler (`pdfinfo`).

## 2. Fresh Checkout

```bash
git clone --branch challenge/agent-kb-electron-phonon --single-branch \
  https://github.com/AroundPeking/quantum.harness.git
cd quantum.harness/tracks/agent-kb/solutions/BOTS-848
git rev-parse HEAD
```

Record the printed commit SHA with any reproduced result. When reviewing a pull
request, use its exact head commit rather than assuming the branch has not moved.

## 3. One-Command Software Reproduction

Run:

```bash
make check
```

The important success lines are:

```text
Ran 82 tests ... OK
BOTS:848 evaluation: 14/14 cases passed
decision_accuracy: 1.000
claim_status_accuracy: 1.000
citation_coverage: 1.000
unsupported_claim_rate: 0.000
held-out synthetic: rmse=3.049e-16, relative_rmse=2.653e-16, max_abs_error=6.661e-16
declared cost model: dfpt_only=100.000, dense_high_level=600.000, corrected=122.000, speedup_vs_dense_high_level=4.918, is_faster_than_dense_high_level=True, is_faster_than_dfpt=False, measured_runtime=False
physical_accuracy_established=False
```

The exact ordering of unit-test lines and elapsed time may differ. A nonzero
exit status means the reproduction failed.

The same checks can be run separately:

```bash
python3 -m unittest discover -s tests -v
python3 eval/evaluate.py
python3 examples/run_example.py
python3 examples/run_sparse_anchor.py
make knowledge-check
```

The inputs and expected role of each command are:

| Command | Inputs | Reproduced result |
|---|---|---|
| unit tests | `tests/`, `src/`, `knowledge/`, reviewer documents | algebraic invariants, decisions, grounding, and submission contract |
| evaluation | `eval/cases.yaml` | 14 declared decision and claim-grounding cases |
| channel examples | `examples/toy_common_shift.yaml`, `examples/toy_orbital_splitting.yaml` | verified full-space strict-q=0 `global_charge` and `internal` toy classifications |
| sparse-anchor example | `examples/sparse_anchor_response.yaml` | response-matrix fit, synthetic held-out error, and conditional cost accounting |
| knowledge check | `knowledge/*.yaml`, `eval/cases.yaml`, `examples/*.yaml` | all machine-readable records parse as JSON-compatible YAML |

`eval/EVALUATION.md` records the expected evaluation and its scope. This is a
deterministic contract test of the supplied reference implementation, not a
held-out physical-accuracy benchmark or an evaluation of an external language
model.

The line labeled `held-out synthetic` is a software contract. Its targets were
generated from the audit matrix stored in the example file, while the fitting
routine reads only the four training inputs and four reference targets. The cost
record charges those four higher-level anchors and retains full-grid DFPT because
the executable model needs `c_DFPT` at every prediction point. Its normalized
ratio is only relative to a dense higher-level correction.
`is_faster_than_dfpt=False`, `measured_runtime=False`, and
`physical_accuracy_established=False` are required outputs: the example neither
measures a DFPT implementation nor validates a material prediction.

## 4. Rebuild and Check the Report

With the TeX requirements installed, run:

```bash
make report-check
```

The command builds `report/build/main.pdf`, rejects unresolved citations or
references and overfull boxes, and prints PDF metadata. It does not overwrite `report/main.pdf`,
which is the distributed artifact. The supplied report has
26 A4 pages. To run every executable and document check together:

```bash
make check-all
```

Open the fresh build with `open report/build/main.pdf` on macOS or
`xdg-open report/build/main.pdf` on Linux. Open `report/main.pdf` only when
checking the artifact distributed by the repository.

The SHA-256 digest of the PDF distributed with this submission is:

```text
03f31b10478d778feb6ad5b529417b09422ae2db645e1c1298d4f2397f4868e2
```

Verify it on macOS with:

```bash
shasum -a 256 report/main.pdf
```

or on Linux with:

```bash
sha256sum report/main.pdf
```

This digest verifies the distributed artifact only. A locally rebuilt PDF can
have a different byte hash because TeX versions or embedded metadata differ.
In that case, use `make report-check`, confirm the 26-page structure, and
compare the rendered content rather than requiring byte-for-byte identity. The
maintainer-only `make -C report dist` target deliberately replaces the
distributed PDF after an accepted source change; reviewer checks do not run it.

## 5. Reproduce the Evidence Audit

The numerical values in `RESULTS.md` are source-routed in
`knowledge/material_cases.yaml`. Each record supplies the material and mode,
momentum, frequency/static limit, observable, units, source ID, exact table or
figure location, normalization warning, and limitation. Bibliographic metadata
and persistent identifiers are in `knowledge/references.bib`.

To audit a literature claim:

1. locate its `case_id` in `knowledge/material_cases.yaml`;
2. follow `source_ids` to `knowledge/references.bib`;
3. inspect the stated table, equation, or figure in the primary source;
4. compare only the same observable, momentum, frequency limit, basis, units,
   and phonon-eigenvector normalization;
5. retain its declared status: `exact-constraint`, `numerical-evidence`,
   `working-hypothesis`, or `open-question`.

This procedure reproduces the evidence trail and the inference made from it.
Reproduction of the original many-body calculations requires the source
authors' separate codes and inputs and is outside this repository's claim.

## 6. Environment Record

For a review record, save the outputs of:

```bash
git rev-parse HEAD
python3 --version
make --version
latexmk -v
xelatex --version
pdfinfo -v
```

The Python checks are the portable acceptance gate. The TeX commands are only
required when rebuilding the report.

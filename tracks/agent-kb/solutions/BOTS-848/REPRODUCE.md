# Reproduce the BOTS:848 Submission

This guide reproduces the executable result, the recorded evaluation, the two
toy predictions, and the human-readable report. The software path uses only the
Python standard library. It does **not** rerun the external DFPT, DFT+DMFT,
DFPT+U, GWPT, or diagrammatic Monte Carlo calculations cited by the report.

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
  https://github.com/TensorSpicyJ/quantum.harness.git
cd quantum.harness/tracks/agent-kb/solutions/BOTS-848
git rev-parse HEAD
```

Record the printed commit SHA with any reproduced result. The pull request is
[QuantumBFS/quantum.harness#256](https://github.com/QuantumBFS/quantum.harness/pull/256).

## 3. One-Command Software Reproduction

Run:

```bash
make check
```

The important success lines are:

```text
Ran 29 tests ... OK
BOTS:848 evaluation: 14/14 cases passed
decision_accuracy: 1.000
claim_status_accuracy: 1.000
citation_coverage: 1.000
unsupported_claim_rate: 0.000
PASS toy_common_shift.yaml
PASS toy_orbital_splitting.yaml
```

The exact ordering of unit-test lines and elapsed time may differ. A nonzero
exit status means the reproduction failed.

The same checks can be run separately:

```bash
python3 -m unittest discover -s tests -v
python3 eval/evaluate.py
python3 examples/run_example.py
make knowledge-check
```

The inputs and expected role of each command are:

| Command | Inputs | Reproduced result |
|---|---|---|
| unit tests | `tests/`, `src/`, `knowledge/`, reviewer documents | algebraic invariants, decisions, grounding, and submission contract |
| evaluation | `eval/cases.yaml` | 14 declared decision and claim-grounding cases |
| examples | `examples/toy_common_shift.yaml`, `examples/toy_orbital_splitting.yaml` | charge-dominated and internal-channel toy classifications |
| knowledge check | `knowledge/*.yaml`, `eval/cases.yaml`, `examples/*.yaml` | all machine-readable records parse as JSON-compatible YAML |

`eval/EVALUATION.md` records the expected evaluation and its scope. This is a
deterministic contract test of the supplied reference implementation, not a
held-out physical-accuracy benchmark or an evaluation of an external language
model.

## 4. Rebuild and Check the Report

With the TeX requirements installed, run:

```bash
make report-check
```

The command builds `report/main.pdf`, rejects unresolved citations or
references and overfull boxes, and prints PDF metadata. The supplied report has
22 A4 pages. To run every executable and document check together:

```bash
make check-all
```

Open the report with `open report/main.pdf` on macOS or
`xdg-open report/main.pdf` on Linux.

The SHA-256 digest of the PDF distributed with this submission is:

```text
c826098ea0e0a9ad6b9400c6a810099cf9716c0ac6781cd82fa810f983bbeebe
```

Verify it on macOS with:

```bash
shasum -a 256 report/main.pdf
```

or on Linux with:

```bash
sha256sum report/main.pdf
```

A locally rebuilt PDF can have a different byte hash because TeX versions or
embedded metadata differ. In that case, use `make report-check`, confirm the
22-page structure, and compare the rendered content rather than requiring
byte-for-byte identity.

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

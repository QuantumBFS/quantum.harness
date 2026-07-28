# Experiment log

Updated: 2026-07-28

Every completed scientific experiment is appended here whether it succeeds,
fails, or only exposes an infrastructure defect. Large outputs live under the
ignored results tree; the committed entry carries enough provenance to rerun
and interpret them.

## Required entry schema

```text
Experiment ID:
Proposal ID:
Question:
Prediction:
Source commit:
Protocol/config:
Host role and resources:
Command:
Result:
Evidence paths and hashes:
Interpretation:
Transferable lesson:
Decision / next experiment:
```

## ENV-0001 — common-baseline verification

- Proposal ID: infrastructure prerequisite
- Question: Does merged common baseline `04e72bd` pass before new research?
- Prediction: all solution tests pass in the documented scientific environment.
- Source commit: `04e72bd8fb70d448647ba57c14ca412559ccde0d`
- Protocol/config: full `tracks/qmc/solutions/no-negative-vibes/tests`, BLAS
  threads fixed to one.
- Host role and resources: WSL worker, 16 logical CPUs, 31 GiB RAM; one test
  process.
- Result: `199 passed, 379 warnings in 6.77s`.
- Evidence: terminal transcript from the goal task; no large artifact.
- Interpretation: the merged teammate branch is a clean functional baseline.
  All warnings originate from the mpmath deprecated `bitcount` helper.
- Transferable lesson: run pytest from the solution root with `PYTHONPATH=.`;
  invoking it from an arbitrary directory produces false
  `ModuleNotFoundError: oracle`. The dedicated conda environment also required
  `pandas` for the report tests.
- Decision: new failures can be attributed to this branch after the same
  command is rerun at each checkpoint.

No scientific candidate experiment has run on this branch yet.

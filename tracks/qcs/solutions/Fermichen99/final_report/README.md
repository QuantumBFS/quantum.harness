# Final report bundle

This is the version-controlled final deliverable for challenge #113. It
contains only the two headline figures and the numerical values used in them.

- `report.json`: structured `/challenge-report` source.
- `report.html`: self-contained offline report.
- `run.json`: consolidated setup, provenance, and headline results.
- `figure1_intrinsic_dimension.png`, `figure1_data.csv`: intrinsic dimension
  and single-qubit query saving.
- `figure2_closed_loop_answer.png`, `figure2_data.csv`: fixed-space failure and
  adaptive recovery.

The full run records remain in `tracks/qcs/results/`. The minimal code path is
listed in the parent `README.md` and `REPORT.md`.

Render this version-controlled copy with:

```bash
python3 skills/report/render_report.py \
  tracks/qcs/solutions/Fermichen99/final_report
```

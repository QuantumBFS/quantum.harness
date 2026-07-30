# Issue #119 challenge report

This folder contains the self-contained challenge report for team
`CCB-LV.999`. It combines the two issue #119 routes:

- observable estimation with the 49-qubit operator Loschmidt echo;
- variational calculations for 2Fe–2S and the four-impurity Anderson model.

Regenerate the two report-specific comparison diagrams and the HTML page from
the repository root:

```bash
MPLCONFIGDIR=/tmp/issue119-mpl \
  python3 tracks/qcs/results/issue119-challenge-report-20260730/build_report_assets.py

python3 skills/report/render_report.py \
  tracks/qcs/results/issue119-challenge-report-20260730
```

`report.html` is standalone: CSS, equations, and all figures are embedded in
the file. The numerical source records remain under the corresponding
`tracks/qcs/solutions/CCB-LV.999/issue-119-*` folders.

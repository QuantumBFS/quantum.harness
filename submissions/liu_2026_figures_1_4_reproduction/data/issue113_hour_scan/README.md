# Issue #113 one-hour gap/seed scan

## Scientific contract

Question: at fixed model-Hessian subspace dimension `k=10`, how does a larger
synthetic AOM model–truth gap change finite-shot closure reliability and the
number of black-box queries needed to reach coherent error `≤ 1e-3`?

Inputs:

- fixed optimized 400-bin waveform and rank-10 Hessian from
  `../figures3_4/data/`;
- AOM gap strengths `0.03`, `0.11`, and `0.70`;
- finite-shot seeds `260605060`, `260605061`, and `260605062`;
- 9 scan points per mode and 50,000 shots per black-box query;
- at most 2 closed-loop cycles per cell.

Outputs:

- one cell manifest plus serialized scans/cycles for every gap/seed pair;
- `parameter-scan.csv` with query and shot accounting;
- `issue113_hour_scan_summary.json` with per-gap means, sample standard
  deviations, and target-success fractions;
- `../../figures/issue113/issue113_hour_scan.png`.

Acceptance:

- all 9 planned cells must serialize successfully;
- failed-to-reach-target cells remain in the aggregate with a null
  query-to-target value;
- the target applies to the correctable coherent component, not to the raw
  observed error, whose declared irreducible floor is `0.004`;
- no result is interpreted as a dimension-scaling result or a full-400
  parameter baseline.

The first uncached four-cycle pilot serialized its numerical data in about
354.9 seconds (maximum resident set approximately 306 MiB) before a missing
plot-directory error. The directory bug was fixed, the already serialized
first two cycles were retained, and the production scan was capped at two
cycles so all nine cells could remain inside the one-hour budget.

## Result

The `0.03` and `0.11` gaps reached the target in 3/3 seeds, requiring
respectively `104.0 ± 10.4` and `218.7 ± 62.9` queries. The `0.70` stress gap
reached the target in 0/3 seeds; after two cycles its coherent error was
`0.0601 ± 0.0140`.

## Re-run

From the harness repository root, regenerate a selected cell with:

```bash
MPLCONFIGDIR=/tmp/liu-issue113-scan-mpl \
JAX_ENABLE_X64=true JAX_PLATFORM_NAME=cpu \
Sim-to-real-reproduction-run/.venv/bin/python \
submissions/liu_2026_figures_1_4_reproduction/source/issue113_hour_scan.py \
run-cell \
--run-spec submissions/liu_2026_figures_1_4_reproduction/data/issue113_hour_scan/run_spec.json \
--cell-id cell-0001 \
--base-run-dir submissions/liu_2026_figures_1_4_reproduction/data/figures3_4 \
--base-config submissions/liu_2026_figures_1_4_reproduction/data/figures3_4/source_constrained_standard.json
```

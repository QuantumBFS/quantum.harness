# Discovery request matrix

`discovery-matrix-v1.json` is generated on SCNet only after the paired pilot passes.
It contains 280 physical-parameter groups and 2240 policy cells, with 20,000
initial shots per cell. The Slurm array is prepared but must not be submitted
until the first run-batch plan is confirmed and pilot storage/runtime evidence
shows that the 45-minute and project-quota guards can be met.

After each completed phase, `reload_qec.discovery analyze` requires every
expected group/run, verifies checksums and exact paired shot ranges, recomputes
all policy-vs-`none` paired statistics, and applies one global
Benjamini-Hochberg correction over the 1,960 discovery comparisons. It writes:

- `discovery-cells.parquet` with logical, occupancy, reload, runtime, and size
  metrics;
- `discovery-comparisons.parquet` with paired intervals, adjusted p-values, and
  provisional/final evidence labels;
- `continuation-plan.json` containing only physical groups that still need
  sampling;
- `analysis-summary.json` and `analysis-checksums.sha256`.

Continuation keeps all eight policies in a physical group on the same new
`shot_id` range. Cumulative shots double from 20,000 until every policy reaches
400 logical failures or the group reaches 2,000,000 shots. A group that reaches
the cap with an under-sampled cell is retained as `inconclusive_at_budget`.
The continuation Slurm script has no default array range: its explicit range is
derived from the validated plan only after the applicable run gate is confirmed.

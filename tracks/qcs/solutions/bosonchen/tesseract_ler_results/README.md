# Result data map

This submitted directory contains the minimal machine-readable evidence used
by the final report. Large intermediate sweeps, duplicate plots, scheduler
logs, caches, and invalid early comparisons are intentionally excluded. The
report verifies every headline value against the canonical JSON below before
rendering.

## Canonical evidence

| Directory | Status | Use |
|---|---|---|
| `slurm-410856/` | Reduced baseline | Figure 2 summary JSON |
| `research-p0-p4/` | Search ablations | Only the three aggregate JSON files cited by the report |
| `research-tempered-domain-wall-phase0/` | Final prototype | Aggregate result, three per-case records, and the independent-baseline audit |

Primary summary files:

```text
slurm-410856/figure2_small_summary.json
research-p0-p4/baseline_audit_final_v6_summary.json
research-p0-p4/p2_certified_summary.json
research-p0-p4/validation_final_summary.json
research-tempered-domain-wall-phase0/aggregate.json
research-tempered-domain-wall-phase0/independent_baseline_audit.json
```

The phase-0 case records make the 30 paired shots and timing components
auditable without committing the much larger unrelated development history.
The independent audit records establish the pinned official baseline
provenance used in the report.

## Regeneration

Rebuild the final tables, figures, evidence hashes, and standalone HTML report:

```bash
python3 tracks/qcs/solutions/bosonchen/challenge_report/build_report.py
```

The report does not copy or edit experiment JSON.

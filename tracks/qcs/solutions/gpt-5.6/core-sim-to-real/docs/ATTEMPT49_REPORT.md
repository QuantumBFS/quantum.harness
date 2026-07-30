# Attempt 49 — fresh confirmation

Date: 2026-07-29

Decision: **PASS**

This one-shot confirmation uses 24 previously unopened synthetic CNOT truth
cells, four nested finite-shot replicates, and three frozen methods. Hidden
exact fidelity is used only after each black-box client closes. It is not an
online target certificate and it is not hardware evidence.

## Result

| Method | Oracle-scored success (95% truth-cell CI) | Full queries/run | Full shots/run |
|---|---:|---:|---:|
| model-informed-k15 | 90.62% [81.25, 97.92] | 66 | 2099200 |
| model-informed-k40 | 25.00% [12.50, 37.50] | 166 | 5376000 |
| raw-coordinate-global-40 | 0.00% [0.00, 0.00] | 166 | 5376000 |

Paired `k=15 - completed k=40` success:
65.62% [51.04, 80.21].

Paired `k=15 - raw k=40` success:
90.62% [81.25, 97.92].

The `k=15` full-cap query ratio is
0.397590; its shot ratio is
0.390476. These are
deterministic two-cycle protocol caps, not empirically observed online
queries-to-target.

The `k=15` destructive accepted-step rate is
0.00% [0.00, 1.80].

## Frozen gate

```json
{
  "destructive_rate_ucb95_at_most_0_05": true,
  "full_cap_query_ratios_below_0_60": true,
  "full_cap_shot_ratios_below_0_60": true,
  "k15_minus_k40_lcb95_above_minus_0_10": true,
  "k15_minus_raw40_lcb95_above_zero": true,
  "k15_success_lcb95_at_least_0_75": true
}
```

All integrity checks:

```json
{
  "all_ledgers_close": true,
  "all_methods_present_per_cell_replicate": true,
  "all_nested_replicates_present": true,
  "all_numeric_values_finite": true,
  "all_runs_exception_free": true,
  "audited_checkpoint_is_ancestor": true,
  "exact_24_truth_cells_retained": true,
  "expected_288_runs": true,
  "fresh_truth_seed_firewall": true,
  "noise_seed_formula_exact": true,
  "paired_noise_seed_shared_across_methods": true,
  "posthoc_separated": true,
  "postrun_source_and_commit_revalidation_passed": true,
  "preregistration_commit_public": true,
  "preregistration_validation_passed_before_truth": true,
  "source_manifest_seals_all_match": true
}
```

## Claim boundary

- Fresh confirmation is limited to the fixed 24-cell synthetic CNOT benchmark.
- The tested grid, not all possible dimensions, selected `k=15`.
- The resource claim is a 60.24% query-cap and 60.95% shot-cap reduction
  relative to the frozen `k=40` two-cycle protocols.
- Oracle-scored first hit is post-hoc and supplementary.
- No cesium-specific, neutral-atom-platform, or real-hardware generalization
  follows from this confirmation.

## Artifacts

- Protocol: `ATTEMPT49_PROTOCOL.md`
- Runner: `../code/attempt49_fresh_confirmation.py`
- Config: `../code/attempt49_fresh_confirmation_config.json`
- Preregistration manifest:
  `../code/attempt49_preregistration_manifest.json`
- Machine result:
  `../results_summary/QL1F-attempt49-fresh-confirmation.json`
- Figure: `../plots/attempt49-fresh-confirmation.{png,svg}`

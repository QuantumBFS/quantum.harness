# Paper II: Geometric Response of Exactly Degenerate Quantum State Bundles

This REVTeX project is result gated. The proposed positive title *The Geometric ETH: Statistical Closure on Degenerate Quantum State Bundles* is selected only if the prospective theory gate passes. In the frozen v14 result it does not pass: the branch is `random_channel_failure`, so the bounded title above is mandatory.

Canonical outputs:

- `../../01_task_folder/task_05/script/output/geometric_eth_theory_v14/geometric_response_exactly_degenerate_bundles_v14.pdf`
- `../../01_task_folder/task_05/script/output/geometric_eth_theory_v14/geometric_response_exactly_degenerate_bundles_supplement_v14.pdf`
- `../../01_task_folder/task_05/script/output/geometric_eth_theory_v14/delivery_audit_v14.json`

Rebuild the manuscript from frozen scientific artifacts:

```bash
bash 01_task_folder/task_05/script/run_geometric_eth_theory_delivery_v14.sh
```

The command runs the theorem, chiral parent, prediction-seal, inference, generated-input, figure, manuscript, and delivery tests before compiling. It does not overwrite the registered prediction or outcomes. A separate non-overwriting scientific recalculation is documented in `../../docs/2026-08-21-two-paper-reproducibility.md`.

The exact theorem assumes mutually independent centered channels, deterministic weights, a common response space, and finite fourth moments. The (1/N_{\mathrm{eff}}) corollary also requires variance normalization and comparable standardized single-channel cumulants. The failed chiral test shows that (N_{\mathrm{eff}}) alone is insufficient for the registered ensemble; it does not identify which assumption fails.


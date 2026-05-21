# script

Compare the script against the protocol and cited methodology.

| Axis | Pass condition |
|---|---|
| Coverage | Script produces evidence for every assigned claim. |
| Route | Imports, commands, entrypoints, manifests, and artifacts match each cell's declared route fields. |
| Stack | Actual imports and library calls match declared `stack`; raw SciPy under `stack = "quspin"` is drift. |
| Deviations | Every difference from paper, method card, selected stack, or route check is recorded. |
| Manifest | Script writes fields required by checks and registers evidence with the required producer role. |
| Regime | Budgets and knobs are sufficient for declared checks. |
| Figure | For figure-producing code, apply AGENTS.md pre-compute figure-reading checklist: quote caption, match axes/normalization/curves/state/window/anchors/NOT. |
| Figure semantics | Code implements the protocol's paper-defined metric/observable, basis or representation, overlap bra/ket or operator objects, state-selection rule, sector, window, normalization, and excluded nearby states. Proxy selectors must be validated against the paper identity or marked as deviations. |

Severity tags: `match`, `proxy`, `route-mismatch`, `stack-drift`, `unrecorded-deviation`, `provenance-gap`, `regime-gap`, `caption-misread`, `axis-mismatch`, `state-mismatch`, `window-mismatch`.

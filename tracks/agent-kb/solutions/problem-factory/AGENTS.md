# Problem Factory — scoped working agreement

Scope: everything under `tracks/agent-kb/solutions/problem-factory/`. Root `AGENTS.md` still applies; this file only adds local conventions.

## What this is

A minimal rocket-test-style problem factory for issue #133. Problems are YAML cards judged by **experiments, not discussion**: static fire (first-principles checks) → hop test (ED grid) → three-state verdict. No card launches without a frozen gate.

## Card schema (interface A)

```yaml
id: xxz-j2-gap-001
model: xxz_j2_chain        # selects the Hamiltonian builder in pf/ed.py
convention: spin           # "spin" (S=σ/2, default) | "pauli" (energies ×4)
setup:
  boundary: pbc
  sizes: [6, 8, 10]        # even L, Sz=0 sector
  delta: [0.5, 1.0, 1.5]
  j2: [0.0, 0.1, 0.3]      # FIRST entry is the baseline, must be 0.0
observable: {name: gap, definition: E1 - E0, sector: sz=0}
gate:
  type: gap_trend
  frozen: true             # never edited after the card enters the pipeline
  kill_if: {decisiveness_below: 2.0}
static_fire: [bethe_delta1, sz_conservation]
```

## Telemetry (interface B)

One JSON per card in `results/telemetry.jsonl`: `problem_id`, `verdict`, `reason`, `metrics` (`decisiveness`, `gradient_vs_L`, `effect`, `noise`).

## Verdicts

- `survivor` — decisiveness ≥ kill threshold
- `deferred` — 0.5 ≤ decisiveness < kill threshold: signal visible, needs a larger launch
- `dead` — `duplicate_fingerprint` | `setup_error` (static fire) | `no_signal` (decisiveness < 0.5). Deaths are deliverables: always record the root cause.

## Quality classes (pf/rubric.py)

The value layer recognizes two publishable classes, distilled from mentor-curated challenges:

- **record** (#124–#128): beat a pinned number — checks `literature_anchor`, `certificate_gate`, `single_scalar`, `publishable_unit`.
- **map** (#112): chart a declared uncharted region — checks `literature_anchor`, `certificate_gate`, `uncharted_region` (named literature gap), `curve_merit` (curve family + `analytic_check`), `publishable_unit`.

`grade()` accepts a candidate passing either class fully and reports which. Calibration fixtures: `calibration/` (dev), `calibration/test/` (held-out); run `python3 run_calibration.py`.

## Code style (hard requirement from the user)

- Minimal code: one job per function, no frameworks, no ABCs, no plugin machinery.
- No defensive programming: schemas are conventions, not runtime validation. A malformed card crashes loudly — that is the desired behavior.
- No try/except inside the pipeline; exceptions only at true external boundaries.
- No speculative generality: no function, parameter, or branch without a current caller.
- Dependencies: stdlib + numpy + scipy + yaml (pipeline core); matplotlib (plots only).

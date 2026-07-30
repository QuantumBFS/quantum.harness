# Recorded Evaluation

Evaluation date: 30 July 2026.

Command:

```bash
python3 eval/evaluate.py
```

Observed result:

```text
BOTS:848 evaluation: 14/14 cases passed
decision_accuracy: 1.000
claim_status_accuracy: 1.000
citation_coverage: 1.000
unsupported_claim_rate: 0.000
```

The set contains eight decision cases and six claim-grounding cases. It covers charge, internal, nonlocal, dynamic, missing-scale, invalid-reference, untraceable-source, and zero-signal decisions, plus the Ward limit, finite-q uniform-electron-gas evidence, the static matching hypothesis, the SrVO3 mode contrast, the absence of a universal theorem, and the proposed channel hypothesis.

This result verifies the deterministic reference implementation against its declared contract. It does not measure a third-party language model, does not calibrate the physical thresholds, and does not establish accuracy on held-out material calculations. The Agent Skill was checked structurally and through these deterministic pressure cases; a separate before/after agent trial without and with the skill remains future evaluation work.

The response-matrix fit, synthetic held-out coefficient prediction, and separate
cost comparisons against DFPT-only and dense higher-level baselines are tested by the unit suite and
`examples/run_sparse_anchor.py`; they are not included in the 14-case scientific
decision score above. The synthetic result is a software contract, and the cost
ratio is not a measured runtime speedup. The executable correction model still
requires DFPT coefficients at every prediction point and is not claimed to be
faster than DFPT alone.

# Evaluation

Run from the BOTS:848 solution directory:

```bash
python3 eval/evaluate.py
```

The 14 deterministic cases test four things:

- decision accuracy for charge, internal, nonlocal, dynamic, invalid-reference, missing-evidence, and zero-signal inputs;
- correct separation of exact constraints, numerical evidence, working hypotheses, and open questions;
- citation coverage against `knowledge/references.bib`;
- unsupported claim rate, where an unsupported statement counts as an error only if the agent asserts it as fact instead of labeling uncertainty.

This is a contract test for grounding and triage behavior. It is not evidence that the physical thresholds are accurate, and it is not an end-to-end benchmark of an external language model. The next evaluation stage should hide material cases, run an actual agent against the knowledge base, and score both its proposed calculation and the result of that calculation.

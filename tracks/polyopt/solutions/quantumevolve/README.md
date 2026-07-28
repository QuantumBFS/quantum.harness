# quantumevolve — fast certified Bell-sandwich evolution

This directory registers team **quantumevolve** for
[challenge #232](https://github.com/QuantumBFS/quantum.harness/issues/232).
It deliberately avoids an HPC-first workflow.

The current seed is a seconds-scale CHSH control problem:

- `initial_code.py` supplies an exact SOHS upper certificate and an imperfect
  explicit two-qubit strategy.
- `verify_candidate.py` reduces the noncommutative operator identity exactly
  over Q(√2), independently evaluates the strategy, and exposes the certified
  upper-minus-lower gap.
- `evaluator.py` makes exact certificate validity a hard tier boundary; invalid
  candidates receive diagnostic residuals but cannot outrank a valid sandwich.
- `config.toml` runs a single local candidate per generation with an 8-second
  verification timeout.

The CHSH seed only validates the research machinery.  Challenge progress begins
when the same candidate/verifier contract is instantiated for a catalogued open
state-polynomial Bell constant.  Numerical solver status alone will never count
as success: promoted results require an exact rational SOHS identity and an
explicit matching finite-dimensional strategy.

## Fast verification

From this directory:

```text
python -m pytest test_verifier.py -q
python verify_candidate.py initial_code.py
```

The first evolution target is the explicit strategy angle pair.  It gives a
continuous gap signal while the exact certificate gate proves that the
evaluation pipeline is working before any larger SDP is introduced.

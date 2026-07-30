# Issue #265 — Machine-discovered Burgers hydrodynamics

## Team

| Field | Value |
|---|---|
| **Team name** | Wander |
| **Members** | Chenxi Wan, Yedi Shen, Junkai Wang |
| **Contact email** | WangTheoPhys@outlook.com |

## Challenge

This submission addresses [Quantum Harness Issue #265](https://github.com/QuantumBFS/quantum.harness/issues/265): determine whether the constant-coefficient Burgers equation discovered from finite-time Heisenberg-chain data is an asymptotic hydrodynamic law or a finite-window closure.

## Current result

The completed public-trajectory pilot supports Burgers only as a finite-window surrogate. It does **not** establish a universal scalar law:

```text
finite_window_surrogate: supported
universal_scalar: unresolved
two_mode: not_tested
overall: insufficient_observables
```

The confirmatory calculation is still running. The twelve preregistered convergence jobs must finish before Production A, model selection, one-time human unblinding, and the conditional `200 <= t <= 400` Production B test.

## Contribution

- frozen fit (`50 <= t <= 150`), validation (`150 <= t <= 200`), and blinded test (`200 <= t <= 400`) windows;
- amplitude, width, background, shape, anisotropy, integrability-breaking, response, equilibrium, current, correlation, and FCS tests;
- scalar Burgers, independent two-Burgers, coupled two-mode, and memory/more-mode outcomes;
- purified finite-temperature TeNPy TEBD backend with exact-diagonalization, FCS, resume, and grouped-equivalence checks;
- fail-closed convergence, Production-A, model-selection, unblinding, and Production-B controllers.

The authoritative scientific contract is [`docs/RESEARCH_PROTOCOL_BURGERS_UNIVERSALITY.md`](docs/RESEARCH_PROTOCOL_BURGERS_UNIVERSALITY.md). The live boundary between completed and pending evidence is recorded in [`CURRENT_STATUS.md`](CURRENT_STATUS.md).

## Reproduce the lightweight checks

From this directory:

```bash
python -m pytest -q
python scripts/validate_tenpy_exact_diagonalization.py
python scripts/validate_tenpy_fcs.py
python scripts/validate_tenpy_resume.py
```

Large tensor-network production is intentionally not run by the local test command. The Slurm entry points and pinned remote dependency set are under `hpc/scnet/`.

## Claim boundary

This PR registers a reproducible falsification program and an audited pilot. It does not claim that Burgers is exact, asymptotic, or already falsified. Final interpretation remains gated on numerical convergence and the frozen A/B protocol.

Addresses #265.

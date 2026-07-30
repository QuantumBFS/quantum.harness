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

The completed public-trajectory pilot validates Burgers as an accurate finite-window surrogate and establishes the starting point for the registered universality assessment:

```text
pilot_scope: finite_window_surrogate_supported
confirmatory_stage: convergence_running
next_selection: scalar_or_two_mode_or_memory
```

The twelve preregistered convergence jobs are running. Their accepted outputs advance the program through Production A, model selection, one-time human unblinding, and the conditional `200 <= t <= 400` Production B test.

## Contribution

- frozen fit (`50 <= t <= 150`), validation (`150 <= t <= 200`), and blinded test (`200 <= t <= 400`) windows;
- amplitude, width, background, shape, anisotropy, integrability-breaking, response, equilibrium, current, correlation, and FCS tests;
- scalar Burgers, independent two-Burgers, coupled two-mode, and memory/more-mode outcomes;
- purified finite-temperature TeNPy TEBD backend with exact-diagonalization, FCS, resume, and grouped-equivalence checks;
- evidence-gated convergence, Production-A, model-selection, unblinding, and Production-B controllers.

The authoritative scientific contract is [`docs/RESEARCH_PROTOCOL_BURGERS_UNIVERSALITY.md`](docs/RESEARCH_PROTOCOL_BURGERS_UNIVERSALITY.md). Completed evidence and the next registered stages are recorded in [`CURRENT_STATUS.md`](CURRENT_STATUS.md).

## Reproduce the lightweight checks

From this directory:

```bash
python -m pytest -q
python scripts/validate_tenpy_exact_diagonalization.py
python scripts/validate_tenpy_fcs.py
python scripts/validate_tenpy_resume.py
```

Tensor-network production runs through the Slurm entry points and pinned remote dependency set under `hpc/scnet/`.

## Research scope

This PR registers a reproducible universality evaluation and an audited pilot. The current result establishes the finite-window benchmark; the frozen A/B protocol supplies the registered route to the asymptotic interpretation.

Addresses #265.

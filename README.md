# Harnessing Quantum 2026

This repo hosts the **Harnessing Quantum 2026** (智御量子 2026) summer school and an ongoing quantum many-body research harness.

Participants: read the [submission guide](https://giggleliu.github.io/summer-school-2026/zh/guide).

## Tracks

| Abbrev | Method | Background |
|---|---|---|
| `mf` | Mean Field | [`.knowledge/methods/mean-field.md`](.knowledge/methods/mean-field.md) |
| `ed` | Exact Diagonalization | [`.knowledge/methods/ed/METHOD.md`](.knowledge/methods/ed/METHOD.md) |
| `mps` | MPS | [`.knowledge/methods/mps-based-algorithm.md`](.knowledge/methods/mps-based-algorithm.md) |
| `peps` | PEPS | [`.knowledge/methods/peps-based-algorithm.md`](.knowledge/methods/peps-based-algorithm.md) |
| `qmc` | Quantum Monte Carlo | [`.knowledge/methods/quantum-monte-carlo.md`](.knowledge/methods/quantum-monte-carlo.md) |
| `vmc` | Variational Monte Carlo / NQS | [`.knowledge/methods/variational-monte-carlo-neural-quantum-states.md`](.knowledge/methods/variational-monte-carlo-neural-quantum-states.md) |
| `qcs` | Quantum Circuit Simulation | [`.knowledge/methods/quantum-circuit-simulation.md`](.knowledge/methods/quantum-circuit-simulation.md) |

Per-track briefs live under [`tracks/<abbrev>/README.md`](tracks/).

## Harness

Outside the event, this repo is a general QMB research harness.

- Method cards under [`.knowledge/methods/`](.knowledge/methods/).
- Skills under [`tools/skills/`](tools/skills/), managed by [Ion](https://github.com/Roger-luo/Ion).
- Cluster mechanism via `/slurm`; per-cluster defaults under [`tools/cluster/`](tools/cluster/).
- Default stack: Julia (ITensors.jl, ITensorMPS.jl, KrylovKit.jl, MPSKit.jl, PEPSKit.jl, XDiag.jl) and Python (NetKet on JAX, QuSpin, TensorCircuit-NG, quimb).
- Common skills: `/solve` (single calculation), `/reproduce-paper` (paper end-to-end), `/slurm` (ship + submit on cluster).

Open an agent session in the repo and invoke `/onboard` for a first-touch setup.

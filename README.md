# Quantum Many-Body Physics Harness

Research assistant for quantum many-body physics. Handles ground-state calculations on lattice models — from setting up the Hamiltonian to picking a method, running the computation, verifying results, and generating plots.

Long multi-agent, remote, and paper-reproduction runs are gate-managed by the core state-machine CLI `tools/cli/flow`.

## What it helps with

- **Ground-state problems** across 8 model families: Heisenberg, transverse-field Ising, J1-J2, Hubbard, t-J, t-V, Anderson impurity, multiorbital Hubbard.
- **Method selection** — DMRG, ED, TEBD, or VMC/NQS (NetKet), chosen based on the problem's lattice, size, and difficulty.
- **Verification** — checks results against known limits, symmetry constraints, convergence, and published benchmarks where available.
- **Contested problems** — for frontier cases like kagome Heisenberg or J1-J2 at intermediate coupling, provides literature context and flags what's settled vs debated.
- **Diagnostic physics questions** — criticality, frustration, spin liquids, Mott transitions, Kondo effect.

## Setup

```bash
make setup && make domain-setup
```

Start a Claude Code session and describe your problem.

## Stack

- **Julia** — ITensors.jl, ITensorMPS.jl, KrylovKit.jl, MPSKit.jl, Plots.jl
- **Python** — NetKet + JAX (VMC/NQS), quimb (optional TN alternative)

Install additional tools with `make install <name>`. Run `make help` for the full list.

## For contributors

Design contract: `AGENTS.md`. Specs and test reports: `docs/`.

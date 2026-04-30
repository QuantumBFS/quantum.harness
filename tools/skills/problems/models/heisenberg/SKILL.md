---
name: heisenberg
description: Use when the user is working on a Heisenberg spin-model ground-state problem, including spin chains, square/triangular/kagome/pyrochlore lattices, frustrated regimes, ground states, gaps, or order parameters.
---

# Heisenberg

Solve Heisenberg-spin ground-state problems. Lattice geometry and coupling regime determine which method works.

## Diagnose

Fix:

- **Spin** (`S = 1/2` default; ask if larger).
- **Lattice and dimension** (chain, square, triangular, kagome, pyrochlore).
- **Coupling sign** — antiferromagnetic (`J > 0`) or ferromagnetic (`J < 0`)?
- **Anisotropy** — isotropic Heisenberg, XXZ, easy-axis/easy-plane, external field?
- **Boundary condition** (OBC default for DMRG).
- **System size** (or `L_y × L_x` for cylinders).
- **Target observable** (`E/N`, gap, structure factor, two-point correlations, magnetization).
- **Accuracy goal** and rough compute budget.

If only "Heisenberg" is given, infer S=1/2, isotropic, NN, antiferromagnetic, OBC; state the assumption.

Build the Hamiltonian per `knowledge-base/conventions.md` (S-operator convention; factor-of-4 difference vs Pauli notation).

## Workflow

1. Set up sites and Hamiltonian per conventions; pin sector via conservation laws (see `knowledge-base/symmetry-cheatsheet.md`).
2. Pick method per the table below.
3. Run a short, conservative first calculation; verify it ran cleanly and respected conservation laws.
4. Sweep the convergence parameter (bond dim for DMRG, basis size for ED) until the target observable stops moving within the accuracy goal.
5. Verify (next section).
6. If the problem branches into a more specific physics question, hand off via the branch table.

## Method recommendations

| Regime | Method | Card |
|---|---|---|
| 1D chain (any N), quasi-1D ladder | DMRG | `knowledge-base/methods/dmrg.md` |
| Small cluster (N ≲ 24 sites), exact spectrum, debugging | ED | `knowledge-base/methods/ed.md` |
| Cylinder (square / triangular / kagome strips, `L_y` small) | DMRG | `knowledge-base/methods/dmrg.md` |
| Imaginary-time route to ground state, gap probes | TEBD | `knowledge-base/methods/tebd.md` |
| Frustrated 2D thermodynamic limit | Beyond current scope; surface uncertainty and report what cylinder DMRG / ED on small clusters can constrain. | — |

## Branch table

| Condition | Action |
|---|---|
| Lattice is triangular, kagome, or pyrochlore (frustrated) | Continue here for setup; if the question is about absence of order or topology, also call `spin-liquid`; if about the source of frustration, call `frustration`. |
| User asks about NN + NNN couplings | Switch to `j1-j2`. |
| Question is about quantum critical behavior (e.g., XXZ at Δ=1, dimerization) | Call `criticality` after the calculation. |
| User wants doped, fermionic correlated physics | Switch to `t-j` or `hubbard`. |
| User asks about real-time dynamics or finite-T | Out of current scope; explain and offer to set up the ground-state calculation that's needed first. |

## Verification

Default checks (always run):

- **Limit checks** — confirm sign convention and trivial limits via `knowledge-base/limits.md`. Examples: at `Δ = 1` XXZ reduces to isotropic Heisenberg; ferromagnetic ground state is fully polarized; `J = 0` gives uncoupled spins.
- **Symmetry** — total `S^z` conservation; expected ground-state sector (singlet for finite AFM); lattice point group respected (see `knowledge-base/symmetry-cheatsheet.md`).
- **Convergence** — bond-dim or basis-size sweep produces a monotonic, asymptoting curve. Report the curve, not just the final value.
- **Internal consistency** — energy variance is small relative to `E²` at the reported accuracy.

Optional check (when a published reference exists):

- Compare to `knowledge-base/benchmark-numbers.md` for the lattice / coupling combination. Report the discrepancy honestly. If the published value is a *range* (e.g., kagome), report whether your value is consistent with the range, not whether it "matches."

If no benchmark exists for the user's specific problem (which is common for non-canonical sizes / parameters), report the converged value with bond-dim trend, variance, and the satisfied limit + symmetry checks. Do not claim a "match" without a reference.

## Related skills

`frustration`, `spin-liquid`, `criticality`, `j1-j2`.

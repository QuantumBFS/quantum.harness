# Heisenberg

Solve Heisenberg-spin ground-state problems. Lattice geometry and coupling regime determine which method works.

## Diagnose

Infer the canonical setup from the user's prompt and propose it for ratification. Do not ask 8 questions.

**Canonical defaults:** S=1/2, isotropic NN, antiferromagnetic (J > 0), OBC, target E/N. Lattice and system size inferred from the prompt — if only "Heisenberg" is given, default to 1D chain N=20.

**Proposal pattern:** "Going with: 1D chain, S=1/2, J=1 AFM, OBC, N=20, target E/N. Override any, or pick a variant: square lattice (4×4 pending ED), triangular cylinder (Ly=4), kagome cylinder (Ly=4)."

Only surface a real choice when the prompt is genuinely ambiguous about the lattice family. Build the Hamiltonian per `.knowledge/conventions.md`.

## Workflow

1. Set up sites and Hamiltonian per conventions; pin sector via conservation laws (see `.knowledge/symmetry-cheatsheet.md`).
2. Pick method per the table below.
3. Run a short, conservative first calculation; verify it ran cleanly and respected conservation laws.
4. Sweep the convergence parameter (bond dim for DMRG, basis size for ED) until the target observable stops moving within the accuracy goal.
5. Verify (next section).
6. If the problem branches into a more specific physics question, hand off via the branch table.

## Method recommendations

| Regime | Method | Card |
|---|---|---|
| 1D chain (any N), quasi-1D ladder | DMRG | `skills/method-mps/SKILL.md` |
| Small cluster (N ≲ 24 sites), exact spectrum, debugging | ED pending refreshed references | `skills/method-ed/SKILL.md` |
| Cylinder (square / triangular / kagome strips, `L_y` small) | DMRG | `skills/method-mps/SKILL.md` |
| Imaginary-time route to ground state, gap probes | TEBD | `skills/method-mps/SKILL.md` |
| Frustrated 2D variational (VMC / NQS) | Compare ansatz energies on kagome / triangular. Requires `make install netket`. | `skills/method-vmc/SKILL.md` |
| Frustrated 2D thermodynamic limit | Beyond current scope for exact methods; surface uncertainty. VMC + DMRG cylinder can constrain. | — |

## Branch table

| Condition | Action |
|---|---|
| Lattice is triangular, kagome, or pyrochlore (frustrated) | Continue here for setup; if the question is about absence of order or topology, also call `spin-liquid`; if about the source of frustration, call `frustration`. |
| User asks about NN + NNN couplings | Switch to `j1-j2`. |
| Question is about quantum critical behavior (e.g., XXZ at Δ=1, dimerization) | Call `criticality` after the calculation. |
| User wants `S = 1` chain with single-ion anisotropy | Switch to `spin-1-xxz`. |
| User wants doped, fermionic correlated physics | Switch to `t-j` or `hubbard`. |
| User asks about `S(q,ω)` or dynamics | Out of current scope. |
| User asks about finite-T (susceptibility, specific heat) | Out of current scope. |

## Verification

Default checks (all auto-run; results aggregated into the report's verification line):

- **Limit checks** — confirm sign convention and trivial limits via `.knowledge/limits.md`. Examples: at `Δ = 1` XXZ reduces to isotropic Heisenberg; ferromagnetic ground state is fully polarized; `J = 0` gives uncoupled spins.
- **Symmetry** — total `S^z` conservation; expected ground-state sector (singlet for finite AFM); lattice point group respected (see `.knowledge/symmetry-cheatsheet.md`).
- **Convergence** — bond-dim or basis-size sweep produces a monotonic, asymptoting curve. Report the curve, not just the final value.
- **Internal consistency** — energy variance is small relative to `E²` at the reported accuracy.
- **Cross-method validation (auto-paired when available)** — use TEBD or another active independent route. Use ED only after `skills/method-ed/SKILL.md` is rebuilt.

Optional check (when a published reference exists):

- Compare to `.knowledge/benchmark-numbers.md` for the lattice / coupling combination. Report the discrepancy honestly. If the published value is a *range* (e.g., kagome), report whether your value is consistent with the range, not whether it "matches."

If no benchmark exists for the user's specific problem (which is common for non-canonical sizes / parameters), report the converged value with bond-dim trend, variance, and the satisfied limit + symmetry checks. Do not claim a "match" without a reference.

## Writeup handoff

After verification, if the user wants to communicate the result, consolidate to a runnable script + short run report, then route to `scientific-visualization`. See AGENTS.md "Writeup handoff".

## Related skills

`frustration`, `spin-liquid`, `criticality`, `j1-j2`.

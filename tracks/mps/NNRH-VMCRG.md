# Neural-Network Renormalized Hamiltonians for VMCRG (NNRH-VMCRG)

NNRH-VMCRG is Team LULU's MPS-track response to
[Issue #28](https://github.com/QuantumBFS/quantum.harness/issues/28), submitted
through [PR #154](https://github.com/QuantumBFS/quantum.harness/pull/154).
It asks whether a symmetry-preserving neural energy can replace a truncated
coupling expansion in variational Monte Carlo renormalization group (VMCRG).

## Scope and final status

| Route | Target | Final status |
|---|---|---|
| Paper baselines | XY-chain LTRG Figs. 4-6a and 2D VMCRG Table I/autocorrelation | `REPRODUCTION_COMPLETE` |
| Easy Goal | Periodic 45 x 45 2D Ising, 3 x 3 majority RG, pure neural Hamiltonian | `PROTOCOL_INCOMPLETE` |
| MPS/TT | chi=2,4,8 local tensor-train bias and sampling diagnostics | `SUPPORTING_EVIDENCE` |
| Hard Goal | Periodic 45 x 45 x 45 iid +/-J Edwards-Anderson spin glass and transition point | `STAGE_6_NO_GO` |

The paper reproduction establishes method and engineering baselines; it is not
Issue #28 completion. The Easy Goal has one complete corrected negative round
and an unpublished interrupted second round, not five valid consecutive
rounds. MPS/TT has exact checks and six chi=2/4 L=27 smoke cells, but no chi=8
formal cells. Hard Goal Stages 4 and 5 pass engineering validation; Stage 6
fails the temperature round-trip gate, so L=45, second RG, and Tc fitting were
not executed.

## Methods and MPS/TT role

The implementation combines Ising/VMCRG sampling, D4/Z2/translation-symmetric
neural local energies, immutable checkpoints, frozen validation, BAR objectives,
and paired baselines. MPS/TT supplies a compact local-bias alternative and the
Route B/C residual representation for 3D validation; it remains supporting
evidence rather than an Easy Goal success gate.

## Start here

- Core code: `tracks/mps/DMRG/src/vmcrg_ref/` and `tracks/mps/DMRG/src/spinglass3d/`
- Tests: `tracks/mps/DMRG/tests/` and `tracks/mps/tests/`
- Configs: `tracks/mps/DMRG/config/`
- Reproduction: `tracks/mps/solutions/` and `tracks/mps/DMRG/reproduce.py`
- Evidence audit: `tracks/mps/docs/nnrh-vmcrg/FINAL_EVIDENCE_AUDIT.md`
- Easy Goal audit: `tracks/mps/docs/nnrh-vmcrg/FINAL_N3_AUDIT.md`
- Hard Goal audit: `tracks/mps/docs/nnrh-vmcrg/FINAL_HARD_GOAL_STATUS.md`
- Final result: `tracks/mps/results/20260730-193234-nnrh-vmcrg-final/`
- Final report: `tracks/mps/results/20260730-193234-nnrh-vmcrg-final/report.html`
- Track-local Skill: `tracks/mps/skills/nnrh-vmcrg/SKILL.md`
- PR material: `tracks/mps/submission/`

## Reproduce and test

```bash
python tracks/mps/DMRG/reproduce.py test
JULIA_NUM_THREADS=1 julia --project=julia-env tracks/mps/solutions/xy_ltrg_reproduction_test.jl
.venv/bin/python -m pytest tracks/mps/DMRG/tests tracks/mps/tests -q
python skills/report/render_report.py tracks/mps/results/20260730-193234-nnrh-vmcrg-final
```

Allowed claims: the two paper baselines are reproduced; the corrected Easy
Goal attempt is incomplete and negative at its observed gates; MPS/TT is
supporting only; 3D mechanics pass small-scale validation and Stage 6 is no-go.
Forbidden claims: Easy Goal success, NNRH-VMCRG completion, MPS/TT superiority,
Hard Goal success, an L=45 3D result, or a transition-temperature estimate.

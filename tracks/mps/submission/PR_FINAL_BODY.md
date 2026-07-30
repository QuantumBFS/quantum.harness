## Team

| | |
|---|---|
| **Team** | LULU |
| **Members** | Weiwei Wang, Yuan Zheng, Dazhong Zhang |
| **Challenge** | Issue #28 |
| **Track** | MPS |

## Neural-Network Renormalized Hamiltonians for VMCRG (NNRH-VMCRG)

This submission implements and audits neural and tensor-network representations
of renormalized Hamiltonians for VMCRG. Core code covers 2D Ising VMCRG,
D4/Z2 neural local energies, MPS/TT supporting routes, immutable checkpointed
workflows, and a validated 3D +/-J spin-glass parallel-tempering implementation.

### Final scientific status

| Route | Status | Result |
|---|---|---|
| Paper reproduction | `REPRODUCTION_COMPLETE` | XY LTRG Figs. 4-6a reproduced; 2D VMCRG Table I values are statistically compatible and biased sampling strongly reduces autocorrelation. |
| 45 x 45 Easy Goal | `PROTOCOL_INCOMPLETE` | The legacy N3 gate was invalid. The corrected chain has one published negative round and an interrupted unpublished round 2; N4/N5 were not run. |
| MPS/TT | `SUPPORTING_EVIDENCE` | Exact checks and six chi=2/4 L=27 smoke cells exist; chi=8 formal cells were not executed. No formal superiority claim is made. |
| 45 x 45 x 45 Hard Goal | `STAGE_6_NO_GO` | Stages 4-5 passed. Stage 6 exchange acceptance passed but full temperature round trips did not; L=45, second RG, FSS and Tc were not run. |

### Engineering validation and entry points

- Start: `tracks/mps/NNRH-VMCRG.md`
- Final report: `tracks/mps/results/20260730-193234-nnrh-vmcrg-final/report.html`
- Final status: `tracks/mps/results/20260730-193234-nnrh-vmcrg-final/final_status.json`
- Track-local workflow: `tracks/mps/skills/nnrh-vmcrg/SKILL.md`
- Tests: `.venv/bin/python -m pytest tracks/mps/DMRG/tests tracks/mps/tests -q`

The PR-source baseline suite passed (`197 passed`). The available Issue #28
shard produced `95 passed, 8 failed`; all eight failures require the shared
root `cluster_guardrail.py directive` API, which is absent at the PR base and
outside this track-only change boundary. The remaining track shards were
skipped on the project administrator's direct-submit instruction. The full
migrated track suite is therefore not claimed as passing; exact records are in
`tracks/mps/submission/FINAL_TEST_RESULTS.txt`.

Known limitations are explicit: no five-round corrected N3 result, no five-seed
N4/N5 analysis, no formal chi=8 TT comparison, no Stage 6 multi-J pass, no
L=45 3D production, and no transition-temperature estimate. The submission
therefore reports reproducible baselines and bounded incomplete/negative
results, not completion of either Issue #28 scientific goal.

Closes no scientific gate automatically; addresses #28 with an auditable stage result.

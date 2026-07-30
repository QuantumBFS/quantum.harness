# Final Evidence Audit

## Repository identity

- PR source: `WWWang2016:challenge/mps/neural-renormalized-hamiltonians`
- Audit worktree branch: `pr154-nnrh-vmcrg-final`
- Audit base HEAD: `15d2c11c23ff786c66d6184075d033b5fe9d3cb6`
- PR: #154; Issue: #28; team: LULU; track: MPS
- Pre-existing external changes: `PRE_EXISTING_EXTERNAL_CHANGE` in the original
  worktree, including root Makefile/knowledge/Ion changes and local credential
  download metadata. None is included in this submission.

## Scientific status

| Area | Status | Primary evidence |
|---|---|---|
| XY LTRG Figs. 4-6a | `REPRODUCTION_COMPLETE` | `tracks/mps/results/20260727-131302-li2011-xy-ltrg/run.json` |
| 2D VMCRG Table I | `REPRODUCTION_COMPLETE` | `tracks/mps/results/20260730-193234-nnrh-vmcrg-final/evidence_snapshots/vmcrg_table1_pooled.json` |
| 2D autocorrelation | PASS | `tracks/mps/results/20260730-193234-nnrh-vmcrg-final/evidence_snapshots/vmcrg_autocorrelation.json` |
| Easy Goal | `PROTOCOL_INCOMPLETE` | corrected N3 result and invalid-gate incident |
| MPS/TT | `SUPPORTING_EVIDENCE` | `tracks/mps/DMRG/results/mps_challenge/` |
| Hard Goal | `STAGE_6_NO_GO` | Stage 6 selections and terminal submission manifest |

LTRG reproduces the free-energy, internal-energy and specific-heat targets;
the separate locked 1% endpoint extension is a retained scientific negative.
For 2D VMCRG, lambda_even=3.01430 with 95% CI [2.93837,3.05357] covers 3.045,
and lambda_odd=7.84600 with CI [7.76379,7.90248] covers 7.858. At L=90,
tau_biased=4.9809 versus tau_unbiased=475.5463.

## Gates and missing work

Passed: reproduction targets, exact/symmetry/cache/checkpoint engineering tests,
Hard Goal Stage 4 regression and Stage 5 small-3D validation. Failed or absent:
five corrected N3 rounds, N4/N5, chi=8 formal MPS/TT cells, multi-J Stage 6
equilibration/ESS/representation/power gates, Stage 7 L=45, Stage 8 FSS, and Tc.

No new scientific calculation is necessary for an honest final submission.
Completing the Easy Goal would require at least four additional published
corrected rounds plus a fresh five-round chain if prior failed rounds cannot
pass; historical rounds cost roughly 0.7-6.8 h locally each. Completing the
Hard Goal is infeasible locally: the first 120-cell Stage 6 pass alone projects
to about 188.4 local wall hours. Deadline completion probability is therefore
low without renewed accelerator authorization.

Recommended classification: paper `REPRODUCTION_COMPLETE`; Easy Goal
`PROTOCOL_INCOMPLETE`; MPS/TT `SUPPORTING_EVIDENCE`; Hard Goal
`STAGE_6_NO_GO`. Engineering submission is ready if final tests and scans pass.

Allowed claims are the verified reproduction and bounded negative/incomplete
results above. Forbidden claims are Easy/Hard success, full NNRH-VMCRG
completion, formal TT superiority, L=45 3D physics, second RG, and Tc.

The 2026-07-27 roadmap is obsolete for later N3/Hard Goal execution. The
2026-07-30 stage report predates the terminal `RESOURCE_NO_GO` decision and is
superseded by this audit and the new final status.

# Challenge 66 Science-Gate Audit

Status: `inconclusive_at_deadline`. This file is an evidence index, not a claim
of completion. A gate changed to `passed` only when the referenced immutable
artifact and checksum were inspected.

Hard deadline: 2026-07-30 15:27 CST.

| Gate | Status | Required evidence |
|---|---|---|
| Frozen question, model, matrix, and acceptance rules | passed | `topics.md`, `MODEL.md`, `WORKFLOW.md` |
| Locked cluster environment | passed | jobs 6760384-6760385; `research/references/cluster-build-env-6760384.md` |
| Deterministic core and independent oracle | passed | jobs 6760435-6760439; `research/references/pilot-gates-6760431-6760439.md` |
| Validator isolation and standard negative controls | passed | jobs 6760456 and 6760472 |
| Frozen candidate exact replay and score | passed | jobs 6760479-6760488; score 185.979924557991 |
| Five v2 negative controls for confirmation candidate | passed | job 6769918 rejected all five controls, including background-escape, before its accepted simulation |
| Discovery core initial phase | passed | array 6766558 completed all 280 groups; analysis job 6769992 verified 2,240 cells and 1,960 comparisons |
| Discovery registered stopping rule | incomplete-at-deadline | Phase-2 analysis 6771281 accepted 89,600,000 cell-shots; 27/2,240 cells stopped and all 280 groups continue; Phase-3 array 23019121 completed but analyses 23019135/23020995 published no accepted manifest |
| Headline independent-seed confirmation | incomplete-at-deadline | job 6769978 accepted through Phase 5 with 12,800,000 cell-shots, 4/40 cells stopped and all 32 comparisons meeting precision; xh5 resume 23018885 timed out without publishing Phase 6 |
| Cost sensitivity and Pareto analysis | not-run-prerequisite-incomplete | executable snapshot `bundle-sensitivity-cycle-7ea851b` passed 26 contracts in job 23006968; final discovery was required first |
| Independent implementation slice | passed | exhaustive independent graph oracle job 6760435; final report must delimit the checked slice |
| Independent-seed reproduction | incomplete-at-deadline | 12,800,000 cumulative Phase-5 cell-shots are accepted under `q66-confirmation-seed-v1`; final stopping evidence was not reached |
| Decoder-ready schema and label isolation | passed-for-validator-slice | exact replay, poison/isolation and checksum gates; final public shards remain to audit |
| Complete draft report with traceable numbers | passed | `research/REPORT_DRAFT.md` and `research/REPORT_ZH.md` contain accepted artifact paths, checksums, limitations, and the deadline disposition |
| One sealed holdout query | unspent-at-deadline | `research/references/holdout-temporal-isolation.md`; budget remains 0/1 because prerequisite gates did not pass |

## Holdout Release Conditions

All items below must be true before the one aggregate holdout allocation:

- discovery status is `final-discovery`;
- confirmation status is `final-confirmation` and the 80% precision gate passes;
- cost sensitivity is final, including baseline reuse and explicit costs;
- independent implementation and independent-seed evidence are linked;
- public shard/schema/checksum audit passes;
- report contains every positive, negative, and budget-inconclusive result;
- candidate tree remains SHA-256
  `829ade4b3ab7408c9151a6a06222e6779df6c65096b8d2e2d947e26238140482`;
- no holdout-spend record exists and the recorded query budget is `0 / 1`.

If any condition remains false at the hard deadline, do not run holdout and
close the project as `inconclusive_at_deadline` with the completed artifacts.

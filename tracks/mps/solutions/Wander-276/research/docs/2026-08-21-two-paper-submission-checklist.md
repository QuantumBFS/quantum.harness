# Two-paper submission checklist

## Common author decisions

- [ ] Confirm that `Thomas J. Wang` and `OkongOyangO` are the final publication names and fix any ORCID records.
- [ ] Confirm author order, affiliations, contributions, and approval of both submissions.
- [ ] Confirm that the Quantum Harness Team table is a competition-team record and not the journal author list.
- [ ] Confirm competing-interest and originality statements.
- [ ] Decide whether the papers are submitted simultaneously and disclose the companion manuscript to both editors.

## Paper I

- [x] REVTeX PRB main text and Supplemental Material compile cleanly.
- [x] Seven vector figures, generated tables, citation audit, claim audit, and archived PDFs are present.
- [x] The 23-page long-form deviation from the frozen 14–18-page estimate is recorded as a later human-authorized scope change.
- [ ] Select final target journal and check current length/supplement policies.
- [ ] Replace repository-only companion wording with an arXiv identifier if one exists before submission.
- [ ] Approve the Paper I cover letter.

## Paper II

- [x] Fallback title and `random_channel_failure` branch agree with the machine gate.
- [x] Six vector figures, theorem supplement, source audit, and archived PDFs are present.
- [x] Empirical values enter prose through generated macros.
- [ ] Choose PRB or PRD and update the document option/cover letter if needed.
- [ ] Replace the internal companion citation with Paper I's arXiv identifier when available.
- [ ] Approve the Paper II cover letter.

## Repository and PR

- [x] Combined reproduction, reviewer, Issue, and PR drafts exist.
- [x] Root/task/paper README files point to the current v13/v14 delivery.
- [x] Reuse the existing Quantum Harness Issue #276 rather than create a duplicate.
- [x] Bind the PR draft to Issue #276.
- [x] Confirm `QuantumBFS/quantum.harness:main` as the Harness target and base branch.
- [x] Merge the inspected `origin/main` update into the research delivery branch.
- [ ] Push `codex/two-paper-geometric-eth` and update open PR #283.
- [ ] Verify the remote PR title, Team table, links, and checks from a clean checkout.

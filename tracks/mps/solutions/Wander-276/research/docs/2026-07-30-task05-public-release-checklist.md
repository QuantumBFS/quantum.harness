# Task 05 Public Release Checklist

## 1. Research Issue Submitted

- Issue: [QuantumBFS/quantum.harness#276](https://github.com/QuantumBFS/quantum.harness/issues/276).
- Title: `What is the Probe of Quantum Chaos for Degenerate Eigenstate Subspace?`
- The PR body now links the issue and supplies the executable geometric answer.

## 2. Open the PR

- Base: `main`
- Head: `codex/task-05-geometric-chaos-baseline`
- Title: `Geometric chaos under exact degeneracy: reproducible task-05 release`
- Body: paste [the prepared PR body](2026-07-30-task05-pr-body.md).
- Suggested mode: Draft during the first scientific review, then Ready for Review after author sign-off.

## 3. Add the Review Comment

- Paste [the prepared review comment](2026-07-30-task05-pr-review-comment.md).
- Keep `@OkongOyangO` in the first line so GitHub sends the review notification.
- Request review from the same collaborator in the PR sidebar.

## 4. Review the Public Landing Page

- Confirm the hero figure renders on the repository front page.
- Open the Markdown technical report and 17-page PDF.
- Check `CITATION.cff` rendering in GitHub's citation panel.
- Confirm every link in the task release guide resolves.

## 5. Run the Release Gate

```bash
cd 01_task_folder/task_05/script
bash run_quick_verify_v1.sh
```

Expected compact release state:

- 38 focused tests;
- 86 passing complete-suite tests;
- 6 production-data tests activated by the manifest-listed arrays;
- 17 rendered article pages;
- 7 synchronized main figures;
- 14 Git-resident compact artifacts;
- 25 production arrays recorded with SHA-256 and byte size.

## 6. Publish the Data Layer

- Create a DOI-backed archive for the 25 production arrays when desired.
- Attach the DOI to the GitHub release, technical report, and challenge issue.
- Regenerate `release_manifest_v1.json` with the archived artifacts present and confirm identical hashes.

## 7. Convert the PR to Ready for Review

- Confirm author names and public contact details.
- Confirm the issue link.
- Confirm the final article hash.
- Publish the prepared review comment.
- Select **Ready for Review**.

# Issue 92 submission package

This directory is the stable, lightweight entry point for the professor review and pull request.

- `report.html` — self-contained offline presentation; open this first.
- `FINAL_REPORT.md` — text version for GitHub review and diffing.
- `report.json` — structured source consumed by the Harness report renderer.
- `run.json` — compact challenge run summary.
- `tables/` — curated accepted/certified rows; floating rows are not mixed in.
- `data_manifest.json` — hashes of aggregate inputs and roles/sizes of raw campaign directories.
- `assets/` — report figures copied from the current aggregate.

Raw solver JSON, primal/dual matrices, and scheduler logs remain in `../results/`, which is git-ignored by Harness policy. Rebuild after fetching an HPC checkpoint:

```bash
make final-report
```

The build is non-destructive: it refreshes aggregate outputs and atomically replaces this snapshot; it never moves or deletes raw evidence.

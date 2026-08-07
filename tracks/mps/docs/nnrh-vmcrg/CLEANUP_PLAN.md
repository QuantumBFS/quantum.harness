# Cleanup Plan

The original tree contains about 472 MB and 4,191 files. Keep all source,
tests, configs, compact manifests/reports, negative results, checkpoint
metadata and selected figures. Exclude generated caches, `tmp/`, PID/job-id
markers, duplicate progress streams, raw chains, archives and large checkpoint
bodies from the PR. No unique scientific data or checkpoint is deleted from
the original worktree.

Deletion-risk rule: only known cache/temp/empty patterns are `DELETE`; unknown
or large data is `REVIEW`. Validate with the full tests, JSON parsing, report
rendering, reference checks, secret/large-file scans and `git diff --check`.

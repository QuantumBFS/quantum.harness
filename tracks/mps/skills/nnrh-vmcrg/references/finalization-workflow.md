# Finalization Workflow

1. Validate final status, report JSON/HTML, references, secrets, large files,
   and `git diff --check`.
2. Confirm every staged path begins with `tracks/mps/`.
3. Commit coherent cleanup, Skill, and final-report changes.
4. Push normally to the existing PR source branch; never force push.
5. Update PR title/body from `tracks/mps/submission/`, mark ready only after
   immediate CI is healthy, and inspect all checks.

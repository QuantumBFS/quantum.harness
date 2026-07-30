---
name: nnrh-vmcrg
description: >-
  Use when auditing, validating, cleaning, finalizing, documenting, or submitting
  Neural-Network Renormalized Hamiltonians for VMCRG (NNRH-VMCRG) for
  QuantumBFS quantum.harness Issue #28 in the MPS track, including the 2D Ising
  Easy Goal, MPS/TT supporting experiments, 3D spin-glass Hard Goal, immutable
  evidence, scientific gates, final reports, or PR submission.
---

# NNRH-VMCRG Finalization

Treat immutable run artifacts as evidence and plans as intent. Engineering PASS
and scientific PASS are independent.

## Workflow

1. Review Issue #28 and confirm the PR source branch, HEAD, and `tracks/mps/` boundary.
2. Review [issue28-scope.md](references/issue28-scope.md) and
   [evidence-policy.md](references/evidence-policy.md).
3. Audit reproduction, Easy Goal, MPS/TT, and Hard Goal in that order. Review the
   matching gate reference before classifying each route.
4. Run `scripts/audit_evidence.py --track-root tracks/mps` and inspect every
   missing or contradictory source.
5. Verify manifests, artifact hashes, checkpoint ancestry, seeds, configs, and
   terminal status. A staging directory is not a completed run.
6. Inventory before cleanup. Follow [cleanup-policy.md](references/cleanup-policy.md);
   preserve negative results and unique recovery metadata.
7. Generate and validate `final_status.json`, then build a new timestamped report.
8. Run Skill, reference, JSON, HTML, secret, large-file, and path-boundary checks.
9. Follow [finalization-workflow.md](references/finalization-workflow.md) for commits
   and PR submission. Never force push.

## Hard Stops

- Never lower a frozen threshold or rewrite an old result.
- Never promote smoke or single-seed evidence to a formal claim.
- Never treat Stage 6 ladder calibration as transition-temperature evidence.
- Never submit long compute without a fresh setup and resource confirmation.
- Never stage a path outside `tracks/mps/`.

This is a track-local Skill. The root Ion registry is intentionally unchanged;
invoke it by asking an agent to review this file explicitly.

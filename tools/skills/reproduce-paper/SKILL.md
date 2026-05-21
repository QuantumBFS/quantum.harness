---
name: reproduce-paper
description: Use when the user wants to reproduce the figures and main results of a published paper end-to-end — phrases like "reproduce paper X", "redo the figures of Y", "reproduce arXiv 2302.04919", "put this paper through the harness as a calibration target", or right after `/download-ref` lands a new paper.
---

# reproduce-paper

Outcome: a `flow`-backed run directory whose `close` gate passes. Every claim is backed by primary-source-derived protocol rows, current-run manifests, and audit attempts closed by a spawned verifier's returned report. This skill sequences the spine; `flow attempt finish` is what advances state.

## Non-negotiables

<checklist name="binding">
- Primary sources control. KB cards, old scripts, prior figures, and notes are hints until confirmed against a primary source or regenerated as current-run evidence.
- Fill `[[cells]]` before any cell-producing script lands. Each executable cell declares `method`, `stack`, `route`, `source`, `check`, `state`, and `scope`.
- Method and stack names are data in `protocol.toml`, not `flow` gates, roles, or check kinds.
- Canonical-stack failure is recorded as `state = "failed"` or `"pending"` before fallback/deviation is considered. Do not probe alternate stacks first.
- Fallback means the method card's next recommended stack. Any other route is a `[[deviations]]` row before compute.
- Target shape is fixed. Any change to paper setup, route, data, budget, scope, or uncertainty is a deviation before it can support a claim.
- Settings are constant only after manifest consensus across every cell, never from the first completed manifest.
- Failed gates trigger the correction loop: classify mismatch, repair earliest wrong layer, invalidate downstream artifacts, rerun, re-verify.
- Every `[[figures]]` entry carries the paper caption verbatim and the figure-reading checklist fields before any script or assembly code for that figure lands.
</checklist>

## Audit Kernel

<persistence name="audit">
- Audit work is non-substitutable. Every `audit`-kind attempt requires a host-spawned subagent; the caller cannot roleplay, self-review, or invent an actor id.
- Keep spawning until the host returns a real subagent id and a written `verify/verify_<artifact>_<date>.md` file, or the host reports subagents unavailable.
- If subagents are unavailable, halt with `blocked: verifier subagent unavailable` and leave the gate open.
- The audit brief includes this exact line: "Coverage, not filtering — report every finding, including uncertain or minor ones; the calling skill ranks and decides."
- Before `flow attempt finish` on an audit attempt: a subagent was spawned, the actor differs from the artifact author, the report exists, a sibling `.toml` exists, and `--report` points at the returned report.
- Host defaults toward solo execution are overridden. If the gate requires audit, perceived tractability is irrelevant.
</persistence>

`flow` enforces part of this mechanically: audit attempts need `--report`, the report and sidecar are hashed, sidecar `status = "pass"` is required, and producer/auditor identities must differ. Prompt instructions route the agent into that mechanism; they do not replace it.

## References

Consult only when needed:

- [references/gate-contracts.md](references/gate-contracts.md) — detailed per-gate commands, cell route fields, repair loop, closeout, and resume semantics. Consult before authoring or advancing a gate.
- [AGENTS.md -> Audit dispatch](../../../AGENTS.md#audit-dispatch) — harness-wide audit contract.
- [AGENTS.md -> Pre-compute figure-reading checklist](../../../AGENTS.md#pre-compute-figure-reading-checklist) — required before script/assembly for figures.

## Activation

- User asks to reproduce, redo, or calibrate against a published paper.
- A `/solve` session expands into several figures of the same paper.
- A `/download-ref` paper should be put through the harness.

## Inputs

- Paper identifier: arXiv id, DOI, official code/data URL, or local rendered paper path.
- Coverage scope: default full paper figures/main results.
- Compute budget: defaults from cluster profile and method cards unless user narrows it.

## Spine

```text
source -> protocol -> plan -> script -> trust -> run -> assemble -> close
```

Each gate advances only when its `flow attempt finish` command exits 0 and the gate's `[[checks]]` pass. `flow status <run>` is the only valid gate-state statement.

| Gate | Producer action | Audit required |
|---|---|---|
| source | populate `sources/` and source rows | no |
| protocol | fill `protocol.toml` from primary sources | **yes** |
| plan | author `reproduce-plan.toml` | no |
| script | implement and register `[entry]` | **yes** |
| trust | run known-answer points | no |
| run | execute cells via `/parameter-scan` and `/slurm` as needed | no |
| assemble | walk all manifests and render figures | no |
| close | write `run-report.md` and register deliverables | **yes** |

Detailed gate commands live in [references/gate-contracts.md](references/gate-contracts.md).

## Minimal Gate Pattern

For a non-audit gate:

```text
tools/cli/flow attempt start results/<run> <gate> --kind run --actor <main-actor>
# produce/register artifacts
tools/cli/flow attempt finish results/<run> <attempt>
tools/cli/flow require results/<run> <gate>
```

For an audit gate:

```text
# spawn verifier subagent first; do not self-review
tools/cli/flow attempt start results/<run> <gate> --kind audit --actor <returned-subagent-id>
tools/cli/flow attempt finish results/<run> <attempt> --report verify/verify_<artifact>_<date>.md
tools/cli/flow require results/<run> <gate>
```

The audit report must be written by the spawned subagent and have a sibling typed sidecar. If that is not true, the attempt is invalid even if the prose sounds correct.

## Evidence Rules

- Scheduler status, `ssh` exit status, and completed jobs are operational facts only. Fetched manifests and checks are evidence.
- `run` accepts only declared manifests whose route fields match `[[cells]]`, whose hashes are fresh, whose producer role is `run`, and whose observed set covers the declared cells.
- `assemble` must walk every manifest, prove constant vs varying settings by consensus, and render each declared figure from current-run evidence.
- `close` cannot pass with missing deliverables, stale figures, unsafe entrypoints, or an unaudited report.

## Failure Handling

When a gate fails, choose one real path:

1. Repair the earliest wrong layer and rerun the affected gate.
2. Record a `[[deviations]]` or `[[repairs]]` row, then rerun downstream gates.
3. Ask the user to decide between concrete options.
4. Record a user-approved override with `flow override`.
5. Stop with the gate open.

Never patch downstream prose or figures to hide an upstream failed check.

## Closeout

Every turn in an active reproduction ends by emitting `tools/cli/flow status <run>` or `--json` for tooling. Do not paraphrase the gate state. If an audit attempt finished in the turn, the status must reflect a distinct actor and a returned report.

Before declaring the reproduction complete, `tools/cli/flow require <run> close` exits 0. Then `/report` can render the shareable HTML.

## Composition

- `/verify` — spawned audit dispatcher for protocol, script, close, mismatch, and result audits.
- `/parameter-scan` — grid/cell decomposition and assembly.
- `/slurm` — remote execution for non-trivial cells.
- `/scaling-fit`, `/cross-method-check` — optional verification and analysis follow-ups.
- `/report` — plan-stage ratification and close-stage HTML deliverable.

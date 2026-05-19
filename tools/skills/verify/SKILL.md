---
name: verify
description: Use after writing or modifying an important artifact (protocol TOML, run plan, reproduction script, computed result, final run report, KB card) or when a reproduction gate fails and needs independent mismatch triage.
---

# verify

MUST SPAWN a real high-effort review subagent to audit an artifact against its declared reference. Generic over target. The subagent reads both sources end-to-end and returns a structured diff report. Never modifies anything.

The verifier must be a **different actor** from the artifact's author. Flow's `audit` check kind enforces this mechanically; this skill is the dispatcher.

Do not roleplay the verifier. Do not write the verifier report yourself. Do not invent reviewer ids. Do not record or finish a flow audit unless the spawned subagent actually returned the review. If the host cannot spawn a verifier, stop with `blocked: verifier subagent unavailable` and leave the gate open.

## When to activate

- After writing or editing a `protocol.toml`, KB card, reproduction entry, or run report.
- After producing a result, figure, or artifact bundle.
- Before claiming a reproduction complete; before merging a KB-card edit.
- When a flow gate fails (`flow check` shows failures) — use `mismatch` mode.

## Inputs

- `<artifact>` — file path of the artifact under review.
- `--against <reference>` — optional. Auto-inferred when obvious.
- `--mode <protocol | plan | kb-card | script | result | mismatch | close>` — selector; picked from artifact extension + content when absent.

## Dispatch

MUST SPAWN the review subagent using the host subagent/delegation tool, with the same model id, reasoning/effort, sandbox, approval policy, and tool access as the main agent. **Same actor cannot author and verify** — flow rejects the `audit` check if `--actor` matches the producer's actor. Record the returned subagent id/name as `reviewer`.

The verifier brief includes:

- The verbatim artifact + the verbatim reference (or precise line range).
- "Think deeply. Inspect both sources end-to-end before reporting; avoid skim-based conclusions."
- "You are independent from the author. Treat author comments and summaries as claims to check, not evidence."
- The per-mode axes below.
- "Output the per-axis status table. Do not write Action items or fixes — that is the calling skill's job."

Minimum context bundle: the artifact, the primary source (or exact excerpts), the current `protocol.toml` when the artifact is downstream of it, and the exact question (which claim, gate, or mismatch is being audited).

## Per-mode axes

### `kb-card`

Per AGENTS.md provenance discipline:

- **Literal** → grep the cited literature file for the verbatim phrase. ✓ with line number, ✗ unsupported, ⚠ near-match.
- **Analytic** → row states a derivation. ✓ if stated, ⚠ if unstated.
- **Harness anchor** → row names a `results/` path and cross-check method. ✓ if both, ⚠ if either missing.
- *Untagged* → ✗.

### `protocol`

Compare the protocol against declared primary sources.

1. **Source authority** — only `primary` rows support paper-derived claims; `hint` rows require an explicit assumption flag.
2. **Claim support** — each claim cites a primary passage or is marked `assumption=true`.
3. **Check coverage** — each non-assumption claim is covered by ≥1 `[[checks]]` entry or by a justified deviation.
4. **Generic check shape** — checks use one of the eight kinds: `audit`, `run`, `exists`, `agree`, `near`, `fresh`, `cover`, `support`; ids are unique override handles. No paper-specific or domain-specific kind names.
5. **Cell routes** — every executable cell declares `method`, `stack`, `route`, `source`, `check`, `state`, and `scope`; `route` is `paper`, `canonical`, `fallback`, or `deviation`.
6. **Route authority** — `paper` routes cite primary / official sources, `canonical` routes cite a method card or stack card, `fallback` routes cite the method card's next recommended fallback stack, and `deviation` routes cite a deviation id before compute. Generic installed libraries are not fallback authority. Empty, failed, or skipped route state blocks compute unless scoped as a declared deviation or pending item.
7. **Deviation clarity** — declared differences from the paper are scoped, claim-tagged, and have their own checks.
8. **Repair clarity** — post-failure or contract-changing edits have `[[repairs]]` rows with `from`, `wrong`, `changed`, `invalidate`, and `state`.
9. **Gate completeness** — every gate the flow template declares has checks sufficient to prevent stale or unsupported artifacts from passing.

Severity tags: `supported`, `unsupported`, `hint-leak`, `assumption`, `deviation`, `repair`, `missing-check`, `missing-route`, `unsupported-route`, `non-generic`.

### `plan`

Compare `reproduce-plan.toml` and `run_spec.json` against the protocol and methodology source.

1. **Claim-to-route coverage** — every non-assumption claim has an executable `cell` route, artifact target, and check.
2. **Figure dependency graph** — shared artifacts and edges consistent with the protocol.
3. **Run-spec provenance** — cells carry source ids, claim ids, deviation ids, method, stack, route, check, state, scope, and settings.
4. **Trusted-reference reachability** — the chosen reference exercises the run code path at easier scale.
5. **Hint quarantine** — old data, old figures, old plans never serve as evidence.

Severity tags: `covered`, `missing-route`, `plan-gap`, `stale-dependency`, `provenance-gap`, `weak-reference`, `hint-leak`.

### `script`

Compare the script against the protocol and the cited methodology section.

1. **Claim coverage** — script produces evidence for every assigned claim.
2. **Route match** — imports, commands, entrypoints, manifests, and generated artifacts match each declared cell's `method`, `stack`, `route`, `source`, `check`, `state`, and `scope`.
3. **Deviation honesty** — every difference from the paper, method card, selected stack, or route check is recorded as a deviation.
4. **Manifest provenance** — script writes the fields required by `exists`/`agree`/`fresh`/`support` checks and registers evidence artifacts with the producer role required by the protocol.
5. **Regime support** — budgets and knobs are sufficient for the declared checks, not just plausible-looking numbers.

Severity tags: `match`, `proxy`, `route-mismatch`, `unrecorded-deviation`, `provenance-gap`, `regime-gap`.

### `result`

For each numerical claim: ✓ within paper's error bar, ⚠ outside paper but within convergence margin, ✗ disagrees. Confirm each result artifact is `current_run` evidence with matching hashes and manifest route fields matching the protocol cell.

### `mismatch`

Audit a failed gate. Input: the failing check, expected vs observed, protocol, source passages, scripts, manifests, prior repair attempt.

1. **Observed-vs-expected mismatch** — concrete disagreement with cited artifacts.
2. **Mismatch class** — `source_misread`, `unsupported_assumption`, `convention_mismatch`, `plan_gap`, `script_bug`, `stack_or_remote_failure`, `stale_or_provenance_gap`, `insufficient_convergence`, `statistical_noise`, `paper_ambiguity`, `out_of_scope`.
3. **Earliest wrong layer** — source/protocol, trusted reference, plan/run spec, script/aggregator, stack, raw cells, figure/report, or paper scope.
4. **Invalidation scope** — downstream gates that can no longer support claims.
5. **Repair row** — the next accepted artifact records the repair with invalidated gates and rerun state.

Severity tags: `classified`, `under-evidenced`, `source-layer`, `plan-layer`, `script-layer`, `compute-layer`, `assembly-layer`, `report-layer`, `scope-layer`.

### `close`

Audit the final run report, declared entry, protocol, verification reports, and manifest set.

1. **Claim boundedness** — every report claim maps to a protocol claim, a result artifact, and a verify report.
2. **Artifact provenance** — manifests carry required hashes, claim ids, deviation ids, method, stack, route, check, state, and scope.
3. **Gate closure** — every flow gate is `passed` (or the run is marked partial / has recorded overrides).
4. **Deviation visibility** — declared differences from the paper appear in the report, linked to protocol deviations.
5. **Repair closure** — each `[[repairs]]` row lists invalidated gates, and those gates have fresh passing attempts after the repair.
6. **Reproducibility** — declared entry + run command sufficient for fresh checkout.
7. **Audience-facing artifact** — when a `report_*.html` is in scope: every editorial sentence in `editorial.json` traces to its `sourced_by` (re-grep the cited file:line); rendered HTML conforms to `docs/DESIGN.md`; mobile rendering at 375×667 has no overflow and ≥ 44×44px tap targets.

Severity tags: `supported`, `unsupported-claim`, `hint-leak`, `stale-artifact`, `provenance-gap`, `open-gate`, `hidden-deviation`, `open-repair`, `repro-gap`, `editorial-leak`, `design-drift`.

## Output

Two files, side by side:

1. **`<run-dir>/verify/verify_<artifact-stem>_<date>.md`** — human-readable per-axis findings.
2. **`<run-dir>/verify/verify_<artifact-stem>_<date>.toml`** — machine-readable verdict sidecar consumed by `flow attempt finish` and surfaced in `flow status --json`. Renderers read claim verdicts from here, never by grepping the markdown.

The sidecar has a top-level gate status plus one `[[verdicts]]` entry per claim the audit voted on:

```toml
status = "pass"      # pass | warn | fail
mode = "protocol"    # protocol | plan | kb-card | script | result | mismatch | close
target = "protocol.toml"
hash = "sha256:..."  # optional, but required when target freshness matters
author = "codex:<author-session>"
reviewer = "subagent:<returned-id>"

[[verdicts]]
claim = "claim.scaling_exponent"
status = "pass"

[[verdicts]]
claim = "claim.universal_constant"
status = "warn"
note = "agrees within 2σ; paper's error bar tighter than ours"

[[verdicts]]
claim = "claim.critical_temperature"
status = "fail"
note = "disagrees by 4σ — see Axis 3"
```

Top-level `status` controls the audit gate: only `pass` passes. Per-claim `status` controls rendered claim chips. `note` is optional.

The markdown carries the verbatim passages, the per-axis table, and the detail. It is what humans read:

```markdown
# /verify report — <artifact> — <date>

**Mode**: protocol | plan | kb-card | script | result | mismatch | close.
**Reference**: <path / lines>.

| Axis / Row | Status | Severity | Claim ids | Notes |
|---|---|---|---|---|
| ... | ✓ / ⚠ / ✗ | ... | `fig4.shape, fig4.minimum` | ... |

## Detailed findings
### Axis N — <name>
... verbatim passage with line number, verbatim script snippet, conclusion ...
```

**No "Action items" section.** Translating findings into next-step options is the *calling skill's* job.

## Discipline

- Inspection-only. Never modify the artifact.
- Same actor cannot author and verify (flow's `audit` check enforces this).
- Conservative on ambiguity: prefer ✗ over rationalized near-matches.
- For Analytic and Harness anchors, the tag is sufficient provenance.
- Generic over artifact type and reference. No artifact-specific logic.
- Subagent matches the main agent's model/effort/sandbox unless the user asks otherwise.

## Composition

- Called by `/reproduce-paper` for protocol, plan, script, result, mismatch, and close audits.
- Called by `/report` for close-mode audit of the rendered HTML.
- Called by KB-card or script authors as a pre-commit gate.
- The subagent surfaces what is wrong; the *calling skill* translates findings into 2–3 user options via the host's native API (`AskUserQuestion` in Claude Code; equivalent in Codex). User ratifies; only then does cleanup happen.

In a flow-backed run, the caller records this audit as an `audit`-kind attempt on the relevant gate, writes the markdown report and typed TOML sidecar, attaches the report path with `--report`, then `flow attempt finish`. Flow's `audit` check verifies actor distinctness, report/sidecar freshness, and top-level sidecar `status = "pass"`.

## Anti-patterns

- Modifying the artifact from inside this skill.
- Treating KB-sourced protocol claims as primary-source support.
- Treating old scripts, plans, data, or figures as evidence without current hashes.
- Adding paper- or domain-specific kind names to `[[checks]]`.
- Closing a final run report without a `close`-mode review.
- Roleplaying a verifier in the main agent.
- Inventing a reviewer id or using role text as reviewer provenance.
- Finishing a flow audit without a returned subagent review.
- Single-line "looks fine" report — the structured per-axis table is the deliverable.
- Downgrading subagent model or effort.
- Subagent prescribing fixes / writing an `## Action items` section.

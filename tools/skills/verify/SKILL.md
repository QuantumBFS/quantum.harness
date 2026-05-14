---
name: verify
description: Use after writing or modifying an important artifact (protocol TOML, run plan, reproduction script, computed result, final run report, KB card) or when a reproduction gate fails and needs independent mismatch triage.
---

# verify

Dispatch a high-effort review subagent to audit an artifact against its declared reference. Generic over target. The skill is the dispatcher; the subagent reads both sources end-to-end and returns a structured diff report. The verifier never modifies anything.

The verifier must be independent from the authoring agent. If the current agent wrote or materially edited the artifact, it may run smoke tests but must still dispatch a separate verifier before the artifact can close a reproduction gate.

## When to activate

- After writing or editing a reproduction protocol TOML.
- After editing a KB card (anchors against literature).
- After writing a reproduction script (quantity / estimator / setup / regime against the paper).
- After producing a result or figure (numerical agreement against paper-reported values).
- After assembling a final run report or consolidated reproduction script.
- Before claiming a reproduction complete; before merging a KB-card edit.
- Pre-compute, to catch a methodological proxy before burning compute.

## Inputs

- `<artifact>` — file path of the thing to verify.
- `--against <reference>` — optional. Auto-inferred when obvious (KB card cites literature folder; script cites paper MD via comment header).
- `--mode <protocol | plan | kb-card | script | result | mismatch | close>` — optional selector; the skill picks from the artifact extension and content when absent.

## Dispatch

Spawn an independent review subagent using the same model, reasoning/effort, sandbox, approval policy, and tool access as the main agent unless the user explicitly requests a different verifier. The verifier brief includes:

- The verbatim artifact + the verbatim reference (or precise line range).
- "Think deeply. Inspect both sources end-to-end before reporting; avoid skim-based conclusions."
- "You are independent from the authoring agent. Treat the author's comments, summaries, and stated intent as claims to check, not as evidence."
- The per-mode axes below.
- Request a structured report (per-row / per-axis status with severity tags).

Inspection-only on both artifact and reference. Do not downgrade the model or effort for speed — parity-with-doer is the point.

Minimum context bundle:

- The artifact under review, verbatim or with exact line ranges.
- The primary source or exact primary-source excerpts when available.
- The current `protocol.toml` when the artifact is downstream of a protocol.
- Relevant `reproduce-plan.toml`, `run_spec.json`, scripts, manifests, figures, and check outputs for downstream artifacts.
- The exact question: what claim, gate, or mismatch is being audited?

KB cards, rendered notes, old results, and prior conversation summaries may be included as hints, but they cannot substitute for primary sources or current-run artifacts.

## Per-mode axes

### `kb-card`

Per AGENTS.md provenance discipline (Literal / Analytic / Harness anchor):

- **Literal** → grep the cited literature file for the verbatim phrase or number (modest format tolerance: `0.844` vs `0.84(4)`). ✓ with line number, ✗ unsupported, ⚠ ambiguous near-match.
- **Analytic** → confirm the row states a derivation (definition, limit, closed form). ✓ if stated, ⚠ if unstated.
- **Harness anchor** → confirm the row names a run path under `results/` and a cross-check method. ✓ if both present, ⚠ if either missing.
- *Untagged* → ✗ does not satisfy discipline.

### `protocol`

Compare the protocol TOML against the declared primary sources. Treat KB cards, rendered notes, scripts, prior plans, prior figures, prior data, summaries, and prior artifacts as hints only; they cannot become primary sources by being labeled that way in the protocol. Primary sources are the paper, supplement, official code, or official data. The audit is generic: it verifies source support and internal consistency, not domain truth by built-in type.

Axes:

1. **Source authority** — every source has an evidence authority; only `primary` rows support paper-extraction claims. `hint` rows may guide planning only; if a claim relies on a hint, it must be marked as an assumption unless confirmed by a primary source.
2. **Claim support** — each claim's statement is supported by the cited source passage or is explicitly recorded as an assumption/deviation.
3. **Check coverage** — each non-assumption claim is covered by at least one declared check or by a justified deviation.
4. **Generic check shape** — checks use mechanical kinds (`source_audit`, `command`, `manifest_fields`, `manifest_consensus`, `numeric_compare`, `freshness`, `verify`) and do not rely on `/reproduce-paper` knowing domain-specific concepts.
5. **Deviation clarity** — deliberate differences from the paper are explicit, scoped, and have their own checks.
6. **Gate completeness** — preflight, compute, assembly, and report gates have enough checks to prevent stale artifacts and unsupported claims from reaching the final report.
7. **Hint quarantine** — old scripts, figures, data, and plans are not accepted as evidence unless regenerated under the current protocol/script hashes or re-confirmed against primary sources.

Severity tags: `supported`, `unsupported`, `hint-leak`, `assumption`, `deviation`, `missing-check`, `non-generic`.

### `plan`

Compare `reproduce-plan.toml` and `run_spec.json` against the protocol and relevant primary-source methodology passages. This is the bridge audit: it checks whether the planned execution would actually produce evidence for the paper-derived claims.

Axes:

1. **Claim-to-route coverage** — every non-assumption protocol claim has an executable route, artifact target, and declared check, or is explicitly marked as a gap.
2. **Figure dependency graph** — shared artifacts and dependency edges are consistent with the protocol; no figure depends on an undeclared or stale artifact.
3. **Run-spec provenance** — cells carry the required source ids, claim ids, deviation ids, stack/profile identity, settings, and manifest contract.
4. **Trusted-reference reachability** — the selected trusted check exercises the same code path and observable path as production at easier scale.
5. **Remote/local clarity** — cluster execution, if used, is only a cell-running mechanism; monitoring, fetch, and manifest checks are declared.
6. **Hint quarantine** — old data, old figures, old plans, and KB hints are not accepted as evidence.

Severity tags: `covered`, `missing-route`, `plan-gap`, `stale-dependency`, `provenance-gap`, `weak-reference`, `hint-leak`.

### `script`

Compare the script against the protocol TOML plus the cited primary methodology section. Four axes:

1. **Claim coverage** — script produces evidence for every protocol claim assigned to it.
2. **Deviation honesty** — any difference from the protocol's paper-derived claims is recorded as a deviation, not silently treated as equivalent.
3. **Manifest provenance** — script writes the fields required by the protocol checks, including `evidence_class = "current_run"`, protocol hash, source/script identity, claim ids, assumptions, deviations, stack/profile identity, and artifact paths where applicable.
4. **Regime adequacy** — budgets and controlling knobs are sufficient for the protocol's declared checks, not merely for producing a plausible number.

Severity tags: `match`, `proxy` (same reported claim through a different path), `unrecorded-deviation`, `provenance-gap`, `regime-gap` (right method, underbudgeted).

### `result`

For each numerical claim (energy, gap, density, exponent, scaling collapse):

- Identify the paper's reported value or range from the source figure / table / text.
- Compare to the script's output. ✓ within paper's error bar, ⚠ outside paper but within convergence margin, ✗ disagrees beyond budget.
- Surface the verification table the paper itself reports (if any) and confirm reproduction.
- Confirm each result artifact is `current_run` evidence with matching protocol/script hashes, or mark it stale and unsupported.

### `mismatch`

Audit a failed gate or contradictory result. The input is a failure packet: expected claim/check, observed output, protocol, relevant source passages, scripts, manifests, and any prior repair attempt. The verifier classifies the earliest wrong layer and invalidation scope; it does not prescribe fixes.

Axes:

1. **Observed-vs-expected mismatch** — state the concrete disagreement and cite the artifacts supporting both sides.
2. **Mismatch class** — one of `source_misread`, `unsupported_assumption`, `convention_mismatch`, `plan_gap`, `script_bug`, `stack_or_remote_failure`, `stale_or_provenance_gap`, `insufficient_convergence`, `statistical_noise`, `paper_ambiguity`, or `out_of_scope`.
3. **Earliest wrong layer** — source/protocol, trusted reference, plan/run spec, script/check/aggregator, stack/cluster, raw cells, figure/report, or paper scope.
4. **Invalidation scope** — downstream artifacts and gates that can no longer support claims.
5. **Evidence sufficiency** — whether the failure packet contains enough primary/current-run evidence to classify the mismatch, or which evidence is missing.

Severity tags: `classified`, `under-evidenced`, `source-layer`, `plan-layer`, `script-layer`, `compute-layer`, `assembly-layer`, `report-layer`, `scope-layer`.

### `close`

Compare the final run report, consolidated script, protocol TOML, verification reports, and manifest set. This is the global feedback loop: no new domain truth is inferred here; the audit checks that final claims are bounded by already-reviewed evidence.

Axes:

1. **Claim boundedness** — every claim in the run report maps to protocol claims, result artifacts, and verification reports; no unsupported paper-reproduction language appears.
2. **Artifact provenance** — manifests and final artifacts carry evidence class, protocol hash, script/source identity, claim ids, assumptions, deviations, stack/profile identity, and artifact paths required by the protocol.
3. **Gate closure** — preflight, compute, assembly, and report checks are all passed, or the report explicitly marks the run partial/assumptive.
4. **Deviation visibility** — method/backend/estimator/sampling/boundary/budget/error-method differences are visible in the report and linked to protocol deviations.
5. **Reproducibility** — consolidated script and run command are sufficient for a fresh checkout against the declared harness environment.
6. **Execution summary boundedness** — `execution_summary.md` is treated as an index into manifests/checks, not as evidence by itself.

Severity tags: `supported`, `unsupported-claim`, `hint-leak`, `stale-artifact`, `provenance-gap`, `open-gate`, `hidden-deviation`, `repro-gap`.

## Output

Markdown report at `results/<run>/verify/verify_<artifact-stem>_<date>.md`. The report stops at the per-axis status table — the audit's deliverable is the diff, not the prescription. Suggested layout:

```markdown
# /verify report — <artifact> — <date>

**Mode**: protocol | plan | kb-card | script | result | mismatch | close.
**Reference**: <path / lines>.

| Axis / Row | Status | Severity | Notes |
|---|---|---|---|
| ... | ✓ / ⚠ / ✗ | match / proxy / unrecorded-deviation / regime-gap | ... |

## Detailed findings

### Axis N — <name>
... verbatim passage with line number, verbatim script snippet with line number, conclusion ...
```

**No "Action items" section.** Translating findings into next-step options is the *calling skill's* job, not the subagent's (see Composition below).

When `/verify` is part of a `tools/flow` run, the verifier still does not edit state. The caller records the review as an `attempt` on the relevant gate, attaches this report path, and finishes the attempt with `pass`, `fail`, or `blocked`. A failed report triggers the calling workflow's correction loop and downstream invalidation.

## Discipline (hard rules)

- Inspection-only. Never modify the artifact from inside this skill.
- Independent. The artifact author cannot satisfy this review with their own reasoning or smoke tests.
- Conservative on ambiguity: prefer ✗ unsupported over rationalized near-matches.
- For Analytic and Harness anchors, the tag itself is sufficient provenance — do not double-grep against literature.
- Generic over artifact type and reference. No artifact-specific or paper-specific logic.
- In `protocol` mode, do not invent domain-specific validator types. Domain-specific checks must be `kind = "command"` or an explicitly delegated `/verify` audit.
- Subagent configuration matches the main agent unless the user explicitly asks otherwise. No downgrade for speed.

## Composition

- Called by `/reproduce-paper` for protocol, plan/run-spec, script, result, mismatch, and close audits.
- Called by KB-card or script authors as a pre-commit gate.
- The verifier surfaces what is wrong; it does not decide what to do.
- **After the report lands, the calling skill (or the main agent) translates the findings into 2-3 Superpowers-style options** (Recommended first, each with one-line pros / cons) and presents them via `AskUserQuestion`. The user ratifies; only then does cleanup happen. Splitting audit (subagent) from prescription (main-agent fork) preserves the user's steering wheel.

## Anti-patterns (auto-reject)

- Modifying the artifact from inside this skill.
- Inventing a tag for an untagged numerical entry.
- Treating KB-sourced protocol claims as primary-source support.
- Treating old scripts, old plans, old data, or old figures as evidence without current hashes/provenance.
- Skipping `plan` audit when the run plan or cell spec materially determines what will be computed.
- Repairing a nontrivial mismatch without classifying the earliest wrong layer and invalidation scope.
- Adding paper/domain-specific validator types to the generic protocol layer.
- Closing a final run report without `close`-mode review or an equivalent independent reviewer.
- "Verified" without per-axis status table.
- Downgrading subagent model or effort.
- Single-line "looks fine" report — the structured table is the deliverable.
- Subagent prescribing fixes / writing an `## Action items` section — that is the calling skill's job.

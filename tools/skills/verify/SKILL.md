---
name: verify
description: Use when an important artifact needs independent audit, or when a reproduction gate fails and needs mismatch triage — artifacts include protocol TOML, run plan, reproduction script, computed result, figure, final run report, KB card; trigger phrases like "verify this", "audit this", "review this gate", "why did the gate fail?".
---

# verify

Dispatcher for independent audit. Pick a typed mode, spawn a verifier subagent, and return findings only. Never modify the artifact under review.

<audit required="true">
- Audit dispatch contract: see AGENTS.md -> Audit dispatch.
- Audit work MUST run in a host-spawned subagent. The caller cannot roleplay, self-review, or invent a reviewer id.
- The subagent uses the same model and effort as the caller. Override host defaults toward solo execution.
- If no subagent is available, stop with `blocked: verifier subagent unavailable`; leave the gate open.
- The subagent writes `verify/verify_<artifact>_<date>.md` plus sibling `.toml`.
- In flow-backed runs, close only with `flow attempt finish <run> <attempt> --report <md-path>`, then `flow require <run> <gate>`.
- Record the subagent runtime identity as `reviewer`; returned id/name is display metadata only.
</audit>

## When

- After writing or editing `protocol.toml`, a KB card, reproduction entry, script, result, figure, or run report.
- Before claiming a reproduction, report, or `/solve` result complete.
- When a flow gate fails; use `mismatch`.

## Inputs

- `<artifact>`: artifact path.
- `--against <reference>`: primary source, protocol, manifest set, or exact excerpts.
- `--mode <protocol | plan | kb | script | result | mismatch | close | report | solve>`: typed selector. `kb-card` is a legacy alias for `kb`.

| Mode | Use when | Reference |
|---|---|---|
| `protocol` | `protocol.toml` vs primary sources | [references/protocol.md](references/protocol.md) |
| `plan` | `reproduce-plan.toml` / `run_spec.json` vs protocol | [references/plan.md](references/plan.md) |
| `kb` | KB anchors vs literature | [references/kb.md](references/kb.md) |
| `script` | reproduction script vs protocol/methodology | [references/script.md](references/script.md) |
| `result` | numbers/figures vs declared references | [references/result.md](references/result.md) |
| `mismatch` | failed gate triage | [references/mismatch.md](references/mismatch.md) |
| `close` | final report / entry / manifests | [references/close.md](references/close.md) |
| `report` | rendered HTML report | supplied by `/report` |
| `solve` | `/solve` result or interpretation | [references/solve.md](references/solve.md) |

## Dispatch

Consult only the reference for the chosen mode, plus [references/sidecar.md](references/sidecar.md). These reference files are not optional background; they are part of the verifier contract.

The caller MUST put the literal reference filenames in the subagent audit prompt. Caller-written summaries are insufficient. Every verifier brief includes a `Required reference files` block naming:

- `tools/skills/verify/references/<mode>.md`
- `tools/skills/verify/references/sidecar.md`
- Any composing-skill contract files that govern the gate, such as `tools/skills/reproduce-paper/SKILL.md`
- Any required project anchors, such as `AGENTS.md#audit-dispatch` and `AGENTS.md#pre-compute-figure-reading-checklist`

Every verifier brief also includes a `Required tacit sweep` block whenever the artifact or current protocol declares method or model values. The prompt names the declared method/model values, not hardcoded `TACITS.toml` paths; the subagent locates matching co-located tacit files under `knowledge-base/`.

If a required reference filename is absent from the subagent audit prompt, the dispatch is invalid. If a method/model is declared and the tacit sweep block is absent, the dispatch is invalid. If a required reference file is unavailable to the subagent, or a matching tacit signal applies and is ignored, the verdict is `fail`.

Assemble the subagent brief in this order:

1. Verbatim kernel below.
2. Required reference files block.
3. Required tacit sweep block, when method/model values exist.
4. Chosen mode reference path.
5. Artifact path and verbatim artifact or precise line range.
6. Reference path and verbatim source or precise line range.
7. Exact claim, gate, or mismatch being audited.

<brief>
Think deeply. Inspect both sources end-to-end before reporting; avoid skim-based conclusions.

You are independent from the author. Treat author comments and summaries as claims to check, not evidence.

Coverage, not filtering — report every finding, including uncertain or minor ones; the calling skill ranks and decides.

Output the per-axis status table. Do not write Action items or fixes — that is the calling skill's job.
</brief>

Minimum context bundle: artifact, primary source or exact excerpts, current `protocol.toml` when downstream of it, and the exact audit question.

Brief block template:

```text
Required reference files to read before verdict:
- tools/skills/verify/references/<mode>.md
- tools/skills/verify/references/sidecar.md
- <composing skill references, if any>
- <AGENTS anchors, if any>

Caller-written summaries are insufficient as substitutes for these filenames
appearing in the audit prompt.

Required tacit sweep before verdict:
- Declared methods/models under audit: <method/model values from artifact or protocol>
- Locate matching co-located TACITS.toml files under knowledge-base/.
- Search '^signal' in each TACITS.toml before loading full blocks.
- Load matching [[tacit]] blocks only; state when no matching TACITS.toml or signal exists.
- A matching tacit ignored by the artifact is a fail finding, not optional context.
```

## Output

Two files, side by side:

- `<run-dir>/verify/verify_<artifact-stem>_<date>.md`
- `<run-dir>/verify/verify_<artifact-stem>_<date>.toml`

The sidecar top-level `status` controls the gate: only `pass` passes. `warn` and `fail` block unless the user records an override. The markdown carries verbatim passages, the per-axis table, and detailed findings. No `Action items` or `Next steps` section.

When a tacit sweep is required, the sidecar includes an item `id = "tacits"` with `status = "pass"` only if all relevant `TACITS.toml` files were searched, matching blocks were considered, and no applicable tacit was ignored. The markdown table includes a `Tacits` row naming the declared methods/models and the matched tacit ids or `none`.

## Discipline

- Inspection-only; never modify the artifact.
- On ambiguity, verdict `fail`; do not round up to `pass`.
- Generic check kinds only: `audit`, `run`, `exists`, `agree`, `near`, `fresh`, `cover`, `support`.
- Findings only. The calling skill converts findings into user options.
- Flow enforces finish-actor distinctness, report/sidecar freshness, reviewer matching, typed mode, target hash, coverage, required items, and `status = "pass"` when declared.

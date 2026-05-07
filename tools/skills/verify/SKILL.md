---
name: verify
description: Use after writing or modifying an important artifact (knowledge-base card, reproduction script, computed result) to dispatch a high-effort review subagent that audits the artifact against its declared reference. Generic over target — KB card vs literature, script vs paper methodology, result vs paper-reported numbers.
---

# verify

Dispatch a high-effort review subagent (Opus, max effort) to audit an artifact against its declared reference. Generic over target. The skill is the dispatcher; the subagent reads both sources end-to-end and returns a structured diff report. The verifier never modifies anything.

## When to activate

- After editing a KB card (anchors against literature).
- After writing a reproduction script (quantity / estimator / setup / regime against the paper).
- After producing a result or figure (numerical agreement against paper-reported values).
- Before claiming a reproduction complete; before merging a KB-card edit.
- Pre-compute, to catch a methodological proxy before burning compute.

## Inputs

- `<artifact>` — file path of the thing to verify.
- `--against <reference>` — optional. Auto-inferred when obvious (KB card cites literature folder; script cites paper MD via comment header).
- `--mode <kb-card | script | result>` — optional override; the skill picks from the artifact extension and content.

## Dispatch

Spawn an Agent subagent with `model: "opus"`, `subagent_type: "general-purpose"`. The prompt MUST include:

- The verbatim artifact + the verbatim reference (or precise line range).
- "Think deeply, max effort, do not skim. Read both sources end-to-end before reporting."
- The per-mode axes below.
- Request a structured report (per-row / per-axis status with severity tags).

Read-only on both artifact and reference. Do not downgrade the model or effort for speed — parity-with-doer is the point.

## Per-mode axes

### `kb-card`

Per AGENTS.md provenance discipline (Literal / Analytic / Harness anchor):

- **Literal** → grep the cited literature file for the verbatim phrase or number (modest format tolerance: `0.844` vs `0.84(4)`). ✓ with line number, ✗ unsupported, ⚠ ambiguous near-match.
- **Analytic** → confirm the row states a derivation (definition, limit, closed form). ✓ if stated, ⚠ if unstated.
- **Harness anchor** → confirm the row names a run path under `results/` and a cross-check method. ✓ if both present, ⚠ if either missing.
- *Untagged* → ✗ does not satisfy discipline.

### `script`

Compare the script against the paper's figure caption + methodology section. Four axes:

1. **Same quantity** — caption's target observable = what the script computes (not a related-but-different quantity).
2. **Same estimator** — paper's methodology names a procedure; script implements that procedure (not a cheaper proxy with the same expectation but different variance scaling).
3. **Same setup** — Hamiltonian sign / normalization, BC, lattice, sector match.
4. **Same regime** — χ, N_S, sweep budget sufficient to validate the paper's *methodological* claim (not just the mean). Example: a paper claiming slower-than-log error scaling cannot be validated by a script with budget that swamps that scaling.

Severity tags: `match`, `proxy` (same mean, different variance), `setup-mismatch` (wrong physics), `regime-gap` (right method, underbudgeted).

### `result`

For each numerical claim (energy, gap, density, exponent, scaling collapse):

- Identify the paper's reported value or range from the source figure / table / text.
- Compare to the script's output. ✓ within paper's error bar, ⚠ outside paper but within convergence margin, ✗ disagrees beyond budget.
- Surface the verification table the paper itself reports (if any) and confirm reproduction.

## Output

Markdown report at `results/<run>/verify_<artifact-stem>_<date>.md`. The report stops at the per-axis status table — the audit's deliverable is the diff, not the prescription. Suggested layout:

```markdown
# /verify report — <artifact> — <date>

**Mode**: kb-card | script | result.
**Reference**: <path / lines>.

| Axis / Row | Status | Severity | Notes |
|---|---|---|---|
| ... | ✓ / ⚠ / ✗ | match / proxy / setup-mismatch / regime-gap | ... |

## Detailed findings

### Axis N — <name>
... verbatim passage with line number, verbatim script snippet with line number, conclusion ...
```

**No "Action items" section.** Translating findings into next-step options is the *calling skill's* job, not the subagent's (see Composition below).

## Discipline (hard rules)

- Read-only. Never modify the artifact from inside this skill.
- Conservative on ambiguity: prefer ✗ unsupported over rationalized near-matches.
- For Analytic and Harness anchors, the tag itself is sufficient provenance — do not double-grep against literature.
- Generic over artifact type and reference. No artifact-specific or paper-specific logic.
- Subagent dispatched with `model: "opus"` and explicit max-effort framing. No downgrade for speed.

## Composition

- Called by `/reproduce-paper` for each (figure, script, result) triple before claiming reproduction.
- Called by KB-card or script authors as a pre-commit gate.
- The verifier surfaces what is wrong; it does not decide what to do.
- **After the report lands, the calling skill (or the main agent) translates the findings into 2-3 Superpowers-style options** (Recommended first, each with one-line pros / cons) and presents them via `AskUserQuestion`. The user ratifies; only then does cleanup happen. Splitting audit (subagent) from prescription (main-agent fork) preserves the user's steering wheel.

## Anti-patterns (auto-reject)

- Modifying the artifact from inside this skill.
- Inventing a tag for an untagged numerical entry.
- "Verified" without per-axis status table.
- Downgrading subagent model or effort.
- Single-line "looks fine" report — the structured table is the deliverable.
- Subagent prescribing fixes / writing an `## Action items` section — that is the calling skill's job.

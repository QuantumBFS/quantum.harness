---
name: reproduce-paper
description: Use when the user wants to reproduce the figures and main results of a published paper end-to-end. Plans the multi-figure sequence, composes the harness primitives, and closes with a runnable script plus run report. Generic over papers.
---

# reproduce-paper

Thin orchestrator. The discipline lives in `protocol.toml`'s `[[checks]]`, evaluated mechanically by `tools/cli/flow`. This skill only sequences the work and composes the primitives.

## When to activate

- The user types "reproduce paper X", "redo the figures of Y", or names a paper to follow end-to-end.
- A `/solve` session is moving through several figures of the same paper and the user wants the full set.
- After `download-ref` lands a paper, the user wants to put it through the harness as a calibration target.

## Inputs

- A paper identifier (arXiv id, DOI, or a path under `knowledge-base/literature/<method>/`).
- A coverage scope (default: full-paper).
- A wall-clock / compute budget (defaults from cluster profile).

## Spine

```
source → protocol → plan → script → trusted_check → production → assembly → close
```

Each gate's contract lives in `protocol.toml` as `[[checks]]`. `flow` runs the checks on `flow attempt finish` and derives the gate status. The agent never declares pass.

## Workflow

1. **Init the ledger.** `tools/cli/flow init results/<run> --template tools/flow/templates/reproduce-paper.toml`. This is the first run-dir action.

2. **Author the contract.** Copy `tools/templates/reproduce-paper/protocol.toml` to `results/<run>/protocol.toml` and fill it from the primary source: `[artifact]`, `[[sources]]`, `[[claims]]`, `[[checks]]`, `[[figures]]`, optional `[[deviations]]` and `[[pending]]`. Use one-word check kinds: `audit`, `run`, `exists`, `agree`, `near`, `fresh`.

3. **Audit the contract.** Start an `audit`-kind attempt on the `protocol` gate with a verifier subagent (different `--actor` from whoever drafted the protocol). The verifier writes a report; finish the attempt with `--report <path>`. `flow` checks actors differ and the report exists.

4. **Plan the figure graph.** Author `results/<run>/reproduce-plan.toml` (figure ids, categorisations — substantive / methodology / verification / cross-check — and dependency edges). Start and finish the `plan` attempt.

5. **Implement scripts.** One per figure (or one per stage). Start a `produce` attempt on `script`; register the script as an artifact (`flow artifact add`); start a separate `audit` attempt; finish both.

6. **Trusted reference.** For each substantive figure, run the script at a point where the answer is known (analytic limit, exact small instance, official benchmark). Declare the check as `kind = "near"`. Failure here blocks production.

7. **Production compute.** Dispatch via `/parameter-scan` + `/slurm` (or the declared primitive). The cell wrappers register manifests as artifacts. Production gate's `[[checks]]` enforce `exists`, `agree`, `fresh`.

8. **Assemble close.** Walk the run dir; generate `consolidated.{jl,py}` (all parameters explicit) and `run-report.md`. For each figure produce `figs/<id>.png` plus `figs/<id>.json` (interactive plot source). Independently audit the close.

9. **Render the deliverable.** `/report` consumes the run dir.

## Composition

- **Parameter sweeps** → `/parameter-scan`
- **Critical scaling** → `/scaling-fit`
- **Cross-checks** → `/cross-method-check`
- **Audits** (gate audit attempts in any mode) → spawn a verifier subagent with the host's option API or direct dispatch; pass it the protocol + primary source + artifact under review; have it write `verify/verify_<artifact>_<date>.md`; record the audit attempt with the verifier's actor id.
- **Cluster execution** → `/slurm` (called by `/parameter-scan`).
- **User-facing forks** → host platform's option API (Claude Code: `AskUserQuestion`; Codex: equivalent). Three options max, recommended first.

## Failed checks

When `flow attempt finish` reports a failing check:

1. **Repair the evidence** — fix the artifact, run a new attempt.
2. **Record a deviation** — edit `protocol.toml`'s `[[deviations]]` to declare the difference; re-run.
3. **Override** — present `AskUserQuestion` (or Codex equivalent) with the failing check as one option. On user confirmation, `flow override <run> <check-id> --reason "<text>"`. The override is recorded forever; downstream artifacts show ⊘.
4. **Stop** — always a real option.

Never edit the script, the protocol, or the run report to *make* a check pass without changing the underlying evidence.

## Resume

The plan file and `progress/events.jsonl` are durable. Re-running this skill on an existing run dir reuses figures already produced (manifest-driven). Failed figures surface with their failure mode; not auto-retried.

## Notes

- Paper-specific words (claim ids, figure ids, deviation labels) live as data values in `protocol.toml`. Never in `flow`'s vocabulary, never in this skill's check-kind names.
- Methodology absorption is a side-effect of running the verification figures the paper declares — they appear alongside the substantive figures because they are also `[[figures]]` entries with `claim_ids`.
- The writeup-handoff close (consolidated script + run report) happens in Step 8. Route to `scientific-writing` / `latex-paper-en` / `scientific-visualization` / `jupyter-notebook` for downstream artifacts.

## Related

- `/solve` — single-problem loop. This skill runs atop solve when the user wants the full paper.
- `/report` — renders the run dir as a shareable HTML page.
- `/verify` — audit subagent dispatcher; the audit-kind attempt this skill records is a `/verify` call.
- `/parameter-scan`, `/scaling-fit`, `/cross-method-check`, `/slurm` — primitives this skill orchestrates.

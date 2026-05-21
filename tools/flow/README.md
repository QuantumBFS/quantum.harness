# harness-flow

`harness-flow` is the generic gate ledger for long reasoning runs. It is not paper-specific: use it for reproduction, brainstorming-review loops, verifier-gated derivations, remote jobs, or multi-agent campaigns.

The tool is intentionally small:

- `gate` — a checkpoint whose status (`pending` / `passed` / `failed`) is **derived live** from the protocol's `[[checks]]` and the event log. Never stored; never declared.
- `strict` — optional gate flag in `flow.toml`. A strict gate must have its template-declared `attempts` finished and its template-declared `checks` present in `protocol.toml`; otherwise it cannot pass.
- `check` — a typed one-word predicate: `audit`, `run`, `exists`, `agree`, `near`, `fresh`, `cover`, or `support`. Check ids are global handles for overrides and cached run results, so `flow` rejects duplicate ids when it parses `protocol.toml`.
- `attempt` — one actor trying to satisfy one gate. Roles are typed: `audit`, `trial`, `run`, `report`. The `--actor` flag is the human-readable label; identity comes from host session ids (`CODEX_THREAD_ID`, `CLAUDE_SESSION_ID`) when present, then `FLOW_ACTOR_ID`, then the parent process id (`ppid:<n>`). `flow` records both start and finish identity; audit checks use finish identity when present. Audit attempts must attach a `verify_*.md` report plus sibling `verify_*.toml` sidecar; flow hashes both at finish, so post-finish edits invalidate the audit.
- `artifact` — a file with a stable content hash, an optional producer attempt, and a `deps` snapshot of any source hashes referenced by `fresh` checks at registration time.
- `producer` — an optional check field, for example `producer = "run"`. When present, each artifact consumed by the check must be registered from that attempt role. Trial artifacts cannot close run evidence.
- `scope` — `[artifact].scope` is typed: `full`, `main`, `subset`, `snapshot`, or `custom`. `flow status --json` emits a run `verdict`: `green`, `muted`, or `blocked`.
- `verdict` — a typed audit result written into a `verify_*.toml` sidecar next to its markdown report. Top-level `status = "pass"` is required for the audit check to pass; `warn` and `fail` block the gate. Per-claim `[[verdicts]]` are exposed via `flow status --json` for renderers.
- `decision` — a recorded fork choice: `flow decide <run> --id <id> --question "..." --choice "..."`. Surfaces in `flow status` so branches aren't buried in chat.
- `deviation` — a recorded departure from the protocol-declared contract: `flow deviate <run> --id <id> --statement "..."`. Renders alongside protocol-declared `[[deviations]]`.
- `override` — a user-confirmed bypass of a failing check: `flow override <run> <check-id> --reason "..."`. Surfaces as ⊘ in downstream artifacts.
- `child` — another flow attached to a parent campaign.

State is append-only. `progress/events.jsonl` is the source of truth (typed Rust enum, JSON-encoded); `progress/state.toml` is the derived projection for humans.

`flow status` is terse for humans: current gate, first blocker, and next command. `flow status --full` prints the full gate table with deviations, decisions, overrides, pending obligations, and the next runnable gate marker. `flow status --json` is the read API for tools (render.py, hooks, dashboards). Tools consume this — they never parse events.jsonl directly.

`run`-kind checks are evaluated by `flow attempt finish` (which has side-effect semantics by design) and their results are cached as events. `flow status` is pure: it never executes commands.

Each command takes a local `progress/.lock` while reading, appending, or rebuilding state. This serializes multiple local agents on the same checkout. Subagents and remote jobs should still report back to the main agent instead of writing the event log directly.

Artifact hashes use SHA-256 and are recorded as `sha256:<hex>`. Re-registering an artifact with a different hash naturally invalidates downstream `fresh` checks (their `deps` snapshot no longer matches). There is no separate "invalidate" command — status is always derived.

Audit sidecars are typed:

```toml
status = "pass"    # pass | warn | fail
mode = "script"    # protocol | plan | script | result | mismatch | close | report | solve | kb
target = "scripts/reproduce"
hash = "sha256:..." # optional current target hash
author = "<author-identity>"
reviewer = "<reviewer-identity>"
brief = "sha256:..."
coverage = true

[[items]]
id = "setup"
status = "pass"

[[verdicts]]
claim = "claim.energy"
status = "pass"
```

When `hash` is present, `target` must be present and match the current file hash at `attempt finish`. `author` and `reviewer`, when both present, must differ. When `reviewer` is present, it must equal the audit attempt's recorded finish identity (`codex:<id>`, `claude:<id>`, `flow:<id>`, or `ppid:<id>`).
Audit checks can require typed dispatch and coverage:

```toml
[[checks]]
id = "audit"
kind = "audit"
gate = "audit"
mode = "solve"
target = "result.json"
coverage = true
items = ["setup", "limits", "symmetry", "convergence", "claim"]
```

When `mode`, `target`, `coverage`, or `items` are declared on an audit check, `flow` verifies the audit sidecar matches them. Missing or non-passing items block the gate.

`cover` checks compare an observed file set to a declared set:

```toml
[[checks]]
id = "cells"
kind = "cover"
gate = "run"
pattern = "cells/*/manifest.json"
paths = ["cells/cell-0001/manifest.json", "cells/cell-0002/manifest.json"]
```

`pattern` is a simple `*` wildcard over relative paths. Flow walks only the literal directory prefix before the first wildcard and skips symlinked directories. This is intentionally generic: it catches missing, extra, trial, or orphan artifacts without knowing what the cells mean.

`support` checks dereference claim fields:

```toml
[[claims]]
id = "energy"
fields = ["cells/*/manifest.json:energy", "cells/*/manifest.json:stderr"]

[[checks]]
id = "energy"
kind = "support"
gate = "assemble"
claims = ["energy"]
producer = "run"
```

`run` checks can execute a declared entry command:

```toml
[entry]
run = "scripts/reproduce run"
help = "scripts/reproduce help"
dry = "scripts/reproduce dry"

[[checks]]
id = "entry"
kind = "run"
gate = "close"
entry = "help"
```

## Run

```bash
tools/cli/flow <command>
```

`make setup` builds the release binary used by this wrapper. `make skills` syncs Ion skills separately. If the binary is absent, the wrapper falls back to `cargo run`.

For a local shell shortcut during a session:

```bash
alias flow=tools/cli/flow
```

## Minimal Loop

```bash
flow init results/run-a --template tools/flow/templates/reproduce-paper.toml
flow next results/run-a

author=$(flow attempt start results/run-a protocol --kind run --actor agent:protocol-author)
flow artifact add results/run-a protocol results/run-a/protocol.toml --kind protocol --producer "$author"
flow attempt finish results/run-a "$author"

audit=$(flow attempt start results/run-a protocol --kind audit --actor agent:source-reviewer)
# write results/run-a/verify/protocol.md and results/run-a/verify/protocol.toml
flow attempt finish results/run-a "$audit" --report results/run-a/verify/protocol.md

flow require results/run-a protocol
flow status results/run-a
```

`init` copies the chosen template into `results/run-a/flow.toml` before creating
`progress/events.jsonl`, so each run keeps the exact gate contract it started
from.

Decisions and deviations are recorded as events, not chat-prose:

```bash
flow decide results/run-a --id scope --question "compute scope?" --choice "reduced grid" --reason "compute budget"
flow deviate results/run-a --id backend --statement "MPS at χ=30 instead of TTN" --reason "TTN not wired"
flow status results/run-a   # shows both in the projection
```

## Goal Prompt

Use `/goal` as the liveness layer and `harness-flow` as the truth layer:

```text
/goal Continue results/run-a until `tools/cli/flow require results/run-a close` exits 0, or stop after 20 turns / 6 hours. After each turn, run `tools/cli/flow status results/run-a` and report the current gate, latest verification, and blocker. Do not claim reproduction if any gate is failed.
```

The completion condition must cite the command the agent will run. Goal evaluators judge from the conversation transcript, so the agent must surface the relevant command output before claiming the goal is met.

## Optional Stop Hooks

Install a Stop hook only when you want deterministic continuation while a flow has runnable gates. It does not replace `/goal`; it prevents the agent from stopping while `tools/cli/flow next <run>` still has work.

For Codex, add this to a trusted `.codex/config.toml` in the repo or to `~/.codex/config.toml`:

```toml
[features]
codex_hooks = true

[[hooks.Stop]]

[[hooks.Stop.hooks]]
type = "command"
command = '"$(git rev-parse --show-toplevel)/tools/flow/hooks/stop-flow.sh" results/run-a close'
timeout = 30
statusMessage = "Checking harness flow"
```

For Claude Code, add this to the project hook settings:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/tools/flow/hooks/stop-flow.sh results/run-a close"
          }
        ]
      }
    ]
  }
}
```

The script exits immediately when `stop_hook_active` is already true, so it does not create an infinite Stop-hook loop. If the close gate is not passed and a runnable gate exists, it returns `decision = "block"` with the next gate. If no gate is runnable, it allows the stop and surfaces a blocker message.

Reference docs: Codex hooks https://developers.openai.com/codex/hooks, Claude Code hooks https://code.claude.com/docs/en/hooks.

## Reproduction Template

Tracked reusable gate contracts:

- `tools/flow/templates/reproduce-paper.toml` — full paper reproduction.
- `tools/flow/templates/solve.toml` — compact audited solve loop.

Add more tracked templates only when another workflow needs a different reusable gate graph.

## Campaigns

Use one child flow per independent paper or major reasoning branch. The parent flow should only track aggregate gates.

```bash
flow init results/campaign --template tools/flow/templates/campaign.toml
flow attach results/campaign results/campaign/runs/paper-a --as child
flow status results/campaign --recursive
```

Remote jobs do not write the event log directly. The main agent records an attempt as passed only after fetching manifests/reports and validating them locally.

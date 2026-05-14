# harness-flow

`harness-flow` is the generic gate ledger for long reasoning runs. It is not paper-specific: use it for reproduction, brainstorming-review loops, verifier-gated derivations, remote jobs, or multi-agent campaigns.

The tool is intentionally small:

- `gate` — a checkpoint that can pass, fail, block, or become invalidated.
- `attempt` — one actor trying to satisfy one gate. Roles are metadata: `--kind verify`, `--actor agent:source-verifier`, `--executor slurm:hpc2`, etc.
- `artifact` — a file with a stable content hash and optional producer attempt.
- `child` — another flow attached to a parent campaign.

State is append-only. `progress/events.jsonl` is the source of truth; `progress/state.toml` is rebuilt for humans.

Each command takes a local `progress/.lock` while reading, appending, or rebuilding state. This serializes multiple local agents on the same checkout. Subagents and remote jobs should still report back to the main agent instead of writing the event log directly.

Artifact hashes use SHA-256 and are recorded as `sha256:<hex>`.

If an existing artifact id is re-added with a different hash, `harness-flow` invalidates the producing gate and its downstream gates automatically. Finishing an older attempt after a newer attempt has started is rejected as stale.

## Run

```bash
tools/cli/flow <command>
```

`make setup` builds the release binary used by this wrapper. If the binary is absent, the wrapper falls back to `cargo run`.

For a local shell shortcut during a session:

```bash
alias flow=tools/cli/flow
```

## Minimal Loop

```bash
flow init results/run-a --template results/run-a/flow.toml
flow next results/run-a

attempt=$(flow attempt start results/run-a protocol --kind verify --actor agent:source-verifier)
flow artifact add results/run-a protocol results/run-a/protocol.toml --kind protocol --producer "$attempt"
flow attempt finish results/run-a "$attempt" --status pass --report results/run-a/verify/protocol.md

flow require results/run-a protocol
flow status results/run-a
```

If a source changes outside the `artifact add` path, invalidate from that artifact or gate explicitly. The producing gate and dependent gates become invalidated.

```bash
flow invalidate results/run-a --from protocol
flow next results/run-a
```

## Goal Prompt

Use `/goal` as the liveness layer and `harness-flow` as the truth layer:

```text
/goal Continue results/run-a until `tools/cli/flow require results/run-a close` exits 0, or stop after 20 turns / 6 hours. After each turn, run `tools/cli/flow status results/run-a` and report the current gate, latest verification, and blocker. Do not claim reproduction if any gate is failed, blocked, or invalidated.
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

## Template

```toml
[flow]
id = "paper_a"

[[gates]]
id = "source"

[[gates]]
id = "protocol"
requires = ["source"]
invalidates = ["plan", "script", "trusted_check", "production", "assembly", "close"]

[[gates]]
id = "plan"
requires = ["protocol"]
invalidates = ["script", "trusted_check", "production", "assembly", "close"]

[[gates]]
id = "script"
requires = ["plan"]
invalidates = ["trusted_check", "production", "assembly", "close"]

[[gates]]
id = "trusted_check"
requires = ["script"]
invalidates = ["production", "assembly", "close"]

[[gates]]
id = "production"
requires = ["trusted_check"]
invalidates = ["assembly", "close"]

[[gates]]
id = "assembly"
requires = ["production"]
invalidates = ["close"]

[[gates]]
id = "close"
requires = ["assembly"]
```

## Campaigns

Use one child flow per independent paper or major reasoning branch. The parent flow should only track aggregate gates.

```bash
flow init results/campaign --template results/campaign/flow.toml
flow attach results/campaign results/campaign/runs/paper-a --as child
flow status results/campaign --recursive
```

Remote jobs do not write the event log directly. The main agent records an attempt as passed only after fetching manifests/reports and validating them locally.

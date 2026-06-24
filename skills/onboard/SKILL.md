---
name: onboard
description: "Use when first-touch harness setup is needed: user is new, asks where or how to start, invokes `/onboard`, opens with an empty or unclear prompt, or has no configured harness environment."
---

# Onboard

First-touch **triggered setup**. Clarify what the user is considering, infer the tools the task depends on, confirm the install plan, then route to the right harness skill.

## Audience

The user may not know the harness vocabulary and may only have a vague first goal. Keep each question warm, short, and concrete. Do not ask them to name support tools.

## Workflow

### 1. Intent Gate

Before installing, configuring, or routing, get the first intent.

If the opening prompt already makes the intent concrete, use it and skip this gate. Otherwise ask one single-choice question. Use an interactive choice UI when the host supports it; otherwise show the same options as a numbered list and wait.

> Tell me what you’re considering first, so I can set up the harness properly. If none of these fit, describe the direction briefly.

Options:
- `Run a calculation`
- `Reproduce a paper`
- `Explore a model or physics question`
- `Set up for later`

If the user answers outside these options or uses a freeform "Other" field, ask at most one short follow-up, then classify triggers from that answer.

Completion criterion: one intent is selected, a freeform intent is understood, or the opening prompt already supplies an equivalent intent.

### 2. Task Detail

Ask only the next missing detail needed to decide triggers and routing:

- Run a calculation: ask for the model/problem and target quantity if absent.
- Reproduce a paper: ask for the paper, figure, or reproduction target if absent.
- Explore a model or physics question: ask for the model/topic/question if absent.
- Set up for later: ask whether the user wants minimal setup, common support tools, or a specific stack.

Completion criterion: the task is concrete enough to decide whether it needs source material, software docs, compute resources, and a method/software route.

### 3. Triggered Setup Survey

Inspect; do not install yet. Add a setup item only when a trigger below is active and the item is not already available.

| Trigger | Setup item | Availability check |
| --- | --- | --- |
| Ion-managed skills are missing or stale | `make skills` | `ion add`/skill state requires sync |
| Task may need source material beyond local KB: arXiv, DOI, PDF, captions, figures, methodology details, benchmark values, or external reference text | `pdf-render` | `.venv/bin/python -c 'import pymupdf4llm'` |
| Task may need precise/current package usage beyond local refs: package APIs, examples, setup, migrations, capabilities, or version-sensitive docs | `node` | Node.js 18+, `npm`, and `npx` |
| Task likely exceeds local compute, needs arrays/scans, or user wants reusable remote compute setup | `/setup-cluster` | `skills/using-slurm/profiles/active.toml` |
| A method/software route has been selected | matching stack install | Makefile `INSTALLABLE` plus `skills/<stack>/stack.toml` |

Source-material support is not a paper-only mode. It is triggered whenever the task may need material outside `.knowledge/` or the local skill references.

Completion criterion: every active trigger is either added to the pending install/config plan, marked already available, or explicitly skipped as irrelevant.

### 4. Route Software Before Installing Stacks

If the task involves a calculation, code, package use, or paper reproduction that needs a method/software route, consult the relevant local sources before proposing stack installs:

- `/model` or `/physics` cards for problem routing.
- `/method-*` skills for method choice.
- `/using-*` skills and `skills/<stack>/stack.toml` for software choice, install target, smoke test, and runtime profile.
- `find-docs` only when package/API details are harness-relevant, hard to find, or version-sensitive.

Present a single-choice fork with 2-3 real software/method options when there is a genuine choice. Each option gets a short reason and tradeoff. Include an `Other / preferred stack` escape hatch when the user may already have a preference.

Completion criterion: either a software route is selected, no route is needed yet, or the task is routed to `/model`, `/physics`, or `/reproduce-paper` to decide the route there.

### 5. Confirm Install Plan

Before running any install or configuration command, show one compact table:

| Benefit | Item | Action |
| --- | --- | --- |
| **cleaner PDF extraction** and **extracted figures** | `pdf-render` | `make install pdf-render` |
| **more precise package usage** | `node` | `make install node` |
| selected calculation stack | `itensors` | `make install itensors` |
| **remote jobs without re-asking** | cluster profile | `/setup-cluster` |

Only include rows that apply. Then ask one yes/no question:

> Install/configure these now?

If the user says no, skip the plan and continue only along paths that do not require the skipped setup.

Completion criterion: the user approves the plan, rejects it, or asks to change it.

### 6. Execute Approved Setup

For each approved Makefile target, confirm the target appears in `INSTALLABLE`, then run `make install <tool>`. For skill sync, run `make skills`. For cluster setup, hand off to `/setup-cluster`.

Classify failures:

- Support tools (`pdf-render`, `node`): say what failed, offer to debug, and continue if the task can proceed without them.
- Domain stacks: block compute on that stack until fixed.
- Cluster setup: continue local-only only if the task remains feasible locally.

Do not inline package-manager commands in chat. The Makefile and stack contracts own install details.

Completion criterion: every approved setup item is installed, skipped by the user, or failed with its effect on the task stated.

### 7. Route or Exit

- `Run a calculation`: route to `/model` for a specific Hamiltonian/model, or `/physics` for a cross-model question.
- `Reproduce a paper`: route to `/reproduce-paper`.
- `Explore a model or physics question`: route to `/model` or `/physics`; install nothing unless computation becomes necessary.
- `Set up for later`: exit after the approved setup plan is handled.

Completion criterion: the next skill owns the task, or setup-only onboarding ends with one line: `Harness setup handled. Bring a model, paper, or calculation when you are ready.`

## Rules

- No installs before intent, trigger survey, and install-plan confirmation.
- No support-tool questions before they are triggered by the task.
- No preinstalling all method stacks.
- One decision per question.
- Use interactive single-choice gates when available; otherwise use concise numbered options.
- Setup gates follow the project decision-anchor rule in `AGENTS.md`.
- Do not lecture about the harness, list every skill, or ask the user to read docs.

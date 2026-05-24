---
name: onboard
description: Use when the user is new to the harness, asks "where do I start" / "how do I use this" / "I'm new here", opens with an empty or unclear prompt, explicitly invokes `/onboard`, or starts a first session with no configured harness environment.
---

# Onboard

First-touch intake. Set up the core harness tools and domain environment, optionally configure the user's compute cluster, then get the user onto a real problem fast.

## Audience definition (binding)

<audience name="binding">
The user is on first touch — they may not know the harness vocabulary (skill, profile), have no `julia-env/`, and have ≤2 minutes of patience before the conversation feels bureaucratic. Every question MUST read as a single warm sentence, not a checklist.
</audience>

## When to activate

- "I'm new here" / "where do I start" / "how do I use this".
- Empty or unclear opening.
- User explicitly invokes `/onboard`.
- First session detected (no `julia-env/` directory).

## Workflow

### 1. Setup — do it, don't ask

<checklist name="setup">

- Install domain stacks on demand via `make install <tool>`, after confirming `<tool>` appears in the Makefile's `INSTALLABLE` list.
- Read the per-stack contract at `tools/software/stacks/<stack>.toml` for install commands, smoke tests, and upstream docs.

</checklist>

Run `make skills` only when skill sync is actually needed.

Install only the stack the user's first selected workflow needs. Do not pre-install other method stacks. Each additional stack is installed on demand when that method is first invoked.

#### 1a. Node toolchain (for `/report`)

`/report` renders its HTML deliverable from a Fumadocs / Next.js project at `tools/skills/report/site/`. This needs Node 18+ and `pnpm`. When the user's first selected workflow leads to a `/report` invocation — directly or via `/reproduce-paper` — run `make install report-site` once. The target probes for `node` and `pnpm`, installs `pnpm` via the local package manager if missing (Homebrew on macOS, `npm i -g pnpm` otherwise), then runs `pnpm install` inside the site directory. Idempotent on re-entry: subsequent calls skip if `tools/skills/report/site/node_modules/` already exists.

Do not pre-install this stack — wait until `/report` is the actual next step. Other workflows (`/solve`, `/model` calculations that don't ship a doc) don't need it.

Report one line:
- All good: "Domain stack ready."
- Something installed: "Installed [what]. Ready."
- Install failed: say what failed, offer to debug. Don't proceed until the stack works.

### 2. Cluster setup — warm gate, always asked

<checklist name="cluster-setup">

Skip this stage if `tools/cluster/active.md` already exists (user has a profile from a prior session — idempotent).

Otherwise, ask one warm gate via `AskUserQuestion`. Most paper-grade calculations end up on a remote cluster eventually, and even a quick setup now persists the profile so future sessions ship/submit/monitor/fetch automatically without re-asking:

<example name="warm-gate good">
*"Will you want to run on a remote cluster at some point (SLURM, PBS, plain ssh)? If yes, I'll capture the config now so future sessions don't have to re-ask. If local-only is genuinely all you need, that's fine too — pick that and we'll move on."*
</example>

<example name="warm-gate bad">
Cluster?
</example>

<example name="warm-gate cold">
Do you want to configure a cluster? Yes/No.
</example>

Options:
- "Yes, capture cluster config now (Recommended — persists for every future session)"
- `"Local-only for now"` — "No cluster config saved. Future remote runs will re-ask before they can ship."

If the user picks "local-only", continue to step 3. If "yes", continue inside this stage:

</checklist>

#### 2a. Path to profile

> *"What's the easiest way for you to share your cluster's setup? Either paste your docs URL — I'll pull out the partitions, walltime caps, and how Julia is provided — or run through 4 quick questions. Either way takes about a minute."*

Options:
- Text field for docs URL (the user pastes; the skill `WebFetch`'s it)
- "Walk me through the 4 questions"

#### 2b. From URL — dispatch a subagent for a thorough crawl

A single `WebFetch` rarely captures everything — most cluster docs sites have a sidebar with 5-10+ sub-pages (connection / scheduler / partitions / filesystem / modules / data) that each carry one piece of the profile. Dispatch an **Agent subagent** (`model: "opus"`, `subagent_type: "general-purpose"`, max-effort framing in the prompt) to crawl the docs site comprehensively.

<brief name="cluster-docs-crawl">

**Subagent brief**:
- Input: the cluster docs root URL the user provided (e.g., `https://docs.hpc.hkust-gz.edu.cn/en/docs/hpc12/`).
- Job:
  1. Fetch the root page; identify the sidebar / nav menu; enumerate every sub-page relevant to: **login & connection**, **scheduler & job submission**, **partitions / queues / resource limits**, **environment setup / modules / `.bashrc`**, **filesystem layout**, **network reach** (internet from login / from compute).
  2. Fetch each relevant sub-page; extract verbatim instructions (sbatch examples, partition tables, module load lines, ssh hostnames, etc.).
  3. Synthesize into the cluster profile schema declared in `tools/cluster/README.md`.
  4. **Identify harness-side gotchas not explicit in the docs**: e.g., non-interactive ssh sessions not sourcing `/etc/profile` (so scheduler binaries are off PATH); two scheduler binaries on the system (`/usr/bin/sbatch` Ubuntu default vs `/opt/slurm/bin/sbatch` cluster's own); login-shell-only quirks. These are inferred from "the docs assume X, our harness uses Y" reasoning.
- Output:
  - The full **sub-page URL index** for the cluster (table: URL → what it documents). This goes into the profile's "Documentation" section so the harness has complete coverage, not a single-link fallback.
  - The proposed `tools/cluster/<short-name>.md` content matching the schema.
  - A **"Harness-side gotchas"** section capturing inferred issues + their workarounds (e.g., "ssh with `bash -l -c '...'` to get a login shell so `/opt/slurm/bin` is on PATH").
  - Anything the subagent could *not* extract from the docs — flagged for fallback to step **2c** (interactive questions) on those specific fields only, not the whole profile.

**Coverage, not filtering.** Report every relevant sub-page URL, every partition row, every module-load line, every harness-side gotcha you spot — including ones you are unsure about or judge minor. Silently dropping a partition or a gotcha is the failure mode, not over-reporting.

</brief>

Display the proposed `tools/cluster/<short-name>.md` content inline as a fenced markdown block, then dispatch one `AskUserQuestion` with options: Accept and save, Edit then save, Discard and use walk-through (2c) instead. Write to disk only after the user picks Accept or completes an edit.

If the subagent fails outright (docs site is paywalled / JS-only with no API / 403 on subpages), fall through to **2c** (questions).

#### 2c. Walk-through fallback (≤4 questions, each warm)

Pre-amble:
> *"OK, let's walk through 4 things — each one fills in a field of your cluster profile."*

1. *"Paste the ssh command you use to reach the login node — e.g., `ssh -i ~/.ssh/id_rsa user@host`. A `~/.ssh/config` stanza works too."* Parse `host` / `user` / `identity_file` (and optional `port`) from the single input; default the alias to the cluster short-name. One paste → four fields, no question pile.
2. AskUserQuestion: *"Which workload manager does the cluster use?"* with options: `Slurm` / `PBS / Torque` / `LSF` / `Plain ssh, no scheduler` / `Not sure — I'll probe`.
3. *"What's your default queue or partition? You can override per job — this is just where jobs go if nothing else is specified."*
4. AskUserQuestion: *"Which region is the cluster in?"* with options: `Mainland China (mirrors will be set up downstream)` / `Outside mainland China (default mirrors)` / `Air-gapped / no internet from login` / `Not sure`.

Write the profile to `tools/cluster/<short-name>.md`, symlink `tools/cluster/active.md → <short-name>.md`. Confirm one line: *"Cluster profile saved at `tools/cluster/<name>.md`. Future jobs will use it automatically."*

Do NOT bootstrap Julia or instantiate environments here — that's `/setup-julia`'s job, dispatched on demand by `/slurm` when the first cluster Julia run happens.

### 3. Problem intake — skippable

Setup and cluster profile are now persisted. Some users want to dive into a problem immediately; some just wanted the harness initialized and will return later. Ask once via `AskUserQuestion`:

> *"Setup is done. Want to start on a problem now, or save what we have and exit?"*

Options:
- "Start a problem now (Recommended if you have one in mind)" — proceed to step 3a
- "Save setup and exit" — skip to exit

#### 3a. Describe the problem

> *"What problem are you trying to solve?"*

That's it. Don't list models. Don't explain the architecture.

### 4. Route

<checklist name="route">

If the user picked "Save setup and exit" in step 3, exit with one line: *"Harness ready. `/model` or `/physics` will route you when you bring a problem."*

Otherwise, infer the model or physics topic from the step 3a answer. Hand off to `/model` (if a specific Hamiltonian) or `/physics` (if a cross-model phenomenon question); the dispatcher reads the matching card. This skill exits.

If the user's prompt is ambiguous between two or three specific routes, surface candidates via the user-facing fork pattern → [AGENTS.md → Output norms](../../../AGENTS.md#ui-ux) (AskUserQuestion; 2–3 options; recommended first; Done always real). Each option is one candidate model card OR one candidate physics card. Do not enumerate the full model or physics card lists.

If nothing fits: *"That's outside current scope (ground-state lattice problems). Want me to try an off-skill approach, or help you reframe?"*

</checklist>

## What this skill does NOT do

- Lecture about the harness.
- Walk through a tutorial.
- Ask the user to read docs.
- Show a menu of 13 skills.
- Hardcode package-level install instructions (the stack contracts in `tools/software/stacks/*.toml` name install commands, smoke tests, and upstream docs; the Makefile and setup scripts execute them).
- Bootstrap Julia on the cluster (that's `/setup-julia`, dispatched by `/slurm` on first cluster Julia run).
- Pile questions on the user — every gate is one question with a clear *why* and an escape hatch.

## UX rule (applies to every gate in this skill)

**Every** user-facing question in this skill — including the warm gate in 2, the path-to-profile gate in 2a, **each** of the 4 walk-through questions in 2c, and the problem-or-exit gate in 3 — follows the pattern: *frame the why → state the consequence → offer the escape hatch → ask*. No question stands alone without context. Telegraphic prompts ("Cluster?", "URL?") are rude even when short. Warm-clear-concise.

One short setup → one optional cluster gate → one problem question → route. Then exit.

---
name: memorize
description: User-invoked at session end. Walk back through the session, distill the lessons that actually surfaced (user pushback, wasted compute, stack failures, caption misreads), and write them as TACITS.toml entries or AGENTS.md invariants so the harness remembers next time. The discipline that turns one wasted hour into a paragraph that saves the next hundred sessions.
---

# memorize

After a session that surfaced real problems — user "no, that's wrong" moments, wasted compute, stack failures, caption misreads, queue mishaps, retries that should have been one shot — look back, extract the signal, and write it into the right scope so future sessions don't re-walk the same path.

This is the discipline that converts session-level pain into harness-level rules and tacit knowledge.

## Audience definition (binding)

<audience name="binding">
The reader of a TACITS entry is a FUTURE agent (possibly different session) doing a one-line grep on `^signal`. They have NO access to this session's transcript. The reader of an AGENTS.md bullet is the next agent reading the project rules cold — they expect imperative-form rules, not stories.
</audience>

**Vocabulary.** A *lesson* is the conceptual finding from a friction moment. A *tacit* is one `[[tacit]]` row in a `TACITS.toml` file. An *entry* is one tacit OR one `AGENTS.md` bullet OR one `SKILL.md` paragraph — the materialized form of a lesson. One lesson becomes one entry in one scope.

## When to activate

- The user explicitly invokes `/memorize` at session end.

<checklist name="triggers">

Triggers worth memorizing:

- User pushback: "no, that's wrong", "you missed X", "I don't think so", "are you sure".
- Computational waste discovered post-hoc.
- Failure mode that took more than ~30 minutes to diagnose.
- Commit-then-revert cycle within the same session.
- User had to teach the agent a harness rule not already in `AGENTS.md` or any `TACITS.toml`.

</checklist>

This skill is NEVER agent-invoked. The user decides when a session's lessons are worth codifying. After a session with three or more clearly identifiable friction moments (per the trigger checklist above), the agent SHOULD surface one line at session end: "Several lessons surfaced this session — run `/memorize` if you want them captured." The agent NEVER starts the `/memorize` workflow without an explicit user invocation.

## Non-negotiables

<checklist name="non-negotiables">

- **One lesson, one entry.** Bundling unrelated lessons into one entry hides them from greppers and breaks the signal-first lookup discipline.

<example name="one-lesson bad">
[[tacit]]
signal = "ED segfault and wrong y-axis label"
understanding = "scipy_openblas32 has ILP issues at large N, AND we missed the L factor in fig 3c's caption"
action = "use openblas64 for N>20000; read figure captions verbatim before coding"
</example>

<example name="one-lesson good">
[[tacit]]
signal = "scipy.linalg.eigh segfault at N > 20000"
understanding = "scipy_openblas32 is 32-bit indexed; LAPACK can't address arrays past 2GB"
action = "link against openblas64 or fall back to dsyevr"

# …and a SEPARATE entry for the figure-reading lesson, in AGENTS.md, not TACITS.
</example>

- **Specific vs generic — pick the right scope.** Method/stack-specific facts → `knowledge-base/methods/<method>/TACITS.toml`. Model-specific → `knowledge-base/models/<model>/TACITS.toml`. Project-wide invariants → `AGENTS.md`. Skill behavior → that skill's `SKILL.md`. Don't dump everything into one big global file.
- **Every TACITS entry has `signal`, `understanding`, `action`, `tags`, `seen_at`.** Signal is what an agent or user sees FIRST (error message, symptom, surface keyword). Agents grep `^signal` to scan the index without reading the rest. `seen_at` is mandatory provenance.
- **Never invent lessons.** Every entry must trace to a specific moment in the session: cite the user message, the failing artifact, or the commit/PR that fixed it. Speculative "we MIGHT see this if…" lessons are anti-knowledge.
- **The user ratifies BEFORE write.** Render all drafts in one consolidated review block (one fenced diff or one fenced TOML/markdown block per entry). Dispatch one `AskUserQuestion` with options: Accept all, Edit selected entries, Reject some, Discard all. Write to disk only after the user picks an accept path and (if Edit) the edits are applied. Silent appends — any commit before the user picks an accept option — are forbidden.
- **Grep before write.** For each draft entry, grep `^signal` in every relevant `TACITS.toml` (path: `knowledge-base/methods/<method>/TACITS.toml` or `knowledge-base/models/<model>/TACITS.toml`) for keywords from the draft's signal line. For `AGENTS.md` bullets, grep `AGENTS.md` for the rule's keyword. If a match exists, append the current run dir to the existing entry's `seen_at` list rather than creating a duplicate.

</checklist>

## Inputs

- The current session — transcript, file changes, commits since session start, artifacts under `results/<run>/` if a reproduction was active.
- Optional: explicit moments the user wants to capture (`/memorize "the figure caption thing"`).

## Workflow

1. **Survey the session.** Walk back through the user's messages and the agent's actions. Flag every moment of friction:
   - User said "wrong", "you missed", "I don't think that's right", "are you sure", "should have", etc.
   - Agent had to retry a compute task (any cell ran more than once for the same scope).
   - A stack or tool failed in a way the agent had not anticipated (segfault, OOM, queue wait, timeout, silent wrong result).
   - A user instruction was given that should have been in `AGENTS.md` already.
   - Settle-time discipline was violated (declared success when not actually successful).
   - The agent over-promised then walked back ("oh wait, that's wrong").

   Do this step inline in the main agent — do NOT spawn a subagent. The main agent is the only context with the full session transcript; a subagent would have to be hand-fed the transcript and would lose the implicit memory of what was said.

   Coverage-not-filtering survey discipline: see [AGENTS.md → Audit dispatch](../../../AGENTS.md#audit-dispatch).

2. **Cluster by root cause.** Group friction moments by what they were ACTUALLY about — not what they looked like. A "wrong y-axis label" and a "wrong state selection" both root-cause to "did not read the caption before coding"; that's one lesson, not two. Forty friction moments often distill to three lessons.

3. **Classify scope** for EACH cluster. When a cluster has aspects of two scopes (e.g., a model-specific lesson that also implies a project-wide rule), SPLIT the cluster into one entry per scope rather than picking the more specific one. Hierarchy when truly identical content fits two scopes: most-specific wins (model > method > skill > project).
   - **Method/stack-specific** (e.g., dsyevd at large N, scipy_openblas32 ILP issues, ITensors bond-dim convergence quirk) → `knowledge-base/methods/<method>/TACITS.toml` as a new `[[tacit]]`. Promote `methods/<method>.md` → `methods/<method>/METHOD.md` folder if not already.
   - **Model-specific** (e.g., PXP 0+ basis combinatorics, J1-J2 critical-point convergence) → `knowledge-base/models/<model>/TACITS.toml`. Create the namespace when first needed.
   - **Project-wide invariant** (e.g., "read figure captions verbatim before coding", "audit declared stack vs actual imports") → `AGENTS.md` as a new bullet in the appropriate section. Phrase as a rule, not a story.
   - **Skill behavior** (e.g., "/slurm must check PD→R transition") → that skill's `SKILL.md`. Add as a step or an explicit constraint.

4. **Draft.** For each lesson, write the entry/edit. Keep it tight:
   - **TACITS entry**: `signal` one line (the keyword/error/symptom an agent will grep for); `understanding` 2–4 lines (root cause, named upstream component if known); `action` 2–4 lines (the concrete fix, not advice); `tags` 3–7 short tokens; `seen_at = ["<run-dir-or-session-anchor>"]`.
   - **AGENTS.md bullet**: one paragraph, imperative form. Cite the witnessing session. Place in the section whose theme matches.
   - **SKILL.md edit**: one paragraph or one new workflow step. Cite. Cross-reference the relevant TACITS if any.

5. **Show the user.** For each draft entry, render in this format: (1) a one-line cite of the friction moment that justified it; (2) a fenced block with the draft entry's full content; (3) the target file path. List all drafts in one message. Then dispatch one `AskUserQuestion` with options: Accept all, Edit selected, Reject specific entries, Discard all and rethink clustering.

6. **Apply.** Once ratified, write to the files. Single commit with title `memorize: <one-line summary>`. Body lists each lesson with its scope (TACITS / AGENTS.md / SKILL.md) and a one-line cite to the witnessing session (commit, message, or run dir). Include the `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer per project convention.

7. **Cross-link.** If a TACITS entry was added with `seen_at = ["results/<run>"]`, append a footer to `results/<run>/run-report.md` noting the lessons memorized from this run. Future readers of the run report find the lessons it produced.

## Output

- File edits / new entries in the right scopes.
- One commit per step 6 above (title, body, and Co-Authored-By trailer specified there).
- A 5–10 line summary back to the user: "Memorized N lessons across M files: …". List each lesson's signal + scope, nothing else.

## Composition

- Often invoked after `/reproduce-paper` close — especially when the close revealed waste.
- Composes with `/verify` only obliquely: a tacit whose action requires the verifier to check something new (e.g., "audit must check declared stack matches actual imports") gets a cross-reference added to the matching mode in `tools/skills/verify/SKILL.md`. Mode choice is by the audited artifact: protocol-level → `protocol` mode; script-level → `script` mode; result-level → `result` mode; KB-card-level → `kb-card` mode.
- Never invoked from inside another skill — this is a session-level retrospective, not a sub-step.

## Anti-patterns

<checklist name="hard-reject">

Mechanically detectable — auto-reject:

- **Writing a TACITS entry with no `seen_at`** — without provenance the lesson is hearsay.
- **Editing `AGENTS.md` without showing the diff to the user first** — even tiny rule additions are user-ratified.
- **Memorizing the same lesson twice (duplicate signal line)** — grep first; append `seen_at` to the existing entry instead.
- **Bundling unrelated lessons** into one big entry — they become ungreppable.

</checklist>

<checklist name="soft-warn">

Judgment calls — flag and reconsider:

- **Memorizing speculative lessons** ("we MIGHT see this issue if…") — only record what actually surfaced.
- **Skipping the cluster step (under-cluster)** — forty friction moments distilled to forty entries buries the signal.
- **Memorizing every minor agent error (over-memorize)** — only lessons that would have prevented real waste belong in the file.

</checklist>

## Example output

<example name="memorize-output">

**(a) Post-workflow summary user sees:**

> Memorized 7 lessons across 4 files:
> - `knowledge-base/methods/ed/TACITS.toml` — 7 `[[tacit]]` entries (segfault chain + stack drift + abandon-Python heuristic).
> - `AGENTS.md` — 3 new invariant bullets (feature-gap-is-not-route-authority, audit-stack-at-protocol-time, pre-compute-figure-reading-checklist) + new "Compute resources" section.
> - `tools/skills/slurm/SKILL.md` — layered settle-time discipline (PD→R + startup + long-run) in workflow Step 6.
> - `tools/skills/verify/SKILL.md` — figure-reading checklist + stack-claim-match as `script` and `result` audit axes.
>
> One commit: `memorize: stack drift, figure-reading, ED segfault chain, cluster settle-time from Turner 2018 reproduction`.

**(b) Sample TACITS entry with all required fields:**

```toml
[[tacit]]
signal = "scipy.linalg.eigh segfault at N > 20000"
understanding = """
scipy_openblas32 is 32-bit indexed; LAPACK can't address arrays past 2GB.
Numpy/scipy wheels on PyPI ship with this build by default.
"""
action = """
Link against openblas64 (system-wide or via conda-forge) or fall back
to dsyevr from scipy.linalg.lapack with explicit driver selection.
"""
tags = ["ed", "scipy", "lapack", "openblas", "segfault", "large-N"]
seen_at = ["results/turner-2018-fig3c/2026-05-12"]
```

</example>

Invoked after the Turner 2018 ED reproduction session, which surfaced five distinct friction clusters: (a) stack drift (raw scipy declared as quspin), (b) Fig 3c caption-misread (wrong y-axis label + wrong state pick), (c) ED-at-large-D segfault chain (four stacked failure modes), (d) local-vs-remote awareness gap (ran L=30 locally that belonged on the cluster), (e) cluster PD→R settle-time gap (treated `sbatch` success as compute success).

That is the volume and shape of a typical heavy-session `/memorize`. Most sessions produce 0–2 lessons; high-friction reproductions produce 3–6.

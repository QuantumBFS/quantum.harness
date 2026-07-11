---
name: challenge-report
description: Generate a challenge completion report from a finished run in tracks/. Checks submission cleanliness first, then walks through each block interactively.
---

# challenge-report

Build a polished HTML report for a completed challenge run. Unlike reproduce-paper reports (mechanical translation of run.json), challenge reports need user-authored narrative — significance, innovation, impact — so this skill drafts each block from available data and pauses for the user to modify or add before moving on.

## Outcome

`<run-dir>/report.json` + `<run-dir>/report.html` — a standalone page rendered by `/report`.

## Step 0 — Submission cleanliness check

**Run this before anything else.** The skill acts as a gatekeeper: verify the student's working tree is clean and all changes are in allowed locations.

1. Run `git status` and `git diff --stat HEAD` to list all changed, staged, and untracked files.

2. Classify every changed/untracked file into one of three categories:

   | Category | Pattern | Action |
   |---|---|---|
   | **Allowed** | Files under `tracks/<track>/solutions/` (the student's committed scripts and solution files) | Pass silently |
   | **Allowed** | Files under `tracks/<track>/results/` (the student's own result folder) | Pass silently |
   | **Allowed** | Updates to skills or knowledge base (`.knowledge/`, `skills/`, `.claude/skills/`) | Pass silently |
   | **Needs confirmation** | Anything else — track READMEs, top-level files, scripts, other tracks' solutions or results, etc. | List each file and ask the student to confirm the change is safe and intentional |

3. If there are files in the "needs confirmation" category, show them in a table with their status (modified/added/deleted) and ask:

   > "These files are outside your solutions/results folders and the knowledge base. Is each change intentional?"

   Present each file for confirmation. Do not proceed until the student confirms or reverts.

4. If the tree is clean (no uncommitted changes) or all changes are in allowed locations, print a short confirmation and move on.

**If the student has uncommitted changes in disallowed locations and cannot explain them, stop. Do not generate a report on a dirty submission.**

---

## Step 1 — Pick a result folder

Scan `tracks/*/results/*/run.json` for completed runs. A run counts as completed if at least one figure entry has a non-empty `results` object (i.e. `results.figure` or `results.match` exists). List them with track name, paper title, date, and scope. Let the user pick one.

If there is only one completed run, confirm it rather than presenting a list.

## Step 2 — Load context

Read three things from the selected run:

1. `run.json` — model, method, figures, verdicts, numbers
2. The track's paper reference `.md` file (the paper card in `tracks/<track>/`) — abstract, authors, significance
3. `tracks/<track>/README.md` — challenge framing

## Step 3 — Draft blocks one by one

The report has **4 sections**. Within each section, draft each block from available data, show it to the user, and let them **accept, modify, or add** before moving on. Use AskUserQuestion when available.

Present each drafted block as a compact preview (the key-value pairs, text, or table content). The user's choices are:
- **Accept** — use as drafted
- **Edit** — user provides replacement text
- **Add** — user adds a block after this one
- **Skip** — omit this block

---

### Section 1: Challenge

*The problem and why it matters.*

Draft these blocks in order:

1. **`text` — Problem statement.** Draft from the paper abstract: what physical phenomenon or computational challenge does this address? One paragraph, plain English.

2. **`card` "Significance" — Why this matters.** Draft from the abstract's broader-impact sentences. Contains:
   - `text` block: 2-3 sentences on scientific or practical significance.

3. **`kv` — Challenge metadata.** Pairs: Paper, Track, Target figures, System size.

After all blocks in this section are confirmed, ask: "Any additional blocks for the Challenge section?" If yes, let the user describe what to add.

---

### Section 2: Approach

*How the challenge was solved.*

4. **`badge` — Exact vs approximation.** From `method.exact` in run.json.

5. **`kv` — Method card.** Pairs: Method, Tool, Settings. From `run.json` method fields.

6. **`text` — Method narrative.** Draft from `method.note` in run.json. One paragraph explaining the approach in plain English.

7. **`table` — Cost estimates.** From `run.json` estimate array. Columns: Run point, Wall time, Memory.

After all blocks: "Any additional blocks for the Approach section?"

---

### Section 3: Results

*What was achieved.*

For each figure in `run.json`:

8. **`heading` — Figure title.** From figure id + plots description.

9. **`figures` — Side-by-side comparison.** Paper figure vs reproduction (if both exist).

10. **`verdict` — Pass/warn/fail.** From `results.match` and `results.why`.

11. **`table` — Key numbers.** From `results.numbers`.

12. **`lattice3d` — Interactive lattice view (offer when the data is site-resolved).** If the run produced per-site or per-bond data on a lattice (local order parameters, correlations, MC snapshots), offer to emit a lattix scene JSON (schema: `viz/README.md`) and embed it with `{"kind": "lattice3d", "src": "<scene>.json", "poster": "<figure>.png", "caption": "…"}` — the static figure doubles as the print fallback. Skip silently for scalar-only results.

After all figures: "Any additional blocks for the Results section?"

---

### Section 4: Highlight

*Innovation, significance, and broader impact.*

This section is primarily user-authored. Draft a starting point, but expect heavy editing.

12. **`card` "What's innovative" — Method innovation.** Draft a placeholder from the method choice: "Used [tool] with [key setting] to solve [challenge]." Ask user to replace with the actual innovation story.

13. **`card` "Significance of output" — What the results mean.** Draft from verdicts: "Successfully reproduced [N] figures, confirming [phenomenon]." Ask user to sharpen.

14. **`card` "Broader impact" — How this benefits understanding or applications.** Draft a placeholder: "This work [deepens understanding of X / enables Y application]." Ask user to fill in.

After all blocks: "Any additional blocks for the Highlight section?"

---

## Step 4 — Assemble and render

1. Collect all confirmed blocks into the 4-section `report.json` structure:

```json
{
  "title": "Challenge: <paper-title-short>",
  "eyebrow": "<track> Track",
  "url": "<paper-url>",
  "lede": "<one-line summary from user or drafted>",
  "sections": [ challenge, approach, results, highlight ]
}
```

2. Before writing, show the user the `lede` (one-line summary) and `title` for confirmation.

3. Write `report.json` to `<run-dir>/report.json`.

4. Render: `python3 skills/report/render_report.py <run-dir>`.

5. Show the path to `report.html` and offer to open it.

## Notes

- All block kinds used (`text`, `card`, `kv`, `figures`, `verdict`, `table`, `badge`, `heading`, `code`, `note`, `lattice3d`) are already supported by `/report`.
- If a figure's `results` is empty, show a `note` block with `"style": "pending"` instead of verdict/numbers.
- Math in text uses `$...$` for inline, `$$...$$` for display — the renderer handles LaTeX to MathML.
- Figure `src` paths are relative to `<run-dir>`.

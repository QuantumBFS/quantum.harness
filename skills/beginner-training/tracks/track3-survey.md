# Track 3 — Conduct a literature survey

**Time:** ~1–2 h · **Prereq:** Track 1 Step 2 (pdf-render) ·
**Live exercise:** build a small, real reference library in `.knowledge/`.

Part of the harness beginner training. Every step follows the Teaching
Protocol in `skills/beginner-training/SKILL.md`.

## Goal

Research starts from what's already known. This track teaches the two survey
tools: `/download-ref` (fetch one known paper: metadata, PDF, markdown render,
index entry) and `/survey` (explore a topic: parallel searches, then a curated
reference library). By the end the student has a topic library they'll reuse
in Track 5 when inventing a challenge.

## Scoped precheck

`.venv/bin/python -c "import pymupdf4llm"` — on failure → Track 1 Step 2 fix.

## Steps

### Step 1 — Pick a small topic (explicit gate)

Default suggestion: the paper the student reproduced in Track 2 (e.g. quantum
many-body scars for the ED track) — a survey is easiest to judge on a topic
you've touched. Ask; the student may name any topic. Keep the scope small: one
question, not a field.

### Step 2 — Download one known reference

Run `/download-ref` on the track paper's arXiv ID (e.g. `1711.03528` for the
ED track). Explain each stage as it happens: metadata lookup, PDF fetch,
markdown render, `INDEX.md` regeneration. Then open
`.knowledge/literature/INDEX.md` together and find the new entry.

### Step 3 — Survey the topic

Run `/survey` on the chosen topic. Explain what the parallel search strategies
are doing and let the student pick which directions to keep when the skill
asks. Expected outcome: a handful of new references land in the library with
BibTeX entries.

### Step 4 — Read the library like a researcher

Pick one downloaded paper and skim its rendered markdown together: abstract,
figures, conclusions — in that order. The lesson: a survey library is for
*targeted reading*, not cover-to-cover.

## Checkpoint — bogus input must fail, and the index must not lie

1. **Negative control**: run `/download-ref` on the nonexistent arXiv ID
   `2513.99999`. Expected: the pipeline reports the lookup failure and adds
   **nothing** to the library. A fetcher that "succeeds" on garbage input
   cannot be trusted on real input.
2. **Integrity check**: count entries in `.knowledge/literature/INDEX.md` and
   compare with the number of reference directories/PDFs actually present.
   The numbers must match — an index that over- or under-counts is worse than
   no index.

Checkpoint passes when both hold and the student can explain what each half
protects against.

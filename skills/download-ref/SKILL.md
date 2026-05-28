---
name: download-ref
user-invocable: false
description: Use when the user pastes an arXiv ID, a DOI, a paper title, a local PDF path, or a bibliography stub and wants it added to the harness's methodology references — phrases like "download this arXiv", "add a DMRG reference", "pull in DOI 10…", "render this PDF", "add a bibliography stub for".
---

# download-ref

Renders methodology PDFs into Markdown under `.knowledge/literature/<method>/`
and indexes them. Raw PDFs and extracted figures stay local (gitignored). The
workflow MUST be run via the bundled scripts — manual editing of `INDEX.md` or
rendered Markdown is not the intended path.

<example name="activate good">
User: "Pull arXiv 1008.3477 into the DMRG references." → download-ref fires.
</example>

<example name="activate not-applicable">
User: "Cite Hewson 1993 in the run report." → download-ref does NOT fire (citation already in KB); just cite directly.
</example>

## When to activate

Trigger phrases: "download this arXiv ID", "add a DMRG reference", "pull in
DOI 10...", "render this PDF I have", "add a bibliography stub for ...".

This is the repo-local adaptation of the `zlp-harness` download workflow. The
upstream workflow assumes a `.knowledge/` root; this harness uses
`.knowledge/` and organizes methodology references by method.

## Layout

```text
.knowledge/literature/
  ref.bib                           # source of truth (committed)
  <method>/
    INDEX.md
    <rendered-reference>.md
    .raw/                           # metadata + PDFs, gitignored
    .figures/                       # extracted PDF images, gitignored
```

| Path | Committed? |
|---|---|
| `ref.bib` (combined library) | YES |
| `INDEX.md` (per-method) | YES |
| `<rendered-reference>.md` | YES |
| `.raw/` | NO (gitignored) |
| `.figures/` | NO (gitignored) |

`ref.bib` is the human-edited source of truth. Each entry's `keywords`
field carries one or more method slugs (`keywords = {mps-based-algorithm}`,
or multiple comma-separated slugs for a paper relevant to several methods).
Per-method JSON manifests are derived from ref.bib via `bibtex_to_manifest.py`.

This layout matches sci-brain's KB conventions closely enough that
sci-brain tools (`download-ref`, `ideas`, `survey`) can operate on any
single method dir by passing `--kb .knowledge/literature/<method>`.

Method slugs MUST match an existing literature dir
`.knowledge/literature/<method>` when one exists. Use these canonical slugs:

```text
mps-based-algorithm
peps-based-algorithm
ltrg
quantum-monte-carlo
variational-monte-carlo-neural-quantum-states
quantum-circuit-simulation
ed
anderson-impurity
dmft
```

Introduce a new slug only when no existing method card matches the
methodology.

## Scripts

The helper scripts are bundled with this skill:

```sh
HELPERS="$(pwd)/skills/download-ref/helpers"
```

They are idempotent. Re-running a manifest skips existing metadata/PDFs and
overwrites rendered markdown from raw sources.

## Workflow

Run all six steps in order. Step 2 (bib edit) is your authored input; steps
3–6 (derive manifest / fetch / render / index) are idempotent and safe to
re-run. Step 7 (verify) is REQUIRED before reporting.

### 1. Resolve paths

```sh
METHOD=mps-based-algorithm
KB="$(pwd)/.knowledge/literature/$METHOD"
BIB="$(pwd)/.knowledge/literature/ref.bib"
mkdir -p "$KB"
```

### 2. Add (or edit) the entry in `ref.bib`

Open `.knowledge/literature/ref.bib` and add an entry. For an arXiv preprint:

```bibtex
@article{schollwoeck_2010_density,
  author = {U. Schollwoeck},
  title = {The density-matrix renormalization group in the age of matrix product states},
  year = {2010},
  journal = {Annals of Physics},
  eprint = {1008.3477},
  archivePrefix = {arXiv},
  doi = {10.1016/j.aop.2010.09.012},
  keywords = {mps-based-algorithm}
}
```

Patterns by entry type:

| Source | BibTeX type | Required fields |
|---|---|---|
| arXiv preprint (with venue) | `@article` | `eprint`, `archivePrefix = {arXiv}`, optional `doi`, `journal` |
| DOI-only journal article | `@article` | `doi`, `journal` |
| Book, lecture notes, closed source | `@book` or `@misc` | `title`, `author`, `year`, `note` |

`keywords = {<method>, ...}` is mandatory — it pins the entry to one or more
method dirs. Fields like `year`, `author`, `journal` act as overrides on top
of Semantic Scholar; the renderer uses them verbatim. Stub entries (no
arxiv / no doi) become local-only references with no fetch step.

Cite key convention: `lastname_year_firstword` (lowercase, ASCII, stop-words
dropped). `md_to_bibtex.py` propose-mode and sci-brain's `append_bibtex.py`
both follow this rule.

### 3. Derive the per-method manifest

```sh
MANIFEST="/tmp/manifest-$METHOD.json"
python3 "$HELPERS/bibtex_to_manifest.py" "$BIB" --method "$METHOD" > "$MANIFEST"
```

The output is the legacy JSON manifest that `fetch_metadata.py` and
`render.py` already consume — derived, not committed. Re-run after every
bib edit.

### 4. Fetch metadata and PDFs

```sh
python3 "$HELPERS/fetch_metadata.py" \
  --kb "$KB" \
  --manifest "$MANIFEST" \
  --download-arxiv-pdfs
```

The helper writes to `$KB/.raw/`. For DOI references, it tries Semantic Scholar
metadata and uses an arXiv preprint when one is available.

### 5. Render markdown

Rendering uses `pymupdf4llm` when installed, then falls back to `markitdown` or
`pdftotext`. If `pymupdf4llm` is missing, full text can still render but figures
may be absent.

| Use case | Command |
|---|---|
| Standard render (manifest) | `python3 "$HELPERS/render.py" --kb "$KB" --manifest "$MANIFEST"` |
| Single PDF in hand | `python3 "$HELPERS/render.py" --pdf sources/paper.pdf --out sources/paper.md` |
| Long book/lecture notes | add `--text-only` |

### 6. Regenerate the method index

```sh
python3 "$HELPERS/index.py" \
  --kb "$KB" \
  --title "$METHOD methodology references" \
  --source-note "Methodology references for the quantum many-body physics harness. Raw PDFs and extracted figures are local-only and gitignored."
```

Keep the title/source-note stable for repeat runs in the same method folder.

### 7. Verify

```sh
git check-ignore "$KB/.raw/" "$KB/.figures/" || true
test -f "$KB/INDEX.md"
find "$KB" -maxdepth 1 -name '*.md' -print
```

<checklist name="verify-render">
- `.raw/` and `.figures/` are gitignored (verify with `git check-ignore`)
- `INDEX.md` exists at the method root
- Each manifest entry has a corresponding `.md` file at the method root
- Each entry's `INDEX.md` row marks `full_text: yes / no / stub` correctly
- The new entry appears in `ref.bib` with a `keywords =` field
</checklist>

Report the rendered files, which entries have `full_text: yes`, and which are
metadata-only or stubs.

## Bootstrap: rebuilding `ref.bib` from rendered markdown

If `ref.bib` is missing or drifts from the rendered `.md` corpus:

```sh
python3 "$HELPERS/md_to_bibtex.py"      # writes .knowledge/literature/ref.bib
```

The script walks `.knowledge/literature/<method>/*.md`, parses YAML
frontmatter, and emits one entry per unique canonical reference (merging
papers shared across methods into a single entry with multi-method
`keywords`). Re-running overwrites the file — review the diff before
committing.

## Notes

- DO NOT commit `.raw/` or `.figures/`.
- DO NOT hand-edit the derived per-method JSON manifest — change `ref.bib`.
- DO NOT put multiple methods in one folder; one method folder per methodology.
- For paywalled books, add a `@book` / `@misc` entry to `ref.bib` (no `eprint`,
  no `doi`) — the manifest derivation will route it as a stub.

#!/usr/bin/env python3
"""Render the .raw/ assets into .knowledge/ markdown.

Reads:
- .raw/{arxiv,doi}/<id>.json — Semantic Scholar metadata (from fetch_metadata.py)
- .raw/{arxiv,doi}/<id>.pdf — original PDFs (optional; rendered as full-text section)
- .raw/repos/<owner>-<repo>/ — shallow clones (rendered as README + ls-tree)
- .raw/web/<slug>.html or .raw/web/<slug>/ subdir — web page or local source dir
- A manifest JSON describing web entries, bib stubs, and any S2-metadata overrides

Manifest schema:
  {
    "arxiv": [{"id": "<id>", "title"?, "authors"?, "year"?, "venue"?, "note"?}, ...],
    "doi":   [...],                          # same shape
    "web":   {"<slug>": {"source_url": "...", "title": "...", "note": "..."}},
    "stub":  [{"slug": ..., "title": ..., "authors": ..., "note": ...}, ...]
  }

Every `arxiv` / `doi` entry is an object. `id` is the only required field.
Optional override fields: `title`, `authors`, `year`, `venue`, `volume`,
`pages`, `note`, plus a verbatim `citation` (full Citation line — bypasses
the merge below). All other overrides merge with S2: the override replaces
its specific token, but vol/pages still flow from the S2 journal block
unless overridden separately. `citation` is the only short-circuit.
For an arXiv preprint with no overrides, write `{"id": "<id>"}`.

Usage:
    render.py --kb /abs/path/.knowledge --manifest manifest.json
    render.py --pdf paper.pdf --out paper.md
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(s: str, max_len: int = 60) -> str:
    s = SLUG_NON_ALNUM.sub("-", s.lower()).strip("-")
    return s[:max_len].rstrip("-")


def yaml_escape(s: str) -> str:
    s = (s or "").replace('"', '\\"').replace("\n", " ").strip()
    return f'"{s}"'


def render_frontmatter(meta: dict) -> str:
    lines = ["---"]
    for k in ("source", "type", "canonical_id", "title", "authors",
              "year", "venue", "arxiv_id", "doi"):
        v = meta.get(k)
        if v not in (None, ""):
            lines.append(f"{k}: {yaml_escape(str(v))}")
    if meta.get("full_text"):
        lines.append(f"full_text: {meta['full_text']}")
    if meta.get("note"):
        lines.append(f"note: {yaml_escape(meta['note'])}")
    lines.append("---")
    return "\n".join(lines)


def authors_str(s2: dict) -> str:
    return ", ".join(a.get("name", "?") for a in (s2.get("authors") or []))


def citation_line(s2: dict, ov: dict) -> str:
    """Merge granular overrides with S2 journal block.

    `ov["citation"]` (verbatim full line) wins outright; otherwise venue /
    volume / pages / year are taken from overrides if present, falling back
    to S2's journal block. A venue override no longer truncates the line —
    it just substitutes the venue token; vol/pages still flow from S2.
    """
    if ov.get("citation"):
        return ov["citation"]
    j = s2.get("journal") or {}
    venue = ov.get("venue") or s2.get("venue") or j.get("name") or "preprint"
    parts = [venue]
    volume = ov.get("volume") or j.get("volume")
    if volume:
        parts.append(f"vol. {volume}")
    pages = ov.get("pages") or j.get("pages")
    if pages:
        parts.append(f"pp. {pages}")
    parts.append(str(ov.get("year") or s2.get("year", "?")))
    return ", ".join(parts)


def extract_pdf_text(
    pdf: Path,
    kb: Path | None = None,
    fig_subdir: str | None = None,
    text_only: bool = False,
) -> str:
    """Render a PDF to markdown.

    Priority: pymupdf4llm (preserves images) → markitdown → pdftotext -layout.
    pymupdf4llm produces markdown with image references; images are written to
    ``kb/.figures/<fig_subdir>/`` and links in the returned markdown are relative
    to ``kb/`` (so they resolve from the rendered ``kb/<slug>.md``).
    """
    text = ""
    tmp_md = Path("/tmp") / (pdf.stem + ".md")
    tmp_txt = Path("/tmp") / (pdf.stem + ".txt")

    if text_only:
        try:
            r = subprocess.run(["pdftotext", "-layout", str(pdf), str(tmp_txt)],
                               capture_output=True, text=True, timeout=300)
            if r.returncode == 0 and tmp_txt.exists():
                text = tmp_txt.read_text(errors="replace")
        except Exception as e:
            print(f"  pdftotext {pdf.name}: {e}", file=sys.stderr)

    if not text and kb is not None and fig_subdir:
        try:
            import pymupdf4llm  # type: ignore
            fig_abs = kb / ".figures" / fig_subdir
            fig_abs.mkdir(parents=True, exist_ok=True)
            rel_path = f".figures/{fig_subdir}"
            old_cwd = os.getcwd()
            try:
                os.chdir(kb)
                md = pymupdf4llm.to_markdown(
                    str(pdf),
                    write_images=True,
                    image_path=rel_path,
                    image_format="png",
                )
            finally:
                os.chdir(old_cwd)
            if md and len(md.strip()) > 100:
                # A PDF with a broken ToUnicode CMap yields lone surrogates here,
                # which are not encodable as UTF-8. Every other extractor below
                # reads through `errors="replace"`; this one returns a str, so
                # normalize it the same way.
                text = md.encode("utf-8", "replace").decode("utf-8")
        except ImportError:
            print("  pymupdf4llm not installed; falling back to markitdown/pdftotext", file=sys.stderr)
        except Exception as e:
            print(f"  pymupdf4llm {pdf.name}: {e}", file=sys.stderr)

    if not text:
        try:
            r = subprocess.run(["markitdown", str(pdf), "-o", str(tmp_md)],
                               capture_output=True, text=True, timeout=300)
            if r.returncode == 0 and tmp_md.exists() and tmp_md.stat().st_size > 100:
                text = tmp_md.read_text(errors="replace")
        except Exception as e:
            print(f"  markitdown {pdf.name}: {e}", file=sys.stderr)
    if not text:
        try:
            r = subprocess.run(["pdftotext", "-layout", str(pdf), str(tmp_txt)],
                               capture_output=True, text=True, timeout=120)
            if r.returncode == 0 and tmp_txt.exists():
                text = tmp_txt.read_text(errors="replace")
        except Exception:
            pass
    for p in (tmp_md, tmp_txt):
        try:
            p.unlink()
        except FileNotFoundError:
            pass
    return text.strip()


def render_pdf_file(pdf: Path, out: Path, text_only: bool = False) -> None:
    pdf = pdf.resolve()
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    text = extract_pdf_text(pdf, kb=out.parent, fig_subdir=out.stem, text_only=text_only)
    if not text:
        raise SystemExit(f"no text extracted from {pdf}")
    out.write_text(text.rstrip() + "\n")


def render_arxiv(kb: Path, raw: Path, manifest: dict | None = None, text_only: bool = False) -> int:
    overrides = {e["id"]: {k: v for k, v in e.items() if k != "id"} for e in (manifest or {}).get("arxiv", [])}
    n = 0
    arx_dir = raw / "arxiv"
    if not arx_dir.exists():
        return 0
    for json_path in sorted(arx_dir.glob("*.json")):
        safe_id = json_path.stem
        s2 = json.loads(json_path.read_text())
        ext = s2.get("externalIds") or {}
        arxiv_id = s2.get("_harness_arxiv_id") or ext.get("ArXiv") or safe_id
        ov = overrides.get(arxiv_id, {})
        title = ov.get("title") or s2.get("title", "(untitled)")
        slug = f"{safe_id}_{slugify(title)}"
        meta = {
            "source": f"https://arxiv.org/abs/{arxiv_id}",
            "type": "arxiv",
            "canonical_id": arxiv_id,
            "title": title,
            "authors": ov.get("authors") or authors_str(s2),
            "year": ov.get("year") or s2.get("year"),
            "venue": ov.get("venue") or s2.get("venue") or (s2.get("journal") or {}).get("name"),
            "arxiv_id": arxiv_id,
            "doi": ext.get("DOI"),
            "note": ov.get("note"),
        }
        body = [render_frontmatter(meta), "", f"# {title}", "",
                f"**Authors:** {meta['authors']}", "",
                f"**Citation:** {citation_line(s2, ov)}", "",
                f"**arXiv:** [{arxiv_id}](https://arxiv.org/abs/{arxiv_id})"]
        if meta.get("doi"):
            body += ["", f"**DOI:** [{meta['doi']}](https://doi.org/{meta['doi']})"]
        body += ["", "## Abstract", "", s2.get("abstract") or "_(abstract unavailable)_"]
        pdf = arx_dir / f"{safe_id}.pdf"
        full = extract_pdf_text(
            pdf, kb=kb, fig_subdir=f"arxiv__{safe_id}", text_only=text_only
        ) if pdf.exists() else ""
        if full:
            meta["full_text"] = "yes"
            body[0] = render_frontmatter(meta)
            body += ["", "## Full Text", "", full]
        else:
            meta["full_text"] = "no"
            body[0] = render_frontmatter(meta)
        (kb / f"{slug}.md").write_text("\n".join(body) + "\n")
        n += 1
    return n


def render_doi(kb: Path, raw: Path, manifest: dict | None = None, text_only: bool = False) -> int:
    overrides = {e["id"]: {k: v for k, v in e.items() if k != "id"} for e in (manifest or {}).get("doi", [])}
    n = 0
    doi_dir = raw / "doi"
    if not doi_dir.exists():
        return 0
    for json_path in sorted(doi_dir.glob("*.json")):
        safe = json_path.stem
        s2 = json.loads(json_path.read_text())
        doi_canon = (s2.get("externalIds") or {}).get("DOI") or safe.replace("-", "/", 1)
        ov = overrides.get(doi_canon, {})
        title = ov.get("title") or s2.get("title", "(untitled)")
        slug = slugify(safe)
        ext = s2.get("externalIds") or {}
        meta = {
            "source": f"https://doi.org/{doi_canon}",
            "type": "doi",
            "canonical_id": doi_canon,
            "title": title,
            "authors": ov.get("authors") or authors_str(s2),
            "year": ov.get("year") or s2.get("year"),
            "venue": ov.get("venue") or s2.get("venue") or (s2.get("journal") or {}).get("name"),
            "doi": doi_canon,
            "arxiv_id": ext.get("ArXiv"),
            "note": ov.get("note"),
        }
        body = [render_frontmatter(meta), "", f"# {title}", "",
                f"**Authors:** {meta['authors']}", "",
                f"**Citation:** {citation_line(s2, ov)}", "",
                f"**DOI:** [{doi_canon}](https://doi.org/{doi_canon})"]
        if meta.get("arxiv_id"):
            body += ["", f"**arXiv preprint:** [{meta['arxiv_id']}](https://arxiv.org/abs/{meta['arxiv_id']})"]
        body += ["", "## Abstract", "", s2.get("abstract") or "_(abstract unavailable)_"]
        pdf = doi_dir / f"{safe}.pdf"
        full = extract_pdf_text(
            pdf, kb=kb, fig_subdir=f"doi__{safe}", text_only=text_only
        ) if pdf.exists() else ""
        if full:
            meta["full_text"] = "yes"
            body[0] = render_frontmatter(meta)
            body += ["", "## Full Text", "", full]
        else:
            meta["full_text"] = "no"
            body[0] = render_frontmatter(meta)
            body += ["", "_Full text not retrieved — abstract-only entry._"]
        (kb / f"{slug}.md").write_text("\n".join(body) + "\n")
        n += 1
    return n


def render_github(kb: Path, raw: Path) -> int:
    n = 0
    repos_dir = raw / "repos"
    if not repos_dir.exists():
        return 0
    for repo_dir in sorted(repos_dir.iterdir()):
        if not repo_dir.is_dir():
            continue
        owner, _, repo = repo_dir.name.partition("-")
        if not repo:
            continue
        canonical = f"{owner}/{repo}"
        meta = {
            "source": f"https://github.com/{canonical}",
            "type": "github",
            "canonical_id": canonical,
            "title": canonical,
        }
        body = [render_frontmatter(meta), "", f"# {canonical}", "",
                f"**Source:** https://github.com/{canonical}"]
        for cand in ("README.md", "Readme.md", "readme.md", "README.rst"):
            p = repo_dir / cand
            if p.exists():
                content = p.read_text(errors="replace")
                if p.suffix.lower() == ".rst":
                    try:
                        r = subprocess.run(["pandoc", "-f", "rst", "-t", "gfm"],
                                           input=content, capture_output=True, text=True, timeout=60)
                        if r.returncode == 0:
                            content = r.stdout
                    except Exception:
                        pass
                body += ["", "## README", "", content.strip()]
                break
        try:
            r = subprocess.run(["git", "-C", str(repo_dir), "ls-tree", "-r", "--name-only", "HEAD"],
                               capture_output=True, text=True, timeout=30)
            tree = r.stdout.splitlines()[:200]
        except Exception:
            tree = []
        if tree:
            body += ["", "## File tree (top 200)", "", "```"]
            body += tree
            body.append("```")
        (kb / f"{repo_dir.name}.md").write_text("\n".join(body) + "\n")
        n += 1
    return n


def render_web(kb: Path, raw: Path, manifest: dict) -> int:
    n = 0
    web_dir = raw / "web"
    cite_idx = manifest.get("web", {})
    if not web_dir.exists():
        return 0
    for slug, info in cite_idx.items():
        meta = {
            "source": info.get("source_url", ""),
            "type": "web",
            "canonical_id": slug,
            "title": info.get("title", slug),
            "year": info.get("year"),
            "note": info.get("note"),
        }
        body = [render_frontmatter(meta), "", f"# {meta['title']}", "",
                f"**Source:** {meta['source']}"]
        html = web_dir / f"{slug}.html"
        local_dir = web_dir / slug
        if html.exists():
            try:
                r = subprocess.run(["pandoc", "-f", "html", "-t", "gfm", str(html)],
                                   capture_output=True, text=True, timeout=60)
                content = r.stdout if r.returncode == 0 else html.read_text(errors="replace")
            except Exception:
                content = html.read_text(errors="replace")
            body += ["", "## Body", "", content.strip()]
        elif local_dir.is_dir():
            for f in sorted(local_dir.iterdir()):
                if f.suffix.lower() in (".tex", ".bib", ".md", ".txt"):
                    body += ["", f"## {f.name}", "", f"```{f.suffix.lstrip('.')}",
                             f.read_text(errors="replace").strip(), "```"]
        (kb / f"{slug}.md").write_text("\n".join(body) + "\n")
        n += 1
    return n


def render_stubs(kb: Path, manifest: dict) -> int:
    n = 0
    for st in manifest.get("stub", []):
        slug = st["slug"]
        meta = {
            "source": "(none — bib stub)",
            "type": "stub",
            "canonical_id": slug,
            "title": st["title"],
            "authors": st.get("authors", "unknown"),
            "year": st.get("year"),
            "note": st.get("note"),
        }
        body = [render_frontmatter(meta), "", f"# {st['title']}", "",
                f"**Authors:** {meta['authors']}"]
        if meta.get("note"):
            body += ["", f"**Note:** {meta['note']}"]
        (kb / f"{slug}.md").write_text("\n".join(body) + "\n")
        n += 1
    return n


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kb", type=Path)
    p.add_argument("--manifest", type=Path, default=None,
                   help="Optional JSON manifest: web entries, bib stubs, plus per-entry S2 overrides for arxiv/doi")
    p.add_argument("--pdf", type=Path,
                   help="Render one PDF into a Markdown file using the same extraction stack")
    p.add_argument("--out", type=Path,
                   help="Output Markdown path for --pdf mode")
    p.add_argument("--text-only", action="store_true",
                   help="Prefer pdftotext and skip image extraction/OCR for faster searchable full text")
    args = p.parse_args()
    if args.pdf or args.out:
        if not args.pdf or not args.out:
            p.error("--pdf and --out must be supplied together")
        render_pdf_file(args.pdf, args.out, text_only=args.text_only)
        print(f"pdf: {args.out}")
        return 0
    if not args.kb:
        p.error("--kb is required unless --pdf/--out are supplied")
    kb = args.kb.resolve()
    manifest = args.manifest.resolve() if args.manifest else None
    raw = kb / ".raw"
    m = json.loads(manifest.read_text()) if manifest else {}
    print(f"arxiv:  {render_arxiv(kb, raw, manifest=m, text_only=args.text_only)}")
    print(f"doi:    {render_doi(kb, raw, manifest=m, text_only=args.text_only)}")
    print(f"github: {render_github(kb, raw)}")
    print(f"web:    {render_web(kb, raw, m)}")
    print(f"stub:   {render_stubs(kb, m)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

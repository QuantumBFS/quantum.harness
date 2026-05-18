#!/usr/bin/env python3
"""Render a /report HTML from a reproduction run.

Usage:
  render.py <run-dir>

Reads:
  <run-dir>/protocol.toml                (required)
  <run-dir>/run-report.md                (optional in dogfood; required for production)
  <run-dir>/cells/<id>/manifest.json     (optional; surfaced in cell drawer)
  <run-dir>/verify/verify_*.md           (optional; backs chip statuses)
  <run-dir>/figs/<id>.{png,json}         (required per [[figures]])
  <run-dir>/editorial.json               (optional; mechanical fallbacks otherwise)
  <run-dir>/progress/state.toml          (optional; flow state for provenance footer)

Writes:
  <run-dir>/report_<run-id>_<YYYY-MM-DD>.html
  <run-dir>/report_latest.html           (symlink, or copy on Windows)

Stdlib only (tomllib, json, base64, datetime, html, re, sys, argparse, pathlib).
"""
import argparse
import base64
import datetime
import html
import json
import re
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "report.html.tmpl"
COLORS = ["#b39c80", "#a87a55", "#c96442", "#7a2a1a"]
SOFT_CAP_BYTES = 1_000_000  # 1MB
HARD_CAP_BYTES = 5_000_000  # 5MB


def load_toml(p: Path) -> dict:
    with open(p, "rb") as f:
        return tomllib.load(f)


def b64_png(p: Path) -> str:
    raw = p.read_bytes()
    if len(raw) > 500_000:
        print(f"[warn] paper PNG {p.name} is {len(raw):,} bytes (> 500KB cap)", file=sys.stderr)
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def resolve(path_str: str, run_dir: Path) -> Path:
    p = Path(path_str)
    if p.is_absolute():
        return p
    candidate = REPO_ROOT / p
    if candidate.exists():
        return candidate
    return run_dir / p


def load_editorial(run_dir: Path) -> dict:
    p = run_dir / "editorial.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"headline": None, "claims": [], "deviations": [], "figures": [], "glossary": [], "gaps": []}


def load_overrides(run_dir: Path) -> list[dict]:
    """Read user-confirmed check bypasses from flow's append-only event log.

    Each override is { check, gate, reason, actor, at }. Reports surface ⊘
    chips and a banner when this list is non-empty. Clean runs return [].
    """
    events = run_dir / "progress" / "events.jsonl"
    if not events.exists():
        return []
    out: list[dict] = []
    for line in events.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("event") == "override_recorded":
            out.append({
                "check": e.get("check", ""),
                "gate": e.get("gate", ""),
                "reason": e.get("reason", ""),
                "actor": e.get("actor", ""),
                "at": e.get("at", ""),
            })
    return out


_GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ",
    "epsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ",
    "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ",
    "nu": "ν", "xi": "ξ", "pi": "π", "rho": "ρ",
    "sigma": "σ", "tau": "τ", "phi": "φ", "chi": "χ",
    "psi": "ψ", "omega": "ω",
    "Alpha": "Α", "Beta": "Β", "Gamma": "Γ", "Delta": "Δ",
    "Sigma": "Σ", "Lambda": "Λ", "Omega": "Ω", "Pi": "Π",
}


def _apply_text_markup(t: str) -> str:
    """Inline markup passes for plain text (no glossary tokens, no placeholders)."""
    t = re.sub(r"_\{([^}]+)\}", r"<sub>\1</sub>", t)
    t = re.sub(r"_([A-Za-z0-9])(?![A-Za-z0-9])", r"<sub>\1</sub>", t)
    t = re.sub(r"\^\{([^}]+)\}", r"<sup>\1</sup>", t)
    t = re.sub(r"\^([A-Za-z0-9])(?![A-Za-z0-9])", r"<sup>\1</sup>", t)
    for word, ch in _GREEK.items():
        t = re.sub(rf"\b{word}\b", ch, t)
    t = t.replace("&lt;=", "≤").replace("&gt;=", "≥")
    t = t.replace("!=", "≠").replace(" +/- ", " ± ").replace("+/-", "±")
    t = t.replace("\\approx", "≈").replace("~=", "≈")
    t = re.sub(r"\*([^*\s][^*\n]*?[^*\s]|[^*\s])\*", r"<em>\1</em>", t)
    return t


def render_inline_markup(text: str) -> str:
    """Escape HTML, then convert ASCII LaTeX-style markup to HTML/Unicode.

    Conversions:
      [[key|display]]  -> <span class="sym" data-term="key">{rendered display}</span>
      *italic*         -> <em>italic</em>
      _{XX}, _X        -> <sub>...</sub>
      ^{XX}, ^X        -> <sup>...</sup>
      Greek words      -> Unicode (alpha→α, chi→χ, ...)
      <=, >=, !=, +/-  -> ≤, ≥, ≠, ±
      \approx, ~=      -> ≈

    Glossary tokens are extracted to placeholders before any other pass so that
    the ASCII key is preserved (Greek expansion on a bare `alpha` would
    otherwise corrupt the data-term attribute via \b{word}\b).
    """
    if not text:
        return ""
    t = html.escape(text)
    placeholders: list[str] = []

    def _stash(m: re.Match) -> str:
        key = m.group(1)
        disp_rendered = _apply_text_markup(m.group(2))
        idx = len(placeholders)
        placeholders.append(
            f'<span class="sym" data-term="{html.escape(key)}">{disp_rendered}</span>'
        )
        return f"\x00GLOSS{idx}\x00"

    t = re.sub(r"\[\[([A-Za-z][A-Za-z0-9_]*)\|([^\]]+)\]\]", _stash, t)
    t = _apply_text_markup(t)
    for i, span in enumerate(placeholders):
        t = t.replace(f"\x00GLOSS{i}\x00", span)
    return t


def chip_for(status: str, label: str, popover: str) -> str:
    return (
        f'<span class="chip {html.escape(status)}" role="button" tabindex="0">'
        f'{render_inline_markup(label)}'
        f'<span class="chip-pop" role="tooltip">{render_inline_markup(popover)}</span>'
        f'</span>'
    )


def claim_status_from_verify(claim_id: str, run_dir: Path) -> str:
    """ok if claim id appears with ✓ nearby; warn if ✗ or ⚠; muted if no verify mentions it.

    Looks in both `<run>/verify/verify_*.md` (canonical layout) and `<run>/verify_*.md`
    (legacy/dogfood layout). The skill spec calls for the subdir; older runs may have
    them at the top level.
    """
    candidates = list((run_dir / "verify").glob("verify_*.md")) if (run_dir / "verify").exists() else []
    candidates += list(run_dir.glob("verify_*.md"))
    for v in candidates:
        text = v.read_text()
        if claim_id not in text:
            continue
        for line in text.splitlines():
            if claim_id in line:
                if "✗" in line or "✗" in text.split(claim_id)[-1][:200]:
                    return "warn"
                if "⚠" in line:
                    return "warn"
                if "✓" in line:
                    return "ok"
    return "muted"


def status_strip_html(protocol: dict, editorial: dict, run_dir: Path, overrides: list[dict]) -> str:
    """Build the status-strip chips from claims, checks, deviations, overrides, pending.

    Chip taxonomy (render order):
      1. claims     — one per [[claims]], status from verify report
      2. checks     — one per [[checks]] flagged for the strip
      3. deviations — one per [[deviations]], warn (⚠ via class)
      4. overrides  — one per recorded flow override, warn with ⊘ prefix
      5. pending    — one per [[pending]], muted
    """
    claims = protocol.get("claims", [])
    checks = protocol.get("checks", [])
    deviations = protocol.get("deviations", [])
    pending = protocol.get("pending", [])

    ed_claims = {c["id"]: c for c in editorial.get("claims") or []}
    ed_checks = {c["id"]: c for c in editorial.get("checks") or []}
    ed_devs = {d["id"]: d for d in editorial.get("deviations") or []}
    ed_pending = {p["id"]: p for p in editorial.get("pending") or []}

    chips: list[str] = []

    for c in claims[:3]:
        cid = c.get("id", "")
        status = claim_status_from_verify(cid, run_dir)
        ed = ed_claims.get(cid, {})
        label = ed.get("display_label") or cid.rsplit(".", 1)[-1] or cid
        popover = ed.get("popover") or c.get("statement", "")
        chips.append(chip_for(status, label, popover))

    for ch in checks:
        if not ch.get("audience"):
            continue
        chid = ch.get("id", "")
        status = claim_status_from_verify(chid, run_dir)
        ed = ed_checks.get(chid, {})
        label = ed.get("display_label") or chid.replace("_", " ")
        popover = ed.get("popover") or ch.get("statement") or f"{ch.get('kind', 'check')} ({chid})"
        chips.append(chip_for(status, label, popover))
        if len(chips) >= 5:
            break

    for d in deviations[:3]:
        did = d.get("id", "")
        ed = ed_devs.get(did, {})
        label = ed.get("display_label") or did
        popover = ed.get("popover") or d.get("statement", "")
        chips.append(chip_for("warn", label, popover))

    for o in overrides[:3]:
        label = f"⊘ {o['check']}"
        popover = f"{o['reason']} — bypassed by {o['actor']}"
        chips.append(chip_for("warn", label, popover))

    for p in pending[:2]:
        pid = p.get("id", "")
        ed = ed_pending.get(pid, {})
        label = ed.get("display_label") or pid.replace("pending.", "").replace("_", " ")
        popover = ed.get("popover") or p.get("statement", "")
        chips.append(chip_for("muted", label, popover))

    chips.append('<span class="chip spacer"></span>')
    chips.append('<span class="chip muted">click any data point for the cell manifest</span>')
    return "\n    ".join(chips)


def bypass_banner_html(overrides: list[dict]) -> str:
    """Banner below the chip strip when the run shipped with bypasses.

    Empty string on clean runs (zero overrides) — the visual delta drives the
    "is this a strict ship?" signal at a glance.
    """
    if not overrides:
        return ""
    items = []
    for o in overrides:
        items.append(
            f'<li><code>{html.escape(o["check"])}</code> — '
            f'{render_inline_markup(o["reason"])} '
            f'<span class="bypass-meta">(by {html.escape(o["actor"])})</span></li>'
        )
    return (
        '<aside class="bypass-banner">\n'
        f'  <span class="bypass-icon">⊘</span>\n'
        f'  <div class="bypass-text">\n'
        f'    <strong>This run shipped with {len(overrides)} bypassed check'
        f'{"s" if len(overrides) != 1 else ""}.</strong>\n'
        f'    <ul class="bypass-list">{"".join(items)}</ul>\n'
        '  </div>\n'
        '</aside>'
    )


def source_pill_label(s: dict, paper_id: str) -> str:
    """Best human label for a source pill.

    Primary sources collapse to the paper id (already shown as a separate pill);
    the caller dedups against `paper_id`. Non-primary sources use their `id`.
    """
    if s.get("authority") == "primary":
        return paper_id or s.get("id") or ""
    return s.get("id") or s.get("path") or ""


def contract_html(protocol: dict) -> str:
    artifact = protocol.get("artifact", {})
    sources = protocol.get("sources", [])
    claims = protocol.get("claims", [])
    deviations = protocol.get("deviations", [])
    budgets = protocol.get("budgets", {})
    paper_id = artifact.get("paper", "")

    parts: list[str] = []
    parts.append('<div class="k">Source</div><div class="v">')
    # Primary first; emit paper_id as a separate pill alongside the venue
    primaries = [s for s in sources if s.get("authority") == "primary"]
    if primaries and paper_id:
        parts.append(f'<span class="pill">{html.escape(paper_id)}</span>')
    for s in sources:
        label = source_pill_label(s, paper_id)
        if not label or label == paper_id:
            continue
        parts.append(f'<span class="pill">{html.escape(label)}</span>')
    parts.append("</div>")

    parts.append(f'<div class="k">Scope</div><div class="v">{render_inline_markup(artifact.get("description", ""))}</div>')

    parts.append('<div class="k">Claims</div><div class="v">')
    for c in claims:
        parts.append(
            f'<div class="claim-line-c"><span class="id">{html.escape(c.get("id", ""))}</span>'
            f'<span class="stmt">{render_inline_markup(c.get("statement", ""))}</span></div>'
        )
    parts.append("</div>")

    parts.append('<div class="k">Deviations</div><div class="v">')
    for d in deviations:
        parts.append(
            f'<div class="claim-line-c"><span class="id">{html.escape(d.get("id", ""))}</span>'
            f'<span class="stmt">{render_inline_markup(d.get("statement", ""))}</span></div>'
        )
    parts.append("</div>")

    parts.append('<div class="k">Budget</div><div class="v">')
    for k in ("wall_clock", "compute"):
        v = budgets.get(k)
        if v:
            parts.append(f'<span class="pill">{render_inline_markup(str(v))}</span>')
    parts.append("</div>")
    return "".join(parts)


def discrepancy_html(deviations: list[dict], editorial: dict) -> str:
    ed_devs = {d["id"]: d for d in editorial.get("deviations") or []}
    paragraphs: list[str] = []
    for d in deviations:
        ed = ed_devs.get(d.get("id", ""), {})
        paragraph = ed.get("discrepancy_paragraph") or d.get("statement", "")
        paragraphs.append(f"<p>{render_inline_markup(paragraph)}</p>")
    if not paragraphs:
        paragraphs.append("<p>No deviations declared.</p>")
    return "\n    ".join(paragraphs)


def provenance_html(run_id: str, protocol: dict, flow_state: dict | None, n_cells: int, total_wall_h: float, today: str) -> str:
    artifact = protocol.get("artifact", {})
    cluster = ""
    finished = ""
    if flow_state:
        cluster = flow_state.get("cluster") or flow_state.get("default_executor", "")
        finished = flow_state.get("finished_at") or flow_state.get("last_event", "")

    return (
        f'<div><div class="label">Run</div>'
        f'<p class="prov-line"><code class="prov-code">results/{html.escape(run_id)}/</code>'
        f'<br>{n_cells} cells · {total_wall_h:.1f} wall-hours</p></div>'
        f'<div><div class="label">Cluster</div>'
        f'<p class="prov-line">{html.escape(str(cluster) or "—")}<br>{html.escape(str(finished))}</p></div>'
        f'<div><div class="label">Source</div>'
        f'<p class="prov-line"><code class="prov-code">{html.escape(artifact.get("paper", ""))}</code>'
        f'<br>{render_inline_markup(artifact.get("description", "")[:80])}</p></div>'
        f'<div><div class="label">Harness</div>'
        f'<p class="prov-line">Report ID: <code class="prov-code">{html.escape(run_id)}</code> @ {today}'
        f'<br>Rendered by <code class="prov-code">/report</code></p></div>'
    )


_VERDICT_ICONS = {"match": "✓", "partial": "◐", "fail": "✗", "unknown": "?"}
_VERDICT_LABELS = {
    "match": "Pass",
    "partial": "Partial",
    "fail": "Fail",
    "unknown": "Pending",
}


def build_verdict_html(editorial: dict, protocol: dict) -> str:
    """Compose the verdict band HTML.

    Editorial supplies (status, label, detail). Mechanical fallback infers
    status from the protocol shape: deviations present → partial; otherwise
    unknown (we never claim a green verdict mechanically).
    """
    v = editorial.get("verdict") or {}
    status = v.get("status") or ("partial" if protocol.get("deviations") else "unknown")
    if status not in _VERDICT_ICONS:
        status = "unknown"
    label = v.get("label") or _VERDICT_LABELS[status]

    detail = v.get("detail") or ""
    if not detail:
        # Mechanical fallback detail: list deviation labels if any.
        ed_devs = {d["id"]: d for d in editorial.get("deviations") or []}
        names = [
            ed_devs.get(d.get("id", ""), {}).get("display_label") or d.get("id", "")
            for d in protocol.get("deviations", [])
        ]
        if names:
            detail = f"Declared deviations: {', '.join(names)}."
        else:
            detail = "Run editorial.json's `verdict` field is unset; see discrepancy and chips below."

    detail_html = render_inline_markup(detail)
    return (
        f'<div class="verdict verdict-{status}">'
        f'<span class="verdict-icon">{_VERDICT_ICONS[status]}</span>'
        f'<div class="verdict-text">'
        f'<span class="verdict-label">{html.escape(label)}</span>'
        f'<span class="verdict-detail">{detail_html}</span> '
        f'<a href="#discrepancy-panel">see discrepancy &rarr;</a>'
        f'</div>'
        f'</div>'
    )


def figure_block_html(fig: dict, ed: dict, paper_id: str, run_id: str, run_dir: Path,
                      eyebrow: str | None = None) -> str:
    """Compose the HTML for one figure's duo (paper PNG | interactive plot).

    `fig` is a [[figures]] entry from protocol.toml; `ed` is the matching
    editorial.figures[i] dict (or {}); `eyebrow` is an optional small label
    rendered above the duo (used for additional figures, e.g. "Figure 2 of 3").
    """
    label = fig["id"]
    fig_display = fig.get("display_id") or label

    paper_path = resolve(fig["paper_path"], run_dir)
    paper_data_url = b64_png(paper_path)

    paper_panel_title = fig.get("paper_attribution", "Paper")
    ours_panel_title = ed.get("caption_ours") or f"Reproduction · {run_id} / {label}"
    paper_caption = ed.get("caption_paper") or ""
    paper_context = ed.get("paper_context") or ""
    paper_alt = ed.get("caption_paper") or fig.get("paper_attribution") or f"Paper figure {label}"
    paper_source = f"{paper_id} · {fig_display}" if paper_id else fig_display
    # Keep ours source short — full run_id is already in the topbar, no need to
    # repeat it in the panel header where it just truncates.
    ours_source = f"figs/{label}.json"

    eye = f'<div class="fig-eyebrow">{html.escape(eyebrow)}</div>' if eyebrow else ""

    return (
        f'<div class="fig-block" data-fig="{html.escape(label)}">\n'
        + eye + '\n'
        + '<div class="duo">\n'
        + '  <div class="panel-card">\n'
        + '    <div class="panel-head">\n'
        + '      <span class="label ref">Reference · the paper</span>\n'
        + f'      <span class="source">{html.escape(paper_source)}</span>\n'
        + '    </div>\n'
        + f'    <h2 class="panel-title">{render_inline_markup(paper_panel_title)}</h2>\n'
        + '    <div class="paper-img-wrap">\n'
        + f'      <img src="{paper_data_url}" alt="{html.escape(paper_alt)}" />\n'
        + '    </div>\n'
        + f'    <div class="paper-cap">{render_inline_markup(paper_caption)}</div>\n'
        + (f'    <div class="paper-context"><span class="paper-context-label">From the paper</span> {render_inline_markup(paper_context)}</div>\n' if paper_context else '')
        + '  </div>\n'
        + '  <div class="panel-card">\n'
        + '    <div class="panel-head">\n'
        + '      <span class="label">Reproduction · this run</span>\n'
        + f'      <span class="source">{html.escape(ours_source)}</span>\n'
        + '    </div>\n'
        + f'    <h2 class="panel-title">{render_inline_markup(ours_panel_title)}</h2>\n'
        + '    <div class="ours-controls">\n'
        + f'      <button class="toggle" id="toggle-window-{html.escape(label)}" style="display:none">\n'
        + '        <span class="swatch"></span> Match paper y-window\n'
        + '      </button>\n'
        + '    </div>\n'
        + '    <div class="plot-area">\n'
        + f'      <svg class="plot" id="plot-{html.escape(label)}" viewBox="0 0 600 360" preserveAspectRatio="xMidYMid meet"></svg>\n'
        + f'      <div class="callout" id="callout-{html.escape(label)}"></div>\n'
        + '    </div>\n'
        + f'    <div class="legend-row" id="legend-{html.escape(label)}"></div>\n'
        + '  </div>\n'
        + '</div>\n'
        + '</div>'
    )


def count_cells_and_wall(run_dir: Path) -> tuple[int, float]:
    cells_dir = run_dir / "cells"
    if not cells_dir.exists():
        return 0, 0.0
    n = 0
    total = 0.0
    for m in list(cells_dir.glob("**/manifest.json")) + list(cells_dir.glob("manifest_*.json")):
        try:
            d = json.loads(m.read_text())
        except json.JSONDecodeError:
            continue
        n += 1
        total += float(d.get("wall_seconds", 0))
    return n, total / 3600.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a /report HTML for a reproduction run")
    parser.add_argument("run_dir", help="Path to the reproduction run directory")
    args = parser.parse_args()
    run_dir = Path(args.run_dir).resolve()
    if not run_dir.is_dir():
        print(f"error: run-dir does not exist: {run_dir}", file=sys.stderr)
        return 1

    protocol = load_toml(run_dir / "protocol.toml")
    editorial = load_editorial(run_dir)
    overrides = load_overrides(run_dir)
    artifact = protocol.get("artifact", {})

    figures = protocol.get("figures", [])
    if not figures:
        print("error: protocol.toml has no [[figures]] entries", file=sys.stderr)
        return 1
    featured_id = protocol.get("featured_figure") or figures[0]["id"]
    # Reorder: featured first, then the rest in protocol order.
    figures_ordered = (
        [next((f for f in figures if f["id"] == featured_id), figures[0])]
        + [f for f in figures if f["id"] != featured_id]
    )

    ed_figs = {f["label"]: f for f in editorial.get("figures") or []}

    # Editorial fields with mechanical fallbacks (report-level, not per-figure)
    headline_text = (editorial.get("headline") or {}).get("text") or (
        protocol.get("claims", [{}])[0].get("statement", "")
    )
    headline_html = render_inline_markup(headline_text)
    discrepancy_headline = (
        editorial.get("discrepancy_headline")
        or ("Differences from the paper" if protocol.get("deviations") else "No declared deviations.")
    )

    run_id = artifact.get("run_id") or run_dir.name
    paper_id = artifact.get("paper", "")
    source_url = artifact.get("url", "")

    authors = artifact.get("authors", "")
    paper_title = artifact.get("title", "")
    venue = artifact.get("venue", "")
    sources = protocol.get("sources", [])
    if not (authors or venue) and sources:
        note = sources[0].get("note", "")
        if "." in note:
            authors_part, _, rest = note.partition(".")
            if not authors:
                authors = authors_part.strip()
            if not venue:
                venue = rest.strip().rstrip(".").strip()

    parts = []
    if authors:
        parts.append(f"<b>{html.escape(authors)}</b>")
    if paper_title:
        parts.append(f"<em>{html.escape(paper_title)}</em>")
    topbar_byline = " &mdash; ".join(parts)
    link_html = (
        f'<a href="{html.escape(source_url)}">{html.escape(source_url)}</a>'
        if source_url else ""
    )
    topbar_paper_html = (
        f'<span class="id">{html.escape(paper_id)}</span>'
        + (topbar_byline + " " if topbar_byline else "")
        + (html.escape(venue) + " &middot; " if venue and link_html else "")
        + link_html
    )

    # Glossary JSON (key matches the data-term attribute on each .sym span;
    # editorial entries supply `key` explicitly, else fall back to the symbol).
    gloss_dict: dict[str, dict] = {}
    for g in editorial.get("glossary") or []:
        key = g.get("key")
        if not key:
            sym = g.get("symbol", "")
            m = re.match(r"[a-zA-Z_]+", sym)
            key = (m.group(0).lower() if m else "term")
        gloss_dict[key] = {
            "name": g.get("name", ""),
            "body": g.get("body", ""),
            "formula": g.get("formula", ""),
        }

    # Flow state (optional)
    flow_state = None
    flow_state_path = run_dir / "progress" / "state.toml"
    if flow_state_path.exists():
        try:
            flow_state = load_toml(flow_state_path)
        except Exception:
            flow_state = None

    n_cells, total_wall_h = count_cells_and_wall(run_dir)

    # Topbar meta line: drop bare separators when cluster missing.
    cluster_str = (flow_state or {}).get("cluster", "") if flow_state else ""
    today = datetime.date.today().isoformat()
    meta_bits = [b for b in (cluster_str, today) if b]
    run_meta = " · ".join(meta_bits)

    # Verdict band — the single visually-loud band carrying both the overall
    # outcome ("did it reproduce?") and the key deviation summary.
    # Source priority: editorial.verdict (sourced from verify reports by the
    # polish subagent) → mechanical fallback derived from protocol shape.
    verdict_html = build_verdict_html(editorial, protocol)

    # Expand multi-panel figures (axes = {main: {...}, inset: {...}}) into one
    # virtual figure per panel. Each virtual figure shares the parent's paper
    # image and editorial entry, but carries its own flat axes + filtered data.
    expanded: list[dict] = []
    for f in figures_ordered:
        data = None
        if f.get("data_path"):
            dp = resolve(f["data_path"], run_dir)
            if dp.exists():
                data = json.loads(dp.read_text())
            else:
                print(f"[warn] data_path for figure {f['id']} not found: {dp}", file=sys.stderr)
        axes = (data or {}).get("axes", {}) or {}
        items = (data or {}).get("data", []) or []
        is_multi = (
            isinstance(axes, dict)
            and len(axes) >= 2
            and all(isinstance(v, dict) and ("x" in v or "y" in v) for v in axes.values())
        )
        if not is_multi:
            expanded.append({"fig": f, "label": f["id"], "fig_js": data or {"label": f["id"], "axes": {}, "data": []}, "panel_name": None})
            continue
        # Stable panel order: main first if present, else axes insertion order.
        panel_names = (["main"] if "main" in axes else []) + [k for k in axes if k != "main"]
        for panel_name in panel_names:
            panel_axes = axes[panel_name]
            # Kind synonyms: "main" matches kind in {None, "curve", "main"}.
            if panel_name == "main":
                panel_data = [d for d in items if d.get("kind") in (None, "curve", "main")]
            else:
                panel_data = [d for d in items if d.get("kind") == panel_name]
            virtual_label = f["id"] if (panel_name == "main" and panel_names[0] == "main") else f"{f['id']}__{panel_name}"
            expanded.append({
                "fig": f,
                "label": virtual_label,
                "fig_js": {"label": virtual_label, "axes": panel_axes, "data": panel_data},
                "panel_name": panel_name,
            })

    figures_js = [e["fig_js"] for e in expanded]

    def _panel_block(entry: dict, eyebrow: str | None) -> str:
        proto = entry["fig"]
        # Build a synthetic figure dict carrying the virtual label so the svg
        # id, callout id, and figures-js lookup match.
        synth = dict(proto)
        synth["id"] = entry["label"]
        synth["display_id"] = entry["label"]
        ed_for_panel = dict(ed_figs.get(proto["id"], {}))
        if entry["panel_name"] and entry["panel_name"] != "main":
            # Inset panels fall back to mechanical captions sourced from the
            # parent's editorial. Drop the parent's captions so the renderer
            # uses panel-specific fallbacks rather than misattributing them.
            ed_for_panel["caption_paper"] = ed_for_panel.get(f"caption_paper_{entry['panel_name']}") or ""
            ed_for_panel["caption_ours"] = ed_for_panel.get(f"caption_ours_{entry['panel_name']}") or ""
            ed_for_panel["paper_context"] = ""
        return figure_block_html(
            synth, ed_for_panel, paper_id, run_id, run_dir, eyebrow=eyebrow,
        )

    featured_entry = expanded[0]
    extras_entries = expanded[1:]
    featured_html = _panel_block(featured_entry, eyebrow=None)
    if extras_entries:
        extra_blocks = []
        for i, e in enumerate(extras_entries, start=2):
            if e["panel_name"] and e["panel_name"] != "main":
                eyebrow = f"Inset · {e['panel_name']}"
            else:
                eyebrow = f"Figure {i} of {len(expanded)} · {e['label']}"
            extra_blocks.append(_panel_block(e, eyebrow=eyebrow))
        extra_section = (
            '<section class="extra-figs">\n' + "\n\n".join(extra_blocks) + '\n</section>'
        )
    else:
        extra_section = ""

    # Compose substitution map
    subs = {
        "__PAGE_TITLE__": html.escape(f"{paper_id} · {run_id} · /report"),
        "__TOPBAR_PAPER_HTML__": topbar_paper_html,
        "__RUN_SCOPE__": html.escape(artifact.get("scope", "")),
        "__RUN_META__": html.escape(run_meta),
        "__HEADLINE_HTML__": headline_html,
        "__RUN_TAG__": html.escape(f"{n_cells} cells · {total_wall_h:.1f} wall-h"),
        "__VERDICT_HTML__": verdict_html,
        "__FEATURED_FIG_HTML__": featured_html,
        "__EXTRA_FIGS_SECTION__": extra_section,
        "__STATUS_STRIP_HTML__": status_strip_html(protocol, editorial, run_dir, overrides),
        "__BYPASS_BANNER_HTML__": bypass_banner_html(overrides),
        "__CONTRACT_HTML__": contract_html(protocol),
        "__DISCREPANCY_HEADLINE__": render_inline_markup(discrepancy_headline),
        "__DISCREPANCY_HTML__": discrepancy_html(protocol.get("deviations", []), editorial),
        "__PROVENANCE_HTML__": provenance_html(run_id, protocol, flow_state, n_cells, total_wall_h, today),
        "__RUN_ID__": run_id,
        "__FIGURES_JSON__": json.dumps(figures_js, separators=(",", ":")),
        "__GLOSS_JSON__": json.dumps(gloss_dict, separators=(",", ":")),
        "__COLORS_JSON__": json.dumps(COLORS),
    }

    template = TEMPLATE_PATH.read_text()
    out_html = template
    for placeholder, value in subs.items():
        out_html = out_html.replace(placeholder, value)

    out_filename = f"report_{run_id}_{today}.html"
    out_path = run_dir / out_filename
    out_path.write_text(out_html)

    size = out_path.stat().st_size
    if size > HARD_CAP_BYTES:
        print(f"error: rendered HTML exceeds 5MB hard cap ({size:,} bytes)", file=sys.stderr)
        return 1
    if size > SOFT_CAP_BYTES:
        print(f"[warn] rendered HTML exceeds 1MB soft cap ({size:,} bytes)", file=sys.stderr)

    # Update report_latest symlink (or copy on Windows)
    latest = run_dir / "report_latest.html"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    try:
        latest.symlink_to(out_filename)
    except OSError:
        latest.write_text(out_html)

    print(f"wrote {out_path}")
    print(f"  size: {size:,} bytes")
    print(f"  symlink: {latest} → {out_filename}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

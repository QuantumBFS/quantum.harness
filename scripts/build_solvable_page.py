#!/usr/bin/env python3
"""Generate .github/template/solvable.html — the exactly-solvable-models catalog page.

Reads .knowledge/solvable/INDEX.md (the 63-model technique tables) and the
built cards' ORACLE.md files, and renders one self-contained dark HTML page:
a sticky filter bar (search + technique/tier/script chips) over seven
technique sections whose rows scan like a table and expand like cards.

Stdlib only. Output is byte-stable run-to-run (no timestamps; INDEX order
preserved; all curated text lives in literal dicts below).

Usage:  python3 scripts/build_solvable_page.py [--out PATH]
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INDEX_MD = REPO / ".knowledge" / "solvable" / "INDEX.md"
OUT_HTML = REPO / ".github" / "template" / "solvable.html"
BLOB = "https://github.com/QuantumBFS/quantum.harness/blob/main/.knowledge/solvable/"

# One crisp physics phrase per technique section (shown under each h2).
SUBTITLES = {
    "T1": "quadratic Hamiltonians — Jordan–Wigner, BdG, Bloch: one single-particle matrix yields the entire spectrum",
    "T2": "classical partition functions in 2D — Onsager transfer matrices, Kasteleyn Pfaffians, vertex weights",
    "T3": "interacting but integrable — Bethe rapidities and Yang–Baxter give exact energies, gaps, and thermodynamics",
    "T4": "every term commutes — stabilizer algebra and fusion categories fix the exact spectrum and topological degeneracy",
    "T5": "the ground state is exact even when the spectrum is not — valence bonds, dimer coverings, scar towers",
    "T6": "all-to-all couplings, single modes, random ensembles — mean field and large N become exact",
    "T7": "exact maps between models and exactly evolvable dynamics — Kramers–Wannier to dual-unitary circuits",
}

# 3–8-word summary-row hooks for the built (wave-1) cards, written from each
# card's scope/solvability content.
HOOKS = {
    "tfim-chain": "Jordan–Wigner free fermions; gap 2|J−h|",
    "xy-chain": "anisotropic Jordan–Wigner; XX to Ising line",
    "kitaev-chain": "p-wave BdG; unpaired Majorana edge modes",
    "long-range-kitaev": "power-law pairing; massive Dirac edge modes",
    "ssh-chain": "dimerized hopping; topological edge states",
    "kitaev-honeycomb": "Majorana Bloch bands; gapless spin liquid",
    "p-ip-superconductor": "chiral BdG; Chern number ±1 phases",
    "tight-binding-lattices": "Bloch bands: square, honeycomb, kagome, Lieb",
    "hofstadter-harper": "Harper equation; Hofstadter butterfly, Chern numbers",
    "haldane-chern": "Chern insulator without Landau levels",
    "anderson-1d": "transfer-matrix Lyapunov exponent; exact localization length",
    "harmonic-chain": "phonon normal modes, closed-form spectrum",
    "bogoliubov-bose-gas": "Bogoliubov quasiparticles; exact at weak coupling",
    "toric-code": "stabilizer counting; fourfold torus degeneracy",
    "quantum-double": "D(G) anyons from group representation theory",
    "string-net": "fusion categories; doubled topological phases",
    "color-code": "6.6.6 stabilizers; two toric-code copies",
    "x-cube": "fracton order; subextensive degeneracy 6L−3",
    "haah-code": "cubic code; number-theoretic ground-space rank",
    "cluster-spt": "cluster stabilizers; SPT with protected edge modes",
    "ising-2d-onsager": "transfer matrix; Onsager free energy, Kaufman finite-torus Z",
    "ising-triangular": "frustrated AFM; Wannier residual entropy",
    "dimer-kasteleyn": "Pfaffian dimer counting; exact tiling entropy",
    "six-vertex": "ice rule; Lieb Bethe-ansatz free energy",
    "eight-vertex": "Yang–Baxter elliptic solution; varying exponents",
    "hard-hexagons": "corner transfer matrix; Rogers–Ramanujan densities",
    "heisenberg-xxx": "coordinate Bethe ansatz; real roots, E/N = 1/4 − ln 2",
    "xxz-chain": "Bethe ansatz; Δ-tuned e0 integral/series, Néel gap",
    "xyz-chain": "Baxter eight-vertex; exact XXZ/XY limits, ED-extrapolated generic",
    "zamolodchikov-fateev-spin1": "integrable spin-1 (Takhtajan–Babujian β=−1); c=3/2, gapless",
    "haldane-shastry": "1/r² exchange; Gutzwiller-RVB GS, E0=−(π²/24)(N+5/N)",
    "inozemtsev-chain": "elliptic exchange; interpolates XXX ↔ Haldane–Shastry",
    "hubbard-1d-lieb-wu": "nested Bethe ansatz; Mott gap opens at any U>0",
    "susy-t-j": "J=2t su(2|1) supersymmetry; cross-sector supermultiplets",
    "lieb-liniger": "δ-Bose gas; Lieb equation e(γ), γ→∞ gives π²/3",
    "tonks-girardeau": "Bose–Fermi mapping; e=π²/3, g₂(0)=0",
    "yang-gaudin": "nested Bethe ansatz; balanced fermions, π²/12→π²/3",
    "calogero-sutherland": "1/sin² ring; closed-form spectrum, E0=(π/L)²λ²N(N²−1)/3",
    "chiral-potts": "superintegrable Z_N; Onsager algebra, genus>1 rapidity curve",
    "richardson-pairing": "reduced BCS; Richardson roots complexify at pairing collisions",
    "gaudin-central-spin": "rational Gaudin magnet; commuting charges, ED-exact GS",
    "kondo-bethe": "s–d Bethe ansatz; Wilson ratio R=2, ln 2→0",
    "anderson-impurity-bethe": "symmetric SIAM Bethe ansatz; ⟨n_d⟩=1, R_W=2",
}

TIER_TITLES = {
    "A": "Tier A — full solution: complete spectrum and/or all correlators",
    "B": "Tier B — integrable: Bethe ansatz / Yang–Baxter exact results",
    "C": "Tier C — exact ground state / exact eigenstates only",
    "D": "Tier D — exact in a limit",
}
FLAG_TITLES = {
    "S": "Script S — all card quantities computable via oracle.py",
    "P": "Script P — a subset is scriptable; the rest tabulated",
    "T": "Script T — tabulated literature values only",
}


# --------------------------------------------------------------------------
# parsers
# --------------------------------------------------------------------------

def parse_group_titles(text: str) -> dict:
    """Map technique code -> section title from the '## T<n> <title>' headings."""
    return {m.group(1): m.group(2).strip()
            for m in re.finditer(r"^## (T\d+)\s+(.+)$", text, re.M)}


def parse_index(text: str) -> list:
    """Parse INDEX.md technique tables into a flat, INDEX-ordered entry list.

    Each entry: slug, name, technique, technique_title, tier, flag, status, built.
    """
    titles = parse_group_titles(text)
    entries = []
    sections = re.split(r"^## ", text, flags=re.M)
    for sec in sections:
        head = re.match(r"(T\d+)\s+(.+)", sec)
        if not head:
            continue
        code = head.group(1)
        for row in re.finditer(
                r"^\|\s*`([^`]+)`\s*\|([^|\n]*)\|([^|\n]*)\|([^|\n]*)\|", sec, re.M):
            slug = row.group(1).strip()
            tier = row.group(2).strip()
            flag = row.group(3).strip()
            status_cell = row.group(4).strip()
            built = status_cell.startswith("✓")
            status = status_cell.lstrip("✓").strip()
            entries.append({
                "slug": slug,
                "name": slug,
                "technique": code,
                "technique_title": titles.get(code, ""),
                "tier": tier,
                "flag": flag,
                "status": status,
                "built": built,
            })
    return entries


def _strip_md(text: str) -> str:
    """Markdown → plain text: drop emphasis/code markers and link targets."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)   # [text](url) -> text
    text = text.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


def _section(text: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


def parse_card(text: str) -> dict:
    """Extract hamiltonian / solvability / benchmarks from an ORACLE.md card."""
    m = re.search(r"\$\$(.+?)\$\$", text, re.S)
    hamiltonian = m.group(1).strip() if m else ""

    solv_sec = _section(text, "Solvability statement")
    paragraphs = [p for p in re.split(r"\n\s*\n", solv_sec) if p.strip()]
    solvability = _strip_md(paragraphs[0]) if paragraphs else ""

    benchmarks = []
    bench_sec = _section(text, "Benchmarks")
    for line in bench_sec.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line)[1:-1]]
        if len(cells) < 4 or cells[0] in ("Quantity", "") or set(cells[0]) <= {"-", ":"}:
            continue
        benchmarks.append({
            "quantity": cells[0], "params": cells[1],
            "value": cells[2], "source": cells[3],
        })

    title = ""
    m = re.match(r"# (.+?)(?: — exact-solution oracle)?\s*$", text.splitlines()[0])
    if m:
        title = m.group(1).strip()

    return {"hamiltonian": hamiltonian, "solvability": solvability,
            "benchmarks": benchmarks, "title": title}


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _fmt_cite(key: str) -> str:
    """'@LiebSchultzMattis1961' -> 'Lieb–Schultz–Mattis 1961' (readable citekey)."""
    key = key.strip().lstrip("@")
    m = re.match(r"(.*?)(\d{4}[a-z]?)?$", key)
    name = re.sub(r"(?<=[a-z])(?=[A-Z])", "–", m.group(1))
    year = m.group(2)
    return f"{name} {year}" if year else name


def _cite_spans(escaped: str) -> str:
    """Replace [@Key] / [@Key1; @Key2] tokens with readable spans.

    The raw citekey token is kept as a title= attribute for provenance.
    """
    def repl(m):
        keys = [k for k in m.group(1).split(";") if k.strip()]
        pretty = ", ".join(_fmt_cite(k) for k in keys)
        return f'<span class="cite" title="{_esc(m.group(0))}">{_esc(pretty)}</span>'
    return re.sub(r"\[@([^\]]+)\]", repl, escaped)


def _md_cell(s: str) -> str:
    """Benchmark cell: escape, humanize [@citekeys], re-inject `code` as <code>."""
    s = s.replace("\\|", "|")
    out = _cite_spans(_esc(s))
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", out)


def _badges(e: dict) -> str:
    tier_title = " / ".join(TIER_TITLES.get(t, f"Tier {t}") for t in e["tier"].split("/"))
    flag_title = FLAG_TITLES.get(e["flag"], f"Script {e['flag']}")
    status_cls = "b-ok" if e["built"] else "b-dim"
    return (
        f'<span class="bset">'
        f'<span class="b" title="{_esc(tier_title)}">{_esc(e["tier"])}</span>'
        f'<span class="b" title="{_esc(flag_title)}">{_esc(e["flag"])}</span>'
        f'<span class="b {status_cls}">{_esc(e["status"])}</span>'
        f'</span>'
    )


def _data_attrs(e: dict) -> str:
    tiers = " ".join(t for t in e["tier"].split("/") if t and t != "—")
    return (f'data-name="{_esc(e["slug"])}" data-hook="{_esc(e.get("hook", ""))}"'
            f' data-tech="{e["technique"]}" data-techtitle="{_esc(e["technique_title"])}"'
            f' data-tier="{_esc(tiers)}" data-flag="{_esc(e["flag"])}"')


def _render_built(e: dict) -> str:
    card = e["card"]
    body = [f'<div class="math">$${_esc(card["hamiltonian"])}$$</div>']
    if card["solvability"]:
        body.append(f'<p class="solv">{_cite_spans(_esc(card["solvability"]))}</p>')
    if card["benchmarks"]:
        rows = "\n".join(
            f'<tr><td>{_md_cell(r["quantity"])}</td><td>{_md_cell(r["params"])}</td>'
            f'<td>{_md_cell(r["value"])}</td><td>{_md_cell(r["source"])}</td></tr>'
            for r in card["benchmarks"])
        body.append(
            '<div class="tablewrap"><table class="bench">'
            '<thead><tr><th>Quantity</th><th>Params</th><th>Exact value</th>'
            f'<th>Source</th></tr></thead>\n<tbody>\n{rows}\n</tbody></table></div>')
    links = [f'<a href="{BLOB}{e["slug"]}/ORACLE.md">ORACLE.md&nbsp;&#8599;</a>']
    if e["flag"] != "T":
        links.append(f'<a href="{BLOB}{e["slug"]}/oracle.py">oracle.py&nbsp;&#8599;</a>')
    body.append(f'<p class="cardlinks">{" ".join(links)}</p>')
    body_html = "\n".join(body)
    return (
        f'<details class="model" {_data_attrs(e)}>\n'
        f'<summary><span class="mname">{_esc(e["slug"])}</span>'
        f'<span class="hook">{_esc(e.get("hook", ""))}</span>{_badges(e)}</summary>\n'
        f'<div class="mbody">\n{body_html}\n</div>\n'
        f'</details>'
    )


def _render_unbuilt(e: dict) -> str:
    return (
        f'<div class="model ghost" {_data_attrs(e)}>'
        f'<div class="grow"><span class="mname">{_esc(e["slug"])}</span>'
        f'<span class="hook"></span>{_badges(e)}</div></div>'
    )


def render(entries: list) -> str:
    """Render the full solvable.html page from parse_index entries.

    Built entries must carry a "card" dict (parse_card output); every entry
    may carry a "hook" string.
    """
    total = len(entries)

    # group by technique, preserving INDEX order
    order, groups = [], {}
    for e in entries:
        code = e["technique"]
        if code not in groups:
            order.append(code)
            groups[code] = {"title": e["technique_title"], "rows": []}
        groups[code]["rows"].append(e)

    sections = []
    for code in order:
        g = groups[code]
        rows = "\n".join(
            _render_built(e) if e["built"] else _render_unbuilt(e)
            for e in g["rows"])
        sections.append(f'''<section class="tgroup" data-tech="{code}">
<h2><span class="tcode">{code}</span> {_esc(g["title"])}
<span class="scount" data-total="{len(g["rows"])}">{len(g["rows"])}</span></h2>
<p class="tsub">{_esc(SUBTITLES.get(code, ""))}</p>
{rows}
</section>''')
    sections_html = "\n\n".join(sections)

    def chips(group, values, titles=None):
        out = []
        for v in values:
            t = f' title="{_esc(titles[v])}"' if titles and v in titles else ""
            out.append(f'<button class="chip" type="button" data-group="{group}"'
                       f' data-val="{v}" aria-pressed="false"{t}>{v}</button>')
        return "".join(out)

    tech_codes = order
    tech_titles = {c: f"{c} {groups[c]['title']}" for c in tech_codes}
    chips_html = (
        f'<span class="cgroup"><span class="clabel">Technique</span>'
        f'{chips("tech", tech_codes, tech_titles)}</span>\n'
        f'<span class="cgroup"><span class="clabel">Tier</span>'
        f'{chips("tier", ["A", "B", "C", "D"], TIER_TITLES)}</span>\n'
        f'<span class="cgroup"><span class="clabel">Script</span>'
        f'{chips("flag", ["S", "P", "T"], FLAG_TITLES)}</span>'
    )

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Exactly-solvable models — Quantum Many-Body Harness</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>
<style>
  :root{{
    --bg:#0f1117; --panel:#171a23; --panel2:#1d2130; --ink:#e7e9ee; --mut:#9aa3b2;
    --line:#2a2f3d; --accent:#7c6cff; --accent2:#22c1a6; --warn:#e0a458;
    --user:#7aa2ff; --ok:#4cc38a;
    --mono:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;
    --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
       line-height:1.55;-webkit-font-smoothing:antialiased}}
  ::selection{{background:var(--accent);color:#fff}}
  a{{color:var(--accent2);text-decoration:none}}
  a:hover{{text-decoration:underline}}
  .wrap{{max-width:980px;margin:0 auto;padding:0 22px}}

  header{{padding:38px 0 22px;border-bottom:1px solid var(--line)}}
  .kicker{{color:var(--accent);font-weight:700;letter-spacing:.12em;text-transform:uppercase;
          font-size:.74rem;margin-bottom:10px}}
  h1{{font-size:2.15rem;margin:.1em 0 .35em;line-height:1.15}}
  .lead{{color:var(--mut);font-size:1.08rem;max-width:74ch;margin:.2em 0 0}}
  .backlink{{font-family:var(--mono);font-size:.78rem}}

  /* ---- sticky filter bar ---- */
  .filterbar{{position:sticky;top:0;z-index:10;background:var(--bg);
    border-bottom:1px solid var(--line);padding:12px 0 10px}}
  .fb-row{{display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
  #q{{flex:1 1 200px;min-width:0;background:var(--panel);border:1px solid var(--line);
    border-radius:8px;color:var(--ink);font-family:var(--mono);font-size:.84rem;
    padding:7px 11px}}
  #q::placeholder{{color:var(--mut)}}
  #q:focus{{outline:none;border-color:var(--accent)}}
  #count{{font-family:var(--mono);font-size:.78rem;color:var(--mut);white-space:nowrap}}
  .fb-chips{{display:flex;gap:14px 18px;flex-wrap:wrap;margin-top:9px}}
  .cgroup{{display:flex;align-items:center;gap:5px;flex-wrap:wrap}}
  .clabel{{font-size:.68rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
    color:var(--mut);margin-right:2px}}
  .chip{{appearance:none;cursor:pointer;background:transparent;color:var(--mut);
    border:1px solid var(--line);border-radius:999px;font-family:var(--mono);
    font-size:.74rem;padding:2px 9px;transition:color .15s,border-color .15s}}
  .chip:hover{{color:var(--ink);border-color:var(--mut)}}
  .chip[aria-pressed="true"]{{color:var(--accent);border-color:var(--accent)}}
  .chip:focus-visible,summary:focus-visible,#q:focus-visible,.cardlinks a:focus-visible{{
    outline:2px solid var(--accent);outline-offset:2px}}

  /* ---- technique sections ---- */
  section.tgroup{{padding:30px 0 6px;border-bottom:1px solid var(--line)}}
  section.tgroup:last-of-type{{border-bottom:none}}
  h2{{font-size:1.3rem;margin:0;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}}
  .tcode{{font-family:var(--mono);color:var(--accent);font-size:1.02rem}}
  .scount{{font-family:var(--mono);font-size:.76rem;color:var(--mut);font-weight:400;
    border:1px solid var(--line);border-radius:999px;padding:1px 9px}}
  .tsub{{color:var(--mut);font-size:.88rem;margin:.4em 0 14px;max-width:78ch}}

  /* ---- model rows ---- */
  .model{{border:1px solid var(--line);border-radius:10px;margin:0 0 8px;
    background:rgba(23,26,35,.5)}}
  .model summary,.model.ghost>.grow{{display:flex;align-items:baseline;gap:10px;
    flex-wrap:wrap;padding:9px 14px}}
  .model summary{{cursor:pointer;list-style:none}}
  .model summary::-webkit-details-marker{{display:none}}
  .model summary::before{{content:"\\25B8";color:var(--accent);flex:none;
    display:inline-block;transition:transform .15s ease}}
  .model[open]>summary::before{{transform:rotate(90deg)}}
  .model.ghost>.grow::before{{content:"\\25B8";color:transparent;flex:none}}
  .mname{{font-family:var(--mono);font-size:.86rem;font-weight:700}}
  .model summary:hover .mname{{color:var(--accent2)}}
  .hook{{color:var(--mut);font-size:.8rem;flex:1 1 auto;min-width:0}}
  .bset{{display:flex;gap:5px;flex:none;margin-left:auto}}
  .b{{font-family:var(--mono);font-size:.68rem;letter-spacing:.04em;color:var(--mut);
    border:1px solid var(--line);border-radius:999px;padding:1px 8px;white-space:nowrap}}
  .b-ok{{color:var(--ok);border-color:rgba(76,195,138,.45)}}
  .b-dim{{opacity:.75}}
  .model.ghost{{opacity:.45}}
  .model[hidden]{{display:none}}

  /* ---- expanded body ---- */
  .mbody{{border-top:1px solid var(--line);padding:14px 16px 16px}}
  .math{{background:#0b0d13;border:1px solid var(--line);border-radius:10px;
    padding:12px 14px;overflow-x:auto;font-size:.95rem}}
  .solv{{color:var(--mut);font-size:.88rem;max-width:78ch;margin:14px 0 0}}
  .tablewrap{{overflow-x:auto;margin-top:14px}}
  table.bench{{width:100%;border-collapse:collapse;font-size:.82rem}}
  table.bench th,table.bench td{{border-bottom:1px solid var(--line);padding:6px 10px;
    text-align:left;vertical-align:top;white-space:nowrap}}
  table.bench td:last-child,table.bench td:nth-child(2){{white-space:normal}}
  table.bench th{{color:var(--ink)}}
  table.bench code,.cardlinks{{font-family:var(--mono);font-size:.9em;color:var(--accent2)}}
  .cardlinks{{margin:14px 0 0;font-size:.78rem;display:flex;gap:16px}}

  footer{{padding:30px 0 60px;color:var(--mut);font-size:.85rem}}
</style>
</head>
<body>
<div class="wrap">

<header>
  <p class="backlink"><a href="index.html">&#8592; harness home</a></p>
  <div class="kicker">Quantum Many-Body Harness</div>
  <h1>Exactly-solvable models</h1>
  <p class="lead">The harness's verification-oracle layer: {total} models whose exact
  results — spectra, ground energies, gaps, degeneracies — serve as ground truth for
  checking ED, DMRG, QMC, and VMC runs. Open a row for the Hamiltonian, the solvability
  statement, and the benchmark values.</p>
</header>

<div class="filterbar">
  <div class="fb-row">
    <input id="q" type="search" placeholder="search models&hellip;" aria-label="Search models">
    <span id="count">{total} of {total}</span>
  </div>
  <div class="fb-chips">
{chips_html}
  </div>
</div>

{sections_html}

<footer>
  <p>Tiers: <b>A</b> full solution &middot; <b>B</b> integrable (Bethe ansatz)
  &middot; <b>C</b> exact ground state only &middot; <b>D</b> exact in a limit.
  Script flags: <b>S</b> full oracle script &middot; <b>P</b> partial &middot;
  <b>T</b> tabulated only. Cards live under
  <a href="{BLOB}INDEX.md">.knowledge/solvable/</a>; run any oracle with
  <code>uv run python &lt;card&gt;/oracle.py --help</code>.</p>
</footer>

</div>
<script>
(function () {{
  var q = document.getElementById('q');
  var count = document.getElementById('count');
  var chips = Array.prototype.slice.call(document.querySelectorAll('.chip'));
  var models = Array.prototype.slice.call(document.querySelectorAll('.model'));
  var sections = Array.prototype.slice.call(document.querySelectorAll('section.tgroup'));
  var total = models.length;

  function picked(group) {{
    return chips.filter(function (c) {{
      return c.dataset.group === group && c.getAttribute('aria-pressed') === 'true';
    }}).map(function (c) {{ return c.dataset.val; }});
  }}

  function apply() {{
    var needle = q.value.trim().toLowerCase();
    var tech = picked('tech'), tier = picked('tier'), flag = picked('flag');
    var shown = 0;
    models.forEach(function (m) {{
      var d = m.dataset;
      var ok = true;
      if (needle) {{
        var hay = (d.name + ' ' + d.hook + ' ' + d.tech + ' ' + d.techtitle).toLowerCase();
        ok = hay.indexOf(needle) !== -1;
      }}
      if (ok && tech.length) ok = tech.indexOf(d.tech) !== -1;
      if (ok && tier.length) ok = d.tier.split(' ').some(function (t) {{
        return tier.indexOf(t) !== -1; }});
      if (ok && flag.length) ok = flag.indexOf(d.flag) !== -1;
      if (ok) shown++; else if (m.open) m.open = false;
      if (ok) m.removeAttribute('hidden'); else m.setAttribute('hidden', '');
    }});
    sections.forEach(function (s) {{
      var vis = s.querySelectorAll('.model:not([hidden])').length;
      var badge = s.querySelector('.scount');
      badge.textContent = vis === +badge.dataset.total ? badge.dataset.total
                        : vis + ' of ' + badge.dataset.total;
      if (vis === 0) s.setAttribute('hidden', ''); else s.removeAttribute('hidden');
    }});
    count.textContent = shown + ' of ' + total;
  }}

  chips.forEach(function (c) {{
    c.addEventListener('click', function () {{
      c.setAttribute('aria-pressed',
        c.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
      apply();
    }});
  }});
  q.addEventListener('input', apply);

  document.addEventListener('DOMContentLoaded', function () {{
    if (window.renderMathInElement) {{
      renderMathInElement(document.body, {{
        delimiters: [{{left: '$$', right: '$$', display: true}}],
        throwOnError: false
      }});
    }}
  }});
}})();
</script>
</body>
</html>
'''


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT_HTML,
                    help="output HTML path (default: .github/template/solvable.html)")
    args = ap.parse_args(argv)

    entries = parse_index(INDEX_MD.read_text(encoding="utf-8"))
    techs_seen = set()
    for e in entries:
        e["hook"] = HOOKS.get(e["slug"], "")
        techs_seen.add(e["technique"])
        if e["built"]:
            card_md = REPO / ".knowledge" / "solvable" / e["slug"] / "ORACLE.md"
            e["card"] = parse_card(card_md.read_text(encoding="utf-8"))
            if not e["hook"]:
                print(f"warning: built slug '{e['slug']}' has no HOOKS entry",
                      file=sys.stderr)
    for code in techs_seen:
        if not SUBTITLES.get(code):
            print(f"warning: technique '{code}' has no SUBTITLES entry",
                  file=sys.stderr)

    page = render(entries)
    args.out.write_text(page, encoding="utf-8")
    built = sum(1 for e in entries if e["built"])
    print(f"wrote {args.out} — {len(entries)} models ({built} built)")


if __name__ == "__main__":
    main()

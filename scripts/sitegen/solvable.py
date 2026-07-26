"""Generate the solvable.html catalog page from .knowledge/solvable/.

Reads .knowledge/solvable/INDEX.md (the 63-model technique tables) and the
built cards' ORACLE.md files, and renders the page through the shared
sitegen shell. Migrated from scripts/build_solvable_page.py (deleted).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from . import benchmarks, parse, shell

REPO = Path(__file__).resolve().parents[2]
INDEX_MD = REPO / ".knowledge" / "solvable" / "INDEX.md"
BLOB = "https://github.com/QuantumBFS/quantum.harness/blob/main/.knowledge/solvable/"

# Back-compatible aliases: the parsing helpers now live in sitegen.parse.
_strip_md = parse.strip_md
_section = parse.section
_esc = parse.esc
_cite_spans = parse.cite_spans
_md_cell = parse.md_inline

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

# 3–8-word summary-row hooks for the built cards, written from each
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
    "aklt-chain": "exact VBS/MPS ground state; string order −4/9",
    "majumdar-ghosh": "two dimer coverings; exact E/L = −3/8",
    "shastry-sutherland-dimer": "orthogonal-dimer product; exact for all J/J'",
    "rk-quantum-dimer": "equal-weight RVB; RK point ↔ classical dimers",
    "motzkin-fredkin": "uniform Motzkin walks; ½ ln n entanglement",
    "eta-pairing-hubbard": "exact excited η-tower; ODLRO, E=mU",
    "pxp-scars": "exact ±√2 MPS scars; ETH outliers",
    "aklt-honeycomb": "spin-3/2 VBS; frustration-free, proven gap",
    "lmg": "collective j=N/2 block; mean-field-exact, N^{−1/3} gap",
    "curie-weiss-tfim": "fully-connected TFIM; mean-field exact in N→∞",
    "jaynes-cummings": "RWA dressed states; vacuum Rabi splitting 2g",
    "dicke-tavis-cummings": "excitation-number blocks; superradiant λ_c=√(ωω₀)/2",
    "quantum-rabi": "Braak G-function roots; exact transcendental spectrum",
    "random-matrix-stats": "Wigner/Atas surmises; ⟨r̃⟩ GOE/GUE/GSE, Kramers doubling",
    "syk": "melonic large-N; N mod 8 class, S₀≈0.2324 entropy",
    "falicov-kimball-dinf": "DMFT-exact in d=∞; checkerboard CDW, sign-free",
    "kramers-wannier": "Ising self-duality; sinh2K·sinh2K*=1 fixes Kc",
    "jw-duality-dictionary": "mapping index: JW, KW, dimers, six-vertex↔XXZ",
    "dual-unitary-circuits": "space-time-unitary gates; exact light-cone correlators",
    "kicked-ising-floquet": "self-dual KIM; exact SFF ramp K(t)=2t−1",
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
    extra = f'{e["technique"]} {e["technique_title"]}'
    return (f'data-name="{_esc(e["slug"])}" data-hook="{_esc(e.get("hook", ""))}"'
            f' data-tech="{e["technique"]}" data-tier="{_esc(tiers)}"'
            f' data-flag="{_esc(e["flag"])}" data-extra="{_esc(extra)}"')


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
    bench = benchmarks.model_table(e["slug"])
    if bench:
        body.append(bench)
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

    tech_codes = order
    tech_titles = {c: f"{c} {groups[c]['title']}" for c in tech_codes}
    chips_html = (
        f'<span class="cgroup"><span class="clabel">Technique</span>'
        f'{shell.chips("tech", tech_codes, tech_titles)}</span>\n'
        f'<span class="cgroup"><span class="clabel">Tier</span>'
        f'{shell.chips("tier", ["A", "B", "C", "D"], TIER_TITLES)}</span>\n'
        f'<span class="cgroup"><span class="clabel">Script</span>'
        f'{shell.chips("flag", ["S", "P", "T"], FLAG_TITLES)}</span>'
    )

    return shell.page(
        title="Exactly-solvable models",
        lead=("The harness's verification-oracle layer: "
              f"{total} models whose exact results — spectra, ground energies, "
              "gaps, degeneracies — serve as ground truth for checking ED, DMRG, "
              "QMC, and VMC runs. Open a row for the Hamiltonian, the solvability "
              "statement, and the benchmark values."),
        total=total,
        chips_html=chips_html,
        sections_html=sections_html,
        footer_html=(
            "<p>Tiers: <b>A</b> full solution &middot; <b>B</b> integrable (Bethe "
            "ansatz) &middot; <b>C</b> exact ground state only &middot; <b>D</b> "
            "exact in a limit. Script flags: <b>S</b> full oracle script &middot; "
            "<b>P</b> partial &middot; <b>T</b> tabulated only. Cards live under "
            f'<a href="{BLOB}INDEX.md">.knowledge/solvable/</a>; run any oracle '
            "with <code>uv run python &lt;card&gt;/oracle.py --help</code>.</p>"),
        here="solvable.html",
        search_placeholder="search models&hellip;",
    )


# --------------------------------------------------------------------------
# build entry points (driven by build_site.py)
# --------------------------------------------------------------------------

def build_entries() -> list:
    """parse_index + attach HOOKS and parsed ORACLE cards (built rows)."""
    entries = parse_index(INDEX_MD.read_text(encoding="utf-8"))
    for e in entries:
        e["hook"] = HOOKS.get(e["slug"], "")
        if e["built"]:
            card_md = REPO / ".knowledge" / "solvable" / e["slug"] / "ORACLE.md"
            e["card"] = parse_card(card_md.read_text(encoding="utf-8"))
            if not e["hook"]:
                print(f"warning: built slug '{e['slug']}' has no HOOKS entry",
                      file=sys.stderr)
    for code in {e["technique"] for e in entries}:
        if not SUBTITLES.get(code):
            print(f"warning: technique '{code}' has no SUBTITLES entry",
                  file=sys.stderr)
    return entries


def build_page() -> str:
    return render(build_entries())

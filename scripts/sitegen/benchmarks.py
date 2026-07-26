"""Benchmark views for the catalog pages.

Single source of truth: .knowledge/solvable/benchmarks.json (emitted by a
benchmark campaign's verdict.py). Two views render from it: per-model
tables on solvable.html and the full model × method matrix on
benchmarks.html. If the file is absent the pages build without them.
"""
import json
import math
from pathlib import Path

from . import shell

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / ".knowledge" / "solvable" / "benchmarks.json"
BLOB = "https://github.com/QuantumBFS/quantum.harness/blob/main/.knowledge/solvable/"

METHOD_ORDER = ["ed", "mps", "peps", "ltrg", "mcrg",
                "qmc", "vmc", "mf", "polyopt", "qcs"]
METHOD_TITLES = {
    "ed": "exact diagonalization",
    "mps": "matrix-product states (DMRG / VUMPS / TEBD)",
    "peps": "projected entangled pair states",
    "ltrg": "linearized tensor renormalization group",
    "mcrg": "Monte Carlo renormalization group",
    "qmc": "quantum Monte Carlo",
    "vmc": "variational Monte Carlo",
    "mf": "mean-field theory",
    "polyopt": "polynomial optimization (moment / SOS hierarchies)",
    "qcs": "quantum-circuit simulation",
}
MODEL_ORDER = ["tfim-chain", "ising-2d-onsager", "toric-code", "aklt-chain",
               "hubbard-1d-lieb-wu", "lmg", "kicked-ising-floquet"]

METHOD_COLORS = {"ed": "#588bff", "mps": "#ff9330", "peps": "#3fca5a",
                 "ltrg": "#ff4f58", "mcrg": "#a874ff", "qmc": "#ffd52e",
                 "vmc": "#ff77cf", "mf": "#b9c2cc", "polyopt": "#00a5a5",
                 "qcs": "#6fdcff"}
MODEL_MARKERS = {"tfim-chain": "circle", "ising-2d-onsager": "square",
                 "toric-code": "diamond", "aklt-chain": "tri-up",
                 "hubbard-1d-lieb-wu": "tri-down", "lmg": "plus",
                 "kicked-ising-floquet": "cross"}
# recorded size -> log2 of the Hilbert-space dimension (2D Ising: classical
# configurations 2^(L^2); LMG: N spin-1/2, full space 2^N)
LOG2DIM = {"tfim-chain": lambda L: L, "ising-2d-onsager": lambda L: L * L,
           "toric-code": lambda L: 2 * L * L,
           "aklt-chain": lambda L: L * math.log2(3),
           "hubbard-1d-lieb-wu": lambda L: 2 * L, "lmg": lambda N: N,
           "kicked-ising-floquet": lambda L: L}

_data = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else None


def _fmt_err(x, long=True) -> str:
    if x == 0:
        return "0 (machine-exact)" if long else "0"
    exp = math.floor(math.log10(abs(x)))
    if -3 <= exp <= 0:
        return f"{x:.2g}"
    return f"{x / 10**exp:.1f}&times;10<sup>{exp}</sup>"


def _fmt_size(s: str, long=True) -> str:
    if not s.isdigit():
        return s
    if long or len(s) <= 5:
        return "&#8239;".join(_group(s)) if len(s) > 4 else s
    exp = len(s) - 1
    if int(s) == 10**exp:
        return f"10<sup>{exp}</sup>"
    m = int(s) / 10**exp
    if f"{m:.1f}" == "10.0":
        exp, m = exp + 1, 1.0
    return f"{m:.1f}&times;10<sup>{exp}</sup>"


def _group(s: str) -> list:
    out, i = [], len(s) % 3 or 3
    out.append(s[:i])
    while i < len(s):
        out.append(s[i:i + 3])
        i += 3
    return out


def _caption(meta: dict) -> str:
    bars = meta["bars"]
    return (f'<p class="solv"><strong>Benchmark</strong> &mdash; {meta["definition"]}. '
            f'Accuracy bar: 10<sup>{math.floor(math.log10(bars["deterministic"]))}</sup> for '
            f'deterministic routes, 10<sup>{math.floor(math.log10(bars["variational"]))}</sup> for '
            f'variational, 2&sigma; for stochastic; entries above their bar report the '
            f'method&#x27;s intrinsic limit at this size ({meta["date"]}).</p>')


def _rows(entries: list, label_key: str) -> str:
    rows = []
    for e in entries:
        label = f'<td><code>{e[label_key]}</code></td>'
        if e["status"] == "COMPLETED":
            full = e.get("observable") or ""
            short = full
            for sep in (" (", " — ", "; ", " at ", " = "):
                if sep in short:
                    short = short.split(sep, 1)[0]
            title = f' title="{full.replace(chr(34), "&quot;")}"' if short != full else ""
            rows.append(
                f'{label}<td><code>{_fmt_size(str(e["size"]))}</code>'
                f'<span class="unit"> {e["size_unit"]}</span></td>'
                f'<td><code>{_fmt_err(e["rel_err"])}</code></td>'
                f'<td><code{title}>{short}</code></td>')
        elif e["status"] == "FAILED":
            rows.append(
                f'{label}<td colspan="3">failed &mdash; the software route broke '
                f'(largest attempted: {_fmt_size(str(e.get("size") or "?"))})</td>')
        else:  # UNSUITABLE
            ref = e.get("card_ref") or ""
            why = (e.get("why") or "").replace('"', "&quot;")
            rows.append(
                f'{label}<td colspan="3">unsuitable &mdash; '
                f'<span class="cite" title="{why}">{ref}</span></td>')
    return "\n".join(f"<tr>{r}</tr>" for r in rows)


def model_table(slug: str) -> str:
    """Benchmark table for one solvable model (methods as rows); "" if none."""
    if not _data:
        return ""
    es = [e for e in _data["entries"] if e["model"] == slug]
    if not es:
        return ""
    es.sort(key=lambda e: METHOD_ORDER.index(e["method"]))
    meta = _data["campaigns"][es[0]["campaign"]]
    return (_caption(meta) +
            '<div class="tablewrap"><table class="bench"><thead><tr><th>Method</th>'
            '<th>Largest size</th><th>rel. error at frontier</th><th>Observable</th>'
            f'</tr></thead>\n<tbody>\n{_rows(es, "method")}\n</tbody></table></div>')


def _cell(e) -> str:
    if e is None:
        return "<td></td>"
    if e["status"] == "COMPLETED":
        size = str(e["size"])
        obs = (e.get("observable") or "").replace('"', "&quot;")
        if size.isdigit() and len(size) > 5:
            obs += f" &middot; exact size = {size}"
        title = f' title="{obs}"' if obs else ""
        return (f'<td{title}>&#10003; <code>{_fmt_size(size, long=False)}</code>'
                f'<span class="err"> &middot; '
                f'<code>{_fmt_err(e["rel_err"], long=False)}</code></span></td>')
    if e["status"] == "FAILED":
        return (f'<td title="the software route broke at this size">&#10007; '
                f'<code>{_fmt_size(str(e.get("size") or "?"), long=False)}</code></td>')
    why = (e.get("why") or "").replace('"', "&quot;")
    return f'<td title="{why}">&empty;</td>'


def _marker(shape: str, x: float, y: float, color: str, title: str) -> str:
    t = f"<title>{title}</title>"
    edge = 'stroke="#0b0d13" stroke-width="1.2"'
    if shape == "circle":
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{color}" {edge}>{t}</circle>'
    if shape == "square":
        return (f'<rect x="{x - 5.2:.1f}" y="{y - 5.2:.1f}" width="10.4" height="10.4" '
                f'fill="{color}" {edge}>{t}</rect>')
    if shape == "diamond":
        p = f"{x:.1f},{y - 7:.1f} {x + 7:.1f},{y:.1f} {x:.1f},{y + 7:.1f} {x - 7:.1f},{y:.1f}"
    elif shape == "tri-up":
        p = f"{x:.1f},{y - 7:.1f} {x + 6.5:.1f},{y + 5.2:.1f} {x - 6.5:.1f},{y + 5.2:.1f}"
    elif shape == "tri-down":
        p = f"{x:.1f},{y + 7:.1f} {x + 6.5:.1f},{y - 5.2:.1f} {x - 6.5:.1f},{y - 5.2:.1f}"
    else:
        d = (f"M{x - 6:.1f} {y:.1f}H{x + 6:.1f}M{x:.1f} {y - 6:.1f}V{y + 6:.1f}"
             if shape == "plus" else
             f"M{x - 4.6:.1f} {y - 4.6:.1f}L{x + 4.6:.1f} {y + 4.6:.1f}"
             f"M{x + 4.6:.1f} {y - 4.6:.1f}L{x - 4.6:.1f} {y + 4.6:.1f}")
        return (f'<path d="{d}" stroke="{color}" stroke-width="3" '
                f'fill="none">{t}</path>')
    return f'<polygon points="{p}" fill="{color}" {edge}>{t}</polygon>'


def _pow10(exp: int) -> str:
    return f'10<tspan dy="-5" font-size="9">{exp}</tspan>'


def _fig(entries: list, meta: dict) -> str:
    """Frontier scatter: x = log2 Hilbert dimension (log scale), y = rel. error."""
    Y_FLOOR = 1e-16
    pts, inf_pts = [], []
    for e in entries:
        if e["status"] != "COMPLETED":
            continue
        size = str(e["size"])
        if size.startswith("∞"):
            inf_pts.append(e)
        else:
            pts.append((e, LOG2DIM[e["model"]](int(size))))
    xlo = math.floor(math.log10(min(x for _, x in pts)))
    xhi = math.ceil(math.log10(max(x for _, x in pts)))
    ylo = -16
    yhi = math.ceil(math.log10(max(e["rel_err"] for e, _ in pts)))
    X0, Y0, W, H = 70, 64, 1240, 470
    BX = X0 + W + 98  # center of the ∞ band, past the axis break
    bot = Y0 + H

    def sx(v):
        return X0 + (math.log10(v) - xlo) / (xhi - xlo) * W

    def sy(v):
        return Y0 + H - (math.log10(max(v, Y_FLOOR)) - ylo) / (yhi - ylo) * H

    s = [f'<svg viewBox="0 0 1500 640" style="width:100%;height:auto" '
         f'font-size="12" role="img" aria-label="frontier scatter">']
    # legends: color = method, shape = model
    lx = X0
    for m in METHOD_ORDER:
        s.append(f'<circle cx="{lx + 5}" cy="18" r="5" fill="{METHOD_COLORS[m]}"/>'
                 f'<text x="{lx + 15}" y="22" fill="var(--mut)">{m}</text>')
        lx += 24 + 8 * len(m)
    lx = X0
    for m in MODEL_ORDER:
        s.append(_marker(MODEL_MARKERS[m], lx + 5, 42, "#8a93a6", m))
        s.append(f'<text x="{lx + 15}" y="46" fill="var(--mut)">{m}</text>')
        lx += 28 + 8 * len(m)
    # grid + ticks
    for ex in range(xlo, xhi + 1):
        x = sx(10**ex)
        s.append(f'<line x1="{x:.1f}" y1="{Y0}" x2="{x:.1f}" y2="{bot}" '
                 f'stroke="var(--line)"/>')
        s.append(f'<text x="{x:.1f}" y="{bot + 18}" text-anchor="middle" '
                 f'fill="var(--mut)">{_pow10(ex)}</text>')
    for ey in range(ylo, yhi + 1, 2):
        y = sy(10.0**ey)
        s.append(f'<line x1="{X0}" y1="{y:.1f}" x2="{X0 + W}" y2="{y:.1f}" '
                 f'stroke="var(--line)"/>')
        s.append(f'<text x="{X0 - 8}" y="{y + 4:.1f}" text-anchor="end" '
                 f'fill="var(--mut)">{_pow10(ey)}</text>')
    # accuracy bars
    for v, label in ((meta["bars"]["deterministic"], "deterministic bar"),
                     (meta["bars"]["variational"], "variational bar")):
        y = sy(v)
        s.append(f'<line x1="{X0}" y1="{y:.1f}" x2="{X0 + W}" y2="{y:.1f}" '
                 f'stroke="var(--mut)" stroke-dasharray="6 5" opacity="0.55"/>')
        s.append(f'<text x="{X0 + W - 6}" y="{y - 6:.1f}" text-anchor="end" '
                 f'fill="var(--mut)" opacity="0.8">{label}</text>')
    # axes, break, ∞ band
    s.append(f'<line x1="{X0}" y1="{bot}" x2="{X0 + W}" y2="{bot}" stroke="var(--mut)"/>')
    s.append(f'<line x1="{X0}" y1="{Y0}" x2="{X0}" y2="{bot}" stroke="var(--mut)"/>')
    s.append(f'<line x1="{X0 + W + 44}" y1="{bot}" x2="1500" y2="{bot}" stroke="var(--mut)"/>')
    for dx in (18, 26):
        s.append(f'<line x1="{X0 + W + dx}" y1="{bot - 7}" x2="{X0 + W + dx + 8}" '
                 f'y2="{bot + 7}" stroke="var(--mut)"/>')
    s.append(f'<text x="{BX}" y="{bot + 20}" text-anchor="middle" '
             f'fill="var(--mut)" font-size="16">&#8734;</text>')
    s.append(f'<text x="{X0 + W / 2:.0f}" y="{bot + 44}" text-anchor="middle" '
             f'fill="var(--ink)">log&#8322; Hilbert-space dimension</text>')
    s.append(f'<text x="20" y="{Y0 + H / 2:.0f}" text-anchor="middle" fill="var(--ink)" '
             f'transform="rotate(-90 20 {Y0 + H / 2:.0f})">relative error at the frontier</text>')
    # points
    for e, x in pts:
        tip = (f'{e["model"]} — {e["method"]}: size {e["size"]} {e["size_unit"]}, '
               f'rel. error {e["rel_err"]:.2g}'
               + (" (machine-exact)" if e["rel_err"] == 0 else ""))
        s.append(_marker(MODEL_MARKERS[e["model"]], sx(x), sy(e["rel_err"]),
                         METHOD_COLORS[e["method"]], tip))
    for i, e in enumerate(inf_pts):
        tip = (f'{e["model"]} — {e["method"]}: size {e["size"]}, '
               f'rel. error {e["rel_err"]:.2g}')
        s.append(_marker(MODEL_MARKERS[e["model"]], BX + (i - (len(inf_pts) - 1) / 2) * 16,
                         sy(e["rel_err"]), METHOD_COLORS[e["method"]], tip))
    s.append("</svg>")
    caption = (
        '<p class="solv"><strong>Frontier figure</strong> &mdash; each point is one '
        'completed model &times; method entry: the largest size reached within the '
        'compute budget (x) against the relative error at that size (y); color = '
        'method, shape = model. The x axis converts each model&#x27;s size to the '
        'log&#8322; of its Hilbert-space dimension: L (TFIM chain, kicked Ising), '
        '1.58&thinsp;L (AKLT, 3 states per site), 2&thinsp;L (Hubbard), '
        'L&sup2; (2D Ising, classical configurations), 2&thinsp;L&sup2; (toric code), '
        'N (LMG). Entries that reached the infinite-size limit sit in the &#8734; band '
        'past the axis break; points on the bottom edge are machine-exact (error 0). '
        'The dashed lines mark the deterministic (10<sup>-8</sup>) and variational '
        '(10<sup>-3</sup>) accuracy bars; the stochastic bar &mdash; agreement with the '
        'exact value within 2&sigma; of the run&#x27;s own statistical error bar &mdash; '
        'is a per-point criterion and has no fixed level to draw.</p>')
    return f'<section class="tgroup">\n{caption}\n{"".join(s)}\n</section>'


def build_page() -> str:
    """benchmarks.html: the full model × method matrix; "" if no data."""
    if not _data:
        return ""
    meta = _data["campaigns"]["solvable-frontier"]
    entries = [e for e in _data["entries"] if e["campaign"] == "solvable-frontier"]
    by = {(e["model"], e["method"]): e for e in entries}
    unit = {e["model"]: e["size_unit"] for e in entries if "size_unit" in e}
    n = {s: sum(e["status"] == s for e in entries)
         for s in ("COMPLETED", "UNSUITABLE", "FAILED")}
    head = "".join(f'<th title="{METHOD_TITLES[m]}">{m}</th>' for m in METHOD_ORDER)
    rows = "\n".join(
        f'<tr><th scope="row">{m}<span class="unit"> ({unit[m]})</span></th>'
        + "".join(_cell(by.get((m, meth))) for meth in METHOD_ORDER) + "</tr>"
        for m in MODEL_ORDER)
    repo, branch = meta["provenance"].split()
    section = f'''<section class="tgroup">
{_caption(meta)}
<p class="solv">&#10003; completed &mdash; largest size &middot; relative error (hover for
the measured observable) &nbsp;&nbsp;&empty; unsuitable &mdash; the method cannot express
this model (hover for why) &nbsp;&nbsp;&#10007; failed &mdash; the software route broke
(largest size attempted).</p>
<div class="tablewrap"><table class="bench matrix">
<thead><tr><th>model \\ method</th>{head}</tr></thead>
<tbody>
{rows}
</tbody></table></div>
</section>
{_fig(entries, meta)}'''
    return shell.page(
        title="Benchmarks",
        lead=(f"Every method family measured on every exactly solvable model: "
              f"{len(entries)} combinations &mdash; {n['COMPLETED']} completed, "
              f"{n['UNSUITABLE']} unsuitable, {n['FAILED']} failed. Each completed "
              "entry is the largest size that method reached within the compute "
              "budget, with its relative error against the exact solution."),
        total=len(entries),
        chips_html="",
        sections_html=section,
        footer_html=(
            f'<p>Data: <a href="{BLOB}benchmarks.json">.knowledge/solvable/benchmarks.json</a>, '
            f'generated by the benchmark campaign at '
            f'<a href="https://github.com/{repo}/tree/{branch}">{repo}</a>. '
            'Per-model detail tables are on the '
            '<a href="solvable.html">solvable models page</a>.</p>'),
        here="benchmarks.html",
        search_placeholder="",
        filterbar=False,
        wide=True,
    )

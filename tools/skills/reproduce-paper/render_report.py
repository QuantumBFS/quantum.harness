#!/usr/bin/env python3
"""Render a run's run.json into a standalone results/<run>/report.html.

    python3 render_report.py <run-dir>

Reads <run-dir>/run.json (the single source of data) and writes
<run-dir>/report.html — a one-way view of run.json. The HTML is fully
self-contained: inline CSS, each figure base64-embedded, equations as inline
MathML. No external assets, no network, no build step — it opens offline like
a PDF.

A run is one shared computation (model + method + sizes) and a `figures` list,
each figure a single view of it. Layout: Model, Method (+ the one cost table),
then one block per figure. Each figure block shows its plan and — once its
`results` block is filled — its figure, numbers, and an honest
matched/partly/didn't read; until then it reads "pending".

Math convention:
  - model.H is a LaTeX equation (no delimiters) and renders as display math.
  - Any other string may carry inline LaTeX in $…$ (or display in $$…$$).
The LaTeX→MathML converter below is stdlib-only and covers the physics subset
(sub/superscripts, groups, \\frac, \\sqrt, sums/products/integrals with limits,
Greek, \\mathbf/\\vec, common operators). Unknown commands render literally.
"""
import base64
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

# ── LaTeX → MathML (stdlib only, physics subset) ──────────────────────────────
_GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "varepsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "ϑ",
    "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ",
    "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ", "upsilon": "υ", "phi": "φ",
    "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω", "Gamma": "Γ",
    "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π",
    "Sigma": "Σ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω", "hbar": "ℏ",
    "ell": "ℓ", "nabla": "∇", "partial": "∂", "infty": "∞",
}
_OP = {
    "cdot": "·", "times": "×", "div": "÷", "pm": "±", "mp": "∓", "ast": "∗",
    "star": "⋆", "otimes": "⊗", "oplus": "⊕", "circ": "∘", "bullet": "∙",
    "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠", "ne": "≠",
    "approx": "≈", "sim": "∼", "simeq": "≃", "equiv": "≡", "propto": "∝",
    "to": "→", "rightarrow": "→", "leftarrow": "←", "mapsto": "↦",
    "Rightarrow": "⇒", "leftrightarrow": "↔", "uparrow": "↑", "downarrow": "↓",
    "langle": "⟨", "rangle": "⟩", "lvert": "|", "rvert": "|", "vert": "|",
    "Vert": "‖", "dagger": "†", "prime": "′", "cdots": "⋯", "dots": "…",
    "ldots": "…", "in": "∈", "notin": "∉", "subset": "⊂", "cup": "∪",
    "cap": "∩", "forall": "∀", "exists": "∃", "wedge": "∧", "vee": "∨",
}
_BIG = {"sum": "∑", "prod": "∏", "int": "∫", "oint": "∮", "coprod": "∐",
        "bigoplus": "⨁", "bigotimes": "⨂", "bigcup": "⋃", "bigcap": "⋂"}
_SPACE = {" ", ",", ";", "!", ":", ">", "quad", "qquad", "thinspace"}


def _tokenize(s):
    toks, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
        elif c == "\\":
            j = i + 1
            if j < n and s[j].isalpha():
                while j < n and s[j].isalpha():
                    j += 1
                toks.append(("cmd", s[i + 1:j]))
                i = j
            elif j < n:
                toks.append(("cmd", s[j]))
                i = j + 1
            else:
                i = j
        elif c in "{}^_":
            toks.append(("punct", c))
            i += 1
        elif c.isdigit():
            j = i
            while j < n and (s[j].isdigit() or s[j] == "."):
                j += 1
            toks.append(("num", s[i:j]))
            i = j
        elif c.isalpha():
            toks.append(("var", c))
            i += 1
        else:
            toks.append(("op", c))
            i += 1
    return toks


class _Tex:
    """Recursive-descent LaTeX→MathML for the physics subset."""

    def __init__(self, src):
        self.toks = _tokenize(src)
        self.i = 0

    def _peek(self):
        return self.toks[self.i] if self.i < len(self.toks) else (None, None)

    def _next(self):
        tok = self._peek()
        if self.i < len(self.toks):
            self.i += 1
        return tok

    def _delim(self, tok):
        kind, val = tok
        if val in (".", None):
            return ""                                    # \left. / \right. → no bar
        return _OP.get(val, _GREEK.get(val, esc(val))) if kind == "cmd" else esc(val)

    def row(self, stop=None):
        out = []
        while True:
            kind, val = self._peek()
            if (kind is None or (kind == "punct" and (val == stop or val == "}"))
                    or (kind == "cmd" and val == "right")):
                break
            if kind == "punct" and val in ("_", "^"):
                base, big = out.pop() if out else ("<mrow></mrow>", False)
                out.append(self._scripts(base, big))
            else:
                out.append(self._atom())
        return "".join(s for s, _ in out)

    def _scripts(self, base, big):
        sub = sup = None
        while True:
            kind, val = self._peek()
            if kind == "punct" and val == "_" and sub is None:
                self._next()
                sub = self._atom()[0]
            elif kind == "punct" and val == "^" and sup is None:
                self._next()
                sup = self._atom()[0]
            else:
                break
        if big:
            tag = ("munderover" if sub and sup else "munder" if sub else
                   "mover" if sup else None)
        else:
            tag = ("msubsup" if sub and sup else "msub" if sub else
                   "msup" if sup else None)
        if tag is None:
            return (base, False)
        inner = base + (sub or "") + (sup or "")
        return (f"<{tag}>{inner}</{tag}>", False)

    def _atom(self):
        kind, val = self._next()
        if kind == "punct" and val == "{":
            inner = self.row(stop="}")
            if self._peek() == ("punct", "}"):
                self._next()
            return (f"<mrow>{inner}</mrow>", False)
        if kind == "num":
            return (f"<mn>{val}</mn>", False)
        if kind == "var":
            return (f"<mi>{val}</mi>", False)
        if kind == "op":
            return (f"<mo>{esc(val)}</mo>", False)
        if kind == "cmd":
            if val == "frac":
                num = self._atom()[0]
                den = self._atom()[0]
                return (f"<mfrac>{num}{den}</mfrac>", False)
            if val == "sqrt":
                return (f"<msqrt>{self._atom()[0]}</msqrt>", False)
            if val in ("mathbf", "boldsymbol", "bm", "vec"):
                a = self._atom()[0].replace("<mi>", '<mi mathvariant="bold">')
                return ((f"<mover>{a}<mo>→</mo></mover>", False) if val == "vec"
                        else (a, False))
            if val in ("mathrm", "operatorname", "mathsf", "mathcal", "text"):
                return (self._atom()[0], False)
            if val == "left":
                od = self._delim(self._next())
                inner = self.row()                       # stops at the matching \right
                cd = ""
                if self._peek() == ("cmd", "right"):
                    self._next()
                    cd = self._delim(self._next())
                o = f'<mo fence="true">{od}</mo>' if od else ""
                c = f'<mo fence="true">{cd}</mo>' if cd else ""
                return (f"<mrow>{o}{inner}{c}</mrow>", False)
            if val == "right":
                return ("", False)                       # stray; normally eaten by \left
            if val in _BIG:
                return (f"<mo>{_BIG[val]}</mo>", True)
            if val in _OP:
                return (f"<mo>{_OP[val]}</mo>", False)
            if val in _GREEK:
                return (f"<mi>{_GREEK[val]}</mi>", False)
            if val in _SPACE:
                return ("", False)
            if not val.isalpha():            # escaped delimiter: \{ \| \&
                return (f"<mo>{esc(val)}</mo>", False)
            return (f"<mi>{esc(val)}</mi>", False)   # unknown command, literal
        return ("", False)


def _mathml(latex, display=False):
    body = _Tex(latex).row()
    da = ' display="block"' if display else ""
    return (f'<math xmlns="http://www.w3.org/1998/Math/MathML"{da}>'
            f"<mrow>{body}</mrow></math>")


_MATH = re.compile(r"\$\$(.+?)\$\$|\$(.+?)\$", re.DOTALL)


def mathify(x):
    """Escape text, converting $…$ / $$…$$ spans to inline MathML."""
    if x is None:
        return ""
    s, out, last = str(x), [], 0
    for m in _MATH.finditer(s):
        out.append(esc(s[last:m.start()]))
        disp = m.group(1) is not None
        out.append(_mathml(m.group(1) if disp else m.group(2), display=disp))
        last = m.end()
    out.append(esc(s[last:]))
    return "".join(out)


# ── palette + components, lifted from docs/ed/ed_review.html ──────────────────
STYLE = """
:root{
  --bg:#fbfaf6; --panel:#fff; --ink:#1a1a1a; --muted:#5b5b5b; --line:#e6e3da;
  --accent:#1f5cd6; --accent-soft:#e6efff; --warm:#b8651e; --warm-soft:#fcefdc;
  --good:#1e7d3c; --good-soft:#e1f3e6; --bad:#b3261e; --bad-soft:#fbe4e2;
  --olive:#7c6f1d; --olive-soft:#f5f1d8; --code-bg:#f2f1eb;
  --serif:"Iowan Old Style","Source Serif 4","Charter",Cambria,Georgia,serif;
  --sans:-apple-system,"Inter","Segoe UI",system-ui,sans-serif;
  --mono:"JetBrains Mono","SF Mono",Menlo,Consolas,monospace;
}
*{box-sizing:border-box}
html,body{background:var(--bg);color:var(--ink);margin:0;font-family:var(--sans);-webkit-font-smoothing:antialiased}
body{line-height:1.55}
a{color:var(--accent);text-decoration:none;border-bottom:1px solid transparent}
a:hover{border-bottom-color:var(--accent)}
code{font-family:var(--mono);font-size:.9em;background:var(--code-bg);padding:1px 5px;border-radius:3px}
math{font-family:var(--serif);font-size:1.04em}
math[display="block"]{font-size:1.2em;margin:2px 0}
.wrap{max-width:880px;margin:0 auto;padding:46px 40px 100px}
@media(max-width:720px){.wrap{padding:26px 18px 70px}}
.eyebrow{font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--accent);font-weight:600}
h1{font-family:var(--serif);font-size:30px;line-height:1.15;margin:8px 0 12px;max-width:32ch}
.sub{font-size:13px;color:var(--muted);margin:0}
.lede{font-size:15px;color:#2a2a2a;margin:14px 0 0;max-width:72ch}
.expected{margin:18px 0 0;padding:12px 15px;background:var(--accent-soft);border:1px solid #c4d9f7;border-radius:6px;font-size:14px}
.expected b{color:#143b87}
.hero{padding-bottom:24px;margin-bottom:8px;border-bottom:1px solid var(--line)}
section{margin:38px 0 0}
section>h2{font-family:var(--serif);font-size:22px;margin:0 0 4px}
section>.note{color:var(--muted);font-size:13px;margin:0 0 16px;max-width:72ch}
.card{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:13px 16px;margin:10px 0}
.card .title{font-family:var(--serif);font-size:15px;font-weight:600;margin-bottom:2px}
.eq{text-align:center;margin:6px 0 12px;padding:6px 0;overflow-x:auto}
.kv{display:grid;grid-template-columns:150px minmax(0,1fr);gap:4px 14px;font-size:13.5px;margin-top:6px}
.kv .k{color:var(--muted)} .kv .v{color:#1a1a1a}
table{width:100%;border-collapse:collapse;font-size:13.5px;background:var(--panel);border:1px solid var(--line);border-radius:6px;overflow:hidden;margin:8px 0}
thead th{background:#f7f5ed;text-align:left;padding:9px 11px;font-weight:600;border-bottom:1px solid var(--line)}
tbody td{padding:9px 11px;border-top:1px solid var(--line);vertical-align:top}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.pill{display:inline-block;font-size:11px;padding:2px 8px;border-radius:999px;border:1px solid var(--line);background:#fafafa;color:#444;white-space:nowrap}
.pill.exact{background:var(--good-soft);border-color:#b4d9bd;color:var(--good)}
.pill.approx{background:var(--warm-soft);border-color:#e7c79b;color:var(--warm)}
ul.flat{padding-left:20px;margin:6px 0} ul.flat li{margin:3px 0;font-size:13.5px}
.verdict{display:flex;gap:12px;align-items:baseline;padding:13px 16px;border-radius:6px;border:1px solid var(--line);margin:6px 0 14px}
.verdict .label{font-family:var(--serif);font-size:17px;font-weight:600;white-space:nowrap}
.verdict .why{font-size:13.5px;color:#222}
.verdict.good{background:var(--good-soft);border-color:#b4d9bd} .verdict.good .label{color:var(--good)}
.verdict.warn{background:var(--olive-soft);border-color:#d9d09b} .verdict.warn .label{color:var(--olive)}
.verdict.bad{background:var(--bad-soft);border-color:#f1bdc1} .verdict.bad .label{color:var(--bad)}
.figs{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;margin:14px 0;width:min(1180px,94vw);position:relative;left:50%;transform:translateX(-50%)}
.figbox{border:1px solid var(--line);border-radius:6px;background:var(--panel);padding:10px;text-align:center}
.figbox img{max-width:100%;height:auto;display:block;margin:0 auto;border-radius:3px}
.figbox .cap{font-size:12px;color:var(--muted);margin-top:7px}
.figblock{border-top:1px solid var(--line);margin-top:22px;padding-top:10px}
.figblock:first-of-type{border-top:none;margin-top:6px;padding-top:0}
.figblock h3{font-family:var(--serif);font-size:18px;margin:0 0 8px}
.pending{padding:14px 16px;border:1px dashed var(--line);border-radius:6px;color:var(--muted);font-size:14px;background:#faf8f2}
.footer{margin-top:56px;padding-top:18px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
.print-btn{position:fixed;top:16px;right:18px;font-family:var(--sans);font-size:12.5px;padding:7px 12px;border:1px solid var(--line);background:#fff;color:var(--ink);border-radius:5px;cursor:pointer}
.print-btn:hover{border-color:var(--accent);color:var(--accent)}
@media print{.print-btn{display:none}.wrap{max-width:100%;padding:0}.figs{position:static;left:auto;transform:none;width:auto}.card,table,.verdict,.figbox{break-inside:avoid}}
"""

MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "svg": "image/svg+xml", "webp": "image/webp", "gif": "image/gif"}


def esc(x):
    return html.escape("" if x is None else str(x))


def data_uri(path: Path) -> str:
    mime = MIME.get(path.suffix.lower().lstrip("."), "application/octet-stream")
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def fmt_map(d) -> str:
    if not isinstance(d, dict) or not d:
        return ""
    return " · ".join(f"{k} = {v}" for k, v in d.items())


def kv(*pairs) -> str:
    rows = "".join(
        f'<div class="k">{esc(k)}</div><div class="v">{mathify(v)}</div>'
        for k, v in pairs if v not in (None, "", [], {})
    )
    return f'<div class="kv">{rows}</div>' if rows else ""


def card(title: str, body: str) -> str:
    return f'<div class="card"><div class="title">{esc(title)}</div>{body}</div>' if body else ""


def figbox(src: str, cap: str) -> str:
    return f'<div class="figbox"><img src="{src}" alt="{esc(cap)}"><div class="cap">{esc(cap)}</div></div>'


def fig_block(f: dict, run_dir: Path) -> str:
    """One figure — a single view of the shared computation: its plan and result."""
    obs = f.get("observe", {})
    res = f.get("results") or {}
    head = " — ".join(p for p in (esc(f.get("id")), mathify(f.get("plots"))) if p)
    plan = kv(("x-axis", f.get("x")), ("y-axis", f.get("y")),
              ("Observable", obs.get("quantity")),
              ("Normalization", obs.get("normalization")),
              ("States used", obs.get("states")))
    expected = (f'<div class="expected"><b>What we expect:</b> {mathify(f["expected"])}</div>'
                if f.get("expected") else "")

    # figure grid: the paper's panel (the target) always when given; ours alongside once run
    ours = run_dir / res["figure"] if res.get("figure") else None
    figs, missing = [], ""
    if f.get("paper_image"):
        paper_img = run_dir / f["paper_image"]
        if paper_img.exists():
            figs.append(figbox(data_uri(paper_img), "From the paper"))
        else:
            missing = (f'<p class="note">Paper panel not embedded — '
                       f'<code>{esc(f["paper_image"])}</code> not found.</p>')
    if ours and ours.exists():
        figs.append(figbox(data_uri(ours), "Our reproduction"))
    figs_html = (f'<div class="figs">{"".join(figs)}</div>' if figs else "") + missing

    done = bool(res.get("figure") or res.get("match") or res.get("numbers"))
    if done:
        verdict_map = {"yes": ("Reproduced", "good"), "partly": ("Partial match", "warn"),
                       "no": ("Did not match", "bad")}
        label, cls = verdict_map.get(str(res.get("match", "")).lower(), ("Result", "warn"))
        verdict = (f'<div class="verdict {cls}"><span class="label">{label}</span>'
                   f'<span class="why">{mathify(res.get("why"))}</span></div>')
        numbers = res.get("numbers") or {}
        if isinstance(numbers, dict) and numbers:
            rows = "".join(f'<tr><td>{mathify(k)}</td><td class="num">{esc(v)}</td></tr>' for k, v in numbers.items())
            num_html = f'<table><thead><tr><th>Quantity</th><th>Value</th></tr></thead><tbody>{rows}</tbody></table>'
        else:
            num_html = ""
        changes = res.get("changes") or []
        ran = kv(("Wall time", res.get("wall")),
                 ("Changes from plan", "; ".join(changes) if changes else "none"))
        rerun = (f'<div class="card"><div class="title">Rerun</div><pre style="margin:6px 0 0;font-size:12.5px;overflow-x:auto"><code>{esc(res.get("rerun"))}</code></pre></div>'
                 if res.get("rerun") else "")
        body = verdict + figs_html + num_html + card("What actually ran", ran) + rerun
    else:
        body = figs_html + ('<div class="pending">Results pending — our figure, the key '
                            'numbers, and the matched / partly / didn\'t read appear here '
                            'after the approved run.</div>')
    return f'<div class="figblock"><h3>{head}</h3>{plan}{expected}{body}</div>'


def render(run: dict, run_dir: Path) -> str:
    paper = run.get("paper", {})
    model = run.get("model", {})
    meth = run.get("method", {})
    scope = run.get("scope", {})
    est = run.get("estimate") or []
    figures = run.get("figures") or []

    title = paper.get("title") or paper.get("id", "Reproduction")
    url = paper.get("url")
    sub = f'<p class="sub"><a href="{esc(url)}">{esc(url)}</a></p>' if url else ""
    fig_ids = ", ".join(esc(f.get("id")) for f in figures if f.get("id"))
    of_model = f' of the {mathify(model.get("name"))}' if model.get("name") else ""
    lede = (f'<p class="lede"><b>Reproducing:</b> {fig_ids}{of_model}.</p>'
            if fig_ids else "")
    header = (
        '<header class="hero">'
        f'<div class="eyebrow">{esc(paper.get("id", "reproduction"))}</div>'
        f'<h1>{esc(title)}</h1>{sub}{lede}'
        '</header>'
    )

    # ── Model ──────────────────────────────────────────────────────────────
    eq = (f'<div class="eq">{_mathml(model["H"], display=True)}</div>'
          if model.get("H") else "")
    model_card = card("Hamiltonian", eq + kv(
        ("Name", model.get("name")), ("Couplings", fmt_map(model.get("couplings"))),
        ("Lattice", model.get("lattice")), ("Boundary", model.get("boundary"))))
    model_sec = (f'<section><h2>Model</h2>'
                 f'<p class="note">The physical system — shared by every figure below.</p>'
                 f'{model_card}</section>')

    # ── Method ─────────────────────────────────────────────────────────────
    exact = meth.get("exact")
    pill = ('<span class="pill exact">exact</span>' if exact is True
            else '<span class="pill approx">approximation</span>' if exact is False else "")
    meth_note = (f'<p class="note" style="margin:8px 0 0">{mathify(meth.get("note"))}</p>'
                 if meth.get("note") else "")
    method_card = card("Approach",
                       (f'<div style="margin:2px 0 8px">{pill}</div>' if pill else "")
                       + kv(("Method", meth.get("family")), ("Tool", meth.get("tool")),
                            ("Settings", fmt_map(meth.get("settings")))) + meth_note)
    cost_rows = "".join(
        f'<tr><td>{mathify(e.get("point"))}</td>'
        f'<td class="num">{esc(e.get("wall"))}</td>'
        f'<td class="num">{esc(e.get("memory"))}</td></tr>'
        for e in est)
    cost = ('<table><thead><tr><th>Run point</th><th>Est. wall time</th>'
            f'<th>Est. memory</th></tr></thead><tbody>{cost_rows}</tbody></table>') if cost_rows else ""
    scope_line = " · ".join(p for p in (
        f'Scope: {esc(scope.get("label"))}' if scope.get("label") else "",
        f'Runs: {esc(run.get("where"))}' if run.get("where") else "") if p)
    scope_html = f'<p class="note">{scope_line}</p>' if scope_line else ""
    risks = run.get("risks") or []
    risk_html = ('<div class="card"><div class="title">Anticipated rough spots</div><ul class="flat">'
                 + "".join(f"<li>{mathify(r)}</li>" for r in risks) + "</ul></div>") if risks else ""
    method_sec = (f'<section><h2>Method</h2>'
                  f'<p class="note">One computation, shared by every figure — and what it should cost.</p>'
                  f'{method_card}{cost}{scope_html}{risk_html}</section>')

    # ── Figures (each a single view of the one computation above) ────────────
    blocks = "".join(fig_block(f, run_dir) for f in figures)
    figures_sec = (f'<section><h2>Figures</h2>'
                   f'<p class="note">Each figure is one view of the computation above — its plan, then its result.</p>'
                   f'{blocks}</section>') if blocks else ""

    footer = (f'<div class="footer">Generated {date.today().isoformat()}. '
              'Built from <code>run.json</code> — the single source of data. '
              'Single file, no external assets, opens offline.</div>')

    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{esc(title)}</title><style>{STYLE}</style></head><body>'
            f'<button class="print-btn" onclick="window.print()">Save as PDF</button>'
            f'<main class="wrap">{header}{model_sec}{method_sec}{figures_sec}{footer}</main></body></html>\n')


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python3 render_report.py <run-dir>")
    run_dir = Path(sys.argv[1]).resolve()
    run = json.loads((run_dir / "run.json").read_text())
    out = run_dir / "report.html"
    out.write_text(render(run, run_dir))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

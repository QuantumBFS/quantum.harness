#!/usr/bin/env python3
"""Render a generic report document into a standalone <run-dir>/report.html.

    python3 skills/report/render_report.py <run-dir>

Reads <run-dir>/report.json and writes <run-dir>/report.html — a fully
self-contained page: inline CSS, each figure base64-embedded, equations as
inline MathML. No external assets, no network, no build step; it opens offline
like a PDF.

report.json is a generic document, not tied to any one kind of report:

    { "title": "…", "eyebrow": "…", "url": "…", "lede": "…",
      "sections": [ { "title": "…", "note": "…", "blocks": [ … ] } ] }

Each block is one piece carrying a "kind": heading, text, equation, kv, table,
figures, verdict, list, code, badge, note, or card (which nests blocks).
Producers (e.g. /reproduce-paper) own the document's shape; this file only
draws whatever pieces it is handed, in order.

Math convention:
  - an `equation` block's `tex` is a LaTeX equation (no delimiters), display math.
  - any string may carry inline LaTeX in $…$ (or display in $$…$$).
  - any string may carry **bold** (→ <strong>) and ==highlight== (→ <mark>) spans for keypoints.
The LaTeX→MathML converter below is stdlib-only and covers the physics subset
(sub/superscripts, groups, \\frac, \\sqrt, sums/products/integrals with limits,
Greek, \\mathbf/\\vec, common operators). Unknown commands render literally.
"""
import base64
import html
import json
import re
import sys
import urllib.parse
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
_EMPH = re.compile(r"\*\*(.+?)\*\*")
_MARK = re.compile(r"==(.+?)==")


def _emph(escaped):
    """Render ==highlight== and **bold** spans in escaped, math-free text."""
    s = _MARK.sub(r"<mark>\1</mark>", escaped)
    return _EMPH.sub(r"<strong>\1</strong>", s)


def mathify(x):
    """Escape text, converting $…$ / $$…$$ to MathML and **…** to <strong>."""
    if x is None:
        return ""
    s, out, last = str(x), [], 0
    for m in _MATH.finditer(s):
        out.append(_emph(esc(s[last:m.start()])))
        disp = m.group(1) is not None
        out.append(_mathml(m.group(1) if disp else m.group(2), display=disp))
        last = m.end()
    out.append(_emph(esc(s[last:])))
    return "".join(out)


# ── palette + components, lifted from docs/ed/review.html ──────────────────
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
mark{background:#fde68a;color:var(--ink);padding:1px 5px;border-radius:3px;font-weight:600;box-decoration-break:clone;-webkit-box-decoration-break:clone}
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
section h3{font-family:var(--serif);font-size:18px;margin:22px 0 6px;border-top:1px solid var(--line);padding-top:14px}
.para{font-size:14px;margin:10px 0;max-width:72ch}
.card{background:var(--panel);border:1px solid var(--line);border-radius:6px;padding:13px 16px;margin:10px 0}
.card .title{font-family:var(--serif);font-size:15px;font-weight:600;margin-bottom:2px}
.eq{text-align:center;margin:6px 0 12px;padding:6px 0;overflow-x:auto}
.kv{display:grid;grid-template-columns:150px minmax(0,1fr);gap:4px 14px;font-size:13.5px;margin-top:6px}
.kv .k{color:var(--muted)} .kv .v{color:#1a1a1a}
table{width:100%;border-collapse:collapse;font-size:13.5px;background:var(--panel);border:1px solid var(--line);border-radius:6px;overflow:hidden;margin:8px 0}
thead th{background:#f7f5ed;text-align:left;padding:9px 11px;font-weight:600;border-bottom:1px solid var(--line)}
tbody td{padding:9px 11px;border-top:1px solid var(--line);vertical-align:top}
tbody tr:hover{background:#faf9f4}
td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
td.muted{color:var(--muted);font-size:.92em}
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
.pending{padding:14px 16px;border:1px dashed var(--line);border-radius:6px;color:var(--muted);font-size:14px;background:#faf8f2}
.toc{position:fixed;top:118px;left:calc(50% - 608px);width:152px;max-height:72vh;overflow:auto;font-size:12.5px;line-height:1.4}
.toc .lbl{text-transform:uppercase;letter-spacing:.07em;font-size:10px;color:var(--muted);font-weight:700;margin-bottom:9px}
.toc a{display:block;color:var(--muted);padding:4px 0 4px 12px;border-left:2px solid var(--line);border-bottom:none}
.toc a:hover{color:var(--ink)}
.toc a.on{color:var(--accent);border-left-color:var(--accent);font-weight:600}
.toc-bar{display:none}
@media(max-width:1299px){
  .toc{display:none}
  .toc-bar{display:flex;gap:7px;overflow-x:auto;margin:20px 0 0;padding-bottom:2px}
  .toc-bar a{white-space:nowrap;font-size:12px;padding:5px 12px;border:1px solid var(--line);border-radius:999px;color:var(--muted);background:var(--panel)}
  .toc-bar a:hover{color:var(--ink)}
  .toc-bar a.on{color:var(--accent);border-color:#bcd2f5;background:var(--accent-soft);font-weight:600}
}
.footer{margin-top:56px;padding-top:18px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
.print-btn{position:fixed;top:16px;right:18px;font-family:var(--sans);font-size:12.5px;padding:7px 12px;border:1px solid var(--line);background:#fff;color:var(--ink);border-radius:5px;cursor:pointer}
.print-btn:hover{border-color:var(--accent);color:var(--accent)}
@media print{.print-btn,.toc,.toc-bar{display:none}.wrap{max-width:100%;padding:0}.figs{position:static;left:auto;transform:none;width:auto}.card,table,.verdict,.figbox{break-inside:avoid}}
"""

MIME = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "svg": "image/svg+xml", "webp": "image/webp", "gif": "image/gif"}


def esc(x):
    return html.escape("" if x is None else str(x))


def _slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return s or "section"


def data_uri(path: Path) -> str:
    mime = MIME.get(path.suffix.lower().lstrip("."), "application/octet-stream")
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def kv(*pairs) -> str:
    rows = "".join(
        f'<div class="k">{mathify(k)}</div><div class="v">{mathify(v)}</div>'
        for k, v in pairs if v not in (None, "", [], {})
    )
    return f'<div class="kv">{rows}</div>' if rows else ""


def figbox(src: str, cap: str) -> str:
    return f'<div class="figbox"><img src="{src}" alt="{esc(cap)}"><div class="cap">{mathify(cap)}</div></div>'


def figures_row(items, base_dir: Path) -> str:
    base = base_dir.resolve()
    figs, missing = [], ""
    for it in items:
        src = it.get("src")
        if not src:
            continue
        p = (base_dir / src).resolve()
        if p.is_relative_to(base) and p.is_file():       # contained in the run dir, no traversal, a real file
            figs.append(figbox(data_uri(p), it.get("caption", "")))
        else:
            missing += (f'<p class="note">Image not embedded — '
                        f'<code>{esc(src)}</code> not found.</p>')
    return (f'<div class="figs">{"".join(figs)}</div>' if figs else "") + missing


def block(b: dict, base_dir: Path) -> str:
    """Render one piece. Unknown kinds are skipped."""
    k = b.get("kind")
    if k == "heading":
        lvl = b.get("level", 3)
        lvl = lvl if isinstance(lvl, int) and 1 <= lvl <= 6 else 3
        return f"<h{lvl}>{mathify(b.get('text'))}</h{lvl}>"
    if k == "text":
        return f'<p class="para">{mathify(b.get("text"))}</p>'
    if k == "equation":
        return f'<div class="eq">{_mathml(b.get("tex", ""), display=True)}</div>'
    if k == "kv":
        pairs = b.get("pairs", [])
        pairs = list(pairs.items()) if isinstance(pairs, dict) else pairs
        return kv(*[(p[0], p[1]) for p in pairs])
    if k == "table":
        cols = b.get("columns", [])
        num = b.get("numeric") or []
        muted = b.get("muted") or []                      # per-column: render as a recessed citation
        widths = b.get("widths") or []                    # per-column CSS widths via <colgroup>
        group = ("<colgroup>" + "".join(f'<col style="width:{w}">' if w else "<col>"
                                        for w in widths) + "</colgroup>") if widths else ""
        head = "".join(f"<th>{mathify(c)}</th>" for c in cols)
        body = ""
        for r in b.get("rows", []):
            cells = ""
            for i, v in enumerate(r):
                cls = (("num " if i < len(num) and num[i] else "")
                       + ("muted" if i < len(muted) and muted[i] else "")).strip()
                cells += f'<td class="{cls}">{mathify(v)}</td>' if cls else f"<td>{mathify(v)}</td>"
            body += f"<tr>{cells}</tr>"
        return (f"<table>{group}<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
                if cols or body else "")
    if k == "figures":
        return figures_row(b.get("items", []), base_dir)
    if k == "verdict":
        cls = b.get("status") if b.get("status") in ("good", "warn", "bad") else "warn"
        return (f'<div class="verdict {cls}"><span class="label">{mathify(b.get("label"))}</span>'
                f'<span class="why">{mathify(b.get("why"))}</span></div>')
    if k == "list":
        items = "".join(f"<li>{mathify(x)}</li>" for x in b.get("items", []))
        if not items:
            return ""
        title = b.get("title")
        return (f'<div class="card"><div class="title">{mathify(title)}</div>'
                f'<ul class="flat">{items}</ul></div>' if title
                else f'<ul class="flat">{items}</ul>')
    if k == "code":
        pre = (f'<pre style="margin:6px 0 0;font-size:12.5px;overflow-x:auto">'
               f'<code>{esc(b.get("text"))}</code></pre>')
        title = b.get("title")
        return (f'<div class="card"><div class="title">{mathify(title)}</div>{pre}</div>'
                if title else f'<div class="card">{pre}</div>')
    if k == "badge":
        style = {"good": "pill exact", "warn": "pill approx"}.get(b.get("style"), "pill")
        return f'<div style="margin:2px 0 8px"><span class="{style}">{mathify(b.get("text"))}</span></div>'
    if k == "note":
        if b.get("style") == "pending":
            return f'<div class="pending">{mathify(b.get("text"))}</div>'
        lead = f'<b>{mathify(b.get("label"))}</b> ' if b.get("label") else ""
        return f'<div class="expected">{lead}{mathify(b.get("text"))}</div>'
    if k == "card":
        inner = "".join(block(c, base_dir) for c in b.get("blocks", []))
        title = f'<div class="title">{mathify(b["title"])}</div>' if b.get("title") else ""
        return f'<div class="card">{title}{inner}</div>' if title or inner else ""
    return ""


def section(s: dict, base_dir: Path, sid: str = None) -> str:
    head = f'<h2>{mathify(s.get("title"))}</h2>' if s.get("title") else ""
    note = f'<p class="note">{mathify(s["note"])}</p>' if s.get("note") else ""
    body = "".join(block(b, base_dir) for b in s.get("blocks", []))
    idattr = f' id="{sid}"' if sid else ""
    return f"<section{idattr}>{head}{note}{body}</section>" if head or note or body else ""


def render(doc: dict, base_dir: Path) -> str:
    title = doc.get("title", "Report")
    eyebrow = f'<div class="eyebrow">{mathify(doc["eyebrow"])}</div>' if doc.get("eyebrow") else ""
    url = doc.get("url")
    if url and urllib.parse.urlparse(url).scheme.lower() in ("http", "https", "mailto"):
        sub = f'<p class="sub"><a href="{esc(url)}">{esc(url)}</a></p>'
    elif url:                                            # unsafe/relative scheme: show as plain text, no live href
        sub = f'<p class="sub">{esc(url)}</p>'
    elif doc.get("subtitle"):
        sub = f'<p class="sub">{mathify(doc["subtitle"])}</p>'
    else:
        sub = ""
    lede = f'<p class="lede">{mathify(doc["lede"])}</p>' if doc.get("lede") else ""
    header = f'<header class="hero">{eyebrow}<h1>{mathify(title)}</h1>{sub}{lede}</header>'
    secs = doc.get("sections", [])
    slugs, seen = [], {}                                 # unique anchor slug per titled section
    for s in secs:
        if not s.get("title"):
            slugs.append(None)
            continue
        sl = _slug(s["title"])
        seen[sl] = seen.get(sl, 0) + 1
        slugs.append(sl if seen[sl] == 1 else f"{sl}-{seen[sl]}")
    body = "".join(section(s, base_dir, sl) for s, sl in zip(secs, slugs))
    nav_items = [(s.get("title"), sl) for s, sl in zip(secs, slugs) if sl]
    if len(nav_items) >= 2:                              # in-page nav: left rail + chip-bar + scroll-spy
        links = "".join(f'<a href="#{sl}">{esc(t)}</a>' for t, sl in nav_items)
        rail = f'<nav class="toc"><div class="lbl">Contents</div>{links}</nav>'
        bar = f'<nav class="toc-bar">{links}</nav>'
        spy = ("<script>(function(){var L=[].slice.call("
               "document.querySelectorAll('.toc a,.toc-bar a'));if(!L.length)return;"
               "var m={};L.forEach(function(a){var i=a.getAttribute('href').slice(1);"
               "(m[i]=m[i]||[]).push(a)});var o=new IntersectionObserver(function(es){"
               "es.forEach(function(e){if(e.isIntersecting){"
               "L.forEach(function(a){a.classList.remove('on')});"
               "(m[e.target.id]||[]).forEach(function(a){a.classList.add('on')})}})},"
               "{rootMargin:'-12% 0px -78% 0px'});"
               "document.querySelectorAll('section[id]').forEach(function(s){o.observe(s)});})();</script>")
    else:
        rail = bar = spy = ""
    footer = (f'<div class="footer">Generated {date.today().isoformat()}. '
              'Single file, no external assets, opens offline.</div>')
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{esc(title)}</title><style>{STYLE}</style></head><body>'
            f'<button class="print-btn" onclick="window.print()">Save as PDF</button>'
            f'<main class="wrap">{rail}{header}{bar}{body}{footer}</main>{spy}</body></html>\n')


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python3 skills/report/render_report.py <run-dir>")
    run_dir = Path(sys.argv[1]).resolve()
    doc = json.loads((run_dir / "report.json").read_text())
    out = run_dir / "report.html"
    out.write_text(render(doc, run_dir))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

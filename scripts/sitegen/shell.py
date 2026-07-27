"""Shared page shell for the catalog pages: CSS, nav, filter JS, page frame.

One dark theme, one sticky filter bar, one expandable-rows interaction for
all three catalogs. The JS filter is generic: it reads every chip's
data-group and matches against the row's data-<group> attribute, so each
catalog page only declares its own chip groups.

Row contract: each .model row carries data-name / data-hook / data-extra
(extra = all other searchable text) plus one data-<group> attribute per
chip group the page declares (space-separated tokens).
"""
from __future__ import annotations

from . import parse

NAV = [("index.html", "Home"), ("solvable.html", "Solvable"),
       ("models.html", "Models"), ("methods.html", "Methods"),
       ("benchmarks.html", "Benchmarks")]

KATEX_HEAD = """\
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>"""

CSS = """\
  :root{
    --bg:#0f1117; --panel:#171a23; --panel2:#1d2130; --ink:#e7e9ee; --mut:#9aa3b2;
    --line:#2a2f3d; --accent:#7c6cff; --accent2:#22c1a6; --warn:#e0a458;
    --user:#7aa2ff; --ok:#4cc38a;
    --mono:"SFMono-Regular",Consolas,"Liberation Mono",Menlo,monospace;
    --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
       line-height:1.55;-webkit-font-smoothing:antialiased}
  ::selection{background:var(--accent);color:#fff}
  a{color:var(--accent2);text-decoration:none}
  a:hover{text-decoration:underline}
  .wrap{max-width:980px;margin:0 auto;padding:0 22px}
  .wrap.wide{max-width:1560px}

  /* ---- shared top nav ---- */
  .topnav{display:flex;justify-content:space-between;align-items:baseline;gap:12px;
    padding:14px 0 0;font-family:var(--mono);font-size:.78rem}
  .topnav .brand{color:var(--mut)}
  .topnav .links a{color:var(--mut);margin-left:14px}
  .topnav .links a:hover{color:var(--ink);text-decoration:none}
  .topnav .links a.here{color:var(--accent);font-weight:700}

  header{padding:38px 0 22px;border-bottom:1px solid var(--line)}
  .kicker{color:var(--accent);font-weight:700;letter-spacing:.12em;text-transform:uppercase;
          font-size:.74rem;margin-bottom:10px}
  h1{font-size:2.15rem;margin:.1em 0 .35em;line-height:1.15}
  .lead{color:var(--mut);font-size:1.08rem;max-width:74ch;margin:.2em 0 0}

  /* ---- sticky filter bar ---- */
  .filterbar{position:sticky;top:0;z-index:10;background:var(--bg);
    border-bottom:1px solid var(--line);padding:12px 0 10px}
  .fb-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
  #q{flex:1 1 200px;min-width:0;background:var(--panel);border:1px solid var(--line);
    border-radius:8px;color:var(--ink);font-family:var(--mono);font-size:.84rem;
    padding:7px 11px}
  #q::placeholder{color:var(--mut)}
  #q:focus{outline:none;border-color:var(--accent)}
  #count{font-family:var(--mono);font-size:.78rem;color:var(--mut);white-space:nowrap}
  .fb-chips{display:flex;gap:14px 18px;flex-wrap:wrap;margin-top:9px}
  .cgroup{display:flex;align-items:center;gap:5px;flex-wrap:wrap}
  .clabel{font-size:.68rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
    color:var(--mut);margin-right:2px}
  .chip{appearance:none;cursor:pointer;background:transparent;color:var(--mut);
    border:1px solid var(--line);border-radius:999px;font-family:var(--mono);
    font-size:.74rem;padding:2px 9px;transition:color .15s,border-color .15s}
  .chip:hover{color:var(--ink);border-color:var(--mut)}
  .chip[aria-pressed="true"]{color:var(--accent);border-color:var(--accent)}
  .chip:focus-visible,summary:focus-visible,#q:focus-visible,.cardlinks a:focus-visible{
    outline:2px solid var(--accent);outline-offset:2px}

  /* ---- catalog sections ---- */
  section.tgroup{padding:30px 0 6px;border-bottom:1px solid var(--line)}
  section.tgroup:last-of-type{border-bottom:none}
  h2{font-size:1.3rem;margin:0;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
  .tcode{font-family:var(--mono);color:var(--accent);font-size:1.02rem}
  .scount{font-family:var(--mono);font-size:.76rem;color:var(--mut);font-weight:400;
    border:1px solid var(--line);border-radius:999px;padding:1px 9px}
  .tsub{color:var(--mut);font-size:.88rem;margin:.4em 0 14px;max-width:78ch}

  /* ---- rows ---- */
  .model{border:1px solid var(--line);border-radius:10px;margin:0 0 8px;
    background:rgba(23,26,35,.5)}
  .model summary,.model.ghost>.grow{display:flex;align-items:baseline;gap:10px;
    flex-wrap:wrap;padding:9px 14px}
  .model summary{cursor:pointer;list-style:none}
  .model summary::-webkit-details-marker{display:none}
  .model summary::before{content:"\\25B8";color:var(--accent);flex:none;
    display:inline-block;transition:transform .15s ease}
  .model[open]>summary::before{transform:rotate(90deg)}
  .model.ghost>.grow::before{content:"\\25B8";color:transparent;flex:none}
  .mname{font-family:var(--mono);font-size:.86rem;font-weight:700}
  .model summary:hover .mname{color:var(--accent2)}
  .hook{color:var(--mut);font-size:.8rem;flex:1 1 auto;min-width:0}
  .bset{display:flex;gap:5px;flex:none;margin-left:auto}
  .b{font-family:var(--mono);font-size:.68rem;letter-spacing:.04em;color:var(--mut);
    border:1px solid var(--line);border-radius:999px;padding:1px 8px;white-space:nowrap}
  .b-ok{color:var(--ok);border-color:rgba(76,195,138,.45)}
  .b-warn{color:var(--warn);border-color:rgba(224,164,88,.45)}
  .b-dim{opacity:.75}
  .model.ghost{opacity:.45}
  .model[hidden]{display:none}

  /* ---- expanded body ---- */
  .mbody{border-top:1px solid var(--line);padding:14px 16px 16px}
  .mbody h3{font-size:.74rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
    color:var(--mut);margin:16px 0 4px}
  .mbody ul{margin:.2em 0 0;padding-left:20px;font-size:.88rem;color:var(--ink)}
  .mbody li{margin:2px 0}
  .math{background:#0b0d13;border:1px solid var(--line);border-radius:10px;
    padding:12px 14px;overflow-x:auto;font-size:.95rem}
  .solv{color:var(--mut);font-size:.88rem;max-width:78ch;margin:14px 0 0}
  .tablewrap{overflow-x:auto;margin-top:14px}
  table.bench{width:100%;border-collapse:collapse;font-size:.82rem}
  table.bench th,table.bench td{border-bottom:1px solid var(--line);padding:6px 10px;
    text-align:left;vertical-align:top;white-space:nowrap}
  table.bench td:last-child,table.bench td:nth-child(2){white-space:normal}
  table.bench th{color:var(--ink)}
  table.bench code,.cardlinks{font-family:var(--mono);font-size:.9em;color:var(--accent2)}
  table.bench .unit{color:var(--mut);font-size:.92em}
  table.matrix{font-size:.78rem}
  table.matrix th,table.matrix td{padding:6px 8px}
  table.matrix td{white-space:nowrap}
  table.matrix code{color:inherit}
  table.matrix .err{color:var(--mut)}
  .cardlinks{margin:14px 0 0;font-size:.78rem;display:flex;gap:16px}

  footer{padding:30px 0 60px;color:var(--mut);font-size:.85rem}"""

FILTER_JS = """\
(function () {
  var q = document.getElementById('q');
  var count = document.getElementById('count');
  var chips = Array.prototype.slice.call(document.querySelectorAll('.chip'));
  var models = Array.prototype.slice.call(document.querySelectorAll('.model'));
  var sections = Array.prototype.slice.call(document.querySelectorAll('section.tgroup'));
  var total = models.length;

  function picked() {
    var groups = {};
    chips.forEach(function (c) {
      if (c.getAttribute('aria-pressed') === 'true') {
        (groups[c.dataset.group] = groups[c.dataset.group] || []).push(c.dataset.val);
      }
    });
    return groups;
  }

  function apply() {
    var needle = q.value.trim().toLowerCase();
    var groups = picked();
    var shown = 0;
    models.forEach(function (m) {
      var d = m.dataset, ok = true;
      if (needle) {
        var hay = (d.name + ' ' + (d.hook || '') + ' ' + (d.extra || '')).toLowerCase();
        ok = hay.indexOf(needle) !== -1;
      }
      Object.keys(groups).forEach(function (g) {
        if (!ok) return;
        var vals = (d[g] || '').split(' ');
        ok = groups[g].some(function (v) { return vals.indexOf(v) !== -1; });
      });
      if (ok) shown++; else if (m.open) m.open = false;
      if (ok) m.removeAttribute('hidden'); else m.setAttribute('hidden', '');
    });
    sections.forEach(function (s) {
      var vis = s.querySelectorAll('.model:not([hidden])').length;
      var badge = s.querySelector('.scount');
      badge.textContent = vis === +badge.dataset.total ? badge.dataset.total
                        : vis + ' of ' + badge.dataset.total;
      if (vis === 0) s.setAttribute('hidden', ''); else s.removeAttribute('hidden');
    });
    count.textContent = shown + ' of ' + total;
  }

  chips.forEach(function (c) {
    c.addEventListener('click', function () {
      c.setAttribute('aria-pressed',
        c.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');
      apply();
    });
  });
  q.addEventListener('input', apply);

  document.addEventListener('DOMContentLoaded', function () {
    if (window.renderMathInElement) {
      renderMathInElement(document.body, {
        delimiters: [{left: '$$', right: '$$', display: true}],
        throwOnError: false
      });
    }
  });
})();"""


def nav(here: str) -> str:
    """Shared top-nav; `here` is the current page's filename."""
    links = []
    for href, label in NAV:
        cls = ' class="here"' if href == here else ""
        links.append(f'<a href="{href}"{cls}>{label}</a>')
    return ('<nav class="topnav"><span class="brand">quantum.harness</span>'
            f'<span class="links">{" ".join(links)}</span></nav>')


def chips(group: str, values, titles=None) -> str:
    """Filter-bar chip buttons for one group."""
    out = []
    for v in values:
        t = f' title="{parse.esc(titles[v])}"' if titles and v in titles else ""
        out.append(f'<button class="chip" type="button" data-group="{parse.esc(group)}"'
                   f' data-val="{parse.esc(v)}" aria-pressed="false"{t}>{parse.esc(v)}</button>')
    return "".join(out)


def page(*, title: str, lead: str, total: int, chips_html: str, sections_html: str,
         footer_html: str, here: str, search_placeholder: str,
         filterbar: bool = True, wide: bool = False) -> str:
    """Assemble a full catalog page from its parts.

    All interpolated args are trusted HTML — escape card-derived text with
    parse.esc / parse.md_inline upstream. filterbar=False drops the search
    bar, chips, and filter JS for static pages.
    """
    fb = f'''<div class="filterbar">
  <div class="fb-row">
    <input id="q" type="search" placeholder="{search_placeholder}" aria-label="Search">
    <span id="count">{total} of {total}</span>
  </div>
  <div class="fb-chips">
{chips_html}
  </div>
</div>

''' if filterbar else ""
    js = f"<script>\n{FILTER_JS}\n</script>\n" if filterbar else ""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Quantum Many-Body Harness</title>
{KATEX_HEAD}
<style>
{CSS}
</style>
</head>
<body>
<div class="wrap{" wide" if wide else ""}">

{nav(here)}

<header>
  <div class="kicker">Quantum Many-Body Harness</div>
  <h1>{title}</h1>
  <p class="lead">{lead}</p>
</header>

{fb}{sections_html}

<footer>
{footer_html}
</footer>

</div>
{js}</body>
</html>
'''

#!/usr/bin/env python3
# make_figs.py — F2 (R_cost curves) and F3 (T1 frontier) as dependency-free
# SVG, generated ONLY from frozen CSVs. F1 is a mermaid diagram inside
# SYNTHESIS_REPORT.md. Run from its-a-trap/ root:  python3 figs/make_figs.py
import csv, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RS = os.path.join(ROOT, 'rg_selection')

def read_csv(p):
    with open(p) as f: return list(csv.DictReader(f))

# ---------- data: structural ratios ----------
db = {(r['N'], r['arm']): r for r in read_csv(f'{RS}/direct/build_costs.csv')}
rb = {}
for r in read_csv(f'{RS}/results/replacement_build.csv'):
    if r['psd_scalars']: rb[(r['N'], r['arm'])] = r
ds0 = {(r['N'], r['arm']): r for r in read_csv(f'{RS}/direct/solve_results.csv') if r['status'] == 'OPTIMAL'}
def Cpsd(N):   # build row if present, else the solve row's scalarized (same count)
    k = (str(N), 'C')
    return float(db[k]['psd_scalars']) if k in db else float(ds0[k]['scalarized'])
A = lambda N: float(rb[(str(N), 'A')]['psd_scalars']) if (str(N), 'A') in rb else float(db[(str(N), 'A')]['psd_scalars'])
direct_struct = [(N, Cpsd(N) / A(N), N in (26, 30))
                 for N in (10, 12, 14, 20, 26, 30)]
addi_struct = [(N, float(rb[(str(N), 'C6')]['psd_scalars']) / A(N), N in (26, 30))
               for N in (14, 20, 26, 30)]
ds = {(r['N'], r['arm']): r for r in read_csv(f'{RS}/direct/solve_results.csv') if r['status'] == 'OPTIMAL'}
rs_ = {(r['N'], r['arm']): r for r in read_csv(f'{RS}/results/replacement_solve.csv') if r.get('status') == 'OPTIMAL'}
def solveA(N):
    return rs_[(str(N), 'A')] if (str(N), 'A') in rs_ else ds[(str(N), 'A')]
wall = [(N, float(ds[(str(N), 'C')]['wall_s']) / float(solveA(N)['wall_s'])) for N in (10, 12, 14, 20)]
rssr = [(N, float(ds[(str(N), 'C')]['rss_gb']) / float(solveA(N)['rss_gb'])) for N in (10, 12, 14, 20)]

# ---------- data: T1 frontier ----------
t1, t1r9 = [], None
with open(os.path.join(ROOT, 'freeze', 'MASTER.csv')) as f:
    for r in csv.DictReader(f):
        if r.get('label', '').startswith('v') and r.get('gap_ref') and r.get('label') not in ('v14', 'v14fp'):
            try:
                N = int(r['N']); g = float(r['gap_ref'])
            except ValueError:
                continue
            if r['label'] == 'v100e8': t1r9 = (N, g)
            elif N >= 50 and r['label'] == f'v{N}': t1.append((N, g))
t1 = sorted(set(t1))

# ---------- tiny SVG plotting ----------
def svg_plot(fname, title, series, xlab, ylab, ylog=False, hline=None):
    W, H, ML, MB, MT, MR = 640, 400, 70, 50, 40, 20
    xs = [x for s in series for (x, y, *_) in s['pts']]
    ys = [y for s in series for (x, y, *_) in s['pts']]
    if hline is not None: ys.append(hline)
    import math
    x0, x1 = min(xs), max(xs)
    ty = (lambda v: math.log10(v)) if ylog else (lambda v: v)
    y0, y1 = min(map(ty, ys)) * 0.98, max(map(ty, ys)) * 1.05
    X = lambda x: ML + (x - x0) / (x1 - x0) * (W - ML - MR)
    Y = lambda y: H - MB - (ty(y) - y0) / (y1 - y0) * (H - MB - MT)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif" font-size="12">',
           f'<rect width="{W}" height="{H}" fill="white"/>',
           f'<text x="{W/2}" y="20" text-anchor="middle" font-size="14">{title}</text>']
    out.append(f'<line x1="{ML}" y1="{H-MB}" x2="{W-MR}" y2="{H-MB}" stroke="black"/>')
    out.append(f'<line x1="{ML}" y1="{MT}" x2="{ML}" y2="{H-MB}" stroke="black"/>')
    for x in sorted(set(xs)):
        out.append(f'<text x="{X(x)}" y="{H-MB+18}" text-anchor="middle">{x}</text>')
    yticks = [y0 + i * (y1 - y0) / 5 for i in range(6)]
    for v in yticks:
        lab = f'{10**v:.2g}' if ylog else f'{v:.2f}'
        yy = H - MB - (v - y0) / (y1 - y0) * (H - MB - MT)
        out.append(f'<text x="{ML-8}" y="{yy+4}" text-anchor="end">{lab}</text>')
        out.append(f'<line x1="{ML}" y1="{yy}" x2="{W-MR}" y2="{yy}" stroke="#eee"/>')
    if hline is not None:
        out.append(f'<line x1="{ML}" y1="{Y(hline)}" x2="{W-MR}" y2="{Y(hline)}" stroke="red" stroke-dasharray="6,3"/>')
        out.append(f'<text x="{W-MR-4}" y="{Y(hline)-5}" text-anchor="end" fill="red">{hline:g}</text>')
    for i, s in enumerate(series):
        pts = s['pts']
        path = ' '.join(f'{"M" if j == 0 else "L"}{X(p[0]):.1f},{Y(p[1]):.1f}' for j, p in enumerate(pts))
        out.append(f'<path d="{path}" fill="none" stroke="{s["color"]}" stroke-width="2" {s.get("dash","")}/>')
        for p in pts:
            hollow = len(p) > 2 and p[2]
            fill = 'white' if hollow else s['color']
            out.append(f'<circle cx="{X(p[0]):.1f}" cy="{Y(p[1]):.1f}" r="5" fill="{fill}" stroke="{s["color"]}" stroke-width="2"/>')
        out.append(f'<text x="{ML+10}" y="{MT+16*(i+1)}" fill="{s["color"]}">{s["label"]}</text>')
    out.append(f'<text x="{W/2}" y="{H-8}" text-anchor="middle">{xlab}</text>')
    out.append(f'<text x="16" y="{H/2}" transform="rotate(-90 16 {H/2})" text-anchor="middle">{ylab}</text>')
    out.append('</svg>')
    open(os.path.join(ROOT, 'figs', fname), 'w').write('\n'.join(out))
    print('wrote', fname)

svg_plot('F2_rcost.svg',
    'F2 — R_cost(N): structural (hollow = build-only) and realized (solved sizes)',
    [{'pts': direct_struct, 'color': '#1f77b4', 'label': 'Direct D=2: structural C/A'},
     {'pts': addi_struct, 'color': '#7f7f7f', 'label': 'Additive D=4 n=6: structural C6/A', 'dash': 'stroke-dasharray="5,4"'},
     {'pts': wall, 'color': '#2ca02c', 'label': 'Direct: realized wall C/A'},
     {'pts': rssr, 'color': '#d62728', 'label': 'Direct: realized RSS C/A'}],
    'N (chain length)', 'ratio vs fine-rich comparator A', hline=1.0)

svg_plot('F3_t1_frontier.svg',
    'F3 — Target 1 frontier: signed per-site gap vs N (red dashed = 1e-5 target)',
    [{'pts': [(n, g) for n, g in t1], 'color': '#1f77b4', 'label': 'CONFIG A (r=5) ladder'},
     {'pts': [t1r9], 'color': '#d62728', 'label': 'reach-extended r=9 (N=100): +9.931e-06'}],
    'N (chain length)', 'gap = E_Bethe − E_LB (per site)', ylog=True, hline=1e-5)

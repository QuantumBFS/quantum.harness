import csv, sys
from collections import defaultdict

rows=list(csv.DictReader(open(sys.argv[1],encoding="utf-8")))
g=defaultdict(list)
for r in rows:g[(int(r["L"]),float(r["beta"]))].append(r)
W,H=1200,380; panels=[("Rp",-1.6,.7),("Qm",.45,.95),("chi",0,400)]
colors={8:"#2b6cb0",16:"#d97706",32:"#15803d"}
svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
     '<rect width="100%" height="100%" fill="white"/>',
     '<text x="600" y="24" text-anchor="middle" font-family="sans-serif" font-size="18">2D long-range Ising FK smoke, sigma=1.875</text>']
for p,(key,y0,y1) in enumerate(panels):
    ox=55+400*p; oy=45; pw=325; ph=275
    svg.append(f'<rect x="{ox}" y="{oy}" width="{pw}" height="{ph}" fill="none" stroke="#777"/>')
    svg.append(f'<text x="{ox+pw/2}" y="355" text-anchor="middle" font-family="sans-serif">beta</text>')
    svg.append(f'<text x="{ox+8}" y="{oy+16}" font-family="sans-serif">{key}</text>')
    for L in (8,16,32):
        pts=[]
        for (l,b),rs in sorted(g.items()):
            if l!=L:continue
            v=sum(float(r[key]) for r in rs)/len(rs)
            x=ox+(b-.326985)/.02*pw; y=oy+ph-(v-y0)/(y1-y0)*ph
            pts.append((x,y))
        svg.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in pts)}" fill="none" stroke="{colors[L]}" stroke-width="2"/>')
        for x,y in pts:svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{colors[L]}"/>')
        svg.append(f'<text x="{ox+235}" y="{oy+20+18*(L//8)}" fill="{colors[L]}" font-family="sans-serif" font-size="12">L={L}</text>')
svg.append('</svg>')
open(sys.argv[2],"w",encoding="utf-8").write("\n".join(svg))

import csv, math, os, sys
from collections import defaultdict

root=sys.argv[1]; analysis=os.path.join(root,"analysis")
rows=list(csv.DictReader(open(os.path.join(analysis,"aggregated.csv"),encoding="utf-8")))
cross=list(csv.DictReader(open(os.path.join(analysis,"crossings.csv"),encoding="utf-8")))
eta=list(csv.DictReader(open(os.path.join(analysis,"eta_fits.csv"),encoding="utf-8")))
bcs={1.75:.329136,1.875:.336985,2.0:.344439,2.5:.369446}
central=[]
for r in rows:
    s=float(r["sigma"])
    if abs(float(r["beta"])-bcs[s])<1e-9: central.append(r)

colors={1.75:"#2563eb",1.875:"#16a34a",2.0:"#dc2626",2.5:"#7c3aed"}
panels=[("Rp",-0.65,.08),("Qm",.68,.87),("chi_scaled",.20,.45)]
W,H=1200,400; svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">',
'<rect width="100%" height="100%" fill="white"/>',
'<text x="600" y="24" text-anchor="middle" font-family="sans-serif" font-size="18">Track A critical finite-size data (published beta_c)</text>']
for p,(q,y0,y1) in enumerate(panels):
    ox=55+p*400; oy=45; pw=325; ph=280
    svg.append(f'<rect x="{ox}" y="{oy}" width="{pw}" height="{ph}" fill="none" stroke="#777"/>')
    label="chi/L^2" if q=="chi_scaled" else q
    svg.append(f'<text x="{ox+8}" y="{oy+18}" font-family="sans-serif">{label}</text>')
    svg.append(f'<text x="{ox+pw/2}" y="365" text-anchor="middle" font-family="sans-serif">L (log2)</text>')
    for s in bcs:
        rr=sorted((r for r in central if float(r["sigma"])==s),key=lambda r:float(r["L"]))
        pts=[]
        for r in rr:
            L=float(r["L"]); v=float(r["chi"])/(L*L) if q=="chi_scaled" else float(r[q])
            x=ox+(math.log2(L)-6)/3*pw; y=oy+ph-(v-y0)/(y1-y0)*ph; pts.append((x,y))
        svg.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x,y in pts)}" fill="none" stroke="{colors[s]}" stroke-width="2"/>')
        for x,y in pts: svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{colors[s]}"/>')
        svg.append(f'<text x="{ox+205}" y="{oy+20+17*list(bcs).index(s)}" fill="{colors[s]}" font-family="sans-serif" font-size="12">sigma={s}</text>')
svg.append('</svg>')
open(os.path.join(analysis,"critical_finite_size.svg"),"w",encoding="utf-8").write("\n".join(svg))

def val(s,L,q):
    r=next(r for r in central if float(r["sigma"])==s and int(float(r["L"]))==L)
    return float(r[q])
lines=["# Issue #86 Track A reproduction report","",
"## Data integrity","",
"- Slurm array 22958313: 96/96 cells completed with exit code 0:0.",
"- 96 summaries, 96 raw-block files, 96 metadata files, and zero non-empty stderr logs.",
"- Each cell used 10,000 thermalization and 100,000 measurement sweeps with two independent seeds per point.",
"- Coupling normalization errors are at floating-point roundoff.","",
"## Critical finite-size values","",
"| sigma | Rp(L=64) | Rp(128) | Rp(256) | Rp(512) | Qm(512) | eta, L>=64 | eta, L>=128 |",
"|---:|---:|---:|---:|---:|---:|---:|---:|"]
for s in bcs:
    e64=next(float(r["eta"]) for r in eta if float(r["sigma"])==s and int(r["Lmin"])==64)
    e128=next(float(r["eta"]) for r in eta if float(r["sigma"])==s and int(r["Lmin"])==128)
    lines.append(f"| {s} | {val(s,64,'Rp'):.5f} | {val(s,128,'Rp'):.5f} | {val(s,256,'Rp'):.5f} | {val(s,512,'Rp'):.5f} | {val(s,512,'Qm'):.5f} | {e64:.4f} | {e128:.4f} |")
lines += ["","## Assessment","",
"The finite-size trends are reproduced: Rp and Qm vary smoothly with L; sigma=2.5 approaches the short-range anchors (Rp=0, Qm=0.857, eta=0.25), while sigma<=2 remains visibly separated at L=512.",
"At sigma=1.875, L=512 gives Rp=-0.27176 and Qm=0.78523, moving toward the published thermodynamic estimates -0.207(9) and 0.815(8). The school-scale eta estimates (0.3290 using L>=64 and 0.3204 using L>=128) remain above the published 0.293(3), demonstrating the stated strong finite-size corrections.",
"The unrestricted three-parameter correction fits are weakly identified with only four sizes; after dropping L=64 they are underdetermined. Power and logarithmic corrections produce model-dependent limits, and AICc is undefined for n=4,k=3. BIC is reported, but it is not sufficient for a stable boundary verdict.",
"",
"**Locked conclusion: finite-size reproduction successful; thermodynamic discrimination between the competing crossover scenarios is inconclusive at L<=512.**",
"",
"This follows Issue #86's no-one-fit rule and is not a failure: the raw data reproduce the expected school-scale drift, but do not justify selecting a thermodynamic scenario."]
open(os.path.join(analysis,"final_report.md"),"w",encoding="utf-8").write("\n".join(lines)+"\n")
print("\n".join(lines))

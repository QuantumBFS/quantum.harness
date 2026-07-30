import csv, glob, math, os, statistics, sys
from collections import defaultdict

root=sys.argv[1]
out=os.path.join(root,"analysis_partial")
os.makedirs(out,exist_ok=True)
rows=[]
for p in glob.glob(os.path.join(root,"cells","*","summary.csv")):
    with open(p,encoding="utf-8") as f:
        r=next(csv.DictReader(f)); r={k:float(v) for k,v in r.items()}
        r["cell"]=os.path.basename(os.path.dirname(p)); rows.append(r)

groups=defaultdict(list)
for r in rows: groups[(r["sigma"],int(r["L"]),r["beta"])].append(r)
assert len(rows)==72 and all(len(v)==2 for v in groups.values())

with open(os.path.join(out,"aggregated_partial.csv"),"w",newline="",encoding="utf-8") as f:
    w=csv.writer(f); w.writerow(["sigma","L","beta","Rp","Rp_seed_se","Qm","Qm_seed_se","chi","tau_m2_max"])
    for k,rs in sorted(groups.items()):
        def mean(q): return statistics.mean(r[q] for r in rs)
        def se(q): return statistics.stdev(r[q] for r in rs)/math.sqrt(2)
        w.writerow([*k,mean("Rp"),se("Rp"),mean("Qm"),se("Qm"),mean("chi"),max(r["tau_m2"] for r in rs)])

bcs={1.75:.329136,1.875:.336985,2.0:.344439,2.5:.369446}
def avg(s,L,b,q): return statistics.mean(r[q] for r in groups[(s,L,b)])
cross=[]
for s,bc in bcs.items():
  for q in ("Rp","Qm"):
    for L1,L2 in ((64,128),(128,256)):
      xs=sorted(b for ss,ll,b in groups if ss==s and ll==L1)
      ds=[avg(s,L1,b,q)-avg(s,L2,b,q) for b in xs]
      xm=statistics.mean(xs); dm=statistics.mean(ds)
      slope=sum((x-xm)*(d-dm) for x,d in zip(xs,ds))/sum((x-xm)**2 for x in xs)
      bx=xm-dm/slope
      cross.append((s,q,L1,L2,bx,"interpolated" if min(xs)<=bx<=max(xs) else "unresolved"))
with open(os.path.join(out,"crossings_partial.csv"),"w",newline="",encoding="utf-8") as f:
    w=csv.writer(f); w.writerow(["sigma","observable","L","2L","beta_cross","status"]); w.writerows(cross)

lines=["# Track A partial validation (L <= 256)","",
       f"- Complete cells: {len(rows)}/72 expected partial cells",
       f"- Maximum tau_int(m2): {max(r['tau_m2'] for r in rows):.3f}",
       f"- Maximum |sumJ-4|: {max(abs(r['sumJ']-4) for r in rows):.3e}","",
       "## sigma=2.5 central-beta control","",
       "| L | Rp | Qm | chi |","|---:|---:|---:|---:|"]
for L in (64,128,256):
    rs=groups[(2.5,L,bcs[2.5])]
    lines.append(f"| {L} | {statistics.mean(r['Rp'] for r in rs):.6f} | {statistics.mean(r['Qm'] for r in rs):.6f} | {statistics.mean(r['chi'] for r in rs):.3f} |")
lines += ["","## Preliminary crossings","","| sigma | obs | L/2L | beta | status |","|---:|:---:|:---:|---:|:---|"]
for s,q,l1,l2,b,status in cross:
    lines.append(f"| {s} | {q} | {l1}/{l2} | {b:.7f} | {status} |")
open(os.path.join(out,"partial_report.md"),"w",encoding="utf-8").write("\n".join(lines)+"\n")
print("\n".join(lines))

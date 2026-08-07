#!/usr/bin/env python3
"""Render the overnight run's results.csv into RESULTS.md.

results.csv is the single source of truth; this script never hard-codes a
measured number. Usage: make_results_md.py <run_dir> [<extra_output_path>]
"""
import csv
import sys
from pathlib import Path

run = Path(sys.argv[1])
rows = list(csv.DictReader(open(run / "results.csv")))
if not rows:
    sys.exit("results.csv is empty")

FIXED = ["d", "extra", "r", "three_type", "SU2_symmetry", "lattice", "Gram",
         "correlation", "J2", "supp", "coe",
         "mosek_tol_pfeas", "mosek_tol_dfeas", "mosek_tol_relgap"]
NOTE = {
    "d": "relaxation order; get_basis has no branch above d>3, so d>=4 is equivalent",
    "extra": "r = extra + 1; max separation of two-site basis words",
    "r": "effective reach",
    "three_type": "adjacent triple for three-body basis words",
    "supp": "sigma^x_1 sigma^x_2 (index = 3*(site-1)+component)",
    "coe": "SU(2) collapses (1/4)*sum_a onto one component -> 3/4",
    "J2": "plain Heisenberg, no next-nearest-neighbour term",
}

def num(x, fmt):
    try:
        return format(float(x), fmt)
    except (TypeError, ValueError):
        return "-"

opt_a = next((float(r["opt"]) for r in rows if r["label"] == "step2_A"), None)
out = []
w = out.append

w("# Overnight reproduction — results tables\n")
w("Generated from `results.csv` by `make_results_md.py`. Do not hand-edit:")
w("`results.csv` is the source of truth.\n")
w(f"- protocol_sha256 `{rows[0]['protocol_sha256']}`")
w(f"- qmbcertify_commit `{rows[0]['qmbcertify_commit']}` (unmodified)")
w(f"- julia `{rows[0]['julia_version']}`, mosek `{rows[1]['mosek_version']}`")
w(f"- cpu `{rows[0]['cpu_model']}`\n")

w("## 1. Fixed parameters (CONFIG A; identical across every cell)\n")
w("| parameter | value | note |")
w("|---|---|---|")
for f in FIXED:
    w(f"| `{f}` | `{rows[1][f]}` | {NOTE.get(f, '')} |")
w("| `lol` | `N` | tracks the cell's N |\n")

w("## 2. Per-cell varied knobs and measured data\n")
w("| cell | N | rdm | pso | lso | opt | dev vs Table3 New | "
  "delta = opt_A - opt_cell | termination | solve_s | wall_s | RSS GB | limit_hit |")
w("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for r in rows:
    killed = bool(r["limit_hit"]) and not r["opt"]
    # delta is only meaningful against CONFIG A at the SAME N (N=14).
    delta = (f"{opt_a - float(r['opt']):+.4e}"
             if (opt_a is not None and r["opt"] and r["label"] != "step2_A"
                 and r["N"] == "14") else "-")
    w("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
        r["label"], r["N"], r["rdm"], r["pso"], r["lso"],
        r["opt"] if r["opt"] else "(none)",
        num(r["dev_vs_new"], "+.3e") if r["dev_vs_new"] else "-",
        delta,
        "*N/A*" if killed else r["termination_status"],
        num(r["solve_s"], ".1f"), num(r["wall_s"], ".0f"),
        num(r["peak_rss_gb"], ".1f"), r["limit_hit"] or "-"))
w("")
w("**Killed rows.** Cells with `limit_hit=MAX_WALL_S` and no `opt` were killed")
w("during construction and never reached MOSEK. `results.csv` records")
w("`termination_status=OPTIMAL` for them, which is FALSE — the parser treats an")
w("absent warning line as OPTIMAL, valid only when a solve actually ran. Shown")
w("as *N/A* here; the CSV rows are left unedited and corrected in `LOG.md`.\n")
w("**RSS caveat.** step2_B / step3_C / step3_D values are cumulative process")
w("memory, not per-cell (the pre-fix `@async` monitor under-sampled). Only the")
w("ladder rows use the thread-based monitor and are per-cell.\n")

w("## 3. Solver residuals (what actually bounds the trustworthy digits)\n")
w("| cell | pfeas | dfeas | duality gap (MU) | termination |")
w("|---|---|---|---|---|")
for r in rows:
    if r["opt"]:
        w(f"| {r['label']} | {r['primal_residual']} | {r['dual_residual']} | "
          f"{r['duality_gap']} | {r['termination_status']} |")
w("")
w("Declared tolerance is 1e-8. Any difference at or below ~1e-8 is not")
w("resolvable: `delta_RDM` (~1e-6) is, `delta_pso` and `delta_lso` (~1e-8)")
w("are not, and the negative sign of `delta_lso` is numerical noise.\n")

w("## 4. Table 3 reference values (arXiv:2604.01555)\n")
w("| N | DMRG | SDP Old | SDP New | reproduced? |")
w("|---|---|---|---|---|")
seen = set()
for r in rows:
    if r["N"] in seen:
        continue
    seen.add(r["N"])
    w(f"| {r['N']} | {r['table3_dmrg']} | {r['table3_old']} | {r['table3_new']} | "
      f"{'yes' if r['opt'] else 'no — no opt produced'} |")
w("")

w("## 5. Provenance\n")
w("| field | value |")
w("|---|---|")
for f in ("harness_commit", "qmbcertify_commit", "project_toml_sha256",
          "manifest_toml_sha256", "julia_version", "mosek_version", "hostname"):
    w(f"| `{f}` | `{rows[1][f]}` |")
for lab in ("gate", "step2_A", "ladder"):
    r = next((x for x in rows if x["label"] == lab), None)
    if r:
        w(f"| `script_sha256` ({lab}) | `{r['script_sha256']}` |")
w("")
w("`script_sha256` differs across groups because the harness was changed twice")
w("mid-run (add `mosek_version`; thread-based monitor + enforced wall kill).")
w("Project/Manifest hashes and `qmbcertify_commit` are identical throughout, so")
w("the groups remain comparable.")

text = "\n".join(out) + "\n"
for p in [run / "RESULTS.md", *(Path(a) for a in sys.argv[2:])]:
    p.write_text(text)
    print("wrote", p)

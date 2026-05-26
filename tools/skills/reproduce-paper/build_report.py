#!/usr/bin/env python3
"""Translate a reproduction's run.json into the generic report.json that
/report renders.

    python3 build_report.py <run-dir>

run.json stays the single semantic source; report.json is a derived render
input — regenerated from run.json each time, like report.html itself, never
edited by hand. The shape it emits (title + sections + blocks) is the generic
document /report draws; this file owns the paper-reproduction layout, /report
owns nothing about papers.
"""
import json
import sys
from pathlib import Path


def fmt_map(d) -> str:
    if not isinstance(d, dict) or not d:
        return ""
    return " · ".join(f"{k} = {v}" for k, v in d.items())


def model_section(model: dict) -> dict:
    inner = []
    if model.get("H"):
        inner.append({"kind": "equation", "tex": model["H"]})
    inner.append({"kind": "kv", "pairs": [
        ["Name", model.get("name")],
        ["Couplings", fmt_map(model.get("couplings"))],
        ["Lattice", model.get("lattice")],
        ["Boundary", model.get("boundary")],
    ]})
    return {"title": "Model",
            "note": "The physical system — shared by every figure below.",
            "blocks": [{"kind": "card", "title": "Hamiltonian", "blocks": inner}]}


def method_section(run: dict, meth: dict, scope: dict) -> dict:
    exact = meth.get("exact")
    badge = ({"kind": "badge", "text": "exact", "style": "good"} if exact is True
             else {"kind": "badge", "text": "approximation", "style": "warn"} if exact is False
             else None)
    approach = [b for b in (
        badge,
        {"kind": "kv", "pairs": [
            ["Method", meth.get("family")], ["Tool", meth.get("tool")],
            ["Settings", fmt_map(meth.get("settings"))]]},
        {"kind": "text", "text": meth["note"]} if meth.get("note") else None,
    ) if b]
    blocks = [{"kind": "card", "title": "Approach", "blocks": approach}]
    est = run.get("estimate") or []
    if est:
        blocks.append({"kind": "table",
                       "columns": ["Run point", "Est. wall time", "Est. memory"],
                       "numeric": [False, True, True],
                       "rows": [[e.get("point"), e.get("wall"), e.get("memory")] for e in est]})
    scope_line = " · ".join(p for p in (
        f'Scope: {scope.get("label")}' if scope.get("label") else "",
        f'Runs: {run.get("where")}' if run.get("where") else "") if p)
    if scope_line:
        blocks.append({"kind": "text", "text": scope_line})
    risks = run.get("risks") or []
    if risks:
        blocks.append({"kind": "list", "title": "Anticipated rough spots", "items": risks})
    return {"title": "Method",
            "note": "One computation, shared by every figure — and what it should cost.",
            "blocks": blocks}


def figure_blocks(f: dict) -> list:
    obs = f.get("observe", {})
    res = f.get("results") or {}
    title = " — ".join(p for p in (f.get("id"), f.get("plots")) if p)
    blocks = [{"kind": "heading", "level": 3, "text": title},
              {"kind": "kv", "pairs": [
                  ["x-axis", f.get("x")], ["Swept range", f.get("x_range")],
                  ["y-axis", f.get("y")],
                  ["Observable", obs.get("quantity")],
                  ["Normalization", obs.get("normalization")],
                  ["States used", obs.get("states")]]}]
    if f.get("expected"):
        blocks.append({"kind": "note", "label": "What we expect:", "text": f["expected"]})
    figs = []
    if f.get("paper_image"):
        figs.append({"src": f["paper_image"], "caption": "From the paper"})
    if res.get("figure"):
        figs.append({"src": res["figure"], "caption": "Our reproduction"})
    if figs:
        blocks.append({"kind": "figures", "items": figs})

    if res.get("figure") or res.get("match") or res.get("numbers"):
        verdict = {"yes": ("Reproduced", "good"), "partly": ("Partial match", "warn"),
                   "no": ("Did not match", "bad")}
        label, status = verdict.get(str(res.get("match", "")).lower(), ("Result", "warn"))
        blocks.append({"kind": "verdict", "status": status, "label": label, "why": res.get("why")})
        numbers = res.get("numbers") or {}
        if isinstance(numbers, dict) and numbers:
            blocks.append({"kind": "table", "columns": ["Quantity", "Value"],
                           "numeric": [False, True],
                           "rows": [[k, v] for k, v in numbers.items()]})
        changes = res.get("changes") or []
        blocks.append({"kind": "card", "title": "What actually ran", "blocks": [
            {"kind": "kv", "pairs": [
                ["Wall time", res.get("wall")],
                ["Changes from plan", "; ".join(changes) if changes else "none"]]}]})
        if res.get("rerun"):
            blocks.append({"kind": "code", "title": "Rerun", "text": res["rerun"]})
    else:
        blocks.append({"kind": "note", "style": "pending",
                       "text": "Results pending — our figure, the key numbers, and the "
                               "Reproduced / Partial / Did-not-match verdict appear here "
                               "after the approved run."})
    return blocks


def translate(run: dict) -> dict:
    paper = run.get("paper", {})
    model = run.get("model", {})
    figures = run.get("figures") or []
    fig_ids = ", ".join(f.get("id") for f in figures if f.get("id"))
    of_model = f' of the {model.get("name")}' if model.get("name") else ""
    sections = [model_section(model),
                method_section(run, run.get("method", {}), run.get("scope", {}))]
    fig_blocks = [blk for f in figures for blk in figure_blocks(f)]
    if fig_blocks:
        sections.append({"title": "Figures",
                         "note": "Each figure is one view of the computation above — its plan, then its result.",
                         "blocks": fig_blocks})
    return {
        "title": paper.get("title") or paper.get("id", "Reproduction"),
        "eyebrow": paper.get("id", "reproduction"),
        "url": paper.get("url"),
        "lede": f"Reproducing: {fig_ids}{of_model}." if fig_ids else None,
        "sections": sections,
    }


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python3 build_report.py <run-dir>")
    run_dir = Path(sys.argv[1]).resolve()
    run = json.loads((run_dir / "run.json").read_text())
    out = run_dir / "report.json"
    out.write_text(json.dumps(translate(run), indent=2, ensure_ascii=False))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

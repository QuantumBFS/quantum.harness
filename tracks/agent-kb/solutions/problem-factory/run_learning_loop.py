#!/usr/bin/env python3
"""Learning-loop demo: round 1's verdicts deposit heuristics; round 2's fleet
is generated under those lessons. Compares budget waste between rounds.

Deliberately does not touch run_demo.py's outputs (results/telemetry.jsonl,
results/report.md) — the mentor quickstart depends on them. Round 2 writes
results/telemetry_round2.jsonl + results/learning_loop.md.
"""

import json
from collections import Counter
from pathlib import Path

from pf import budget, cards as cards_mod, heuristics, probe, round2, static_fire, verdict


def fly(cards):
    """Same pipeline as run_demo.main (dedupe -> static fire -> hop -> verdict),
    factored here so both rounds share it and run_demo stays frozen."""
    seen, records = set(), []
    for card in cards:
        fp = cards_mod.fingerprint(card)
        if fp in seen:
            records.append(verdict.record(card, "dead", "duplicate_fingerprint", {}))
            continue
        seen.add(fp)
        ok, detail = static_fire.run(card)
        if not ok:
            records.append(verdict.record(card, "dead", f"setup_error: {detail}", {}))
            continue
        m = probe.metrics(card, probe.run_grid(card))
        v, reason = verdict.judge(card, m)
        records.append(verdict.record(card, v, reason, m))
    return records


def main():
    fleet1 = cards_mod.generate()
    rec1 = fly(fleet1)
    heuristics.dump(rec1, "heuristics")

    fleet2 = round2.generate()
    rec2 = fly(fleet2)
    heuristics.dump(rec2, "heuristics")
    cards_mod.write(fleet2, "cards/round2")

    with open("results/telemetry_round2.jsonl", "w", encoding="utf-8") as fh:
        for r in rec2:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    s1 = budget.summarize(rec1, {c["id"]: c for c in fleet1})
    s2 = budget.summarize(rec2, {c["id"]: c for c in fleet2})
    t1, t2 = Counter(r["verdict"] for r in rec1), Counter(r["verdict"] for r in rec2)

    lines = [
        "# Learning loop: round 1 -> heuristics -> round 2",
        "",
        "Round 2's fleet is generated under the lessons deposited by round 1",
        "(every card names its `licensed_by` entries in `cards/round2/`).",
        "Same pipeline, same gates — only the fleet changed.",
        "",
        "| round | launched | survivor | deferred | dead | hop EDs | wasted on no_signal | waste rate |",
        "|---|---|---|---|---|---|---|---|",
        "| 1 (no heuristics) | {} | {} | {} | {} | {} | {} | {:.0%} |".format(
            len(rec1), t1.get("survivor", 0), t1.get("deferred", 0), t1.get("dead", 0),
            s1["total_hop"], s1["wasted_hop"], s1["waste_rate"]),
        "| 2 (heuristics applied) | {} | {} | {} | {} | {} | {} | {:.0%} |".format(
            len(rec2), t2.get("survivor", 0), t2.get("deferred", 0), t2.get("dead", 0),
            s2["total_hop"], s2["wasted_hop"], s2["waste_rate"]),
        "",
        "## Round-2 cards and their licenses",
        "",
        "| card | licensed_by | verdict | decisiveness | reason |",
        "|---|---|---|---|---|",
    ]
    by_id = {r["problem_id"]: r for r in rec2}
    for card in fleet2:
        r = by_id[card["id"]]
        m = r["metrics"]
        lines.append("| {} | {} | {} | {} | {} |".format(
            card["id"], ", ".join(card["licensed_by"]), r["verdict"],
            f"{m['decisiveness']:.2f}" if m else "—", r["reason"]))
    lines += [
        "",
        "Heuristics library: {} entries ({} deposited this flight).".format(
            len(list(Path("heuristics").glob("*.yaml"))), len(rec2)),
        "",
        "Honesty note: the round-2 fleet is rule-generated with each choice",
        "citing its heuristic entry — the demo shows the loop mechanism",
        "(verdicts change the next fleet), not an LLM generator.",
    ]
    Path("results/learning_loop.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("round 1: {}  waste {:.0%} ({}/{} hop EDs)".format(
        dict(t1), s1["waste_rate"], s1["wasted_hop"], s1["total_hop"]))
    print("round 2: {}  waste {:.0%} ({}/{} hop EDs)".format(
        dict(t2), s2["waste_rate"], s2["wasted_hop"], s2["total_hop"]))
    for r in rec2:
        print(f"[{r['verdict']:<8}] {r['problem_id']}  {r['reason']}")
    print("wrote results/telemetry_round2.jsonl, results/learning_loop.md, cards/round2/")


if __name__ == "__main__":
    main()

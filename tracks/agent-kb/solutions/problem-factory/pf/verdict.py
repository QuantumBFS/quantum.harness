"""Three-state verdict and the battle report."""

import json
from collections import Counter
from pathlib import Path

DEFER_BAND = 0.5  # decisiveness in [DEFER_BAND, kill_below) -> visible but not decisive -> deferred


def judge(card, m):
    kill = card["gate"]["kill_if"]["decisiveness_below"]
    if m["decisiveness"] >= kill:
        return "survivor", f"decisiveness {m['decisiveness']:.2f} >= {kill}"
    if m["decisiveness"] >= DEFER_BAND:
        return "deferred", (
            f"signal visible (decisiveness {m['decisiveness']:.2f}) but below kill threshold "
            f"{kill} — worth a larger launch (gradient {m['gradient_vs_L']:+.4f}/site)"
        )
    return "dead", f"no_signal: decisiveness {m['decisiveness']:.2f} < {DEFER_BAND}"


def record(card, verdict, reason, metrics):
    return {"problem_id": card["id"], "verdict": verdict, "reason": reason, "metrics": metrics}


def write_report(records, outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "telemetry.jsonl", "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    tally = Counter(r["verdict"] for r in records)
    lines = [
        "# Problem Factory — Flight Report",
        "",
        f"launched {len(records)}: "
        + ", ".join(f"{v} {tally.get(v, 0)}" for v in ("survivor", "deferred", "dead")),
        "",
        "| card | verdict | decisiveness | gradient/L | reason |",
        "|---|---|---|---|---|",
    ]
    for r in records:
        m = r["metrics"]
        lines.append(
            "| {} | {} | {} | {} | {} |".format(
                r["problem_id"], r["verdict"],
                f"{m['decisiveness']:.2f}" if m else "—",
                f"{m['gradient_vs_L']:.4f}" if m else "—",
                r["reason"],
            )
        )
    lines += [
        "",
        "## Mishap review",
        "",
    ]
    for r in records:
        if r["verdict"] == "dead":
            lines.append(f"- **{r['problem_id']}** — {r['reason']}")
    with open(out / "report.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return tally

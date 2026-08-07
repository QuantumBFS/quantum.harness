#!/usr/bin/env python3
"""One-command demo flight: generate -> dedupe -> static fire -> hop -> verdict -> report."""

from pf import cards as cards_mod
from pf import heuristics, plots, probe, static_fire, verdict


def main():
    cards = cards_mod.generate()
    cards_mod.write(cards, "cards")

    seen, records = set(), []
    for card in cards:
        fp = cards_mod.fingerprint(card)
        if fp in seen:
            records.append(verdict.record(card, "dead", "duplicate_fingerprint", {}))
            print(f"[dead]     {card['id']}  duplicate_fingerprint", flush=True)
            continue
        seen.add(fp)

        ok, detail = static_fire.run(card)
        if not ok:
            records.append(verdict.record(card, "dead", f"setup_error: {detail}", {}))
            print(f"[dead]     {card['id']}  setup_error: {detail}", flush=True)
            continue

        m = probe.metrics(card, probe.run_grid(card))
        v, reason = verdict.judge(card, m)
        records.append(verdict.record(card, v, reason, m))
        print(f"[{v:<8}] {card['id']}  {reason}", flush=True)

    tally = verdict.write_report(records, "results")
    n = heuristics.dump(records, "heuristics")
    plots.plot("results/telemetry.jsonl", "results/metrics.png")
    print("\nlaunched {}: {}".format(
        len(records),
        ", ".join(f"{v} {tally.get(v, 0)}" for v in ("survivor", "deferred", "dead")),
    ))
    print(f"deposited {n} heuristics entries")
    print("wrote cards/*.yaml, results/telemetry.jsonl, results/report.md, results/metrics.png")


if __name__ == "__main__":
    main()

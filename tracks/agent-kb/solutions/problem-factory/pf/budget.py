"""Budget accounting: how much hop-test compute did a flight burn, and how
much of it was wasted on cards that died at the hop (no_signal).

Unit of cost = one ED solve (one (L, delta, j2) grid point). Cards that die
at dedup or static fire never reach the hop and cost ~nothing here; deferred
cards consumed compute but are unresolved, not wasted.
"""


def hop_cost(card):
    s = card["setup"]
    return len(s["sizes"]) * len(s["delta"]) * len(s["j2"])


def summarize(records, cards):
    """records: verdict records (interface B). cards: id -> card. Only records
    with metrics reached the hop."""
    total = wasted = 0
    for r in records:
        if not r["metrics"]:
            continue
        cost = hop_cost(cards[r["problem_id"]])
        total += cost
        if r["verdict"] == "dead" and r["reason"].startswith("no_signal"):
            wasted += cost
    return {"total_hop": total, "wasted_hop": wasted,
            "waste_rate": wasted / total if total else 0.0}

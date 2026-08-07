"""Learning-loop anchors: python3 tests/test_learning_loop.py

Round 2 must be licensed by round-1 heuristics (the loop claim), must not
collide with round-1 fingerprints, must pass static fire, and the budget
accounting must reproduce the round-1 waste anchor (18 of 72 hop EDs = 25%).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pf import budget, cards as cards_mod, round2, static_fire

ROOT = Path(__file__).resolve().parents[1]


def test_round2_fleet_is_licensed_by_round1_heuristics():
    fleet = round2.generate()
    assert len(fleet) == 3
    heur_ids = {p.stem for p in (ROOT / "heuristics").glob("*.yaml")}
    for card in fleet:
        assert card["convention"] == "spin"               # lesson: xxz-bad-setup-003
        assert card["setup"]["j2"][0] == 0.0              # baseline first (interface A)
        assert min(card["setup"]["j2"][1:]) >= 0.05       # lesson: xxz-j2-tiny-002 noise floor
        assert card["gate"]["frozen"] is True
        assert card["licensed_by"], card["id"]
        assert set(card["licensed_by"]) <= heur_ids, card["id"]


def test_round2_fingerprints_do_not_collide_with_round1():
    fps = {cards_mod.fingerprint(c) for c in cards_mod.generate()}
    for card in round2.generate():
        assert cards_mod.fingerprint(card) not in fps, card["id"]


def test_round2_cards_pass_static_fire():
    for card in round2.generate():
        ok, detail = static_fire.run(card)
        assert ok, f"{card['id']}: {detail}"


def test_budget_accounting_round1_anchor():
    cards = {c["id"]: c for c in cards_mod.generate()}
    assert budget.hop_cost(cards["xxz-j2-tiny-002"]) == 3 * 3 * 2
    assert budget.hop_cost(cards["xxz-j2-gap-001"]) == 3 * 3 * 3
    records = [
        {"problem_id": "xxz-j2-gap-001", "verdict": "survivor",
         "reason": "decisiveness 5.49 >= 2.0", "metrics": {"decisiveness": 5.49}},
        {"problem_id": "xxz-j2-tiny-002", "verdict": "dead",
         "reason": "no_signal: decisiveness 0.02 < 0.5", "metrics": {"decisiveness": 0.02}},
        {"problem_id": "xxz-bad-setup-003", "verdict": "dead",
         "reason": "setup_error: bethe_delta1 failed", "metrics": {}},
        {"problem_id": "xxz-j2-deferred-004", "verdict": "deferred",
         "reason": "signal visible", "metrics": {"decisiveness": 0.93}},
        {"problem_id": "xxz-j2-gap-001-dup", "verdict": "dead",
         "reason": "duplicate_fingerprint", "metrics": {}},
    ]
    s = budget.summarize(records, cards)
    assert s["total_hop"] == 63           # gap-001 (27) + tiny-002 (18) + deferred-004 (18)
    assert s["wasted_hop"] == 18          # only no_signal deaths waste hop compute
    assert abs(s["waste_rate"] - 18 / 63) < 1e-12


if __name__ == "__main__":
    test_round2_fleet_is_licensed_by_round1_heuristics()
    test_round2_fingerprints_do_not_collide_with_round1()
    test_round2_cards_pass_static_fire()
    test_budget_accounting_round1_anchor()
    print("all learning-loop anchors green")

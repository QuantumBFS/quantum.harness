from __future__ import annotations

from oracle.exterior_longword_adversarial import (
    exact_replay_candidate,
    search_adversarial_words,
)
from oracle.exterior_seed61_counterexample import WORD


def test_exact_replay_is_the_only_negative_hit_gate() -> None:
    record = exact_replay_candidate(
        target="exact5-shear-loop-pair:61",
        word=tuple(int(symbol) for symbol in WORD),
        discovery={"method": "compound-ratio", "score": 0.980565465},
    )

    assert record["hit"] is True
    assert record["exact_weight"]["sign"] == -1
    assert record["exact_weight"]["numerator"].startswith("-")
    assert record["word"]["length"] == 150


def test_small_oddcycle_search_is_deterministic_and_exactly_replayed() -> None:
    kwargs = {
        "target": "exact5-oddcycle-block-pair:117",
        "lengths": (4,),
        "restarts": 2,
        "rng_seed": 7,
        "rounds": 1,
        "proposals_per_round": 2,
    }
    first = search_adversarial_words(**kwargs)
    second = search_adversarial_words(**kwargs)

    assert first == second
    assert first["target"] == "exact5-oddcycle-block-pair:117"
    assert first["lengths"] == [4]
    assert first["candidates"][0]["word"]["length"] == 4
    assert first["candidates"][0]["exact_weight"]["sign"] == 1
    assert first["candidates"][0]["hit"] is False
    assert first["status"] == "no-exact-negative-found"

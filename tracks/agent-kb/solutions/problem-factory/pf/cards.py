"""Template-generated problem cards for the demo flight.

Cards are fixtures, not LLM output: each one exercises one pipeline outcome
(survivor / no_signal / setup_error / duplicate / deferred). Swapping in an
LLM generator later means replacing generate() only — the schema is the contract.
"""

from pathlib import Path

import yaml


def _xxz_card(cid, sizes, delta, j2, kill_below=2.0, convention="spin"):
    return {
        "id": cid,
        "model": "xxz_j2_chain",
        "convention": convention,
        "setup": {"boundary": "pbc", "sizes": sizes, "delta": delta, "j2": j2},
        "observable": {"name": "gap", "definition": "E1 - E0", "sector": "sz=0"},
        "gate": {
            "type": "gap_trend",
            "frozen": True,
            "baseline": "j2 = first entry of setup.j2 (must be 0.0)",
            "kill_if": {"decisiveness_below": kill_below},
        },
        "static_fire": ["bethe_delta1", "sz_conservation"],
    }


def generate():
    cards = [
        # survivor: strong J2, gap shift should dwarf finite-size noise
        _xxz_card("xxz-j2-gap-001", [6, 8, 10], [0.5, 1.0, 1.5], [0.0, 0.1, 0.3]),
        # no_signal: perturbation far below finite-size noise floor
        _xxz_card("xxz-j2-tiny-002", [6, 8, 10], [0.5, 1.0, 1.5], [0.0, 0.001]),
        # setup_error: pauli vs spin convention, energies off by 4x, Bethe oracle fails
        _xxz_card("xxz-bad-setup-003", [6, 8, 10], [1.0], [0.0], convention="pauli"),
        # deferred: weak but size-growing signal expected
        _xxz_card("xxz-j2-deferred-004", [6, 8, 10], [0.5, 1.0, 1.5], [0.0, 0.05]),
    ]
    dup = dict(cards[0], id="xxz-j2-gap-001-dup")
    return cards + [dup]


def fingerprint(card):
    s = card["setup"]
    return "{}/{}/{}/{}/{}/{}".format(
        card["model"], card["convention"], card["observable"]["name"],
        s["sizes"], s["delta"], s["j2"],
    )


def write(cards, outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    for card in cards:
        with open(out / f"{card['id']}.yaml", "w", encoding="utf-8") as fh:
            yaml.safe_dump(card, fh, allow_unicode=True, sort_keys=False)

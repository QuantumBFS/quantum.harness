"""Round-2 fleet: generated under the constraints deposited by round 1's
heuristics library. Every card names the entries that licensed it.

Lessons applied (heuristics/*.yaml):
- xxz-j2-tiny-002   J2 below the finite-size noise floor is invisible -> never
                    launch |J2| < 0.05 at these sizes
- xxz-bad-setup-003 convention mix-ups die at static fire -> generator pins
                    convention="spin"
- xxz-j2-gap-001-dup duplicate fingerprints -> fleet is pre-deduped
- xxz-j2-gap-001    J2=0.3 is decisive -> probe where the boundary lies
- xxz-j2-deferred-004 "launch bigger" -> relaunch the same question at L+2

The fleet is rule-generated, not LLM-generated: the point of the demo is the
loop mechanism (verdicts change the next fleet), not the generator.
"""

from .cards import _xxz_card


def generate():
    fleet = [
        # boundary probe: between 0.05 (deferred) and 0.3 (survivor)
        _xxz_card("xxz-j2-boundary-101", [6, 8, 10], [0.5, 1.0, 1.5], [0.0, 0.1]),
        _xxz_card("xxz-j2-boundary-102", [6, 8, 10], [0.5, 1.0, 1.5], [0.0, 0.2]),
        # deferred-004 relaunched bigger, per its own telemetry recommendation
        _xxz_card("xxz-j2-relaunch-103", [8, 10, 12], [0.5, 1.0, 1.5], [0.0, 0.05]),
    ]
    fleet[0]["licensed_by"] = ["xxz-j2-tiny-002", "xxz-j2-gap-001"]
    fleet[1]["licensed_by"] = ["xxz-j2-tiny-002", "xxz-j2-gap-001"]
    fleet[2]["licensed_by"] = ["xxz-j2-deferred-004"]
    return fleet

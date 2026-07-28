"""Fast seed for challenge #232: certified Bell-constant sandwiches.

This first target is deliberately the solved CHSH inequality.  It is a smoke
test for the research loop, not the claimed research result: every candidate
must provide both

1. an exact SOHS upper-bound certificate, and
2. an explicit finite-dimensional strategy giving a lower bound.

Once the loop reliably closes this known sandwich, ``PROBLEM_ID`` and the
objective in ``verify_candidate.py`` can be replaced by an open state-
polynomial constant without changing the evaluator contract.
"""

from __future__ import annotations


PROBLEM_ID = "chsh-smoke-v1"

# IMMUTABLE INTERFACE: the verifier imports this file and calls
# build_candidate() with no arguments. Never rename or remove that function.


def qsqrt2(rational: str = "0", sqrt2: str = "0") -> dict[str, str]:
    """Represent ``rational + sqrt2 * √2`` using exact rational strings."""
    return {"rational": rational, "sqrt2": sqrt2}


def term(coeff: dict[str, str], *word: str) -> dict[str, object]:
    return {"coeff": coeff, "word": list(word)}


def build_candidate() -> dict[str, object]:
    """Return an exact CHSH certificate and a deliberately imperfect strategy.

    The certificate uses

      2√2 I - CHSH
        = (1/√2) [A0-(B0+B1)/√2]†[A0-(B0+B1)/√2]
        + (1/√2) [A1-(B0-B1)/√2]†[A1-(B0-B1)/√2].

    The initial measurement angles are close to, but not at, the optimum.
    OmniEvolve therefore receives a cheap, continuous sandwich-gap signal
    while exact certificate validity remains a hard gate.
    """
    inv_sqrt2 = qsqrt2(sqrt2="1/2")
    one = qsqrt2(rational="1")
    minus_inv_sqrt2 = qsqrt2(sqrt2="-1/2")

    p0 = [
        term(one, "A0"),
        term(minus_inv_sqrt2, "B0"),
        term(minus_inv_sqrt2, "B1"),
    ]
    p1 = [
        term(one, "A1"),
        term(minus_inv_sqrt2, "B0"),
        term(inv_sqrt2, "B1"),
    ]

    return {
        "problem_id": PROBLEM_ID,
        "upper_bound": qsqrt2(sqrt2="2"),
        "sos": [
            {"weight": inv_sqrt2, "polynomial": p0},
            {"weight": inv_sqrt2, "polynomial": p1},
        ],
        # Observables are O(theta) = cos(theta) Z + sin(theta) X on |Phi+>.
        # These angles are intentionally suboptimal so evolution has room.
        "strategy": {
            "state": "phi_plus",
            "alice_angles": [0.0, 1.5707963267948966],
            "bob_angles": [0.6, -0.6],
        },
        "notes": "Exact upper certificate; evolve the explicit strategy first.",
    }

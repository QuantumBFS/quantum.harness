"""Independent exact verifier for the fast #232 CHSH evolution seed.

Only Python's standard library is used.  Algebraic coefficients live in
Q(√2), and operator words are reduced exactly under

    A_i² = B_j² = I,    [A_i, B_j] = 0.

The candidate cannot choose the Bell objective or the score formula.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path


PROBLEM_ID = "chsh-smoke-v1"
SYMBOLS = {"A0", "A1", "B0", "B1"}
Word = tuple[str, ...]


@dataclass(frozen=True)
class Qsqrt2:
    rational: Fraction = Fraction(0)
    sqrt2: Fraction = Fraction(0)

    def __add__(self, other: object) -> "Qsqrt2":
        rhs = parse_qsqrt2(other)
        return Qsqrt2(self.rational + rhs.rational, self.sqrt2 + rhs.sqrt2)

    def __sub__(self, other: object) -> "Qsqrt2":
        rhs = parse_qsqrt2(other)
        return Qsqrt2(self.rational - rhs.rational, self.sqrt2 - rhs.sqrt2)

    def __neg__(self) -> "Qsqrt2":
        return Qsqrt2(-self.rational, -self.sqrt2)

    def __mul__(self, other: object) -> "Qsqrt2":
        rhs = parse_qsqrt2(other)
        return Qsqrt2(
            self.rational * rhs.rational + 2 * self.sqrt2 * rhs.sqrt2,
            self.rational * rhs.sqrt2 + self.sqrt2 * rhs.rational,
        )

    def __rmul__(self, other: object) -> "Qsqrt2":
        return self * other

    def __bool__(self) -> bool:
        return bool(self.rational or self.sqrt2)

    def to_float(self) -> float:
        return float(self.rational) + float(self.sqrt2) * math.sqrt(2.0)

    def render(self) -> str:
        return f"({self.rational})+({self.sqrt2})*sqrt(2)"


ZERO = Qsqrt2()
ONE = Qsqrt2(Fraction(1))
Polynomial = dict[Word, Qsqrt2]


def parse_qsqrt2(value: object) -> Qsqrt2:
    if isinstance(value, Qsqrt2):
        return value
    if isinstance(value, (int, str, Fraction)):
        return Qsqrt2(Fraction(value))
    if not isinstance(value, dict):
        raise TypeError("coefficient must be an integer, rational string, or Q(sqrt(2)) mapping")
    allowed = {"rational", "sqrt2"}
    if set(value) - allowed:
        raise ValueError(f"unknown coefficient fields: {sorted(set(value) - allowed)}")
    return Qsqrt2(
        Fraction(str(value.get("rational", "0"))),
        Fraction(str(value.get("sqrt2", "0"))),
    )


def _cancel_involutions(symbols: list[str]) -> tuple[str, ...]:
    stack: list[str] = []
    for symbol in symbols:
        if stack and stack[-1] == symbol:
            stack.pop()
        else:
            stack.append(symbol)
    return tuple(stack)


def canonical_word(word: tuple[str, ...] | list[str]) -> Word:
    if any(symbol not in SYMBOLS for symbol in word):
        raise ValueError(f"unknown operator in word {word!r}")
    # Alice and Bob words commute across parties, but ordering inside a party
    # remains noncommutative.
    alice = _cancel_involutions([symbol for symbol in word if symbol.startswith("A")])
    bob = _cancel_involutions([symbol for symbol in word if symbol.startswith("B")])
    return alice + bob


def clean(poly: Polynomial) -> Polynomial:
    return {word: coeff for word, coeff in poly.items() if coeff}


def add(left: Polynomial, right: Polynomial, scale: Qsqrt2 = ONE) -> Polynomial:
    result = dict(left)
    for word, coeff in right.items():
        result[word] = result.get(word, ZERO) + scale * coeff
    return clean(result)


def multiply(left: Polynomial, right: Polynomial) -> Polynomial:
    result: Polynomial = {}
    for left_word, left_coeff in left.items():
        for right_word, right_coeff in right.items():
            word = canonical_word(left_word + right_word)
            result[word] = result.get(word, ZERO) + left_coeff * right_coeff
    return clean(result)


def adjoint(poly: Polynomial) -> Polynomial:
    result: Polynomial = {}
    for word, coeff in poly.items():
        reversed_word = canonical_word(tuple(reversed(word)))
        result[reversed_word] = result.get(reversed_word, ZERO) + coeff
    return clean(result)


def parse_polynomial(raw: object) -> Polynomial:
    if not isinstance(raw, list):
        raise TypeError("polynomial must be a list of terms")
    result: Polynomial = {}
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"coeff", "word"}:
            raise ValueError("each polynomial term must contain exactly coeff and word")
        word_raw = item["word"]
        if not isinstance(word_raw, list) or not all(isinstance(x, str) for x in word_raw):
            raise TypeError("word must be a list of operator names")
        word = canonical_word(word_raw)
        result[word] = result.get(word, ZERO) + parse_qsqrt2(item["coeff"])
    return clean(result)


def objective() -> Polynomial:
    # CHSH = A0B0 + A0B1 + A1B0 - A1B1.
    return {
        ("A0", "B0"): ONE,
        ("A0", "B1"): ONE,
        ("A1", "B0"): ONE,
        ("A1", "B1"): -ONE,
    }


def certificate_residual(candidate: dict[str, object]) -> tuple[Polynomial, float]:
    upper = parse_qsqrt2(candidate["upper_bound"])
    left = add({(): upper}, objective(), scale=-ONE)
    right: Polynomial = {}
    sos = candidate.get("sos")
    if not isinstance(sos, list) or not sos:
        raise ValueError("sos must be a non-empty list")
    for entry in sos:
        if not isinstance(entry, dict) or set(entry) != {"weight", "polynomial"}:
            raise ValueError("each sos entry must contain exactly weight and polynomial")
        weight = parse_qsqrt2(entry["weight"])
        if not math.isfinite(weight.to_float()) or weight.to_float() <= 0.0:
            raise ValueError("SOHS weights must be strictly positive")
        polynomial = parse_polynomial(entry["polynomial"])
        right = add(right, multiply(adjoint(polynomial), polynomial), scale=weight)
    residual = add(left, right, scale=-ONE)
    residual_l1 = sum(abs(coeff.to_float()) for coeff in residual.values())
    return residual, residual_l1


def strategy_value(candidate: dict[str, object]) -> float:
    strategy = candidate.get("strategy")
    if not isinstance(strategy, dict) or strategy.get("state") != "phi_plus":
        raise ValueError("strategy.state must be phi_plus")
    alice = strategy.get("alice_angles")
    bob = strategy.get("bob_angles")
    if not (
        isinstance(alice, list)
        and isinstance(bob, list)
        and len(alice) == 2
        and len(bob) == 2
    ):
        raise ValueError("strategy requires two Alice and two Bob angles")
    angles = [float(x) for x in alice + bob]
    if not all(math.isfinite(x) and abs(x) <= 100.0 * math.pi for x in angles):
        raise ValueError("strategy angles must be finite and reasonably bounded")
    a0, a1, b0, b1 = angles
    return (
        math.cos(a0 - b0)
        + math.cos(a0 - b1)
        + math.cos(a1 - b0)
        - math.cos(a1 - b1)
    )


def evaluate(candidate: dict[str, object]) -> dict[str, object]:
    if candidate.get("problem_id") != PROBLEM_ID:
        raise ValueError(f"problem_id must remain {PROBLEM_ID!r}")
    residual, residual_l1 = certificate_residual(candidate)
    certificate_valid = not residual
    upper = parse_qsqrt2(candidate["upper_bound"]).to_float()
    lower = strategy_value(candidate)
    if not (math.isfinite(upper) and math.isfinite(lower)):
        raise ValueError("bounds must be finite")
    gap = upper - lower
    sandwich_valid = certificate_valid and gap >= -1e-9

    if sandwich_valid:
        score = 0.80 + 0.20 * math.exp(-10.0 * max(gap, 0.0))
    else:
        # Dense feedback helps evolution repair an almost-correct identity,
        # but no invalid certificate can outrank a valid sandwich.
        score = 0.79 * math.exp(-min(residual_l1, 50.0))
    score = min(max(score, 0.0), 1.0)

    first_residual = None
    if residual:
        word, coeff = sorted(residual.items(), key=lambda item: (-abs(item[1].to_float()), item[0]))[0]
        first_residual = {"word": list(word), "coefficient": coeff.render()}

    signature_payload = {
        "certificate_valid": certificate_valid,
        "lower_rounded": round(lower, 10),
        "residual_terms": len(residual),
    }
    signature = hashlib.sha256(
        json.dumps(signature_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    closed = sandwich_valid and gap <= 1e-8
    return {
        "valid": True,
        # A valid sandwich may remain a parent even before the gap is closed.
        "passed": sandwich_valid,
        "closed": closed,
        "score": score,
        "problem_id": PROBLEM_ID,
        "certificate_valid": certificate_valid,
        "sandwich_valid": sandwich_valid,
        "upper_bound": upper,
        "lower_bound": lower,
        "sandwich_gap": gap,
        "residual_l1": residual_l1,
        "residual_terms": len(residual),
        "first_residual": first_residual,
        "behavior_signature": signature,
    }


def load_candidate(path: str) -> dict[str, object]:
    candidate_path = Path(path).resolve()
    spec = importlib.util.spec_from_file_location("evolved_candidate", candidate_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import candidate {candidate_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    builder = getattr(module, "build_candidate", None)
    if not callable(builder):
        raise AttributeError("candidate must define build_candidate()")
    candidate = builder()
    if not isinstance(candidate, dict):
        raise TypeError("build_candidate() must return a dictionary")
    return candidate


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: verify_candidate.py CANDIDATE.py", file=sys.stderr)
        return 2
    try:
        result = evaluate(load_candidate(sys.argv[1]))
    except Exception as exc:
        result = {
            "valid": False,
            "passed": False,
            "score": 0.0,
            "error": f"{type(exc).__name__}: {exc}",
        }
    # Prefix makes it harder for candidate chatter to be mistaken for verifier output.
    print("OMNIEVOLVE_BELL_RESULT=" + json.dumps(result, sort_keys=True))
    return 0 if result.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())

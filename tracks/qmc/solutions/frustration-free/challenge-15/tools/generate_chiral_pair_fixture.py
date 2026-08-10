#!/usr/bin/env python3
"""Generate the independent LHYR covariant-pair convention fixture."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from decimal import Decimal
from math import comb, factorial
from pathlib import Path

import mpmath as mp


EXPECTED_TWO_Q = [15, 31, 63]
SERIALIZED_DIGITS = 70
DECIMAL_PATTERN = re.compile(
    r"(?:0e\+0|-?[1-9]\.\d{69}e[+-](?:0|[1-9]\d*))\Z"
)
DEFINITION = {
    "convention_document": (
        ".superpowers/sdd/chiral-microscopic-source-resolution.md"
    ),
    "oracle": "planar-lhyr-coulomb-source-wigner-eckart-covariantization",
    "curved_sphere_effective_mass_claim": False,
    "energy_unit": "E_C",
    "relative_m_order": "ascending-positive-odd",
    "global_components": [-2, -1, 0, 1, 2],
}


def finite_sum_amplitude(relative_m: int) -> mp.mpf:
    """Evaluate Eq. (5.6) using its finite gamma sum."""
    terms = [
        (
            (-1) ** k
            * comb(relative_m + 2, relative_m - k)
            * mp.gamma(mp.mpf(k) + mp.mpf("2.5"))
            / factorial(k)
        )
        for k in range(relative_m + 1)
    ]
    return mp.fsum(terms) / (
        2 * mp.sqrt((relative_m + 1) * (relative_m + 2))
    )


def integral_amplitude(relative_m: int) -> mp.mpf:
    """Evaluate Eq. (5.5) by generalized Gauss-Laguerre quadrature.

    The quadrature weight is x^(3/2) exp(-x).  Its remaining integrand,
    L_r^2(x), has degree r, so ceil((r+1)/2) nodes integrate it exactly
    apart from the active arbitrary-precision arithmetic.
    """
    node_count = (relative_m + 2) // 2
    nodes, weights = mp.gauss_quadrature(
        node_count, "glaguerre", alpha=mp.mpf("1.5")
    )
    integral = mp.fdot(
        [
            (mp.laguerre(relative_m, 2, node), weight)
            for node, weight in zip(nodes, weights, strict=True)
        ]
    )
    return integral / (2 * mp.sqrt((relative_m + 1) * (relative_m + 2)))


def canonical_decimal(value: mp.mpf) -> str:
    """Return the fixture's 70-significant-digit scientific spelling."""
    if not mp.isfinite(value):
        raise ValueError("fixture decimals must be finite")
    if value == 0:
        return "0e+0"
    decimal_value = Decimal(mp.nstr(value, n=mp.mp.dps))
    result = format(decimal_value, f".{SERIALIZED_DIGITS - 1}e")
    if not DECIMAL_PATTERN.fullmatch(result):
        raise RuntimeError(f"noncanonical decimal generated: {result}")
    return result


def canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _validate_formula(relative_m: int, finite_sum: mp.mpf, integral: mp.mpf) -> None:
    difference = abs(finite_sum - integral)
    relative_difference = difference / abs(finite_sum)
    if not (
        relative_difference <= mp.mpf("1e-70")
        or difference <= mp.mpf("1e-75")
    ):
        raise RuntimeError(
            f"finite sum and integral disagree for relative m={relative_m}"
        )
    if finite_sum <= 0 or integral <= 0:
        raise RuntimeError(f"amplitude is not positive for relative m={relative_m}")


def build_case(two_q: int) -> dict[str, object]:
    relative_m = list(range(1, two_q - 1, 2))
    amplitudes: list[mp.mpf] = []
    for value in relative_m:
        finite_sum = finite_sum_amplitude(value)
        integral = integral_amplitude(value)
        _validate_formula(value, finite_sum, integral)
        amplitudes.append(finite_sum)

    norm = mp.sqrt(mp.fsum(amplitude * amplitude for amplitude in amplitudes))
    if norm <= 0 or not mp.isfinite(norm):
        raise RuntimeError(f"invalid Euclidean norm for two_q={two_q}")
    normalized = [amplitude / norm for amplitude in amplitudes]
    normalized_norm = mp.fsum(value * value for value in normalized)
    if abs(normalized_norm - 1) > mp.mpf("1e-70"):
        raise RuntimeError(f"normalization failed for two_q={two_q}")
    if normalized[0] <= 0:
        raise RuntimeError(f"first normalized entry is not positive for two_q={two_q}")

    raw_values = [[canonical_decimal(value), "0e+0"] for value in amplitudes]
    normalized_values = [
        [canonical_decimal(value), "0e+0"] for value in normalized
    ]
    norm_decimal = canonical_decimal(norm)
    unsigned_case: dict[str, object] = {
        "two_q": two_q,
        "orientation": {
            "sphere": "outward",
            "electron_charge": "-e",
            "monopole_sign": 1,
        },
        "spatial_geometry": "fixed-round-sphere",
        "spatial_metric_varied": False,
        "area_varied": False,
        "chord_coulomb_varied": False,
        "source_definition": "equations-5.1-through-6.3",
        "metric_coordinates": {
            "inverse_mass_linearization": "[[1+h1,h2],[h2,1-h1]]",
            "h_plus": "h1+i*h2",
            "h_minus": "h1-i*h2",
            "curved_sphere_metric_used": False,
        },
        "landau_level_derivative_used": False,
        "relative_m": relative_m,
        "minus": {
            "direction": "m_plus_2_to_m",
            "raw_values_E_C": raw_values,
            "raw_euclidean_norm_E_C": norm_decimal,
            "normalized_values": normalized_values,
        },
        "plus": {
            "direction": "m_to_m_plus_2",
            "raw_values_E_C": [pair.copy() for pair in raw_values],
            "raw_euclidean_norm_E_C": norm_decimal,
            "normalized_values": [pair.copy() for pair in normalized_values],
        },
        "selected_minus_family": "m_plus_2_to_m",
        "diagnostics": {
            "first_nonzero_normalized_positive_real": True,
            "adjoint_residual": "0e+0",
            "formula": "gamma-finite-sum-5.6",
        },
    }
    digest = hashlib.sha256(canonical_json_bytes(unsigned_case)).hexdigest()
    case = {**unsigned_case, "payload_sha256": digest}
    recomputed_unsigned = {
        key: value for key, value in case.items() if key != "payload_sha256"
    }
    if hashlib.sha256(canonical_json_bytes(recomputed_unsigned)).hexdigest() != digest:
        raise RuntimeError(f"payload digest validation failed for two_q={two_q}")
    return case


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the bounded LHYR covariant-pair fixture."
    )
    parser.add_argument("--two-q", nargs="+", type=int, required=True)
    parser.add_argument("--digits", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.two_q != EXPECTED_TWO_Q:
        raise SystemExit(f"--two-q must be exactly {' '.join(map(str, EXPECTED_TWO_Q))}")
    if args.digits < 80:
        raise SystemExit("--digits must be at least 80")

    # Alternating gamma sums lose digits through cancellation at large r.
    # Guard digits preserve at least the requested precision in the result.
    working_digits = args.digits + 2 * max(args.two_q)
    with mp.workdps(working_digits):
        root = {
            "schema": "challenge15.chiral-covariant-pair-fixture.v1",
            "definition": DEFINITION,
            "cases": [build_case(two_q) for two_q in args.two_q],
        }
    serialized = canonical_json_bytes(root) + b"\n"
    if serialized.endswith(b"\n\n") or serialized.startswith(b"\xef\xbb\xbf"):
        raise RuntimeError("root serialization is not canonical")
    args.output.write_bytes(serialized)
    print(f"wrote {len(args.two_q)} LHYR covariant-pair cases")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
from fractions import Fraction
from pathlib import Path

from trottercert.cubic_field import fourth_order_suzuki_cubic_stages
from trottercert.cubic_local import exact_d5_density, exact_log_e5_density
from trottercert.intervals import cube_root_four_interval
from trottercert.support_groups import (
    build_d5_payload,
    canonical_gzip_bytes,
    certify_support_partition,
    decode_d5_gzip,
    discover_support_partition,
    verify_d5_payload,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "certificates" / "issue128-d5-groups.json.gz"
EXPECTED_TERM_COUNT = 605_832
EXPECTED_GROUP_COUNT = 123_106
EXPECTED_SITE_DENSITY = Fraction(
    44_948_270_001_027_856_175_670_154_896_253,
    4_000_000_000_000_000_000_000_000_000_000,
)
SITE_DENSITY_GATE = Fraction(12)


def _require_regression_gates(
    *,
    term_count: int,
    group_count: int,
    site_density: Fraction,
) -> None:
    if term_count != EXPECTED_TERM_COUNT:
        raise ValueError(
            f"D5 term-count regression: {term_count} != {EXPECTED_TERM_COUNT}"
        )
    if group_count != EXPECTED_GROUP_COUNT:
        raise ValueError(
            f"D5 group-count regression: {group_count} != {EXPECTED_GROUP_COUNT}"
        )
    if site_density > SITE_DENSITY_GATE:
        raise ValueError(
            f"D5 site-density gate failed: {site_density} > {SITE_DENSITY_GATE}"
        )
    if site_density != EXPECTED_SITE_DENSITY:
        raise ValueError(
            "D5 site-density regression: "
            f"{site_density} != {EXPECTED_SITE_DENSITY}"
        )


def _report(term_count: int, group_count: int, site_density: Fraction) -> None:
    print(f"term_count={term_count}")
    print(f"group_count={group_count}")
    print(f"site_density={site_density}")
    print(f"site_density_decimal={float(site_density):.16g}")


def verify_only() -> None:
    raw = OUTPUT.read_bytes()
    payload = decode_d5_gzip(raw)
    certificate = verify_d5_payload(payload)
    term_count = len(certificate.paulis)
    group_count = len(certificate.groups)
    site_density = certificate.bound / 4
    _require_regression_gates(
        term_count=term_count,
        group_count=group_count,
        site_density=site_density,
    )
    _report(term_count, group_count, site_density)


def build() -> None:
    stages = fourth_order_suzuki_cubic_stages(4)
    registry, e5 = exact_log_e5_density(stages)
    d5 = exact_d5_density(registry, e5)
    root = cube_root_four_interval(24)
    root_midpoint = root.midpoint()
    coefficients = {
        pauli: coefficient.enclose(root)
        for pauli, coefficient in d5.items()
    }
    discovery_scores = {
        pauli: coefficient.a0
        + coefficient.a1 * root_midpoint
        + coefficient.a2 * root_midpoint**2
        for pauli, coefficient in d5.items()
    }
    groups = discover_support_partition(
        coefficients,
        max_group_size=10,
        discovery_scores=discovery_scores,
    )
    certificate = certify_support_partition(coefficients, groups)
    term_count = len(certificate.paulis)
    group_count = len(certificate.groups)
    site_density = certificate.bound / 4
    _report(term_count, group_count, site_density)
    _require_regression_gates(
        term_count=term_count,
        group_count=group_count,
        site_density=site_density,
    )

    payload = build_d5_payload(coefficients, groups)
    raw = canonical_gzip_bytes(payload)
    verified = verify_d5_payload(decode_d5_gzip(raw))
    if verified.bound != certificate.bound:
        raise ValueError("D5 round-trip certificate bound mismatch")
    OUTPUT.write_bytes(raw)
    print(f"output={OUTPUT}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    arguments = parser.parse_args()
    if arguments.verify_only:
        verify_only()
    else:
        build()


if __name__ == "__main__":
    main()

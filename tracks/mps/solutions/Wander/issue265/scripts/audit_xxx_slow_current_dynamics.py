#!/usr/bin/env python3
"""Audit finite-volume scaling of the exact XXX slow-current dynamics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def derive(sources: tuple[Path, ...]) -> dict[str, object]:
    payloads = [json.loads(path.read_text(encoding="utf-8")) for path in sources]
    fixed_cutoffs = (np.pi / 4.0, np.pi / 2.0)
    sequences = []
    for target in fixed_cutoffs:
        rows = []
        for source, payload in zip(sources, payloads, strict=True):
            row = min(
                payload["rows"],
                key=lambda item: abs(item["cutoff_wave_number"] - target),
            )
            if abs(row["cutoff_wave_number"] - target) > 1.0e-12:
                raise ValueError("source does not contain the required fixed cutoff")
            length = int(payload["inputs"]["length"])
            retained_fraction = 1.0 - float(
                row["qlp_fraction_of_projected_liouvillian_norm"]
            )
            rows.append(
                {
                    "source": str(source),
                    "length": length,
                    "cutoff_mode": row["cutoff_mode"],
                    "plp_fraction_of_projected_liouvillian_norm": retained_fraction,
                    "length_squared_times_plp_fraction": length**2 * retained_fraction,
                    "maximum_plp_frequency": row[
                        "plp_generalized_frequency_maximum"
                    ],
                    "length_times_maximum_plp_frequency": length
                    * row["plp_generalized_frequency_maximum"],
                }
            )
        lengths = np.asarray([row["length"] for row in rows], dtype=float)
        fractions = np.asarray(
            [row["plp_fraction_of_projected_liouvillian_norm"] for row in rows]
        )
        slope, intercept = np.polyfit(np.log(lengths), np.log(fractions), 1)
        sequences.append(
            {
                "cutoff_wave_number": float(target),
                "rows": rows,
                "fitted_power_of_length": float(slope),
                "fitted_amplitude": float(np.exp(intercept)),
                "last_length_squared_scaled_fraction": rows[-1][
                    "length_squared_times_plp_fraction"
                ],
                "last_length_scaled_maximum_frequency": rows[-1][
                    "length_times_maximum_plp_frequency"
                ],
            }
        )
    return {
        "schema": 1,
        "method": "fixed_momentum_cutoff_finite_volume_plp_qlp_scaling",
        "sources": [str(path) for path in sources],
        "uses_target_trajectory": False,
        "uses_target_a_or_D": False,
        "sequences": sequences,
        "gates": {
            "all_source_gates_pass": all(
                all(payload["gates"].values()) for payload in payloads
            ),
            "plp_fraction_decreases_with_volume": all(
                all(
                    later
                    < earlier
                    for earlier, later in zip(
                        [
                            row["plp_fraction_of_projected_liouvillian_norm"]
                            for row in sequence["rows"]
                        ][:-1],
                        [
                            row["plp_fraction_of_projected_liouvillian_norm"]
                            for row in sequence["rows"]
                        ][1:],
                        strict=True,
                    )
                )
                for sequence in sequences
            ),
            "finite_bilinear_subspace_dynamically_closed": False,
        },
        "interpretation": (
            "At fixed physical momentum cutoff, the fraction of L Pj retained "
            "inside the two-spin bilinear subspace decreases approximately as "
            "L^-2, while its frequency scale decreases as L^-1.  The Q-space "
            "operator continuum therefore survives and cannot be replaced by "
            "a closed finite-field model as a microscopic identity."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", type=Path, nargs="+")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = derive(tuple(args.sources))
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(encoded, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

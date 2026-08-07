"""Reproduce the issue #117 large-N target selection from primary record tables."""

from __future__ import annotations

import json
import re
import urllib.request

TABLES = (
    "https://doye.chem.ox.ac.uk/jon/structures/LJ/LJ310-561.html",
    "https://doye.chem.ox.ac.uk/jon/structures/LJ/LJ562-1000.html",
)
KNOWN_447_CORRECTION = -2992.783729449165


def fetch_records() -> dict[int, float]:
    records: dict[int, float] = {}
    pattern = re.compile(
        r'<a href="LJ(?:310-561|562-1000)/(\d+)\.TXT">(\d+)</a></td>'
        r"\s*<td>\s*(-?\d+\.\d+)"
    )
    for url in TABLES:
        with urllib.request.urlopen(url, timeout=30) as response:
            page = response.read().decode("latin1")
        for href_n, label_n, energy in pattern.findall(page):
            if href_n != label_n:
                raise ValueError(f"record label mismatch: {href_n} != {label_n}")
            records[int(label_n)] = float(energy)
    return records


def audit(records: dict[int, float]) -> dict:
    corrected = dict(records)
    corrected[447] = KNOWN_447_CORRECTION
    residuals = []
    for n in range(min(corrected) + 1, max(corrected)):
        if not all(k in corrected for k in (n - 1, n, n + 1)):
            continue
        residual = corrected[n] - 0.5 * (corrected[n - 1] + corrected[n + 1])
        residuals.append(
            {
                "N": n,
                "energy": corrected[n],
                "local_interpolation_residual": residual,
                "delta_from_prev": corrected[n] - corrected[n - 1],
                "delta_to_next": corrected[n + 1] - corrected[n],
            }
        )

    violations = []
    previous = None
    for n in sorted(records):
        average_pair_energy = 2.0 * records[n] / (n * (n - 1))
        if previous and average_pair_energy < previous[1]:
            violations.append(
                {
                    "left_N": previous[0],
                    "right_N": n,
                    "left_average_pair_energy": previous[1],
                    "right_average_pair_energy": average_pair_energy,
                }
            )
        previous = (n, average_pair_energy)

    return {
        "source_tables": TABLES,
        "record_count": len(records),
        "range": [min(records), max(records)],
        "known_raw_violations": violations,
        "top_positive_residuals_after_447_correction": sorted(
            residuals,
            key=lambda row: row["local_interpolation_residual"],
            reverse=True,
        )[:25],
        "selected_target": 924,
        "selection_reason": (
            "largest positive local interpolation residual in N=310..1000 after "
            "the documented N=447 typo correction; record traces to the 2004 "
            "lattice-seeded 562..1000 survey"
        ),
    }


if __name__ == "__main__":
    print(json.dumps(audit(fetch_records()), indent=2))

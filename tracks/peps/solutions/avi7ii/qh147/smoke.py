from __future__ import annotations

import json
from dataclasses import asdict

from .thermo import evolve_exact_contraction


def main() -> None:
    points = [
        evolve_exact_contraction(
            2,
            2,
            j=1.0,
            h=3.0,
            beta=beta,
            delta_beta=0.01,
            max_bond=16,
        )
        for beta in (0.1, 0.2)
    ]
    print(json.dumps([asdict(point) for point in points], indent=2), flush=True)


if __name__ == "__main__":
    main()

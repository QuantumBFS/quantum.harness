"""Generate small-system ED and NQS results for Challenge #15."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from chiral_graviton.basis import SphereSystem
from chiral_graviton.ed import neutral_gap
from chiral_graviton.nqs import SharedProjectedMLP


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, nargs="+", default=[3, 4])
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--hidden-width", type=int, default=24)
    parser.add_argument("--max-iterations", type=int, default=400)
    parser.add_argument("--samples", type=int, default=50_000)
    parser.add_argument("--seed", type=int, default=1729)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for n_electrons in args.n:
        system = SphereSystem.from_electron_count(n_electrons)
        ed = neutral_gap(system, "coulomb")
        model = SharedProjectedMLP.build(
            system, "coulomb", hidden_width=args.hidden_width, seed=args.seed
        )
        nqs = model.fit(max_iterations=args.max_iterations)
        sample_l0 = model.sample_energy(
            nqs.parameters, 0, n_samples=args.samples, seed=args.seed
        )
        sample_l2 = model.sample_energy(
            nqs.parameters, 2, n_samples=args.samples, seed=args.seed + 1
        )
        row = {
            "n_electrons": n_electrons,
            "two_q": system.two_q,
            "ed_e_l0": ed.e_l0,
            "ed_e_l2": ed.e_l2,
            "ed_gap": ed.gap,
            "nqs_e_l0": nqs.ground.energy,
            "nqs_e_l2": nqs.graviton.energy,
            "nqs_gap": nqs.gap,
            "gap_absolute_error": abs(nqs.gap - ed.gap),
            "nqs_l2": nqs.graviton.l2_expectation,
            "nqs_variance_l0": nqs.ground.variance,
            "nqs_variance_l2": nqs.graviton.variance,
            "sample_count": args.samples,
            "sampled_gap": sample_l2.mean - sample_l0.mean,
            "sampled_gap_standard_error": (
                sample_l0.standard_error**2 + sample_l2.standard_error**2
            ) ** 0.5,
            "optimizer_success": nqs.success,
            "optimizer_iterations": nqs.iterations,
            "seed": args.seed,
        }
        rows.append(row)
        (output_dir / f"n{n_electrons}.json").write_text(
            json.dumps(row, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    with (output_dir / "gap_table.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(rows, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

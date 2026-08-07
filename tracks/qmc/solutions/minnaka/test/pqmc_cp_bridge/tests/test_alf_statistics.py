#!/usr/bin/env python3
"""Tests for chain-aware ALF ratio statistics and hard gates."""

from __future__ import annotations

import math
import csv
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from alf_statistics import (  # noqa: E402
    ReplicaData,
    choose_additional_nbin,
    estimate_energy,
    parse_replica,
    write_diagnostics,
)


def replica(
    chain: int,
    values: list[float],
    *,
    seed: int | None = None,
    signs: list[float] | None = None,
    offset: float = 0.0,
) -> ReplicaData:
    energies = [value + offset for value in values]
    phase = signs or [1.0] * len(values)
    return ReplicaData(
        chain=chain,
        batch=0,
        seed=seed or 1000 + chain,
        theta=10,
        ltrot=420,
        energy=tuple(e * s for e, s in zip(energies, phase)),
        kinetic=tuple((e - 4.0) * s for e, s in zip(energies, phase)),
        potential=tuple(4.0 * s for s in phase),
        particles=tuple(16.0 * s for s in phase),
        signs=tuple(phase),
        max_green_precision=1.0e-12,
    )


class AlfStatisticsTest(unittest.TestCase):
    def test_ratio_mean_discards_first_bin_of_each_replica(self) -> None:
        replicas = [
            replica(chain, [999.0, -14.0, -13.0, -12.0, -11.0, -10.0, -9.0])
            for chain in range(6)
        ]
        estimate = estimate_energy(replicas)
        self.assertAlmostEqual(estimate.mean, -11.5)
        self.assertEqual(estimate.retained_bins, 6)
        self.assertEqual(estimate.replicas, 6)
        self.assertIsNone(estimate.hard_failure)

    def test_equal_bin_numbers_are_combined_across_chains(self) -> None:
        replicas = [
            replica(chain, [999.0, -14.0 + chain, -12.0 + chain])
            for chain in range(6)
        ]
        estimate = estimate_energy(replicas)
        self.assertEqual(estimate.aggregated_bins, 2)
        self.assertAlmostEqual(estimate.mean, -10.5)

    def test_replica_offsets_control_final_error_and_order_is_irrelevant(self) -> None:
        replicas = [
            replica(chain, [0.0] + [-13.62] * 16, offset=(chain - 2.5) * 0.01)
            for chain in range(6)
        ]
        estimate = estimate_energy(replicas)
        reversed_estimate = estimate_energy(list(reversed(replicas)))
        self.assertEqual(estimate.sigma, 0.0)
        self.assertGreater(estimate.sigma_replica, 0.0)
        self.assertAlmostEqual(estimate.mean, reversed_estimate.mean)
        self.assertAlmostEqual(estimate.sigma, reversed_estimate.sigma)

    def test_negative_sign_and_duplicate_seed_are_hard_failures(self) -> None:
        replicas = [
            replica(chain, [0.0] + [-13.62] * 8)
            for chain in range(6)
        ]
        bad_sign = list(replicas)
        bad_sign[2] = replica(
            2,
            [0.0] + [-13.62] * 8,
            signs=[1.0] * 8 + [-1.0],
        )
        self.assertIn("negative sign", estimate_energy(bad_sign).hard_failure)
        duplicate = list(replicas)
        duplicate[5] = replica(5, [0.0] + [-13.62] * 8, seed=1000)
        self.assertIn("duplicate seed", estimate_energy(duplicate).hard_failure)

    def test_parse_rejects_energy_identity_and_wrong_info(self) -> None:
        scalar = "{:10d} ({:25.17E}, {:25.17E}) {:25.17E}\n"
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            values = {
                "Ener_scal": [-13.0, -13.1],
                "Kin_scal": [-17.0, -17.1],
                "Pot_scal": [4.0, 4.2],
                "Part_scal": [16.0, 16.0],
            }
            for name, rows in values.items():
                (run / name).write_text(
                    "".join(scalar.format(2, value, 0.0, 1.0) for value in rows),
                    encoding="utf-8",
                )
            (run / "info").write_text(
                " Theta : 10\n"
                " dtau,Ltrot_eff: 0.05 420\n"
                " No initial configuration, Seed_in 8\n"
                " Precision Green  Mean, Max : 1E-13 1E-12\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "E != K \\+ V"):
                parse_replica(
                    run,
                    {
                        "chain": 0,
                        "batch": 0,
                        "seed": 8,
                        "theta": 10,
                        "ltrot": 420,
                        "nbin": 2,
                    },
                )
            values["Pot_scal"][1] = 4.0
            (run / "Pot_scal").write_text(
                "".join(
                    scalar.format(2, value, 0.0, 1.0)
                    for value in values["Pot_scal"]
                ),
                encoding="utf-8",
            )
            parsed = parse_replica(
                run,
                {
                    "chain": 0,
                    "batch": 0,
                    "seed": 8,
                    "theta": 10,
                    "ltrot": 420,
                    "nbin": 2,
                },
            )
            self.assertEqual(parsed.ltrot, 420)
            with self.assertRaisesRegex(RuntimeError, "Ltrot"):
                parse_replica(
                    run,
                    {
                        "chain": 0,
                        "batch": 0,
                        "seed": 8,
                        "theta": 10,
                        "ltrot": 500,
                        "nbin": 2,
                    },
                )

    def test_additional_batch_formula(self) -> None:
        replicas = [
            replica(chain, [0.0] + [-13.62 + 0.02 * chain] * 12)
            for chain in range(6)
        ]
        estimate = estimate_energy(replicas)
        requested = choose_additional_nbin(estimate)
        self.assertGreaterEqual(requested, 7)
        self.assertTrue(math.isfinite(float(requested)))

    def test_sixty_four_chain_cluster_estimate_is_supported(self) -> None:
        replicas = [
            replica(
                chain,
                [0.0, -13.63, -13.62, -13.61],
                offset=(chain - 31.5) * 1.0e-5,
            )
            for chain in range(64)
        ]
        estimate = estimate_energy(replicas)
        self.assertIsNone(estimate.hard_failure)
        self.assertEqual(estimate.replicas, 64)
        self.assertEqual(estimate.retained_bins, 3)
        self.assertEqual(
            choose_additional_nbin(estimate, chains=64),
            choose_additional_nbin(estimate, chains=6),
        )

    def test_mixed_sixty_four_and_128_chain_batches_are_supported(self) -> None:
        replicas = [
            replica(
                chain,
                [0.0, -13.63, -13.62, -13.61],
                seed=10_000 + chain,
            )
            for chain in range(64)
        ]
        replicas.extend(
            ReplicaData(
                **{
                    **replica(
                        chain,
                        [0.0, -13.625, -13.615, -13.605],
                        seed=20_000 + chain,
                    ).__dict__,
                    "batch": 1,
                }
            )
            for chain in range(128)
        )
        estimate = estimate_energy(replicas)
        self.assertIsNone(estimate.hard_failure)
        self.assertEqual(estimate.replicas, 128)
        self.assertEqual(estimate.retained_bins, 6)

    def test_statistical_and_green_gates_are_independent(self) -> None:
        values = [0.0] + [
            -13.62 + (index % 2) * 1.0e-3 for index in range(24)
        ]
        replicas = [replica(chain, values) for chain in range(128)]
        estimate = estimate_energy(replicas)
        self.assertTrue(estimate.statistical_precision_pass)
        self.assertTrue(estimate.green_stability_pass)
        unstable = list(replicas)
        unstable[7] = ReplicaData(
            **{
                **unstable[7].__dict__,
                "max_green_precision": 2.0e-8,
            }
        )
        failed = estimate_energy(unstable)
        self.assertTrue(failed.statistical_precision_pass)
        self.assertFalse(failed.green_stability_pass)
        self.assertFalse(failed.precision_ready)

    def test_writes_raw_aggregate_jackknife_and_green_products(self) -> None:
        values = [0.0] + [
            -13.62 + (index % 2) * 1.0e-3 for index in range(24)
        ]
        replicas = [replica(chain, values) for chain in range(128)]
        replicas[3] = ReplicaData(
            **{
                **replicas[3].__dict__,
                "green_location": (2, 17, -1, 205, 4, 9, 2),
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            summary = write_diagnostics(
                replicas, output, ensemble="TI", theta=10
            )
            self.assertEqual(
                summary["measurement_bins_after_thermalization"], 24
            )
            with (output / "raw_chain_bins.csv").open() as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 128 * 25)
            with (output / "cross_chain_bins.csv").open() as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 24)
            with (output / "green_stability.csv").open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 128)
            self.assertEqual(rows[3]["slice"], "205")
            parsed = json.loads((output / "summary.json").read_text())
            self.assertTrue(parsed["statistical_precision_pass"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

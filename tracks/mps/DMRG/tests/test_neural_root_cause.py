from __future__ import annotations

import json
from pathlib import Path
import unittest

import numpy as np

import reproduce
from scripts.diagnose_neural_root_cause import (
    eligible_micro_sites,
    metropolis_probability,
    validate_protocol,
    walsh_degree_power,
)
from vmcrg_ref.neural_energy import D4EvenLocalMLP


PROTOCOL_PATH = Path("config/neural_root_cause_v1.json")
ARCHIVE_PATH = Path("output/neural_confirmation_frozen_v1")
THREE_ARM_PATH = Path("output/neural_three_arm_formal_v1")


class NeuralRootCauseTests(unittest.TestCase):
    def test_protocol_is_locked_and_uses_new_streams(self) -> None:
        protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
        records = validate_protocol(
            protocol, ARCHIVE_PATH.resolve(), THREE_ARM_PATH.resolve()
        )
        self.assertEqual(len(records), 10)
        streams = [int(record["seed"]) for record in records]
        streams.extend(int(value) for value in protocol["bootstrap_seeds"].values())
        self.assertEqual(len(streams), len(set(streams)))

    def test_walsh_spectrum_of_constant_model_is_zero_nonconstant(self) -> None:
        model = D4EvenLocalMLP.random(1, 4, 61, feature_mode="patch")
        model.weight_out.fill(0.0)
        spectrum = walsh_degree_power(model)
        self.assertEqual(spectrum["nonconstant_power"], 0.0)
        self.assertEqual(spectrum["odd_power_fraction"], 0.0)

    def test_walsh_spectrum_respects_exact_z2_symmetry(self) -> None:
        model = D4EvenLocalMLP.random(1, 6, 62, feature_mode="patch")
        model.weight_out[:] = np.linspace(-0.1, 0.1, model.hidden)
        spectrum = walsh_degree_power(model)
        self.assertLess(spectrum["odd_power_fraction"], 1e-24)
        self.assertAlmostEqual(
            spectrum["degree_2_power_fraction"]
            + spectrum["degree_4_power_fraction"]
            + spectrum["degree_6_plus_power_fraction"],
            1.0,
            places=12,
        )

    def test_metropolis_probability(self) -> None:
        self.assertEqual(metropolis_probability(-1.0), 1.0)
        self.assertEqual(metropolis_probability(0.0), 1.0)
        self.assertAlmostEqual(metropolis_probability(1.0), np.exp(-1.0))

    def test_unified_entry_exposes_root_cause_protocol(self) -> None:
        args = reproduce.build_parser().parse_args(["neural-root-cause", "--dry-run"])
        self.assertEqual(args.handler, reproduce._neural_root_cause)
        self.assertEqual(args.protocol, PROTOCOL_PATH)


if __name__ == "__main__":
    unittest.main()

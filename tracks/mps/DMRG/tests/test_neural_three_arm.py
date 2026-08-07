from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

import numpy as np

import reproduce
from scripts.neural_three_arm import (
    _manifest_hashes,
    assess_results,
    validate_protocol,
    verify_frozen_source,
    zero_neural_model,
)
from vmcrg_ref.neural_energy import D4EvenLocalMLP


PROTOCOL_PATH = Path("config/neural_three_arm_v1.json")
ARCHIVE_PATH = Path("output/neural_confirmation_frozen_v1")


def synthetic_results(hybrid_over_linear: float) -> list[dict]:
    records = []
    for repeat in range(10):
        linear_over_unbiased = np.full(8, 0.08 + repeat * 0.001)
        primary = np.full(8, hybrid_over_linear + repeat * 0.001)
        records.append(
            {
                "status": "COMPLETE",
                "tau_by_chain": {
                    "unbiased": np.full(8, 100.0).tolist(),
                    "linear": (100.0 * linear_over_unbiased).tolist(),
                    "hybrid": (100.0 * linear_over_unbiased * primary).tolist(),
                },
                "ratio_by_chain": {
                    "hybrid_over_linear": primary.tolist(),
                    "linear_over_unbiased": linear_over_unbiased.tolist(),
                    "hybrid_over_unbiased": (
                        primary * linear_over_unbiased
                    ).tolist(),
                },
            }
        )
    return records


class NeuralThreeArmTests(unittest.TestCase):
    def setUp(self) -> None:
        self.protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))

    def test_protocol_is_locked_and_uses_new_streams(self) -> None:
        records = validate_protocol(self.protocol, ARCHIVE_PATH.resolve())
        self.assertEqual(len(records), 10)
        streams = [record["seed"] for record in records]
        streams.extend(self.protocol["bootstrap_seeds"].values())
        self.assertEqual(len(streams), len(set(streams)))

    def test_zero_neural_model_has_exactly_zero_energy(self) -> None:
        model = D4EvenLocalMLP.random(1, 7, 44, feature_mode="patch")
        model.weight_out[:] = np.linspace(-0.2, 0.2, model.hidden)
        zero = zero_neural_model(model)
        spins = 2 * np.random.default_rng(45).integers(0, 2, size=(5, 5)) - 1
        self.assertEqual(zero.energy(spins), 0.0)
        self.assertTrue(np.all(zero.weight_in == 0.0))
        self.assertTrue(np.all(zero.bias_hidden == 0.0))
        self.assertTrue(np.all(zero.weight_out == 0.0))

    def test_all_models_are_included_without_ablation_survivorship_filter(self) -> None:
        archive = ARCHIVE_PATH.resolve()
        hashes = _manifest_hashes(archive)
        statuses = []
        for record in self.protocol["repeat_sources"]:
            source, _ = verify_frozen_source(archive, record, hashes)
            statuses.append(
                json.loads(
                    (source / "neural_residual_ablation_formal.json").read_text(
                        encoding="utf-8"
                    )
                )["status"]
            )
        self.assertEqual(len(statuses), 10)
        self.assertIn("PASS", statuses)
        self.assertIn("FAIL", statuses)

    def test_primary_gate_passes_and_fails_without_posthoc_changes(self) -> None:
        small = copy.deepcopy(self.protocol)
        small["formal_requirements"]["bootstrap_samples"] = 200
        self.assertEqual(assess_results(synthetic_results(0.80), small)["status"], "PASS")
        self.assertEqual(assess_results(synthetic_results(1.05), small)["status"], "FAIL")

    def test_unified_entry_exposes_three_arm_protocol(self) -> None:
        args = reproduce.build_parser().parse_args(["neural-three-arm", "--dry-run"])
        self.assertEqual(args.handler, reproduce._neural_three_arm)
        self.assertEqual(args.protocol, PROTOCOL_PATH)


if __name__ == "__main__":
    unittest.main()

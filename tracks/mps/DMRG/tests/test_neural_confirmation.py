from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest

import numpy as np

import reproduce
from scripts.neural_confirmation import STAGES, hierarchical_summary, validate_protocol


PROTOCOL_PATH = Path("config/neural_confirmation_v1.json")


class NeuralConfirmationProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))

    def test_formal_protocol_is_locked_and_has_independent_streams(self) -> None:
        repeats = validate_protocol(self.protocol, "formal")
        self.assertEqual(len(repeats), 5)
        self.assertEqual(
            self.protocol["formal_requirements"]["ablation_chains_per_repeat"],
            32,
        )
        streams = [record[stage] for record in repeats for stage in STAGES]
        streams.extend(self.protocol["bootstrap_seeds"].values())
        self.assertEqual(len(streams), len(set(streams)))

    def test_formal_protocol_rejects_duplicate_streams(self) -> None:
        modified = copy.deepcopy(self.protocol)
        modified["repeat_seeds"][1]["validation"] = modified["repeat_seeds"][0][
            "validation"
        ]
        with self.assertRaisesRegex(ValueError, "must be unique"):
            validate_protocol(modified, "formal")

    def test_hierarchical_bootstrap_is_deterministic(self) -> None:
        groups = [
            np.array([-4.0, -3.0, -5.0, -4.0]),
            np.array([-2.0, -3.0, -2.5, -3.5]),
            np.array([-6.0, -5.0, -4.0, -5.0]),
        ]
        first = hierarchical_summary(
            groups, seed=91, samples=1000, multiplier=2.0
        )
        second = hierarchical_summary(
            groups, seed=91, samples=1000, multiplier=2.0
        )
        self.assertEqual(first, second)
        self.assertLess(first["upper_bound"], 0.0)

    def test_unified_entry_exposes_locked_confirmation(self) -> None:
        args = reproduce.build_parser().parse_args(
            ["neural-confirm", "--preset", "formal", "--dry-run"]
        )
        self.assertEqual(args.handler, reproduce._neural_confirm)
        self.assertEqual(args.protocol, PROTOCOL_PATH)


if __name__ == "__main__":
    unittest.main()

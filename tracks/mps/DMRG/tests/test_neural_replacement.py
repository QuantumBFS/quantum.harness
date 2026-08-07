from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import reproduce
from scripts.assess_neural_replacement_pilot import assess_metrics
from scripts.neural_challenge import fit_operator_projection
from scripts.neural_confirmation import STAGES, run_repeat, validate_protocol
from vmcrg_ref.operators import EVEN_SHAPES, OperatorBasis


FORMAL_PROTOCOL = Path("config/neural_replacement_formal_v1.json")


class NeuralReplacementTests(unittest.TestCase):
    def test_projection_recovers_known_couplings_with_vmcrg_sign(self) -> None:
        rng = np.random.default_rng(20260721)
        basis = OperatorBasis(9, EVEN_SHAPES)
        samples = 1000
        densities = np.empty((samples, len(EVEN_SHAPES)))
        for index in range(samples):
            spins = rng.choice(np.array([-1, 1], dtype=np.int8), size=(9, 9))
            densities[index] = basis.values(spins) / 81.0
        couplings = np.linspace(-0.03, 0.04, len(EVEN_SHAPES))
        # Synthetic V=-K.S gives H'=-V=K.S.
        parameters, rank, _ = fit_operator_projection(
            densities, densities @ couplings
        )
        self.assertEqual(rank, len(EVEN_SHAPES) + 1)
        np.testing.assert_allclose(parameters[1:], couplings, atol=1e-13, rtol=0.0)

    def test_unified_entry_exposes_pure_neural_replacement(self) -> None:
        args = reproduce.build_parser().parse_args(
            ["neural-replacement", "--preset", "pilot", "--dry-run"]
        )
        self.assertEqual(args.handler, reproduce._neural_replacement)
        self.assertEqual(args.preset, "pilot")
        self.assertEqual(
            args.fixed_point_map,
            Path(
                "output/reproduction/fixed_point_newton_v2/corrected_rg_v3/summary.json"
            ),
        )

    def test_go_no_go_requires_every_predeclared_direction(self) -> None:
        pure = {"max_equivalence_bound": 0.4, "excess_patch_tv_upper_bound": 0.3}
        zero = {"max_operator_bound": 0.5, "excess_patch_tv_upper_bound": 0.4}
        projection = {"fixed_point_linf_residual": 0.3}
        ablation = {"delta_omega_per_block_site_upper_bound": -0.01}
        correlation = {"paired_ratio_upper_bound": 0.8}
        passed = assess_metrics(pure, zero, projection, 0.4, ablation, correlation)
        self.assertEqual(passed["status"], "GO_FORMAL_PROTOCOL_DESIGN")
        projection["fixed_point_linf_residual"] = 0.5
        failed = assess_metrics(pure, zero, projection, 0.4, ablation, correlation)
        self.assertEqual(failed["status"], "NO_GO")

    def test_pure_formal_protocol_is_locked_and_independent(self) -> None:
        protocol = json.loads(FORMAL_PROTOCOL.read_text(encoding="utf-8"))
        repeats = validate_protocol(protocol, "formal")
        self.assertEqual(protocol["representation"], "pure_d4_z2_radius3_shell_neural_energy")
        self.assertEqual(protocol["formal_requirements"]["fixed_linear_bias_linf"], 0.0)
        self.assertEqual(protocol["formal_requirements"]["neural_radius"], 3)
        streams = [record[stage] for record in repeats for stage in STAGES]
        streams.extend(protocol["bootstrap_seeds"].values())
        self.assertEqual(len(streams), len(set(streams)))

    def test_pure_formal_protocol_rejects_nonzero_linear_bias(self) -> None:
        protocol = json.loads(FORMAL_PROTOCOL.read_text(encoding="utf-8"))
        modified = copy.deepcopy(protocol)
        modified["formal_requirements"]["fixed_linear_bias_linf"] = 1e-12
        with self.assertRaisesRegex(ValueError, "zero linear bias"):
            validate_protocol(modified, "formal")

    def test_unified_entry_exposes_pure_formal_confirmation(self) -> None:
        args = reproduce.build_parser().parse_args(
            ["neural-replacement-confirm", "--dry-run"]
        )
        self.assertEqual(args.handler, reproduce._neural_replacement_confirm)
        self.assertEqual(args.protocol, FORMAL_PROTOCOL)

    def test_confirmation_repeat_routes_to_pure_training_without_early_abort(self) -> None:
        seeds = {
            "repeat": 1,
            "model": 11,
            "optimizer": 12,
            "validation": 13,
            "projection": 14,
            "ablation": 15,
            "autocorrelation": 16,
        }
        with tempfile.TemporaryDirectory() as directory, patch(
            "scripts.neural_confirmation.train"
        ) as train_mock, patch(
            "scripts.neural_confirmation.validate"
        ) as validate_mock, patch(
            "scripts.neural_confirmation.project"
        ) as project_mock, patch(
            "scripts.neural_confirmation.ablate"
        ) as ablate_mock:
            run_repeat(
                Path(directory),
                "formal",
                Path("fixed.json"),
                seeds,
                32,
                "pure",
            )
        self.assertEqual(train_mock.call_args.kwargs["representation"], "pure")
        self.assertFalse(validate_mock.call_args.kwargs["enforce_formal_gate"])
        self.assertFalse(project_mock.call_args.kwargs["enforce_formal_gate"])
        self.assertFalse(ablate_mock.call_args.kwargs["enforce_formal_gate"])


if __name__ == "__main__":
    unittest.main()

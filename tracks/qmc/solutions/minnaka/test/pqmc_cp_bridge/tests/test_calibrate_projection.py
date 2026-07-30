#!/usr/bin/env python3
"""State-machine tests for adaptive TI selection and II confirmation."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from alf_statistics import EnergyEstimate  # noqa: E402
from calibrate_projection import BatchBudgetExhausted, calibrate  # noqa: E402


def estimate(
    mean: float,
    sigma: float,
    *,
    ready: bool,
    failure: str | None = None,
) -> EnergyEstimate:
    return EnergyEstimate(
        mean=mean,
        sigma_bin=sigma,
        sigma_replica=sigma / 2,
        sigma=sigma,
        retained_bins=36,
        replicas=6,
        loo_min=mean - sigma,
        loo_max=mean + sigma,
        mean_sign=1.0,
        negative_sign_bins=0,
        precision_ready=ready,
        hard_failure=failure,
        loo_stable=ready,
        max_green_precision=1.0e-12,
        statistical_precision_pass=ready,
        green_stability_pass=True,
        aggregated_bins=24,
    )


class FakeBackend:
    def __init__(self, sequences: dict[tuple[str, int], list[EnergyEstimate]]):
        self.sequences = {
            key: list(value) for key, value in sequences.items()
        }
        self.batches: dict[tuple[str, int], list[int]] = {}
        self.ensure_calls: list[tuple[str, int, int, int]] = []
        self.analyze_calls: list[tuple[str, int]] = []
        self.chains = 6
        self.initial_nbin = 7
        self.max_nbin: int | None = None
        self.max_new_batches: int | None = None
        self.nwrap = 5

    def ensure_batch(
        self, ensemble: str, theta: int, batch: int, nbin: int, nsweep: int
    ) -> None:
        key = (ensemble, theta)
        values = self.batches.setdefault(key, [])
        if batch not in values:
            if (
                self.max_new_batches is not None
                and len(self.ensure_calls) >= self.max_new_batches
            ):
                raise BatchBudgetExhausted("test budget exhausted")
            values.append(batch)
            self.ensure_calls.append((ensemble, theta, batch, nbin))

    def analyze(self, ensemble: str, theta: int) -> EnergyEstimate:
        self.analyze_calls.append((ensemble, theta))
        sequence = self.sequences[(ensemble, theta)]
        index = min(len(self.batches.get((ensemble, theta), [])) - 1,
                    len(sequence) - 1)
        return sequence[index]


class CalibrationStateMachineTest(unittest.TestCase):
    def run_case(self, sequences, *, include_ii=True):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        backend = FakeBackend(sequences)
        selected = calibrate(
            backend,
            results_root=root,
            trial_manifest_sha256="trial-hash",
            alf_binary_sha256="alf-hash",
            include_ii=include_ii,
        )
        return root, backend, selected

    def test_adds_statistics_before_revealing_and_selecting_theta_10(self) -> None:
        root, backend, selected = self.run_case({
            ("TI", 10): [
                estimate(-99.0, 0.02, ready=False),
                estimate(-13.621, 0.004, ready=True),
            ],
            ("II", 10): [estimate(-13.622, 0.004, ready=True)],
        })
        self.assertEqual(selected["theta_star"], 10)
        self.assertEqual(selected["status"], "target_reached")
        self.assertEqual(
            [call[2] for call in backend.ensure_calls if call[:2] == ("TI", 10)],
            [0, 1],
        )
        state = json.loads((root / "theta_scan.json").read_text())
        attempts = state["TI"]["10"]["attempts"]
        self.assertNotIn("mean", attempts[0])
        self.assertAlmostEqual(state["TI"]["10"]["estimate"]["mean"], -13.621)

    def test_advances_to_12_only_after_precise_energy_fails(self) -> None:
        _root, backend, selected = self.run_case({
            ("TI", 10): [estimate(-13.60, 0.004, ready=True)],
            ("TI", 12): [estimate(-13.622, 0.004, ready=True)],
            ("II", 12): [estimate(-13.622, 0.004, ready=True)],
        })
        self.assertEqual(selected["theta_star"], 12)
        self.assertIn(("TI", 10), backend.analyze_calls)
        self.assertIn(("TI", 12), backend.analyze_calls)

    def test_theta_20_fallback_waits_for_precision(self) -> None:
        sequences = {
            ("TI", theta): [estimate(-13.60, 0.004, ready=True)]
            for theta in (10, 12, 14, 16, 18)
        }
        sequences[("TI", 20)] = [
            estimate(-99.0, 0.02, ready=False),
            estimate(-13.60, 0.004, ready=True),
        ]
        sequences[("II", 20)] = [estimate(-13.622, 0.004, ready=True)]
        _root, backend, selected = self.run_case(sequences)
        self.assertEqual(selected["theta_star"], 20)
        self.assertEqual(selected["status"], "max_theta_fallback")
        calls = [
            call for call in backend.ensure_calls if call[:2] == ("TI", 20)
        ]
        self.assertEqual([call[2] for call in calls], [0, 1])

    def test_hard_failure_writes_no_selection(self) -> None:
        root, _backend, selected = self.run_case(
            {
                ("TI", 10): [
                    estimate(
                        -13.62, 0.004, ready=False, failure="negative sign"
                    )
                ]
            },
            include_ii=False,
        )
        self.assertIsNone(selected)
        self.assertFalse((root / "selected_projection.json").exists())

    def test_ii_addition_and_failure_status(self) -> None:
        _root, backend, selected = self.run_case({
            ("TI", 10): [estimate(-13.622, 0.004, ready=True)],
            ("II", 10): [
                estimate(-99.0, 0.02, ready=False),
                estimate(-13.60, 0.004, ready=True),
            ],
        })
        self.assertEqual(selected["status"], "reference_confirmation_failed")
        self.assertEqual(selected["ii_confirmation"]["mean"], -13.60)
        calls = [
            call for call in backend.ensure_calls if call[:2] == ("II", 10)
        ]
        self.assertEqual([call[2] for call in calls], [0, 1])

    def test_resume_reuses_frozen_theta_and_complete_selection(self) -> None:
        root, backend, selected = self.run_case({
            ("TI", 10): [estimate(-13.622, 0.004, ready=True)],
            ("II", 10): [estimate(-13.622, 0.004, ready=True)],
        })
        calls = len(backend.ensure_calls)
        resumed = calibrate(
            backend,
            results_root=root,
            trial_manifest_sha256="trial-hash",
            alf_binary_sha256="alf-hash",
        )
        self.assertEqual(resumed, selected)
        self.assertEqual(len(backend.ensure_calls), calls)

    def test_cluster_call_uses_bounded_initial_and_followup_bins(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        backend = FakeBackend({
            ("TI", 10): [
                estimate(-99.0, 0.02, ready=False),
                estimate(-13.622, 0.004, ready=True),
            ],
        })
        backend.chains = 64
        backend.initial_nbin = 3
        backend.max_nbin = 2
        selected = calibrate(
            backend,
            results_root=Path(temporary.name),
            trial_manifest_sha256="trial-hash",
            alf_binary_sha256="alf-hash",
            include_ii=False,
        )
        self.assertEqual(selected["theta_star"], 10)
        self.assertEqual(
            [call[3] for call in backend.ensure_calls],
            [3, 2],
        )

    def test_cluster_call_stops_cleanly_after_one_new_batch(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        backend = FakeBackend({
            ("TI", 10): [estimate(-99.0, 0.02, ready=False)],
        })
        backend.chains = 64
        backend.initial_nbin = 3
        backend.max_nbin = 3
        backend.max_new_batches = 1
        with self.assertRaises(BatchBudgetExhausted):
            calibrate(
                backend,
                results_root=root,
                trial_manifest_sha256="trial-hash",
                alf_binary_sha256="alf-hash",
                include_ii=False,
            )
        state = json.loads((root / "theta_scan.json").read_text())
        self.assertEqual(state["TI"]["10"]["batches"][0]["nbin"], 3)
        self.assertNotIn("mean", state["TI"]["10"]["attempts"][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)

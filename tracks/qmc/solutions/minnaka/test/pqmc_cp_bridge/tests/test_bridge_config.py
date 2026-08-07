#!/usr/bin/env python3
"""Contract tests for the ALF projection calibration."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from bridge_config import (  # noqa: E402
    approved_config,
    energy_ok,
    ltrot,
    theta_candidates,
    validate_config,
)


class BridgeConfigTest(unittest.TestCase):
    def test_fixed_projection_grid(self) -> None:
        cfg = approved_config()
        self.assertEqual(theta_candidates(), (10, 12, 14, 16, 18, 20))
        self.assertEqual(
            [ltrot(theta, cfg) for theta in theta_candidates()],
            [420, 500, 580, 660, 740, 820],
        )

    def test_energy_window_is_absolute_005(self) -> None:
        cfg = approved_config()
        self.assertTrue(energy_ok(cfg.exact_energy + 0.005, cfg))
        self.assertTrue(energy_ok(cfg.exact_energy - 0.005, cfg))
        self.assertFalse(energy_ok(cfg.exact_energy + 0.0050001, cfg))

    def test_rejects_unapproved_model_variants(self) -> None:
        cfg = approved_config()
        invalid = (
            replace(cfg, pbc_x=False),
            replace(cfg, pbc_y=False),
            replace(cfg, n_up=7),
            replace(cfg, n_down=7),
            replace(cfg, dt=0.0),
            replace(cfg, hs_transform="charge"),
        )
        for candidate in invalid:
            with self.subTest(candidate=candidate):
                with self.assertRaises(ValueError):
                    validate_config(candidate)

    def test_ltrot_rejects_noninteger_slice_count(self) -> None:
        cfg = replace(approved_config(), dt=0.08)
        with self.assertRaises(ValueError):
            ltrot(10, cfg)


if __name__ == "__main__":
    unittest.main(verbosity=2)

#!/usr/bin/env python3
"""Population-combing genealogy and reference-free fragility tests."""

from __future__ import annotations

import math
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pc_fragility import (  # noqa: E402
    comb_parent_indices,
    lineage_fragility,
    propagate_immutable_tags,
    freeze_growth_reference,
    static_fragility,
    assign_complete_stratum,
)


class PcFragilityTest(unittest.TestCase):
    def test_static_reference_is_free_of_common_eref_shift(self) -> None:
        reference = freeze_growth_reference(
            [[1.0, 2.0], [1.2, 1.8]],
            [[0.3, 0.4], [0.5, 0.2]],
        )
        shifted = freeze_growth_reference(
            [[2.0, 3.0], [2.2, 2.8]],
            [[1.3, 1.4], [1.5, 1.2]],
        )
        for value, shifted_value in zip(reference, shifted):
            self.assertAlmostEqual(value, shifted_value, places=14)
        first = static_fragility([0.0, -1.0, 0.5], reference)
        second = static_fragility([9.0, 8.0, 9.5], reference)
        self.assertEqual(first["min_interval"], second["min_interval"])
        self.assertAlmostEqual(
            first["min_log_a_static"],
            second["min_log_a_static"],
            places=14,
        )
        self.assertAlmostEqual(
            first["recovery_after_valley"],
            second["recovery_after_valley"],
            places=14,
        )

    def test_complete_strata_have_fixed_priority(self) -> None:
        self.assertEqual(assign_complete_stratum(
            support="dead", proposal_low=True,
            prefix_high=True, pc_fragile=True,
        ), "dead_support")
        self.assertEqual(assign_complete_stratum(
            support="alive", proposal_low=False,
            prefix_high=False, pc_fragile=True,
        ), "alive_pc_fragile_not_previous")

    def test_fixed_combing_parent_tree(self) -> None:
        parents, offspring = comb_parent_indices(
            [0.2, 0.8, 2.0, 1.0], u0=0.25
        )
        self.assertEqual(len(parents), 4)
        self.assertEqual(sum(offspring), 4)
        self.assertEqual(
            offspring,
            [parents.count(index) for index in range(4)],
        )
        self.assertEqual(parents, [1, 2, 2, 3])

    def test_late_blooming_extinct_lineage_is_not_resurrected(self) -> None:
        # Lineage 10 has a deep realized interval and no descendants after
        # the first comb; a later recovery belongs to lineage 20.
        history = {
            10: [-8.0],
            20: [-0.1, 3.0],
        }
        descendants = {10: 0, 20: 4}
        result = lineage_fragility(history, descendants)
        self.assertLess(result[10]["retention_proxy"], 1.0e-3)
        self.assertEqual(result[10]["descendant_survival"], 0)
        self.assertEqual(result[10]["largest_recovery_after_valley"], 0.0)
        self.assertGreater(result[20]["largest_recovery_after_valley"], 0.0)

    def test_tags_are_assigned_before_combing_and_only_inherited(self) -> None:
        tags = [False, True, False, False]
        parents = [0, 0, 2, 2]
        inherited = propagate_immutable_tags(tags, parents)
        self.assertEqual(inherited, [False, False, False, False])
        tags = [True, False, False, False]
        self.assertEqual(
            propagate_immutable_tags(tags, parents),
            [True, True, False, False],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

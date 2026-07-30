#!/usr/bin/env python3
"""Preregistered target selection for no-PC proposal-prefix checks."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_proposal_check import select_targets  # noqa: E402


def row(index: int, category: str) -> dict[str, object]:
    data = {
        "sample_id": 1000 + index,
        "ensemble": "TI",
        "chain": index % 3,
        "alive": "1",
        "numerically_ambiguous": "False",
        "proposal_risk": "regular",
        "prefix_risk": "regular",
        "near_node_risk": "regular",
        "log_q_prop": -float(index),
        "prefix_barrier": float(index),
        "near_node_count": index,
    }
    if category == "low_final_q":
        data["proposal_risk"] = "lowest_1pct"
    elif category == "deep_prefix":
        data["prefix_risk"] = "highest_1pct"
    elif category == "near_node":
        data["near_node_risk"] = "highest_1pct"
    return data


class ProposalCheckTest(unittest.TestCase):
    def test_selects_five_disjoint_targets_per_preregistered_category(self) -> None:
        rows = []
        for category_index, category in enumerate(
            ("regular", "low_final_q", "deep_prefix", "near_node")
        ):
            rows.extend(
                row(category_index * 10 + index, category)
                for index in range(6)
            )
        selected = select_targets(rows, per_category=5)
        self.assertEqual(len(selected), 20)
        self.assertEqual(len({item["sample_id"] for item in selected}), 20)
        self.assertEqual(
            {category: sum(item["target_category"] == category
                           for item in selected)
             for category in (
                 "regular", "low_final_q", "deep_prefix", "near_node"
             )},
            {
                "regular": 5,
                "low_final_q": 5,
                "deep_prefix": 5,
                "near_node": 5,
            },
        )

    def test_rejects_non_training_or_ambiguous_rows(self) -> None:
        rows = [row(index, "regular") for index in range(20)]
        rows[0]["chain"] = 5
        rows[1]["numerically_ambiguous"] = "True"
        with self.assertRaisesRegex(ValueError, "insufficient"):
            select_targets(rows, per_category=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)

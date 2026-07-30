import pathlib
import sys
import unittest

import numpy as np
import pandas as pd


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pattern_analysis.mechanisms import (  # noqa: E402
    attribute_events,
    classify_overlap,
    join_critical_mask_predictions,
    summarize_recovery,
)


def synthetic_steps():
    rows = []
    paths = {
        "case_1": {
            "role": "case",
            "cumulative_log_w": [-0.1, -2.0, -1.0, 2.0],
            "cumulative_log_q": [-0.2, -2.5, -2.8, -3.0],
            "sigma_min_up": [0.6, 0.01, 0.2, 0.6],
            "sigma_min_down": [0.7, 0.5, 0.5, 0.7],
            "log_normalized_overlap": [-0.1, -5.0, -2.0, -0.1],
            "overlap_after": [0.9, 0.01, 0.2, 1.2],
            "q_selected": [1.0, 0.01, 0.4, 1.0],
            "c_factor": [0.9, 0.2, 1.5, 2.0],
        },
        "control_1": {
            "role": "control",
            "cumulative_log_w": [-0.1, -0.2, -0.3, -0.4],
            "cumulative_log_q": [-0.2, -0.4, -0.6, -0.8],
            "sigma_min_up": [0.6, 0.5, 0.5, 0.6],
            "sigma_min_down": [0.7, 0.6, 0.6, 0.7],
            "log_normalized_overlap": [-0.1, -0.2, -0.3, -0.4],
            "overlap_after": [0.9, 0.8, 0.7, 0.6],
            "q_selected": [1.0, 0.4, 0.4, 1.0],
            "c_factor": [0.9, 0.9, 0.9, 0.9],
        },
    }
    for path_id, values in paths.items():
        previous_q = 0.0
        previous_w = 0.0
        for event_index in range(4):
            cumulative_q = values["cumulative_log_q"][event_index]
            cumulative_w = values["cumulative_log_w"][event_index]
            rows.append(
                {
                    "path_id": path_id,
                    "role": values["role"],
                    "case_id": 1,
                    "trial": "rhf_x",
                    "weight_bin": "important",
                    "event_index": event_index,
                    "slice": event_index // 2,
                    "kind": "site" if event_index in (1, 2) else "half_k",
                    "cumulative_log_q": cumulative_q,
                    "cumulative_log_w": cumulative_w,
                    "delta_log_q": cumulative_q - previous_q,
                    "delta_log_w": cumulative_w - previous_w,
                    "sigma_min_up": values["sigma_min_up"][event_index],
                    "sigma_min_down": values["sigma_min_down"][event_index],
                    "log_normalized_overlap": values[
                        "log_normalized_overlap"
                    ][event_index],
                    "log_orbital_scale": 0.0,
                    "overlap_after": values["overlap_after"][event_index],
                    "q_selected": values["q_selected"][event_index],
                    "c_factor": values["c_factor"][event_index],
                    "ratio_residual": 1e-13,
                    "field": 1,
                    "predicted_low_field": (
                        1 if event_index == 1 else -1
                    ),
                }
            )
            previous_q = cumulative_q
            previous_w = cumulative_w
    return pd.DataFrame(rows)


class RecoveryTest(unittest.TestCase):
    def test_one_event_recovery_is_distinguished_from_repeated_penalties(self):
        one = summarize_recovery(np.array([-0.1, -3.0, 3.2, 0.0]))
        repeated = summarize_recovery(np.array([-0.8, -0.8, -0.8, 2.5]))

        self.assertGreater(one["recovery_concentration"], 0.5)
        self.assertLess(repeated["penalty_concentration"], 0.5)

    def test_subspace_and_scale_failures_are_separate(self):
        self.assertEqual(
            classify_overlap(min_sigma=1e-8, log_scale=0.0),
            "near_orthogonal",
        )
        self.assertEqual(
            classify_overlap(min_sigma=0.4, log_scale=-20.0),
            "orbital_scale",
        )


class AttributionTest(unittest.TestCase):
    def test_near_orthogonal_bottleneck_and_recovery_are_attributed(self):
        selection = pd.DataFrame(
            [
                {
                    "path_id": "case_1",
                    "trial": "rhf_x",
                    "role": "case",
                    "case_id": 1,
                    "weight_bin": "important",
                },
                {
                    "path_id": "control_1",
                    "trial": "rhf_x",
                    "role": "control",
                    "case_id": 1,
                    "weight_bin": "important",
                },
            ]
        )

        summaries, annotated = attribute_events(selection, synthetic_steps())
        summary = summaries.iloc[0]

        self.assertEqual(summary["path_id"], "case_1")
        self.assertEqual(summary["first_low_w_step"], 1)
        self.assertEqual(summary["min_sigma_step"], 1)
        self.assertEqual(summary["recovery_step"], 3)
        self.assertEqual(summary["max_positive_weight_step"], 3)
        self.assertEqual(summary["max_negative_weight_step"], 1)
        self.assertAlmostEqual(summary["max_positive_delta_log_w"], 3.0)
        self.assertAlmostEqual(summary["max_negative_delta_log_w"], -1.9)
        self.assertAlmostEqual(summary["minimum_q_selected"], 0.01)
        self.assertAlmostEqual(summary["minimum_c_factor"], 0.2)
        self.assertTrue(summary["min_q_predicted_low_match"])
        self.assertTrue(summary["min_sigma_predicted_low_match"])
        self.assertAlmostEqual(summary["min_q_delta_log_w"], -1.9)
        self.assertAlmostEqual(summary["max_recovery_delta_log_w"], 3.0)
        self.assertTrue(summary["near_orthogonal"])
        self.assertEqual(summary["mechanism"], "near_orthogonal_recovery")
        event = annotated.loc[
            (annotated.path_id == "case_1")
            & (annotated.event_index == 1)
        ].iloc[0]
        self.assertLess(event["paired_delta_log_w"], 0.0)

    def test_half_kinetic_factor_is_not_classified_as_site_branching(self):
        steps = synthetic_steps()
        case = steps["path_id"] == "case_1"
        control = steps.loc[steps["path_id"] == "control_1"].reset_index()
        for column in (
            "sigma_min_up",
            "sigma_min_down",
            "log_normalized_overlap",
            "overlap_after",
            "q_selected",
        ):
            steps.loc[case, column] = control[column].to_numpy()
        steps.loc[case, "c_factor"] = [0.01, 0.9, 0.9, 0.9]
        steps.loc[case, "cumulative_log_w"] = [-2.0, -1.9, -1.8, -1.7]
        steps.loc[case, "delta_log_w"] = [-2.0, 0.1, 0.1, 0.1]
        selection = pd.DataFrame(
            [
                {
                    "path_id": "case_1",
                    "trial": "rhf_x",
                    "role": "case",
                    "case_id": 1,
                    "weight_bin": "important",
                },
                {
                    "path_id": "control_1",
                    "trial": "rhf_x",
                    "role": "control",
                    "case_id": 1,
                    "weight_bin": "important",
                },
            ]
        )

        summaries, _ = attribute_events(selection, steps)
        summary = summaries.iloc[0]

        self.assertFalse(summary["small_c_event"])
        self.assertTrue(summary["half_k_contraction"])
        self.assertEqual(summary["mechanism"], "half_kinetic_contraction")

    def test_critical_slices_receive_exhaustive_mask_predictions(self):
        summaries, _ = attribute_events(
            pd.DataFrame(
                [
                    {
                        "path_id": "case_1",
                        "trial": "rhf_x",
                        "role": "case",
                        "case_id": 1,
                        "weight_bin": "important",
                    },
                    {
                        "path_id": "control_1",
                        "trial": "rhf_x",
                        "role": "control",
                        "case_id": 1,
                        "weight_bin": "important",
                    },
                ]
            ),
            synthetic_steps(),
        )
        masks = pd.DataFrame(
            [
                {
                    "path_id": "case_1",
                    "slice": 0,
                    "realized_rank": 2,
                    "hamming_best": 1,
                    "hamming_greedy": 0,
                    "realized_mask": 9,
                    "best_mask": 6,
                    "greedy_mask": 9,
                },
                {
                    "path_id": "case_1",
                    "slice": 1,
                    "realized_rank": 1,
                    "hamming_best": 0,
                    "hamming_greedy": 0,
                    "realized_mask": 6,
                    "best_mask": 6,
                    "greedy_mask": 6,
                },
            ]
        )

        joined = join_critical_mask_predictions(summaries, masks).iloc[0]

        self.assertEqual(joined["onset_realized_rank"], 2)
        self.assertEqual(joined["recovery_realized_rank"], 1)


if __name__ == "__main__":
    unittest.main()

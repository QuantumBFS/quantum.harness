import math
import pathlib
import sys
import unittest

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pattern_analysis.patterns import (  # noqa: E402
    canonical_path,
    canonical_mask,
    decode_masks,
    mask_class,
    site_permutations_2x2,
    spatial_components,
    temporal_features,
    trial_preserving_permutations_2x2,
)
from pattern_analysis.statistics import (  # noqa: E402
    benjamini_hochberg,
    bit_itemset_table,
    connected_itemset_table,
    contingency_statistics,
    count_adjacent_pairs,
    fourth_order_parity_table,
    motif_tables,
)


class SlicePatternTest(unittest.TestCase):
    def test_decode_masks_reverses_chronological_bits_to_site_bits(self):
        config_id = np.array([0b11000100], dtype=np.uint64)

        masks = decode_masks(config_id, slices=2, sites=4)

        np.testing.assert_array_equal(
            masks, np.array([[0b0011, 0b0010]], dtype=np.uint8)
        )

    def test_all_masks_have_one_mutually_exclusive_class(self):
        labels = [mask_class(mask) for mask in range(16)]

        self.assertEqual(labels.count("uniform_plus"), 1)
        self.assertEqual(labels.count("uniform_minus"), 1)
        self.assertEqual(
            sum(label.startswith("one_defect") for label in labels), 8
        )
        self.assertEqual(sum(label.startswith("neel") for label in labels), 2)
        self.assertEqual(
            sum(label.startswith("x_stripe") for label in labels), 2
        )
        self.assertEqual(
            sum(label.startswith("y_stripe") for label in labels), 2
        )

    def test_neel_mask_has_only_staggered_component(self):
        components = spatial_components(0b1001)

        self.assertEqual(
            components,
            {"uniform": 0, "staggered": 4, "x_stripe": 0, "y_stripe": 0},
        )

    def test_full_lattice_orbit_rotates_x_stripe_to_y_stripe(self):
        transforms = site_permutations_2x2()

        self.assertEqual(
            canonical_mask(0b0101, transforms),
            canonical_mask(0b0011, transforms),
        )
        for mask in range(16):
            canonical = canonical_mask(mask, transforms)
            self.assertEqual(
                canonical_mask(canonical, transforms), canonical
            )

    def test_canonical_path_uses_one_spatial_transform_for_all_slices(self):
        transforms = site_permutations_2x2()
        x_stripe_path = 0b10101010
        y_stripe_path = 0b11001100

        self.assertEqual(
            canonical_path(x_stripe_path, 2, transforms),
            canonical_path(y_stripe_path, 2, transforms),
        )

    def test_rhf_x_preserving_subgroup_does_not_merge_stripe_axes(self):
        transforms = trial_preserving_permutations_2x2("rhf_x")

        self.assertNotEqual(
            canonical_mask(0b0101, transforms),
            canonical_mask(0b0011, transforms),
        )

    def test_temporal_features_detect_repeat_and_global_flip(self):
        masks = np.array([[0b0011, 0b0011, 0b1100, 0b1100]], dtype=np.uint8)

        features = temporal_features(masks)

        self.assertEqual(features["hamming_previous"].tolist(), [-1, 0, 4, 0])
        self.assertEqual(features["repeat_previous"].tolist(), [False, True, False, True])
        self.assertEqual(
            features["global_flip_previous"].tolist(),
            [False, False, True, False],
        )
        self.assertEqual(features["class_run_length"].tolist(), [1, 2, 3, 4])


class MotifStatisticsTest(unittest.TestCase):
    def test_enrichment_counts_inserted_repeated_mask(self):
        cases = np.array([[3, 3, 3], [3, 3, 4], [3, 3, 5]], dtype=np.uint8)
        controls = np.array(
            [[1, 2, 4], [4, 5, 6], [7, 8, 9]], dtype=np.uint8
        )

        table = count_adjacent_pairs(cases, controls)
        row = table.loc[
            (table["mask_a"] == 3) & (table["mask_b"] == 3)
        ].iloc[0]

        self.assertEqual(row["case_count"], 4)
        self.assertEqual(row["control_count"], 0)
        self.assertGreater(row["odds_ratio"], 1.0)

    def test_haldane_corrected_odds_ratio_is_finite(self):
        result = contingency_statistics(10, 0, 2, 8)

        self.assertTrue(math.isfinite(result["odds_ratio"]))
        self.assertGreater(result["odds_ratio"], 1.0)
        self.assertGreater(result["risk_difference"], 0.0)

    def test_bh_adjustment_is_monotone_in_rank(self):
        adjusted = benjamini_hochberg(np.array([0.04, 0.001, 0.02]))

        np.testing.assert_allclose(adjusted, [0.04, 0.003, 0.03])

    def test_fourth_order_parity_recovers_even_case_rule(self):
        cases = np.array(
            [0b0000, 0b0011, 0b0101, 0b1001, 0b1111], dtype=np.uint64
        )
        controls = np.array(
            [0b0001, 0b0010, 0b0100, 0b1000], dtype=np.uint64
        )

        table = fourth_order_parity_table(cases, controls, bits=4)
        row = table.iloc[0]

        self.assertEqual(row["subset_mask"], 0b1111)
        self.assertEqual(row["case_positive"], 5)
        self.assertEqual(row["control_positive"], 0)
        self.assertGreater(row["odds_ratio"], 1.0)

    def test_motif_tables_include_all_single_pair_and_triple_codes(self):
        cases = np.array([[3, 3, 3], [4, 5, 6]], dtype=np.uint8)
        controls = np.array([[1, 2, 3], [7, 8, 9]], dtype=np.uint8)

        tables = motif_tables(cases, controls)

        self.assertEqual(len(tables["slice"]), 16)
        self.assertEqual(len(tables["pair"]), 256)
        self.assertEqual(len(tables["triple"]), 4096)
        repeated = tables["triple"].loc[
            (tables["triple"].mask_a == 3)
            & (tables["triple"].mask_b == 3)
            & (tables["triple"].mask_c == 3)
        ].iloc[0]
        self.assertEqual(repeated["case_count"], 1)

    def test_bit_itemsets_include_inserted_pair_rule(self):
        cases = np.array([0b11, 0b11], dtype=np.uint64)
        controls = np.array([0b00, 0b01], dtype=np.uint64)

        table = bit_itemset_table(cases, controls, bits=2, max_order=2)
        pair = table.loc[table["subset_mask"] == 0b11].iloc[0]

        self.assertEqual(pair["case_count"], 2)
        self.assertEqual(pair["control_count"], 0)
        self.assertEqual(pair["chronological_positions"], "0,1")

    def test_connected_itemsets_follow_space_time_edges(self):
        cases = np.array([0b1100, 0b1100], dtype=np.uint64)
        controls = np.array([0b0000, 0b0000], dtype=np.uint64)

        table = connected_itemset_table(
            cases,
            controls,
            slices=1,
            sites=4,
            lx=2,
            ly=2,
            max_size=2,
            min_support=0.0,
        )
        pair = table.loc[table["chronological_positions"] == "0,1"].iloc[0]

        self.assertEqual(pair["case_count"], 2)
        self.assertEqual(pair["control_count"], 0)


if __name__ == "__main__":
    unittest.main()

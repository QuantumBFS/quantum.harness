#!/usr/bin/env python3

import unittest
from unittest.mock import patch

import bdd_sat_occam_fixed
import bdd_sat_occam_v2


class FixedOrderWrapperTests(unittest.TestCase):
    def test_forwards_one_valid_order(self) -> None:
        captured = {}

        def fake_main(arguments):
            captured["arguments"] = arguments
            captured["orders"] = bdd_sat_occam_v2.base_orders(2)
            captured["chosen"] = bdd_sat_occam_v2.choose_order([], 2, seed=42)
            return 7

        with patch.object(bdd_sat_occam_v2, "main", fake_main):
            status = bdd_sat_occam_fixed.main(
                [
                    "--fixed-order",
                    "0,2,1,3",
                    "--fixed-order-name",
                    "lsb_interleaved",
                    "--instance",
                    "practice-add-n4",
                ]
            )
        self.assertEqual(status, 7)
        self.assertEqual(captured["arguments"], ["--instance", "practice-add-n4"])
        self.assertEqual(captured["orders"], {"lsb_interleaved": [0, 2, 1, 3]})
        self.assertEqual(captured["chosen"][0], [0, 2, 1, 3])


if __name__ == "__main__":
    unittest.main(verbosity=2)

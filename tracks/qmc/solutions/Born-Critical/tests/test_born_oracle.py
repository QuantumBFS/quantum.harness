import math
import unittest

import numpy as np

from borncritical.born_oracle import (
    enumerate_born_distribution,
    sample_by_exact_conditionals,
    vacuum_wilson_loop,
)
from borncritical.conventions import ISING_K_CRITICAL


class BornOracleTests(unittest.TestCase):
    def test_exact_born_distribution_is_normalized_and_in_vacuum_sector(
        self,
    ) -> None:
        outcomes = enumerate_born_distribution(
            nx=2,
            ny=1,
            coupling=ISING_K_CRITICAL,
            vacuum_only=True,
            max_variables=8,
        )
        self.assertGreater(len(outcomes), 1)
        self.assertAlmostEqual(
            sum(outcome.probability for outcome in outcomes), 1.0
        )
        self.assertTrue(
            all(vacuum_wilson_loop(outcome.fields) == 1 for outcome in outcomes)
        )
        self.assertTrue(all(outcome.probability >= 0.0 for outcome in outcomes))

    def test_exact_conditional_sampler_returns_consistent_log_probability(
        self,
    ) -> None:
        outcomes = enumerate_born_distribution(
            nx=2,
            ny=1,
            coupling=ISING_K_CRITICAL,
            vacuum_only=True,
            max_variables=8,
        )
        rng = np.random.default_rng(20260727)
        sampled, log_probability = sample_by_exact_conditionals(outcomes, rng)
        self.assertAlmostEqual(
            log_probability, math.log(sampled.probability), delta=2e-12
        )

    def test_distribution_guard_rejects_exponential_explosion(self) -> None:
        with self.assertRaisesRegex(ValueError, "exceeds max_variables"):
            enumerate_born_distribution(
                nx=3,
                ny=2,
                coupling=ISING_K_CRITICAL,
                max_variables=4,
            )


if __name__ == "__main__":
    unittest.main()

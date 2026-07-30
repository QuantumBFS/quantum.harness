from __future__ import annotations

import pytest

from trottercert.cubic_field import fourth_order_suzuki_cubic_stages
from trottercert.cubic_local import exact_log_e5_density
from trottercert.refined_error import certified_d4_cell_coefficients
from trottercert.rigorous_fourth import fourth_order_suzuki_interval_stages


@pytest.mark.slow
def test_exact_e5_is_enclosed_by_existing_interval_coefficients() -> None:
    stages = fourth_order_suzuki_cubic_stages(4)
    _, exact = exact_log_e5_density(stages)
    interval_stages, root = fourth_order_suzuki_interval_stages(4)
    expected = certified_d4_cell_coefficients(interval_stages)
    observed = {
        pauli: value.enclose(root) * 5
        for pauli, value in exact.items()
    }
    # The interval implementation can retain ghost terms whose exact cubic
    # coefficients cancel to zero after dependency information is restored.
    assert set(observed) <= set(expected)
    assert all(
        expected[pauli].lower
        <= observed[pauli].lower
        <= observed[pauli].upper
        <= expected[pauli].upper
        for pauli in observed
    )

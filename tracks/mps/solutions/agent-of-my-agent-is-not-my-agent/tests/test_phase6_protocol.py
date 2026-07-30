from __future__ import annotations

import numpy as np
import pytest

from lrtfim.phase6_protocol import (
    build_run_spec,
    locked_gamma_grid,
    symmetric_extended_gamma_grid,
)


def test_locked_gamma_grid_has_identical_24_values_for_every_size() -> None:
    coarse = np.arange(1.540, 1.580 + 0.0025, 0.005)
    fine = np.arange(1.552, 1.570 + 0.0005, 0.001)
    expected = np.unique(np.round(np.r_[coarse, fine], 12))

    np.testing.assert_array_equal(locked_gamma_grid(), expected)
    assert len(expected) == 24
    spec = build_run_spec(
        sigma=1.75,
        fit_id="fit-sha256",
        output_dir="results/phase6",
    )
    assert spec["sizes"] == [32, 64, 128, 256]
    assert spec["settings"]["full_scan_chi"] == 128
    for length in spec["sizes"]:
        assert [
            cell["gamma"] for cell in spec["cells"] if cell["length"] == length
        ] == pytest.approx(expected)


def test_gamma_window_extension_is_symmetric_and_rejects_one_sided_request() -> None:
    extended = symmetric_extended_gamma_grid(extension=0.010)
    assert extended["coarse"][0] == pytest.approx(1.530)
    assert extended["coarse"][-1] == pytest.approx(1.590)
    assert extended["fine"][0] == pytest.approx(1.542)
    assert extended["fine"][-1] == pytest.approx(1.580)
    with pytest.raises(ValueError, match="symmetric"):
        symmetric_extended_gamma_grid(extension=(0.0, 0.010))

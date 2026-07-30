from __future__ import annotations

import pandas as pd

from oracle.majorana_report import first_negative_rows, summarize_angles


def _rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "cell_id": "a",
                "block_size": 2,
                "angle": 0.0,
                "scale": 1.0,
                "depth": 2,
                "status": "success",
                "negative": 0,
                "complex": 0,
                "uncertain": 0,
                "max_structure_residual": 1e-15,
                "max_common_reality_residual": 2e-15,
                "max_square_identity_residual": 3e-15,
                "max_reliable_square_identity_residual": 3e-15,
                "unreliable_determinant_checks": 0,
                "min_cancellation_ratio": 0.2,
                "samples_per_cell": 10,
            },
            {
                "cell_id": "b",
                "block_size": 2,
                "angle": 0.4,
                "scale": 1.0,
                "depth": 4,
                "status": "success",
                "negative": 2,
                "complex": 0,
                "uncertain": 0,
                "max_structure_residual": 2e-15,
                "max_common_reality_residual": 3e-15,
                "max_square_identity_residual": 4e-15,
                "max_reliable_square_identity_residual": 4e-15,
                "unreliable_determinant_checks": 0,
                "min_cancellation_ratio": 0.1,
                "samples_per_cell": 10,
            },
        ]
    )


def test_majorana_angle_summary_counts_negative_weights() -> None:
    summary = summarize_angles(_rows(), samples_per_cell=10)
    failing = summary[summary["angle"] == 0.4].iloc[0]
    assert failing["negative"] == 2
    assert failing["negative_rate"] == 0.2


def test_first_negative_depth_marks_survivors_and_failures() -> None:
    first = first_negative_rows(_rows())
    survivor = first[first["angle"] == 0.0].iloc[0]
    failure = first[first["angle"] == 0.4].iloc[0]
    assert pd.isna(survivor["first_negative_depth"])
    assert failure["first_negative_depth"] == 4

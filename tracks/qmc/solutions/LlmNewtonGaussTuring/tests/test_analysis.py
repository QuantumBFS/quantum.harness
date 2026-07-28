# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Deterministic validation for the Stage 4 statistics pipeline."""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "analyze_stage4", ROOT / "tools" / "analyze_stage4.py"
)
ANALYSIS = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ANALYSIS)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expect_value_error(function, message: str) -> None:
    try:
        function()
    except ValueError:
        return
    raise AssertionError(message)


HEADER = (
    "lattice,geometry_version,L,N,Nb,h,beta,seed,bin,n_thermal,n_bins,"
    "sweeps_per_bin,E,spacetime_m2,spacetime_m4,S0,Sq,q_norm,q_count\n"
)


def valid_rows() -> list[str]:
    rows = []
    fields = (3.02, 3.06)
    for size in (4, 6):
        for field_index, field in enumerate(fields):
            for replica in (1, 2):
                seed = size * 10000 + field_index * 100 + replica
                for bin_index in (0, 1):
                    rows.append(
                        f"square,square-v1,{size},{size * size},{2 * size * size},"
                        f"{field:.17g},{size / field:.17g},{seed},{bin_index},10,2,5,"
                        f"-1.0,0.2,0.08,0.2,0.1,{2 * np.pi / size:.17g},4\n"
                    )
    return rows


def write_csv(path: Path, rows: list[str], header: str = HEADER) -> None:
    path.write_text(header + "".join(rows), encoding="utf-8")


def test_input_validation(directory: Path) -> None:
    valid = directory / "valid.csv"
    rows = valid_rows()
    write_csv(valid, rows)
    chains, metadata = ANALYSIS.load_bins(valid)
    require(len(chains) == 8, "valid rectangular input should contain eight chains")
    require(len(metadata) == 4, "valid rectangular input should contain four cells")

    missing_bin = directory / "missing_bin.csv"
    write_csv(missing_bin, rows[:-1])
    expect_value_error(
        lambda: ANALYSIS.load_bins(missing_bin),
        "a chain with a missing bin must be rejected",
    )

    reused_seed = directory / "reused_seed.csv"
    first_seed = rows[0].split(",")[7]
    altered = rows.copy()
    columns = altered[8].split(",")
    columns[7] = first_seed
    altered[8] = ",".join(columns)
    write_csv(reused_seed, altered)
    expect_value_error(
        lambda: ANALYSIS.load_bins(reused_seed),
        "a seed reused across parameter cells must be rejected",
    )

    incomplete_grid = directory / "incomplete_grid.csv"
    write_csv(incomplete_grid, [row for row in rows if not row.startswith("square,square-v1,6,36,72,3.06")])
    expect_value_error(
        lambda: ANALYSIS.load_bins(incomplete_grid),
        "an incomplete (L,h) rectangle must be rejected",
    )

    missing_column = directory / "missing_column.csv"
    write_csv(missing_column, rows, HEADER.replace(",q_count", ""))
    expect_value_error(
        lambda: ANALYSIS.load_bins(missing_column),
        "a missing metadata column must be rejected",
    )


def test_scaling_fit() -> None:
    sizes = np.repeat(np.asarray([6.0, 8.0, 10.0, 12.0]), 7)
    fields = np.tile(np.linspace(4.73, 4.81, 7), 4)
    true_hc = 4.76811
    coefficients = np.asarray([0.62, 0.012, -0.00015, 0.04, 0.003])
    values = ANALYSIS.design_matrix(sizes, fields, true_hc) @ coefficients
    errors = np.full_like(values, 0.002)
    fitted_hc, chi2, dof, _, rank, condition = ANALYSIS.fit_hc(
        sizes, fields, values, errors
    )
    require(abs(fitted_hc - true_hc) < 2e-6, "synthetic critical field was not recovered")
    require(chi2 < 1e-12, "exact synthetic fit should have zero residual")
    require(dof == len(values) - len(coefficients) - 1, "fit degrees of freedom are wrong")
    require(rank == len(coefficients), "synthetic design should have full rank")
    require(np.isfinite(condition), "synthetic design condition number must be finite")

    degenerate_sizes = np.full(12, 8.0)
    degenerate_fields = np.linspace(4.74, 4.80, 12)
    expect_value_error(
        lambda: ANALYSIS.fit_hc(
            degenerate_sizes,
            degenerate_fields,
            np.linspace(0.5, 0.6, 12),
            np.full(12, 0.01),
        ),
        "rank-deficient scaling design must be rejected",
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        test_input_validation(Path(directory))
    test_scaling_fit()
    print("All Stage 4 analysis tests passed.")


if __name__ == "__main__":
    main()

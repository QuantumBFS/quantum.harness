import csv

import numpy as np
import pytest

from qh147.checkpoint import save_checkpoint
from qh147.contract import ThermodynamicPoint
from qh147.measure import local_polynomial_derivative, measure_chain
from qh147.pepo import FinitePEPO


class FakeContractor:
    def thermodynamic_point(self, pepo, *, j, h, log_scale):
        return ThermodynamicPoint(z=1.0 + log_scale, u=-2.0)

    def hermiticity_residual(self, pepo):
        return 0.0


def _factory(chi, cutoff):
    return FakeContractor()


def _checkpoint_grid(root, *, count=40, mode="ordinary"):
    for step in range(1, count + 1):
        beta = round(step * 0.025, 12)
        save_checkpoint(
            root / f"beta-{beta:.6f}",
            FinitePEPO.identity(1, 1),
            beta=beta,
            mode=mode,
            log_scale=beta,
            config_sha256="abc",
            diagnostics={},
        )


def test_local_polynomial_derivative_is_exact_for_cubic():
    beta = np.arange(0.025, 1.0001, 0.025)
    values = -3.0 + 2.0 * beta - beta**2 + 0.5 * beta**3
    expected = 2.0 - 2.0 * beta + 1.5 * beta**2

    actual = local_polynomial_derivative(beta, values)

    assert np.allclose(actual, expected, rtol=1e-10, atol=1e-10)


@pytest.mark.parametrize(
    "beta,values",
    [
        ([0.1, 0.2], [1.0, 2.0]),
        ([0.1] * 5, [1.0] * 5),
        ([0.1] * 5, [1.0] * 4),
        ([0.1, 0.2, 0.3, 0.4, np.nan], [1.0] * 5),
    ],
)
def test_local_polynomial_derivative_rejects_invalid_grids(beta, values):
    with pytest.raises(ValueError):
        local_polynomial_derivative(beta, values)


def test_measurement_writes_dense_and_ten_point_public_tables(tmp_path):
    checkpoint_root = tmp_path / "ordinary" / "checkpoints"
    _checkpoint_grid(checkpoint_root)
    output = tmp_path / "measurements" / "ordinary" / "chi-16"

    result = measure_chain(
        checkpoint_root,
        output,
        expected_config_sha256="abc",
        j=1.0,
        h=3.0,
        chi=16,
        cutoff=1e-10,
        contractor_factory=_factory,
    )

    with result.dense_path.open(encoding="utf-8") as handle:
        dense = list(csv.DictReader(handle))
    with result.public_path.open(encoding="utf-8") as handle:
        public = list(csv.DictReader(handle))
    assert result.dense_count == 40
    assert result.public_count == 10
    assert len(dense) == 40
    assert [float(row["beta"]) for row in public] == pytest.approx(
        np.arange(0.1, 1.0001, 0.1)
    )
    assert all(float(row["c"]) == pytest.approx(0.0, abs=1e-12) for row in dense)
    assert result.manifest_path.is_file()


def test_measurement_rejects_a_missing_beta_point(tmp_path):
    checkpoint_root = tmp_path / "ordinary" / "checkpoints"
    _checkpoint_grid(checkpoint_root, count=39)

    with pytest.raises(ValueError, match="missing checkpoint at beta 1"):
        measure_chain(
            checkpoint_root,
            tmp_path / "measurements" / "ordinary" / "chi-16",
            expected_config_sha256="abc",
            j=1.0,
            h=3.0,
            chi=16,
            cutoff=1e-10,
            contractor_factory=_factory,
        )


def test_measurement_chi_outputs_are_isolated(tmp_path):
    checkpoint_root = tmp_path / "ordinary" / "checkpoints"
    _checkpoint_grid(checkpoint_root)
    root = tmp_path / "measurements" / "ordinary"

    first = measure_chain(
        checkpoint_root,
        root / "chi-16",
        expected_config_sha256="abc",
        j=1.0,
        h=3.0,
        chi=16,
        cutoff=1e-10,
        contractor_factory=_factory,
    )
    second = measure_chain(
        checkpoint_root,
        root / "chi-32",
        expected_config_sha256="abc",
        j=1.0,
        h=3.0,
        chi=32,
        cutoff=1e-10,
        contractor_factory=_factory,
    )

    assert first.dense_path != second.dense_path
    assert first.dense_path.is_file()
    assert second.dense_path.is_file()

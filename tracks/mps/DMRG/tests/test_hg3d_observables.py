from __future__ import annotations

import numpy as np
import pytest

from spinglass3d.observables import aggregate_disorder
from spinglass3d.overlap import DisorderRecord


def _record(
    j_id: str,
    *,
    q2: float,
    q4: float,
    qk2: tuple[float, float, float] = (0.1, 0.1, 0.1),
    length: int = 6,
    temperature: float = 1.1,
) -> DisorderRecord:
    return DisorderRecord(
        j_id=j_id,
        temperature=temperature,
        length=length,
        measurement_count=200,
        q_mean=0.0,
        q2=q2,
        q4=q4,
        qk2_axes=qk2,
    )


def test_disorder_average_precedes_binder_ratio() -> None:
    records = [
        _record("J-1", q2=0.2, q4=0.08),
        _record("J-2", q2=0.6, q4=0.40),
    ]
    result = aggregate_disorder(records)
    expected = 0.5 * (3.0 - 0.24 / 0.4**2)
    assert result.binder == pytest.approx(expected, abs=2e-15, rel=0.0)


def test_spin_glass_susceptibility_and_correlation_length_convention() -> None:
    records = [
        _record("J-1", q2=0.4, q4=0.2, qk2=(0.10, 0.12, 0.08)),
        _record("J-2", q2=0.5, q4=0.3, qk2=(0.11, 0.13, 0.09)),
    ]
    result = aggregate_disorder(records)
    n_sites = 6**3
    mean_q2 = 0.45
    mean_qk2 = np.mean((0.10, 0.12, 0.08, 0.11, 0.13, 0.09))
    chi0 = n_sites * mean_q2
    chik = n_sites * mean_qk2
    xi = np.sqrt(chi0 / chik - 1.0) / (2.0 * np.sin(np.pi / 6))
    assert result.chi_sg_0 == pytest.approx(chi0, abs=2e-13, rel=0.0)
    assert result.chi_sg_kmin == pytest.approx(chik, abs=2e-13, rel=0.0)
    assert result.xi_l == pytest.approx(xi, abs=2e-13, rel=0.0)
    assert result.xi_l_over_l == pytest.approx(xi / 6, abs=2e-13, rel=0.0)
    assert result.chi_sg_kmin_axes == pytest.approx(
        (n_sites * 0.105, n_sites * 0.125, n_sites * 0.085),
        abs=2e-13,
        rel=0.0,
    )


def test_aggregate_requires_unique_compatible_disorder_records() -> None:
    one = _record("J-1", q2=0.4, q4=0.2)
    with pytest.raises(ValueError, match="at least two"):
        aggregate_disorder([one])
    with pytest.raises(ValueError, match="duplicate"):
        aggregate_disorder([one, one])
    with pytest.raises(ValueError, match="length"):
        aggregate_disorder([one, _record("J-2", q2=0.4, q4=0.2, length=9)])
    with pytest.raises(ValueError, match="temperature"):
        aggregate_disorder(
            [one, _record("J-2", q2=0.4, q4=0.2, temperature=1.2)]
        )


def test_invalid_spectral_denominator_and_radicand_fail_closed() -> None:
    with pytest.raises(ValueError, match="positive"):
        aggregate_disorder(
            [
                _record("J-1", q2=0.4, q4=0.2, qk2=(0.0, 0.0, 0.0)),
                _record("J-2", q2=0.5, q4=0.3, qk2=(0.0, 0.0, 0.0)),
            ]
        )
    with pytest.raises(ValueError, match="radicand"):
        aggregate_disorder(
            [
                _record("J-1", q2=0.1, q4=0.02, qk2=(0.3, 0.3, 0.3)),
                _record("J-2", q2=0.1, q4=0.02, qk2=(0.3, 0.3, 0.3)),
            ]
        )

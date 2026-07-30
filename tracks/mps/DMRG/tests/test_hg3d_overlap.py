from __future__ import annotations

import numpy as np
import pytest

from spinglass3d.exact import ExactThermalRecord, enumerate_l2
from spinglass3d.model import EABonds
from spinglass3d.observables import aggregate_disorder
from spinglass3d.overlap import (
    DisorderRecord,
    ReplicaPair,
    ThermalOverlapAccumulator,
    measure_sample,
    overlap_field,
)


def _fixed_pair() -> ReplicaPair:
    a = np.array(
        [
            [[1, -1], [-1, 1]],
            [[-1, 1], [1, -1]],
        ],
        dtype=np.int8,
    )
    b = np.array(
        [
            [[1, 1], [-1, -1]],
            [[-1, -1], [1, 1]],
        ],
        dtype=np.int8,
    )
    return ReplicaPair(a, b)


def _fixed_l2_bonds() -> EABonds:
    values = np.array(
        [1, -1, 1, 1, 1, -1, -1, 1, 1, 1, -1, -1,
         1, 1, 1, -1, -1, 1, -1, 1, -1, 1, -1, 1],
        dtype=np.int8,
    ).reshape(2, 2, 2, 3)
    return EABonds(values)


def test_overlap_symmetries() -> None:
    pair = _fixed_pair()
    q = overlap_field(pair)
    np.testing.assert_array_equal(overlap_field(pair.swapped()), q)
    np.testing.assert_array_equal(overlap_field(pair.flip_both()), q)
    np.testing.assert_array_equal(overlap_field(pair.flip_a()), -q)


def test_replica_pair_requires_independent_binary_cubes() -> None:
    spins = np.ones((3, 3, 3), dtype=np.int8)
    with pytest.raises(ValueError, match="share memory"):
        ReplicaPair(spins, spins.view())
    with pytest.raises(ValueError, match="shape"):
        ReplicaPair(spins, np.ones((3, 3, 2), dtype=np.int8))
    malformed = spins.copy()
    malformed[0, 0, 0] = 0
    with pytest.raises(ValueError, match=r"-1 and \+1"):
        ReplicaPair(spins, malformed)


def test_measurement_retains_three_axial_wavevectors() -> None:
    pair = _fixed_pair()
    measurement = measure_sample(pair)
    q = overlap_field(pair).astype(np.float64)
    spectrum = np.fft.fftn(q) / q.size
    expected = (
        float(abs(spectrum[1, 0, 0]) ** 2),
        float(abs(spectrum[0, 1, 0]) ** 2),
        float(abs(spectrum[0, 0, 1]) ** 2),
    )
    assert measurement.abs_qk2 == pytest.approx(expected, abs=2e-15, rel=0.0)
    assert measurement.q2 == pytest.approx(measurement.q**2, abs=0.0, rel=0.0)
    assert measurement.q4 == pytest.approx(measurement.q**4, abs=0.0, rel=0.0)


def test_accumulator_emits_one_record_and_preserves_axes() -> None:
    accumulator = ThermalOverlapAccumulator(length=2)
    uniform = np.ones((2, 2, 2), dtype=np.int8)
    nonuniform = uniform.copy()
    nonuniform[0, 0, :] = -1
    first = measure_sample(ReplicaPair(uniform.copy(), uniform.copy()))
    second = measure_sample(ReplicaPair(uniform.copy(), nonuniform))
    accumulator.update(first)
    accumulator.update(second)
    record = accumulator.finalize(j_id="J-7", temperature=1.25)
    assert record.measurement_count == 2
    assert record.q_mean == pytest.approx(0.75, abs=0.0, rel=0.0)
    assert record.q2 == pytest.approx(0.625, abs=0.0, rel=0.0)
    assert record.q4 == pytest.approx(0.53125, abs=0.0, rel=0.0)
    assert record.qk2_axes == pytest.approx(
        (0.125, 0.125, 0.0),
        abs=0.0,
        rel=0.0,
    )
    with pytest.raises(RuntimeError, match="finalized"):
        accumulator.update(first)
    with pytest.raises(RuntimeError, match="finalized"):
        accumulator.finalize(j_id="J-7", temperature=1.25)


def test_invalid_finalize_metadata_does_not_consume_accumulator() -> None:
    accumulator = ThermalOverlapAccumulator(length=2)
    accumulator.update(measure_sample(_fixed_pair()))
    with pytest.raises(ValueError, match="temperature"):
        accumulator.finalize(j_id="J-8", temperature=0.0)
    record = accumulator.finalize(j_id="J-8", temperature=1.0)
    assert record.measurement_count == 1


def _measure_exact_l2(
    bonds: EABonds,
    j_id: str,
) -> tuple[ExactThermalRecord, DisorderRecord]:
    exact = enumerate_l2(0.0, bonds)
    accumulator = ThermalOverlapAccumulator(length=2)
    for left in exact.states:
        for right in exact.states:
            accumulator.update(
                measure_sample(ReplicaPair(left.copy(), right.copy()))
            )
    return exact, accumulator.finalize(j_id=j_id, temperature=1.0)


def test_l2_overlap_moments_match_exact_two_copy_oracle() -> None:
    first_exact, first_record = _measure_exact_l2(
        _fixed_l2_bonds(),
        "J-exact-1",
    )
    second_exact, second_record = _measure_exact_l2(
        EABonds(-_fixed_l2_bonds().values),
        "J-exact-2",
    )
    observables = aggregate_disorder((first_record, second_record))

    assert first_record.q2 == pytest.approx(first_exact.q2, abs=2e-13, rel=0.0)
    assert first_record.q4 == pytest.approx(first_exact.q4, abs=2e-13, rel=0.0)
    assert second_record.q2 == pytest.approx(second_exact.q2, abs=2e-13, rel=0.0)
    assert second_record.q4 == pytest.approx(second_exact.q4, abs=2e-13, rel=0.0)
    assert observables.chi_sg_0 == pytest.approx(
        8.0 * (first_exact.q2 + second_exact.q2) / 2.0,
        abs=2e-13,
        rel=0.0,
    )

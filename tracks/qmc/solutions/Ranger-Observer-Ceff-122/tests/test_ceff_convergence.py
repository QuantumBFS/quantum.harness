import json

import numpy as np
import pytest

from ceffflow.convergence import (
    _load_particle_blocks,
    summarize_particle_pair,
    summarize_particle_samples,
)


def test_particle_convergence_uses_paired_high_level_equivalence_bound():
    common = np.linspace(-1.0, 1.0, 20)
    summary = summarize_particle_samples(
        {
            64: common + 0.08,
            128: common + 0.015,
            256: common + 0.005,
        },
        absolute_tolerance=0.05,
        confidence_z=1.96,
    )
    assert summary["production_gate_passed"] is True
    assert (
        summary["comparisons"]["128_to_256"]
        ["absolute_shift_upper_confidence_bound"]
        == pytest.approx(0.01)
    )


def test_particle_convergence_fails_when_high_level_shift_exceeds_margin():
    common = np.linspace(-1.0, 1.0, 20)
    summary = summarize_particle_samples(
        {64: common, 128: common, 256: common + 0.051},
        absolute_tolerance=0.05,
        confidence_z=1.96,
    )
    assert summary["production_gate_passed"] is False


def test_high_statistics_particle_pair_uses_declared_levels():
    common = np.linspace(-1.0, 1.0, 100)
    summary = summarize_particle_pair(
        {256: common, 512: common + 0.01},
        lower_particles=256,
        higher_particles=512,
        absolute_tolerance=0.05,
        confidence_z=1.96,
    )
    assert summary["production_gate_passed"] is True
    comparison = summary["comparisons"]["256_to_512"]
    assert comparison["higher_minus_lower"] == pytest.approx(0.01)
    assert comparison["absolute_shift_upper_confidence_bound"] == pytest.approx(
        0.01
    )


@pytest.mark.parametrize(
    "samples",
    [
        {64: np.ones(2), 128: np.ones(2)},
        {64: np.ones(2), 128: np.ones(3), 256: np.ones(2)},
        {64: np.ones(2), 128: np.ones(2), 256: np.asarray([1.0, np.nan])},
    ],
)
def test_particle_convergence_rejects_incomplete_or_unaligned_samples(samples):
    with pytest.raises(ValueError):
        summarize_particle_samples(
            samples,
            absolute_tolerance=0.05,
            confidence_z=1.96,
        )


@pytest.mark.parametrize(
    ("kind", "parameter"), [("confusion", 0.5), ("erasure", 0.0)]
)
def test_particle_loader_skips_analytic_endpoints(tmp_path, kind, parameter):
    spec = tmp_path / "run_spec.json"
    spec.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_id": "analytic",
                        "settings": {
                            "model": "self_dual",
                            "lengths": [6, 8, 10, 12, 14, 16],
                            "channel": {"kind": kind, "parameter": parameter},
                            "steps": 20,
                            "burn_in": 0,
                            "block_size": 10,
                            "seed": 0,
                            "particles": 128,
                        },
                    }
                ]
            }
        )
    )
    assert _load_particle_blocks(spec, {128}) == ({}, {}, {})

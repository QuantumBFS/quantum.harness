from vqetape.holdout import LongitudinalIsingSpec
from vqetape.holdout_report import (
    run_holdout_fresh_process,
)


def test_holdout_report_runs_in_fresh_process():
    result = run_holdout_fresh_process(
        LongitudinalIsingSpec(
            nqubits=3,
            depth=1,
            longitudinal_field=0.2,
            dtype="complex128",
        ),
        target_energy_error=0.5,
        max_steps=2,
        timeout_seconds=120,
    )

    assert result["converged"]
    assert not result["z2_spatial_compression"][
        "applicable"
    ]
    assert result["z2_spatial_compression"][
        "commutator_norm"
    ] > 0

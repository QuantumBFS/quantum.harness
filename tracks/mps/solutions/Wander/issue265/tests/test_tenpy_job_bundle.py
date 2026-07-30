from __future__ import annotations

import pytest

from scripts.build_tenpy_job_bundle import _resource_spec


@pytest.mark.parametrize(
    ("level", "fcs", "cpus", "memory"),
    (
        ("coarse", False, 4, "12G"),
        ("coarse", True, 8, "24G"),
        ("medium", False, 8, "30G"),
        ("medium", True, 16, "60G"),
        ("fine", False, 16, "60G"),
        ("fine", True, 32, "120G"),
        ("selected_after_convergence", False, 16, "60G"),
        ("selected_after_convergence", True, 32, "120G"),
    ),
)
def test_resource_ladder_matches_accepted_scnet_pilot(
    level: str,
    fcs: bool,
    cpus: int,
    memory: str,
) -> None:
    observables = ["magnetization"]
    if fcs:
        observables.append("fcs_logZ")
    resource = _resource_spec(
        {
            "resolution_level": level,
            "observables": observables,
        }
    )
    assert resource["cpus"] == cpus
    assert resource["memory"] == memory
    assert resource["walltime"] == "7-00:00:00"
    assert resource["resource_pilot_job_id"] == "23009308"
    assert resource["fcs_counting_branches"] == (3 if fcs else 0)

import json
from pathlib import Path

import numpy as np
import pytest

from lrtfim.checkpoints import CheckpointProvenance
from lrtfim.dmrg_workflow import build_mpo_model, default_dmrg_options
from lrtfim.mpo import build_rotated_nearest_neighbor_tfim_mpo
from lrtfim.parity_dmrg import run_parity_spectrum
from lrtfim.staged_dmrg import run_staged_sector
from lrtfim.validation import dense_mpo_hamiltonian, lowest_eigenpairs


def _provenance(sector: str) -> CheckpointProvenance:
    return CheckpointProvenance(
        sigma=1.75,
        length=8,
        gamma=1.0,
        num_exponentials=24,
        alpha=0.5,
        r_fit=2048,
        sector=sector,
        requested_chi=128,
        reached_chi=1,
        sweep_statistics={},
        code_hash="test-code",
        fit_hash="test-fit",
        active_channels=tuple(range(24)),
    )


@pytest.mark.parametrize(
    "schedule",
    [[32, 32, 128], [64, 32, 128], [32, 64], []],
)
def test_staged_schedule_must_increase_and_end_at_128(schedule) -> None:
    model = build_mpo_model(build_rotated_nearest_neighbor_tfim_mpo(8, 1.0))
    with pytest.raises(ValueError, match="chi schedule"):
        run_staged_sector(
            model,
            "even",
            schedule,
            default_dmrg_options(128),
        )


def test_staged_chi_matches_direct_and_ed_and_saves_every_stage(
    tmp_path: Path,
) -> None:
    model = build_mpo_model(build_rotated_nearest_neighbor_tfim_mpo(8, 1.0))
    options = default_dmrg_options(128)
    options["max_sweeps"] = 20
    direct = run_parity_spectrum(model, options)
    even = run_staged_sector(
        model,
        "even",
        [32, 64, 128],
        options,
        checkpoint_root=tmp_path / "even",
        provenance=_provenance("even"),
    )
    odd = run_staged_sector(
        model,
        "odd",
        [32, 64, 128],
        options,
        checkpoint_root=tmp_path / "odd",
        provenance=_provenance("odd"),
    )

    assert all(
        later.energy <= earlier.energy + 1e-9
        for earlier, later in zip(even.stages, even.stages[1:])
    )
    assert even.final.energy == pytest.approx(direct.ground.energy, abs=1e-9)
    assert odd.final.energy == pytest.approx(direct.excited.energy, abs=1e-9)
    dense = dense_mpo_hamiltonian(model)
    exact, _ = lowest_eigenpairs(dense, count=2)
    np.testing.assert_allclose(
        [even.final.energy, odd.final.energy],
        exact,
        atol=1e-9,
    )
    for sector in ("even", "odd"):
        for chi in (32, 64, 128):
            metadata = json.loads(
                (tmp_path / sector / f"chi{chi}" / "checkpoint.json").read_text()
            )
            assert metadata["provenance"]["requested_chi"] == chi
            assert metadata["provenance"]["sweep_statistics"]["sweep"]

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from tenpy.networks.mps import MPS
from tenpy.networks.site import SpinHalfSite

from lrtfim.checkpoints import (
    CheckpointMismatch,
    CheckpointProvenance,
    code_tree_hash,
    load_initialization_checkpoint,
    load_checkpoint,
    mps_lattice_fingerprint,
    save_checkpoint,
)


def _provenance(**changes) -> CheckpointProvenance:
    base = CheckpointProvenance(
        sigma=1.75,
        length=4,
        gamma=1.56,
        num_exponentials=24,
        alpha=0.5,
        r_fit=2048,
        sector="even",
        requested_chi=16,
        reached_chi=4,
        sweep_statistics={"sweep": [1, 2], "max_chi": [2, 4]},
        code_hash="code-abc",
        fit_hash="fit-xyz",
        active_channels=(0, 2, 3),
    )
    return replace(base, **changes)


def _state() -> MPS:
    site = SpinHalfSite(conserve="parity")
    return MPS.from_product_state([site] * 4, ["up"] * 4, bc="finite")


def test_checkpoint_round_trip_preserves_state_and_metadata(tmp_path: Path) -> None:
    psi = _state()
    provenance = _provenance()
    diagnostics = {"energy": -4.2, "variance": 1e-12}
    save_checkpoint(tmp_path, psi, provenance, diagnostics)

    loaded, metadata = load_checkpoint(tmp_path, provenance)

    assert abs(loaded.overlap(psi)) == pytest.approx(1.0, abs=1e-13)
    np.testing.assert_array_equal(loaded.get_total_charge(), psi.get_total_charge())
    assert metadata["status"] == "success"
    assert metadata["diagnostics"] == diagnostics
    assert metadata["provenance"]["sector"] == "even"
    assert (tmp_path / "state.h5").is_file()
    assert (tmp_path / "checkpoint.json").is_file()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("gamma", 1.561),
        ("sector", "odd"),
        ("fit_hash", "other-fit"),
        ("code_hash", "other-code"),
        ("length", 6),
    ],
)
def test_checkpoint_rejects_incompatible_provenance(
    tmp_path: Path,
    field: str,
    value,
) -> None:
    psi = _state()
    provenance = _provenance()
    save_checkpoint(tmp_path, psi, provenance, {"energy": -4.2})

    with pytest.raises(CheckpointMismatch, match=field):
        load_checkpoint(tmp_path, replace(provenance, **{field: value}))


def test_higher_chi_refinement_can_load_lower_chi_checkpoint(tmp_path: Path) -> None:
    provenance = _provenance(requested_chi=32, reached_chi=16)
    save_checkpoint(tmp_path, _state(), provenance, {"energy": -4.2})

    loaded, _ = load_checkpoint(
        tmp_path,
        replace(provenance, requested_chi=64, reached_chi=16),
    )
    assert loaded.L == 4


def test_checkpoint_rejects_refinement_below_reached_chi(tmp_path: Path) -> None:
    provenance = _provenance(requested_chi=64, reached_chi=32)
    save_checkpoint(tmp_path, _state(), provenance, {"energy": -4.2})

    with pytest.raises(CheckpointMismatch, match="requested_chi"):
        load_checkpoint(
            tmp_path,
            replace(provenance, requested_chi=16, reached_chi=32),
        )


def test_code_tree_hash_tracks_source_content_not_mtime(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    module = source / "module.py"
    module.write_text("VALUE = 1\n")
    first = code_tree_hash(tmp_path)
    module.touch()
    assert code_tree_hash(tmp_path) == first
    module.write_text("VALUE = 2\n")
    assert code_tree_hash(tmp_path) != first


def test_gamma_continuation_requires_explicit_opt_in(tmp_path: Path) -> None:
    stored = _provenance(gamma=1.559)
    requested = replace(stored, gamma=1.560)
    save_checkpoint(tmp_path, _state(), stored, {"energy": -4.2})
    with pytest.raises(CheckpointMismatch, match="gamma"):
        load_checkpoint(tmp_path, requested)
    loaded, metadata = load_checkpoint(
        tmp_path,
        requested,
        allow_gamma_continuation=True,
    )
    assert loaded.L == 4
    assert metadata["provenance"]["gamma"] == 1.559


def test_audited_initialization_allows_only_code_hash_mismatch(
    tmp_path: Path,
) -> None:
    stored = _provenance(code_hash="historical-code")
    save_checkpoint(tmp_path, _state(), stored, {"energy": -4.2})
    expected = replace(
        stored,
        code_hash="current-code",
        requested_chi=32,
    )

    loaded, audit = load_initialization_checkpoint(
        tmp_path,
        expected,
        coefficient_hash="coefficients-abc",
        operator_convention="rotated-xz-periodized-v1",
        lattice_fingerprint=mps_lattice_fingerprint(_state()),
    )

    assert loaded.L == 4
    assert audit["checkpoint_code_hash"] == "historical-code"
    assert audit["current_code_hash"] == "current-code"
    assert audit["coefficient_hash"] == "coefficients-abc"
    assert audit["operator_convention"] == "rotated-xz-periodized-v1"
    assert audit["fully_reoptimize_required"] is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("gamma", 1.565),
        ("num_exponentials", 32),
        ("alpha", 0.25),
        ("r_fit", 1024),
        ("sector", "odd"),
        ("fit_hash", "other-fit"),
    ],
)
def test_audited_initialization_rejects_physical_mismatch(
    tmp_path: Path,
    field: str,
    value,
) -> None:
    stored = _provenance(code_hash="historical-code")
    save_checkpoint(tmp_path, _state(), stored, {"energy": -4.2})
    expected = replace(
        stored,
        code_hash="current-code",
        requested_chi=32,
        **{field: value},
    )

    with pytest.raises(CheckpointMismatch, match=field):
        load_initialization_checkpoint(
            tmp_path,
            expected,
            coefficient_hash="coefficients-abc",
            operator_convention="rotated-xz-periodized-v1",
            lattice_fingerprint=mps_lattice_fingerprint(_state()),
        )


def test_audited_initialization_rejects_lattice_mismatch(tmp_path: Path) -> None:
    stored = _provenance(code_hash="historical-code")
    save_checkpoint(tmp_path, _state(), stored, {"energy": -4.2})

    with pytest.raises(CheckpointMismatch, match="lattice"):
        load_initialization_checkpoint(
            tmp_path,
            replace(stored, code_hash="current-code", requested_chi=32),
            coefficient_hash="coefficients-abc",
            operator_convention="rotated-xz-periodized-v1",
            lattice_fingerprint="wrong-lattice",
        )

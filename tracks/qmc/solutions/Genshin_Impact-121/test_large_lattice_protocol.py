from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path

import numpy as np
import pytest

import large_lattice_protocol as protocol


META = Path(__file__).with_name("large_lattice_run.json")


def confirmed_meta() -> dict:
    return json.loads(META.read_text(encoding="utf-8"))


def small_execution() -> dict:
    value = deepcopy(protocol.DEFAULT_EXECUTION)
    value["g1"].update(
        steps=20, warmup=4, measure_every=2,
        checkpoint_every=10, rebuild_every=4,
    )
    value["production"].update(
        steps=24, warmup=4, measure_every=2,
        checkpoint_every=12, rebuild_every=4,
    )
    return value


def write_meta(path: Path, value: dict) -> None:
    protocol.write_json(path, value)


def test_pending_and_physics_drift_are_rejected() -> None:
    pending = confirmed_meta()
    pending["document_type"] = "preregistered_large_lattice_run_draft"
    pending["status"] = "proposed_pending_single_setup_ratification"
    pending["ratification"]["status"] = "pending"
    with pytest.raises(protocol.ProtocolError):
        protocol.validate_meta(pending)
    drift = confirmed_meta()
    drift["model"]["local_parameters"]["kappa"] = 0.021
    with pytest.raises(protocol.ProtocolError, match="kappa"):
        protocol.validate_meta(drift)
    measurement_drift = confirmed_meta()
    measurement_drift["measurement_protocol"]["momenta"]["qmin"].append([1, 1])
    with pytest.raises(protocol.ProtocolError, match="qmin"):
        protocol.validate_meta(measurement_drift)


def test_strict_json_rejects_nonfinite(tmp_path: Path) -> None:
    with pytest.raises(protocol.ProtocolError, match="finite"):
        protocol.canonical_bytes({"bad": math.nan})
    bad = tmp_path / "bad.json"
    bad.write_text('{"bad": NaN}\n', encoding="utf-8")
    with pytest.raises(protocol.ProtocolError, match="finite"):
        protocol.load_json(bad)


def test_materialization_cardinality_hashes_and_frozen_manifests(
    tmp_path: Path,
) -> None:
    meta_path = tmp_path / "confirmed.json"
    write_meta(meta_path, confirmed_meta())
    root = tmp_path / "materialized"
    index = protocol.materialize(
        meta_path, root, small_execution()
    )
    assert index["counts"] == {
        "g1_chains": 32,
        "production_chains": 80,
        "pilot_chains": 12,
        "full_remaining_chains": 68,
    }
    assert len(index["entries"]) == 112
    assert not (root / "COMPLETE").exists()
    assert protocol.verify_materialization(root) == index

    production = [
        entry for entry in index["entries"]
        if entry["stage"] == "production"
        and entry["L"] == 6
        and entry["beta_index"] == 2
    ]
    assert len(production) == 4
    assert [entry["seed"] for entry in production] == [
        121060020, 121060021, 121060022, 121060023
    ]
    manifests = [
        protocol.load_json(root / entry["manifest"])
        for entry in production
    ]
    assert [item["monte_carlo"]["initialization"] for item in manifests] == [
        {"mode": "cold", "initial_order": 0},
        {"mode": "cold", "initial_order": 0},
        {"mode": "hot", "initial_order": 72},
        {"mode": "hot", "initial_order": 72},
    ]
    first = manifests[0]
    assert first["model"] == {
        "epsilon": "1/100",
        "kappa": "1/50",
        "vertex_strength": "1/4",
        "g_A": "1/4",
        "g_B": "1/4",
        "beta": "2",
    }
    measurements = first["measurements"]
    assert len(measurements["displacements"]) == 36
    assert measurements["momenta"] == [
        [0, 0], [1, 0], [0, 1],
        [3, 0], [0, 3], [3, 3],
        [2, 4], [4, 2],
    ]
    labels = measurements["momentum_labels"]
    assert labels["Gamma"] == [0, 0]
    assert labels["qmin"] == [[1, 0], [0, 1]]
    assert labels["M_points"] == {
        "condition": "L even",
        "indices": [[3, 0], [0, 3], [3, 3]],
    }
    assert labels["K_points"] == {
        "condition": "L%3==0",
        "indices": [[2, 4], [4, 2]],
    }
    assert labels["K_note"] == "two exact K points included"

    def manifest_for(size: int) -> dict:
        return next(
            protocol.load_json(root / entry["manifest"])
            for entry in index["entries"]
            if entry["stage"] == "production"
            and entry["L"] == size
            and entry["beta_index"] == 0
            and entry["chain_id"] == 0
        )

    l4 = manifest_for(4)
    assert len(l4["measurements"]["displacements"]) == 16
    assert l4["measurements"]["momenta"] == [
        [0, 0], [1, 0], [0, 1],
        [2, 0], [0, 2], [2, 2],
    ]
    assert l4["measurements"]["momentum_labels"]["K_points"]["indices"] == []
    assert l4["measurements"]["momentum_labels"]["K_note"] == (
        "K points omitted because L%3!=0"
    )

    l16 = manifest_for(16)
    assert len(l16["measurements"]["displacements"]) == 256
    assert l16["measurements"]["momenta"] == [
        [0, 0], [1, 0], [0, 1],
        [8, 0], [0, 8], [8, 8],
    ]
    assert l16["measurements"]["momentum_labels"]["K_points"]["indices"] == []

    assert "#SBATCH --array=0-31%8" in (
        root / "slurm" / "run_g1_array.sbatch"
    ).read_text(encoding="utf-8")
    submit = (
        root / "slurm" / "submit_after_live_cluster_check.sh"
    ).read_text(encoding="utf-8")
    assert submit.count("afterok:") == 6
    assert "sinfo" in submit and "squeue" in submit


def test_manifest_tamper_is_detected(tmp_path: Path) -> None:
    meta_path = tmp_path / "confirmed.json"
    write_meta(meta_path, confirmed_meta())
    root = tmp_path / "materialized"
    index = protocol.materialize(
        meta_path, root, small_execution()
    )
    manifest = root / index["entries"][0]["manifest"]
    manifest.write_text(
        manifest.read_text(encoding="utf-8") + " ",
        encoding="utf-8",
    )
    with pytest.raises(protocol.ProtocolError, match="manifest hash"):
        protocol.verify_materialization(root)


def test_ips_and_rank_split_diagnostics_are_finite() -> None:
    constant = [np.ones(32) for _ in range(4)]
    result = protocol.multi_chain_diagnostics(constant)
    assert result["split_r_hat"] == pytest.approx(1.0)
    assert result["bulk_ess"] == pytest.approx(128.0)
    assert result["tail_ess"] == pytest.approx(128.0)
    assert result["tau_int_by_original_chain"] == pytest.approx(
        [0.5] * 4
    )

    rng = np.random.default_rng(121)
    chains = [rng.normal(size=256) for _ in range(4)]
    noisy = protocol.multi_chain_diagnostics(chains)
    assert math.isfinite(noisy["split_r_hat"])
    assert 0.9 <= noisy["split_r_hat"] <= 1.1
    assert 0 < noisy["bulk_ess"] <= 1024
    assert 0 < noisy["tail_ess"] <= 1024


def fake_result(offset: float) -> dict:
    length = 64
    phase = np.linspace(0.0, 4.0 * np.pi, length, endpoint=False)
    order = 10.0 + np.sin(phase + offset)
    density = 0.5 + 0.01 * np.cos(phase + offset)
    number = 4.0 * density
    number2 = number * number + 0.25
    energy = -0.2 + 0.01 * np.sin(phase + offset)
    traces = {
        "order": order.tolist(),
        "energy_density": energy.tolist(),
        "particle_number": number.tolist(),
        "particle_number_squared": number2.tolist(),
        "particle_density": density.tolist(),
        "particle_density_squared": (
            number2 / 16.0
        ).tolist(),
    }
    return {
        "observables": {
            "count": length,
            "primary_traces": traces,
            "momentum": {},
        },
        "counters": {
            "moves": {
                "insert": {"attempted": 100, "accepted": 50},
                "delete": {"attempted": 100, "accepted": 50},
                "rotate_left_to_right": {
                    "attempted": 0, "accepted": 0
                },
                "rotate_right_to_left": {
                    "attempted": 0, "accepted": 0
                },
            },
            "zero_weight_rejections": 0,
        },
        "rebuild_diagnostics": [
            {
                "delta_logdet": 1.0e-12,
                "relative_T_drift_inf": 1.0e-12,
                "relative_Q_drift_inf": 1.0e-12,
                "fast_inverse_residual_inf": 1.0e-12,
                "rebuilt_inverse_residual_inf": 1.0e-12,
            }
        ],
    }


def test_cell_merge_acceptance_rebuild_and_observables() -> None:
    thresholds = {
        "r_hat_max": 2.0,
        "bulk_ess_min": 1,
        "tail_ess_min": 1,
        "fast_vs_rebuild_relative_error_max": 1.0e-9,
        "inverse_residual_max": 1.0e-8,
    }
    results = [
        fake_result(0.0),
        fake_result(0.2),
        fake_result(0.4),
        fake_result(0.6),
    ]
    summary = protocol.summarize_cell(
        results, beta=1.0, n_sites=4,
        thresholds=thresholds, acceptance_range=(0.2, 0.7),
    )
    assert summary["acceptance"]["rate"] == pytest.approx(0.5)
    assert summary["acceptance"]["pass"]
    assert summary["rebuild"]["pass"]
    assert summary["positivity"]["pass"]
    assert math.isfinite(summary["compressibility"])
    assert summary["pass"]


def test_only_outer_all_pass_protocol_writes_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meta_path = tmp_path / "confirmed.json"
    write_meta(meta_path, confirmed_meta())
    root = tmp_path / "materialized"
    protocol.materialize(meta_path, root, small_execution())

    with pytest.raises(protocol.ProtocolError):
        protocol.write_protocol_complete(root)

    for gate in ("G0", "G1", "G2", "G3", "G4"):
        protocol._gate(
            root, gate,
            {"status": "PASS", "test_fixture": True},
        )
    complete = protocol.write_protocol_complete(root)
    assert complete["status"] == "complete"
    assert (root / "COMPLETE").is_file()
    with pytest.raises(protocol.ProtocolError, match="overwrite"):
        protocol.write_protocol_complete(root)

    monkeypatch.setattr(
        protocol, "audit",
        lambda root, stage, write_complete=False: {
            "status": "INCONCLUSIVE"
        },
    )
    assert protocol.main([
        "audit", "--root", str(root), "--stage", "pilot"
    ]) == 2
    monkeypatch.setattr(
        protocol, "audit",
        lambda root, stage, write_complete=False: {"status": "PASS"},
    )
    assert protocol.main([
        "audit", "--root", str(root), "--stage", "g1"
    ]) == 0

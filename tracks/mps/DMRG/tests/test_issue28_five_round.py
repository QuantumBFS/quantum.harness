from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import vmcrg_ref.five_round as five_round_module
from scripts.issue28_five_round import (
    five_round_pilot_bundle,
    run_five_round_chain,
)
from vmcrg_ref.artifacts import atomic_write_json, sha256_bytes, sha256_file
from vmcrg_ref.issue28_protocol import load_issue28_protocol
from vmcrg_ref.neural_energy import D4EvenLocalMLP
from vmcrg_ref.operators import EVEN_SHAPES, OperatorBasis


PROTOCOL_PATH = Path("config/issue28_easy_v1.json")


def test_n3_sampling_reuses_prebuilt_monitor_basis(monkeypatch) -> None:
    model = D4EvenLocalMLP.random(3, 32, 19, feature_mode="multiscale")
    basis = OperatorBasis(7, EVEN_SHAPES)
    bundle = five_round_pilot_bundle()

    def fail_construction(*args, **kwargs):
        raise AssertionError("operator basis constructed after worker startup")

    monkeypatch.setattr(five_round_module, "OperatorBasis", fail_construction)
    differences, observed, target, energies, acceptances = (
        five_round_module._neural_samples(
            model,
            model,
            length=21,
            block_size=3,
            stream=bundle.streams["monitoring"],
            child_prefix=(2, 25),
            chains=2,
            thermal=1,
            measurements=2,
            spacing=1,
            workers=2,
            basis=basis,
        )
    )

    assert differences.shape == (2, 2, len(EVEN_SHAPES))
    assert observed.shape == target.shape == (2, 512)
    assert energies.shape == (2, 2, 2)
    assert len(acceptances) == 2


def test_n3_monitor_and_validation_use_excess_patch_tv(monkeypatch) -> None:
    uniform = np.full(512, 1.0 / 512.0)
    observed = uniform.copy()
    target = uniform.copy()
    observed[:16] = 0.0
    observed[16:32] *= 2.0
    target[32:48] = 0.0
    target[48:64] *= 2.0
    differences = np.zeros((2, 5, 13), dtype=np.float64)
    biased_patches = np.stack((observed, observed))
    target_patches = np.stack((target, target))
    energies = np.zeros((2, 2, 5), dtype=np.float64)

    def fake_samples(*args, **kwargs):
        return differences, biased_patches, target_patches, energies, [1.0, 1.0]

    monkeypatch.setattr(five_round_module, "_neural_samples", fake_samples)
    model = D4EvenLocalMLP.random(3, 32, 11, feature_mode="multiscale")
    bundle = five_round_pilot_bundle()

    validation = five_round_module._validate_neural_round(
        model,
        model,
        length=15,
        block_size=1,
        bundle=bundle,
        round_index=2,
        preset="smoke",
        workers=1,
    )
    window, _, _, diagnostics = five_round_module._monitor_window(
        model,
        model,
        length=15,
        block_size=1,
        stream=bundle.streams["monitoring"],
        round_index=2,
        update=25,
        budget=five_round_module._sampling_budget("smoke"),
        previous_objective=None,
        previous_parameters=None,
        record_gradient_norm=0.01,
        polyak_fraction=0.5,
        workers=1,
    )

    assert validation["status"] == "PASS"
    assert abs(validation["excess_patch_tv_upper_bound"]) < 1e-15
    assert min(validation["raw_two_sample_patch_tv_by_chain"]) > 0.02
    assert abs(window.patch_tv) < 1e-15
    assert min(diagnostics["raw_two_sample_patch_tv_by_chain"]) > 0.02


def test_round_two_consumes_round_one_manifest_hash(tmp_path: Path) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    report = run_five_round_chain(
        protocol,
        five_round_pilot_bundle(),
        tmp_path / "N3",
        backend="local",
        resume=False,
        preset="smoke",
        rounds=2,
        allow_large_local=True,
        workers=1,
    )
    assert len(report["rounds"]) == 2
    assert report["rounds"][0]["round"] == 1
    assert report["rounds"][1]["round"] == 2
    assert report["rounds"][1]["predecessor_manifest_sha256"] == report["rounds"][0][
        "manifest_sha256"
    ]
    assert report["rounds"][0]["fixed_linear_bias_linf"] == 0.0
    assert report["rounds"][1]["fixed_linear_bias_linf"] == 0.0
    assert report["rounds"][1]["microscopic_hamiltonian"] == "U_round_2=-V_round_1"
    for round_record in report["rounds"]:
        assert round_record["resources"]["threads"] == 1
        assert round_record["resources"]["execution_policy"] == (
            "LOCAL_COMPUTE_DEVIATION"
        )
        assert round_record["resources"]["proposals_per_second"] > 0.0
        assert round_record["resources"]["sweeps_per_second"] > 0.0
        assert round_record["resources"]["checkpoint_bytes"] > 0
        assert round_record["resources"]["compact_output_bytes"] > 0
    assert (tmp_path / "N3" / "round-01" / "manifest.json").is_file()
    assert (tmp_path / "N3" / "round-02" / "manifest.json").is_file()
    assert (tmp_path / "N3" / "manifest.json").is_file()
    assert report["resources"]["workers_per_bundle"] == 1
    assert report["resources"]["max_parallel_bundles"] == 2
    assert report["resources"]["execution_policy"] == "LOCAL_COMPUTE_DEVIATION"
    assert report["resources"]["host"]["node"]
    second_report = json.loads(
        (tmp_path / "N3" / "round-02" / "round_report.json").read_text(
            encoding="ascii"
        )
    )
    assert second_report["validation"]["workers_per_bundle"] == 1
    assert second_report["objective"]["workers_per_bundle"] == 1


def test_large_local_five_round_compute_requires_explicit_authorization(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="allow_large_local"):
        run_five_round_chain(
            load_issue28_protocol(PROTOCOL_PATH),
            five_round_pilot_bundle(),
            tmp_path / "N3",
            backend="local",
            resume=False,
            preset="pilot",
            rounds=5,
            workers=8,
        )
    assert not (tmp_path / "N3").exists()


def test_complete_chain_resume_is_hash_verified_and_nonmutating(tmp_path: Path) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    bundle = five_round_pilot_bundle()
    output = tmp_path / "N3"
    first = run_five_round_chain(
        protocol,
        bundle,
        output,
        backend="local",
        resume=False,
        preset="smoke",
        rounds=2,
    )
    before = sha256_file(output / "manifest.json")
    resumed = run_five_round_chain(
        protocol,
        bundle,
        output,
        backend="local",
        resume=True,
        preset="smoke",
        rounds=2,
    )
    assert resumed["rounds"] == first["rounds"]
    assert sha256_file(output / "manifest.json") == before


def test_complete_chain_resume_rejects_tampered_round_manifest(
    tmp_path: Path,
) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    bundle = five_round_pilot_bundle()
    output = tmp_path / "N3"
    run_five_round_chain(
        protocol,
        bundle,
        output,
        backend="local",
        resume=False,
        preset="smoke",
        rounds=2,
    )
    path = output / "round-01" / "manifest.json"
    value = json.loads(path.read_text(encoding="ascii"))
    value["reason"] = "TAMPERED_AFTER_COMPLETION"
    atomic_write_json(path, value)
    with pytest.raises(ValueError, match="round manifest dependency"):
        run_five_round_chain(
            protocol,
            bundle,
            output,
            backend="local",
            resume=True,
            preset="smoke",
            rounds=2,
        )


def test_pilot_bundle_is_disjoint_from_all_formal_bundles() -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    pilot = five_round_pilot_bundle()
    pilot_records = {
        (stream.entropy, stream.spawn_key) for stream in pilot.streams.values()
    }
    formal_records = {
        (stream.entropy, stream.spawn_key)
        for bundle in protocol.formal_bundles
        for stream in bundle.streams.values()
    }
    assert pilot.bundle_id not in {bundle.bundle_id for bundle in protocol.formal_bundles}
    assert pilot_records.isdisjoint(formal_records)


def test_five_round_chain_records_explicit_paired_initial_states(
    tmp_path: Path,
) -> None:
    protocol = load_issue28_protocol(PROTOCOL_PATH)
    first = np.ones((2, 21, 21), dtype=np.int8)
    first[1] *= -1
    second = -first
    report = run_five_round_chain(
        protocol,
        five_round_pilot_bundle(),
        tmp_path / "N3",
        backend="local",
        resume=False,
        preset="smoke",
        rounds=2,
        initial_spins_by_round={1: first, 2: second},
    )
    assert report["rounds"][0]["initial_state_sha256"] == sha256_bytes(
        np.ascontiguousarray(first).tobytes(order="C")
    )
    assert report["rounds"][1]["initial_state_sha256"] == sha256_bytes(
        np.ascontiguousarray(second).tobytes(order="C")
    )

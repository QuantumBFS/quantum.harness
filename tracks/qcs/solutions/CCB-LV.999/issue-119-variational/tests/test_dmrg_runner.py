from __future__ import annotations

import json
from pathlib import Path

from src.dmrg_runner import (
    DMRGStage,
    build_result_document,
    limit_bond_dimensions,
    load_config,
    load_resume_ordering,
    normalized_mps_expectation,
    seed_block2_random,
    stage_schedule,
    validate_resume_stages,
)

SOLUTION_ROOT = Path(__file__).resolve().parents[1]


def test_stage_schedule_turns_noise_off_for_final_two_sweeps() -> None:
    schedule = stage_schedule(
        n_sweeps=8,
        is_final=False,
        final_tolerance=1.0e-9,
    )

    assert schedule.noises == (1.0e-4,) * 6 + (0.0, 0.0)
    assert schedule.thresholds == (1.0e-6,) * 8


def test_final_stage_uses_tight_last_two_davidson_thresholds() -> None:
    schedule = stage_schedule(
        n_sweeps=8,
        is_final=True,
        final_tolerance=1.0e-9,
    )

    assert schedule.noises == (1.0e-5,) * 6 + (0.0, 0.0)
    assert schedule.thresholds == (1.0e-7,) * 6 + (1.0e-9, 1.0e-9)


def test_anderson_stage_uses_declared_pre_tolerance_threshold() -> None:
    schedule = stage_schedule(
        n_sweeps=8,
        is_final=True,
        final_tolerance=1.0e-9,
        final_stage_threshold=1.0e-6,
    )

    assert schedule.thresholds == (1.0e-6,) * 6 + (1.0e-9, 1.0e-9)


def test_load_config_rejects_sector_disagreement(tmp_path: Path) -> None:
    config = tmp_path / "bad.toml"
    config.write_text(
        """
[instance]
name = "tiny"
filename = "tiny.FCIDUMP"
sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
norb = 2
nelec = 2
ms2 = 0

[dmrg]
symmetry = "SU2"
spin = 2
seed = 1234
threads = 1
stack_mem_gb = 1.0
bond_dimensions = [8]
n_sweeps_per_m = 4
tolerance = 1e-9
iprint = 0

[ordering]
method = "none"
""",
        encoding="utf-8",
    )

    try:
        load_config(config)
    except ValueError as exc:
        assert "singlet" in str(exc)
    else:
        raise AssertionError("sector disagreement was accepted")


def test_result_document_headline_is_last_finite_m_stage() -> None:
    stages = [
        DMRGStage(8, -0.7, 2.0e-4, 1.0, 100.0),
        DMRGStage(16, -0.8, 1.0e-5, 2.0, 110.0),
    ]

    document = build_result_document(
        instance="tiny",
        norb=2,
        nelec=2,
        ms2=0,
        spin=0,
        input_sha256="a" * 64,
        ordering_method="fiedler",
        ordering=[0, 1],
        stages=stages,
        status="completed",
    )

    assert document["headline"] == {
        "kind": "finite_m_mps_expectation",
        "bond_dimension": 16,
        "energy_hartree": -0.8,
    }
    json.dumps(document)


def test_committed_configs_preserve_confirmed_sectors_and_local_budget() -> None:
    expected = {
        "2fe2s-local.toml": (20, 30, "fiedler", (250, 500)),
        "anderson-fiedler-local.toml": (32, 32, "fiedler", (100,)),
        "anderson-ga-local.toml": (32, 32, "ga", (100,)),
        "anderson-ga-m400-local.toml": (
            32,
            32,
            "ga",
            (100, 200, 400),
        ),
        "anderson-ga-m800-local.toml": (
            32,
            32,
            "ga",
            (100, 200, 400, 600, 800),
        ),
        "anderson-ga-m1000-local.toml": (
            32,
            32,
            "ga",
            (100, 200, 400, 600, 800, 1000),
        ),
        "anderson-ga-m1500-local.toml": (
            32,
            32,
            "ga",
            (100, 200, 400, 600, 800, 1000, 1500),
        ),
        "anderson-production.toml": (
            32,
            32,
            "ga",
            (100, 200, 400, 600, 800, 1000),
        ),
        "anderson-fiedler-m200.toml": (32, 32, "fiedler", (100, 200)),
        "anderson-ga-m200.toml": (32, 32, "ga", (100, 200)),
    }

    for filename, (norb, nelec, method, dimensions) in expected.items():
        config = load_config(SOLUTION_ROOT / "configs" / filename)
        assert (config.instance.norb, config.instance.nelec) == (norb, nelec)
        assert config.instance.ms2 == 0
        assert config.dmrg.symmetry == "SU2"
        assert config.dmrg.spin == 0
        assert config.ordering.method == method
        assert config.dmrg.bond_dimensions == dimensions
        if filename.startswith("anderson") and filename.endswith("-local.toml"):
            assert config.dmrg.threads == 8
            assert config.dmrg.stack_mem_gb == 10.0


def test_2fe_local_config_keeps_m500_on_public_nonfinal_schedule() -> None:
    config = load_config(SOLUTION_ROOT / "configs" / "2fe2s-local.toml")

    assert config.dmrg.tighten_final_stage is False


def test_anderson_config_tightens_last_two_sweeps_at_every_m() -> None:
    config = load_config(SOLUTION_ROOT / "configs" / "anderson-ga-local.toml")

    assert config.dmrg.tighten_each_stage is True
    assert config.dmrg.final_stage_threshold == 1.0e-6


def test_block2_backend_receives_declared_random_seed() -> None:
    received: list[int] = []

    class Driver:
        class bw:
            class b:
                class Random:
                    @staticmethod
                    def rand_seed(seed: int) -> None:
                        received.append(seed)

    seed_block2_random(Driver(), 1234)

    assert received == [1234]


def test_saved_mps_expectation_is_normalized_before_headline() -> None:
    class Driver:
        @staticmethod
        def get_identity_mpo() -> str:
            return "identity"

        @staticmethod
        def expectation(bra: object, mpo: object, ket: object, iprint: int) -> float:
            return 5.0 if mpo == "hamiltonian" else 2.0

    energy, norm = normalized_mps_expectation(
        Driver(),
        mpo="hamiltonian",
        ket=object(),
    )

    assert energy == 2.5
    assert norm == 2.0


def test_cluster_stage_limit_keeps_an_exact_prefix_of_bond_dimensions() -> None:
    config = load_config(SOLUTION_ROOT / "configs" / "anderson-production.toml")

    limited = limit_bond_dimensions(config, 800)

    assert limited.dmrg.bond_dimensions == (100, 200, 400, 600, 800)
    assert config.dmrg.bond_dimensions[-1] == 1000


def test_production_worker_counts_fit_the_fast_scnet_allocation() -> None:
    config = load_config(SOLUTION_ROOT / "configs" / "anderson-production.toml")

    assert config.dmrg.threads == 32
    assert config.ordering.ga_tasks == 32
    assert config.ordering.ga_tasks <= config.dmrg.threads
    assert config.dmrg.stack_mem_gb == 64.0


def test_cluster_stage_limit_rejects_a_target_outside_the_declared_ladder() -> None:
    config = load_config(SOLUTION_ROOT / "configs" / "anderson-production.toml")

    try:
        limit_bond_dimensions(config, 500)
    except ValueError as exc:
        assert "declared bond-dimension ladder" in str(exc)
    else:
        raise AssertionError("an undeclared target bond dimension was accepted")


def test_resume_reuses_the_checkpoint_orbital_ordering(tmp_path: Path) -> None:
    ordering_path = tmp_path / "ordering.json"
    ordering_path.write_text(
        json.dumps(
            {
                "method": "ga",
                "permutation": [2, 0, 1],
                "ga": {"selected_cost": 1.25},
            }
        ),
        encoding="utf-8",
    )

    ordering, document = load_resume_ordering(
        ordering_path,
        n_orbitals=3,
        expected_method="ga",
    )

    assert ordering == (2, 0, 1)
    assert document["ga"]["selected_cost"] == 1.25


def test_resume_rejects_an_ordering_method_change(tmp_path: Path) -> None:
    ordering_path = tmp_path / "ordering.json"
    ordering_path.write_text(
        json.dumps({"method": "fiedler", "permutation": [0, 1]}),
        encoding="utf-8",
    )

    try:
        load_resume_ordering(
            ordering_path,
            n_orbitals=2,
            expected_method="ga",
        )
    except ValueError as exc:
        assert "ordering method changed" in str(exc)
    else:
        raise AssertionError("resume accepted a different orbital-ordering method")


def test_resume_rejects_a_target_below_the_saved_checkpoint() -> None:
    config = load_config(SOLUTION_ROOT / "configs" / "anderson-production.toml")
    limited = limit_bond_dimensions(config, 800)
    stages = [
        DMRGStage(100, -1.0, 1.0e-3, 1.0, 100.0),
        DMRGStage(1000, -2.0, 1.0e-4, 2.0, 200.0),
    ]

    try:
        validate_resume_stages(limited, stages)
    except ValueError as exc:
        assert "not a prefix" in str(exc)
    else:
        raise AssertionError("resume accepted a target below the saved checkpoint")

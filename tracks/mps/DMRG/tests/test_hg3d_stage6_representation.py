from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from spinglass3d.backend import BackendCase
from spinglass3d.bias import BiasRoute
from spinglass3d.stage6_representation import (
    PhysicalCandidateAssessment,
    assess_physical_candidate,
    finalize_representation_selection,
    load_stage6_representation_config,
    sample_frozen_physical_route,
    select_validation_candidate,
    train_physical_route,
)
from spinglass3d.vmcrg import (
    FrozenEvaluation,
    ImprovementAssessment,
    VMCRGProtocol,
)


TRACK = Path(__file__).resolve().parents[1]
CONFIG = TRACK / "config/hard_goal/stage6_representation_v1.toml"


def test_stage6_physical_representation_protocol_is_fully_frozen() -> None:
    config = load_stage6_representation_config(CONFIG)
    assert config.length == 12
    assert config.target_temperature == pytest.approx(1.10)
    assert (config.train_j, config.validation_j, config.test_j) == (32, 16, 16)
    assert config.disorder_count == 64
    assert config.templates == ("cube", "cross")
    assert config.cube_routes == ("C", "B")
    assert config.cross_routes == ("B",)
    assert config.chis == (2, 4, 8)
    assert config.initializations == 2
    assert (config.c1_steps, config.c2_steps, config.c3_steps) == (24, 48, 0)
    assert config.draw_count == 16
    assert config.sweeps_per_batch == 4
    assert config.equilibration_sweeps == 512
    assert config.proposal_measurement_sweeps == 1024
    assert config.wall_budget_seconds == pytest.approx(600.0)
    assert config.bootstrap_replicates == 2000


def test_representation_config_rejects_silent_protocol_reduction(tmp_path: Path) -> None:
    text = CONFIG.read_text(encoding="ascii").replace("train_j = 32", "train_j = 8")
    changed = tmp_path / "reduced.toml"
    changed.write_text(text, encoding="ascii")
    with pytest.raises(ValueError, match="train_j"):
        load_stage6_representation_config(changed)


def test_small_physical_route_c_training_checkpoints_complete_sampler_state(
    tmp_path: Path,
) -> None:
    pytest.importorskip("jax")
    case = BackendCase.random(
        length=3,
        temperatures=2,
        samples=1,
        walkers=2,
        seed=2026073580,
    )
    split = {"train": ("J-0",), "validation": ("V-0",), "test": ("T-0",)}
    protocol = VMCRGProtocol(
        c1_steps=1,
        c2_steps=1,
        c3_steps=0,
        linear_learning_rate=0.01,
        tt_learning_rate=0.002,
        gradient_clip=0.1,
        canonicalize_every=8,
        momentum=0.0,
    )

    result = train_physical_route(
        (case,),
        ("J-0",),
        kind="cube",
        route=BiasRoute.C_LINEAR_PLUS_TT,
        chi=2,
        initialization_seed=2026073581,
        protocol=protocol,
        draw_count=1,
        sweeps_per_batch=0,
        target_temperature=float(1.0 / case.betas[-1]),
        hashes={"test": "a" * 64},
        j_split=split,
        checkpoint_root=tmp_path / "checkpoints",
        checkpoint_every=1,
        resume=False,
    )

    assert [record.stage for record in result.records] == ["C1", "C2"]
    assert result.trainer.step_index == 2
    assert result.bias.route is BiasRoute.C_LINEAR_PLUS_TT
    assert (result.checkpoint / "state.npz").is_file()
    assert len(tuple((tmp_path / "checkpoints").glob("step-*"))) <= 2
    assert np.all(np.isfinite(result.bias.coefficients))


def test_small_frozen_physical_sampling_records_matched_budget_metadata(
    tmp_path: Path,
) -> None:
    pytest.importorskip("jax")
    case = BackendCase.random(
        length=3,
        temperatures=2,
        samples=1,
        walkers=2,
        seed=2026073590,
    )
    protocol = VMCRGProtocol(
        c1_steps=0,
        c2_steps=1,
        c3_steps=0,
        linear_learning_rate=0.01,
        tt_learning_rate=0.002,
        gradient_clip=0.1,
        canonicalize_every=8,
        momentum=0.0,
    )
    trained = train_physical_route(
        (case,),
        ("J-0",),
        kind="cube",
        route=BiasRoute.B_CONDITIONED_TT,
        chi=2,
        initialization_seed=2026073591,
        protocol=protocol,
        draw_count=1,
        sweeps_per_batch=0,
        target_temperature=float(1.0 / case.betas[-1]),
        hashes={"test": "b" * 64},
        j_split={"train": ("J-0",), "validation": (), "test": ()},
        checkpoint_root=tmp_path / "training",
        checkpoint_every=1,
        resume=False,
    )

    frozen = sample_frozen_physical_route(
        (case,),
        ("V-0",),
        trained.bias,
        target_temperature_index=trained.target_temperature_index,
        split="validation",
        budget_kind="proposal",
        equilibration_sweeps=0,
        proposal_measurement_sweeps=2,
        wall_budget_seconds=0.01,
        measurement_cadence=1,
        seed=2026073592,
    )

    assert frozen.batch.target.shape == frozen.batch.biased.shape
    assert frozen.batch.target.shape[:2] == (1, 2)
    assert frozen.batch.budget_kind == "proposal"
    assert frozen.batch.proposal_count > 0
    assert 0.0 <= frozen.batch.acceptance <= 1.0
    assert frozen.batch.iat > 0.0
    assert frozen.batch.ess > 0.0
    assert frozen.sweeps_per_j == 2


def _evaluation(
    route: str,
    budget: str,
    primary: tuple[float, ...],
    other: tuple[float, ...],
    *,
    split: str = "validation",
    initialization_hash: str | None = None,
) -> FrozenEvaluation:
    return FrozenEvaluation(
        objective_estimate=0.0,
        total_variation=0.1,
        jensen_shannon=0.01,
        standardized_moments=(0.0,),
        mmd=float(np.mean(primary)),
        acceptance=0.5,
        iat=1.0,
        ess=20.0,
        projection=None,
        route_name=route,
        split=split,
        budget_kind=budget,
        proposal_count=100,
        wall_seconds=10.0,
        j_ids=tuple(f"J-{index}" for index in range(len(primary))),
        primary_metric_by_j=np.asarray(primary),
        other_metric_by_j=np.asarray(other),
        initialization_hash=initialization_hash,
        finite=True,
    )


def test_physical_candidate_uses_paired_whole_j_bootstrap_for_both_budgets() -> None:
    baseline = tuple(
        _evaluation("linear", budget, (0.5, 0.6, 0.7, 0.8), (0.2,) * 4)
        for budget in ("proposal", "wall")
    )
    candidate = tuple(
        _evaluation(
            "C",
            budget,
            (0.1, 0.2, 0.3, 0.4),
            (0.1,) * 4,
            initialization_hash="init-0",
        )
        for budget in ("proposal", "wall")
    )

    result = assess_physical_candidate(
        baseline,
        candidate,
        template="cube",
        chi=2,
        initialization_index=0,
        parameter_count=101,
        seed=2026073603,
        bootstrap_replicates=200,
        material_regression=0.0,
    )

    assert result.passed is True
    assert result.proposal.confidence_interval[0] > 0.0
    assert result.wall.confidence_interval[0] > 0.0
    with pytest.raises(ValueError, match="proposal budgets"):
        assess_physical_candidate(
            baseline,
            (replace(candidate[0], proposal_count=99), candidate[1]),
            template="cube",
            chi=2,
            initialization_index=0,
            parameter_count=101,
            seed=2026073603,
            bootstrap_replicates=200,
            material_regression=0.0,
        )


def _assessment(
    template: str,
    route: str,
    initialization: int,
    *,
    passed: bool,
    split: str = "validation",
) -> PhysicalCandidateAssessment:
    classification = "PASS" if passed else "SCIENTIFIC_NEGATIVE"
    evidence = ImprovementAssessment(
        classification=classification,
        mean_improvement=0.2 if passed else -0.1,
        confidence_interval=(0.1, 0.3) if passed else (-0.2, 0.0),
        maximum_other_regression=-0.1 if passed else 0.1,
    )
    return PhysicalCandidateAssessment(
        template=template,
        route=route,
        chi=2,
        initialization_index=initialization,
        initialization_hash=f"{template}-{route}-{initialization}",
        parameter_count=100 if template == "cube" else 140,
        split=split,
        proposal=evidence,
        wall=evidence,
    )


def _reduced_config():
    return replace(
        load_stage6_representation_config(CONFIG),
        chis=(2,),
        initializations=2,
    )


def test_validation_selection_prefers_stable_low_cost_route_c_then_opens_test() -> None:
    candidates = tuple(
        _assessment(template, route, initialization, passed=True)
        for template, routes in (("cube", ("C", "B")), ("cross", ("B",)))
        for route in routes
        for initialization in range(2)
    )

    validation = select_validation_candidate(candidates, _reduced_config())

    assert validation.classification == "VALIDATION_SELECTED"
    assert (validation.template, validation.route, validation.chi) == (
        "cube",
        "C",
        2,
    )
    assert validation.initialization_index == 0
    test = _assessment("cube", "C", 0, passed=True, split="test")
    selection = finalize_representation_selection(validation, test)
    assert selection.classification == "PASS"
    assert selection.as_pilot_selection()["mps_beats_conditioned_linear"] is True


def test_validation_selection_uses_route_b_only_after_route_c_family_fails() -> None:
    candidates = []
    for template, routes in (("cube", ("C", "B")), ("cross", ("B",))):
        for route in routes:
            for initialization in range(2):
                candidates.append(
                    _assessment(
                        template,
                        route,
                        initialization,
                        passed=not (route == "C" and initialization == 1),
                    )
                )

    validation = select_validation_candidate(tuple(candidates), _reduced_config())

    assert (validation.template, validation.route) == ("cube", "B")
    failed_test = _assessment("cube", "B", 0, passed=False, split="test")
    selection = finalize_representation_selection(validation, failed_test)
    assert selection.classification == "SCIENTIFIC_NEGATIVE"
    assert selection.as_pilot_selection()["mps_beats_conditioned_linear"] is False

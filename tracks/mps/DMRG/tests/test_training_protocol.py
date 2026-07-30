from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from vmcrg_ref.neural_energy import D4EvenLocalMLP, MLPGradient
from vmcrg_ref.hybrid_neural import HybridNeuralVMCRGOptimizer
from vmcrg_ref.operators import EVEN_SHAPES
from vmcrg_ref.training_protocol import (
    PolyakAverager,
    RobbinsMonroSchedule,
    TrainingStopConfig,
    TrainingStopState,
    TrainingProtocol,
    TrainingWindow,
    clip_mlp_gradient,
    load_training_protocol,
)


def test_robbins_monro_uses_literal_formula() -> None:
    schedule = RobbinsMonroSchedule(eta_0=2.0, t_0=4.0, p=0.75)
    assert schedule.rate(0) == pytest.approx(2.0 * 4.0**-0.75)
    assert schedule.rate(10) == pytest.approx(2.0 * 14.0**-0.75)


def _stop_config(patience: int = 3) -> TrainingStopConfig:
    return TrainingStopConfig(
        minimum_updates=2,
        maximum_updates=8,
        monitor_every=1,
        patience_windows=patience,
        held_out_objective_change_upper=0.01,
        gradient_norm_upper=0.1,
        operator_equivalence_upper=0.02,
        patch_tv_upper=0.02,
        parameter_drift_upper=0.005,
        minimum_polyak_fraction=0.10,
    )


def _window(update: int, **changes: float) -> TrainingWindow:
    values = {
        "update": update,
        "held_out_objective": -0.2,
        "held_out_objective_change": 0.001,
        "gradient_norm": 0.05,
        "operator_equivalence": 0.01,
        "patch_tv": 0.01,
        "parameter_drift": 0.001,
        "polyak_fraction": 0.2,
        "parameters_finite": True,
        "gradient_finite": True,
    }
    values.update(changes)
    return TrainingWindow(**values)


def test_stop_requires_every_monitor_gate() -> None:
    state = TrainingStopState(_stop_config(patience=3))
    assert state.observe(_window(2)) is None
    assert state.observe(_window(3, parameter_drift=1.0)) is None
    assert state.observe(_window(4)) is None
    assert state.observe(_window(5)) is None
    assert state.observe(_window(6)) == "CONVERGED"


def test_hard_cap_and_nonfinite_values_fail_closed() -> None:
    state = TrainingStopState(_stop_config())
    assert state.observe(_window(8, gradient_norm=1.0)) == "NOT_CONVERGED"
    nonfinite = TrainingStopState(_stop_config())
    assert nonfinite.observe(_window(2, held_out_objective=np.nan)) == (
        "CORRECTNESS_FAILURE"
    )


def test_gradient_clipping_preserves_direction_and_reports_both_norms() -> None:
    gradient = MLPGradient(
        np.array([[3.0, 4.0]]),
        np.array([0.0]),
        np.array([0.0]),
    )
    clipped, original_norm, clipped_norm = clip_mlp_gradient(gradient, max_norm=1.0)
    assert original_norm == pytest.approx(5.0)
    assert clipped_norm == pytest.approx(1.0)
    np.testing.assert_allclose(clipped.weight_in, gradient.weight_in / 5.0)


def test_polyak_averager_uses_only_frozen_post_start_updates() -> None:
    model = D4EvenLocalMLP.random(1, 2, 7, feature_mode="shell")
    average = PolyakAverager(start_update=2)
    model.weight_out[:] = 1.0
    average.observe(1, model)
    model.weight_out[:] = 2.0
    average.observe(2, model)
    model.weight_out[:] = 4.0
    average.observe(3, model)
    averaged = model.copy()
    average.assign_to(averaged)
    np.testing.assert_allclose(averaged.weight_out, 3.0)
    assert average.sample_count == 2


def test_pilot_training_config_contains_every_formal_parameter() -> None:
    value = json.loads(Path("config/issue28_pilot_v1.json").read_text(encoding="ascii"))
    protocol = load_training_protocol(value["training"])
    assert protocol.schedule == RobbinsMonroSchedule(
        eta_0=1.2574334296829355,
        t_0=250.0,
        p=0.75,
    )
    assert protocol.maximum_updates == 1000
    assert protocol.polyak_start_update == 500
    assert protocol.gradient_clip_l2 == 10.0

    missing = dict(value["training"])
    missing.pop("parameter_drift_upper")
    with pytest.raises(ValueError, match="missing"):
        load_training_protocol(missing)


def test_hybrid_optimizer_explicit_path_uses_schedule_clip_stop_and_polyak() -> None:
    model = D4EvenLocalMLP.random(1, 3, 19, feature_mode="patch")
    optimizer = HybridNeuralVMCRGOptimizer(
        15,
        np.zeros(len(EVEN_SHAPES)),
        np.zeros(len(EVEN_SHAPES)),
        model,
        EVEN_SHAPES,
        walkers=2,
        seed=20,
        parallel_walkers=False,
    )
    protocol = TrainingProtocol(
        schedule=RobbinsMonroSchedule(eta_0=0.02 * 4.0**0.75, t_0=4.0, p=0.75),
        stop=TrainingStopConfig(
            minimum_updates=1,
            maximum_updates=2,
            monitor_every=1,
            patience_windows=1,
            held_out_objective_change_upper=0.01,
            gradient_norm_upper=0.1,
            operator_equivalence_upper=0.02,
            patch_tv_upper=0.02,
            parameter_drift_upper=0.01,
            minimum_polyak_fraction=0.5,
        ),
        sweeps_per_gradient_batch=1,
        gradient_accumulation_batches=1,
        target_samples_per_batch=2,
        polyak_start_update=1,
        polyak_start_fraction=0.5,
        gradient_clip_l2=1e-4,
        checkpoint_every=1,
        progress_every=1,
        independent_sampling_before_update=True,
        monitoring_stream_role="held_out_stopping_only",
    )

    def monitor(update, current_model, record, polyak_fraction):
        return _window(
            update,
            gradient_norm=record.clipped_gradient_norm,
            polyak_fraction=polyak_fraction,
        )

    records = optimizer.run_protocol(protocol, monitor_callback=monitor)
    assert len(records) == 1
    assert records[0].learning_rate == pytest.approx(protocol.schedule.rate(0))
    assert records[0].unclipped_gradient_norm >= records[0].clipped_gradient_norm
    assert records[0].clipped_gradient_norm == pytest.approx(1e-4)
    assert records[0].stop_reason == "CONVERGED"
    assert optimizer.training_stop_reason == "CONVERGED"


def test_hybrid_optimizer_uses_supplied_paired_initial_states() -> None:
    model = D4EvenLocalMLP.random(1, 3, 29, feature_mode="patch")
    initial = np.ones((2, 15, 15), dtype=np.int8)
    initial[1] *= -1
    optimizer = HybridNeuralVMCRGOptimizer(
        15,
        np.zeros(len(EVEN_SHAPES)),
        np.zeros(len(EVEN_SHAPES)),
        model,
        EVEN_SHAPES,
        walkers=2,
        seed=30,
        parallel_walkers=False,
        initial_spins=initial,
    )
    np.testing.assert_array_equal(optimizer.samplers[0].lattice.spins, initial[0])
    np.testing.assert_array_equal(optimizer.samplers[1].lattice.spins, initial[1])


def test_training_protocol_api_is_available_from_package_root() -> None:
    import vmcrg_ref

    assert vmcrg_ref.RobbinsMonroSchedule is RobbinsMonroSchedule
    assert vmcrg_ref.load_training_protocol is load_training_protocol


def test_pure_neural_script_consumes_explicit_training_protocol(tmp_path: Path) -> None:
    from scripts.neural_challenge import train

    fixed_map = tmp_path / "map.json"
    fixed_map.write_text(
        json.dumps(
            {
                "operator_names": [shape.name for shape in EVEN_SHAPES],
                "input_couplings": [0.436, *([0.0] * 12)],
                "final_renormalized_couplings": [0.0] * 13,
            }
        ),
        encoding="utf-8",
    )
    protocol = TrainingProtocol(
        schedule=RobbinsMonroSchedule(eta_0=0.02, t_0=1.0, p=0.75),
        stop=TrainingStopConfig(
            minimum_updates=1,
            maximum_updates=1,
            monitor_every=1,
            patience_windows=1,
            held_out_objective_change_upper=0.01,
            gradient_norm_upper=1.0,
            operator_equivalence_upper=0.02,
            patch_tv_upper=0.02,
            parameter_drift_upper=0.01,
            minimum_polyak_fraction=1.0,
        ),
        sweeps_per_gradient_batch=1,
        gradient_accumulation_batches=1,
        target_samples_per_batch=2,
        polyak_start_update=1,
        polyak_start_fraction=1.0,
        gradient_clip_l2=1.0,
        checkpoint_every=1,
        progress_every=1,
        independent_sampling_before_update=True,
        monitoring_stream_role="held_out_stopping_only",
    )

    def monitor(update, current_model, record, polyak_fraction):
        return _window(
            update,
            gradient_norm=record.clipped_gradient_norm,
            polyak_fraction=polyak_fraction,
        )

    output = tmp_path / "run"
    train(
        output,
        "smoke",
        fixed_map,
        representation="pure",
        training_protocol=protocol,
        monitor_callback=monitor,
    )
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert summary["training_stop_reason"] == "CONVERGED"
    np.testing.assert_array_equal(summary["fixed_linear_bias"], np.zeros(13))


def test_pure_neural_script_records_supplied_initial_state_hash(tmp_path: Path) -> None:
    from scripts.neural_challenge import train
    from vmcrg_ref.artifacts import sha256_bytes

    fixed_map = tmp_path / "map.json"
    fixed_map.write_text(
        json.dumps(
            {
                "operator_names": [shape.name for shape in EVEN_SHAPES],
                "input_couplings": [0.436, *([0.0] * 12)],
                "final_renormalized_couplings": [0.0] * 13,
            }
        ),
        encoding="utf-8",
    )
    initial = np.ones((2, 15, 15), dtype=np.int8)
    initial[1] *= -1
    train(
        tmp_path / "run",
        "smoke",
        fixed_map,
        representation="pure",
        block_size=1,
        training_overrides={
            "length": 15,
            "walkers": 2,
            "steps": 1,
            "sweeps": 1,
            "targets": 2,
        },
        initial_spins=initial,
    )
    config = json.loads((tmp_path / "run" / "config.json").read_text(encoding="utf-8"))
    assert config["initial_state_sha256"] == sha256_bytes(initial.tobytes(order="C"))

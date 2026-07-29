from __future__ import annotations

import importlib
import importlib.util


def _stage4():
    spec = importlib.util.find_spec("tensor_square.stage4")
    assert spec is not None, "Stage 4 scan contract is not implemented"
    return importlib.import_module("tensor_square.stage4")


def test_dense_grid_freezes_core_and_paired_competition_cells() -> None:
    stage4 = _stage4()

    cells = stage4.dense_grid()

    assert len(cells) == 90
    assert len({cell.cell_id for cell in cells}) == 90
    core = [cell for cell in cells if cell.cohort == "half_filled_core"]
    competition = [
        cell for cell in cells if cell.cohort == "paired_competition"
    ]
    assert len(core) == 54
    assert {
        (
            cell.config.g_b_over_g_a,
            cell.config.t,
            cell.config.mu,
            cell.config.m,
            cell.config.beta,
        )
        for cell in core
    } == {
        (g, t, 0.0, m, beta)
        for g in (0.25, 0.5, 1.0)
        for t in (0.25, 0.5, 1.0)
        for m in (4, 6, 8)
        for beta in (4.0, 8.0)
    }
    assert len(competition) == 36
    assert {
        (
            cell.config.g_b_over_g_a,
            cell.config.t,
            cell.config.mu,
            cell.config.m,
            cell.config.beta,
        )
        for cell in competition
    } == {
        (g, t, mu, m, 8.0)
        for g in (0.75, 1.0, 1.25)
        for t in (0.5, 1.0)
        for mu in (-1.5, 1.5)
        for m in (4, 6, 8)
    }
    pair_counts: dict[str, int] = {}
    for cell in competition:
        pair_counts[cell.pair_id] = pair_counts.get(cell.pair_id, 0) + 1
    assert set(pair_counts.values()) == {2}


def test_dense_grid_shards_are_disjoint_and_respect_machine_limits() -> None:
    stage4 = _stage4()
    cells = stage4.dense_grid()

    wsl = stage4.select_shard(cells, "wsl")
    cpu = stage4.select_shard(cells, "cpu")

    assert len(wsl) == 18
    assert len(cpu) == 72
    assert {cell.cell_id for cell in wsl}.isdisjoint(
        {cell.cell_id for cell in cpu}
    )
    assert {cell.cell_id for cell in wsl + cpu} == {
        cell.cell_id for cell in cells
    }
    assert {cell.worker_id for cell in wsl} <= set(range(14))
    assert {cell.worker_id for cell in cpu} <= set(range(14, 76))


def test_replica_seed_is_deterministic_and_separates_phase_and_replica() -> None:
    stage4 = _stage4()

    seed = stage4.replica_seed("cell-a", "pilot", 0, 7)

    assert seed == stage4.replica_seed("cell-a", "pilot", 0, 7)
    assert seed != stage4.replica_seed("cell-a", "pilot", 1, 7)
    assert seed != stage4.replica_seed("cell-a", "production", 0, 7)


def _pilot_summary(*, tau: float = 5.0, acceptance: float = 0.7):
    return {
        "acceptance": acceptance,
        "direct_sign_min": 1.0,
        "weight_log_error_max": 1.0e-12,
        "density_min": 0.2,
        "density_max": 0.8,
        "q_combined_tau_int": tau,
        "q_a_sq_tau_int": tau - 1.0,
        "q_b_sq_tau_int": tau - 2.0,
        "hs_q_a_tau_int": 2.0,
        "hs_q_b_tau_int": 2.5,
        "staggered_structure_tau_int": 1.5,
    }


def test_adaptive_budget_targets_ess_from_worst_pilot_autocorrelation() -> None:
    stage4 = _stage4()
    policy = stage4.Stage4Policy()

    decision = stage4.adaptive_budget(
        [_pilot_summary(tau=4.0), _pilot_summary(tau=5.0)],
        policy=policy,
    )

    assert decision["status"] == "RUN"
    assert decision["worst_tau_int"] == 5.0
    assert decision["warmup_sweeps"] == 240
    assert decision["measurement_sweeps"] == 800
    assert decision["projected_ess_per_replica"] == 40.0


def test_adaptive_budget_stops_unaffordable_tau_or_bad_acceptance() -> None:
    stage4 = _stage4()
    policy = stage4.Stage4Policy()

    too_slow = stage4.adaptive_budget(
        [_pilot_summary(tau=25.0), _pilot_summary(tau=24.0)],
        policy=policy,
    )
    bad_acceptance = stage4.adaptive_budget(
        [_pilot_summary(acceptance=0.01), _pilot_summary()],
        policy=policy,
    )

    assert too_slow["status"] == "STOP"
    assert too_slow["reason"] == "autocorrelation budget cap exceeded"
    assert bad_acceptance["status"] == "STOP"
    assert bad_acceptance["reason"] == "pilot acceptance outside audit window"


def test_adaptive_budget_rejects_missing_determinant_audit() -> None:
    stage4 = _stage4()
    incomplete = _pilot_summary()
    del incomplete["direct_sign_min"]

    decision = stage4.adaptive_budget(
        [incomplete, _pilot_summary()],
        policy=stage4.Stage4Policy(),
    )

    assert decision["status"] == "STOP"
    assert decision["reason"] == "pilot determinant or stability audit failed"


def test_paired_mu_cells_receive_the_same_larger_statistical_budget() -> None:
    stage4 = _stage4()
    cells = stage4.dense_grid()
    pair_id = next(cell.pair_id for cell in cells if cell.pair_id is not None)
    pair = [cell for cell in cells if cell.pair_id == pair_id]
    decisions = {
        pair[0].cell_id: {
            "status": "RUN",
            "warmup_sweeps": 240,
            "measurement_sweeps": 800,
        },
        pair[1].cell_id: {
            "status": "RUN",
            "warmup_sweeps": 360,
            "measurement_sweeps": 1200,
        },
    }

    synchronized = stage4.synchronize_pair_budgets(pair, decisions)

    for cell in pair:
        assert synchronized[cell.cell_id]["warmup_sweeps"] == 360
        assert synchronized[cell.cell_id]["measurement_sweeps"] == 1200
        assert synchronized[cell.cell_id]["paired_budget"] is True


def test_replica_specs_apply_fixed_pilot_and_adaptive_production_budgets() -> None:
    stage4 = _stage4()
    policy = stage4.Stage4Policy()
    cell = stage4.select_shard(stage4.dense_grid(), "wsl")[0]

    pilot = stage4.replica_specs([cell], phase="pilot", policy=policy)
    production = stage4.replica_specs(
        [cell],
        phase="production",
        policy=policy,
        decisions={
            cell.cell_id: {
                "status": "RUN",
                "warmup_sweeps": 360,
                "measurement_sweeps": 1200,
            }
        },
    )

    assert len(pilot) == 2
    assert {spec.replica for spec in pilot} == {0, 1}
    assert {spec.warmup_sweeps for spec in pilot} == {160}
    assert {spec.measurement_sweeps for spec in pilot} == {320}
    assert len(production) == 4
    assert {spec.replica for spec in production} == {0, 1, 2, 3}
    assert {spec.warmup_sweeps for spec in production} == {360}
    assert {spec.measurement_sweeps for spec in production} == {1200}
    assert len({spec.seed for spec in pilot + production}) == 6


def test_production_requires_every_blas_backend_to_be_single_threaded() -> None:
    stage4 = _stage4()
    healthy = {
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
    }

    stage4.validate_blas_environment(healthy)

    for name in healthy:
        broken = {**healthy, name: "2"}
        try:
            stage4.validate_blas_environment(broken)
        except ValueError as error:
            assert name in str(error)
        else:
            raise AssertionError(f"{name}=2 was accepted")

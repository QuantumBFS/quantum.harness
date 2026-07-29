from __future__ import annotations

from tensor_square.scan import (
    classify_regions,
    coarse_grid,
    deterministic_seed,
    needs_stable_retry,
    portable_command,
    run_fingerprint,
    select_shard,
    validate_run_fingerprint,
    validate_source_revision,
)


def test_coarse_grid_covers_the_approved_675_cells_once() -> None:
    cells = coarse_grid()
    assert len(cells) == 675
    assert len({cell.cell_id for cell in cells}) == 675
    assert {cell.config.m for cell in cells} == {4, 6, 8}
    assert {cell.config.beta for cell in cells} == {2.0, 4.0, 8.0}
    assert {cell.config.g_b_over_g_a for cell in cells} == {
        0.0,
        0.25,
        0.5,
        1.0,
        2.0,
    }
    assert {cell.config.t for cell in cells} == {0.0, 0.25, 0.5, 1.0, 2.0}
    assert {cell.config.mu for cell in cells} == {-1.5, 0.0, 1.5}
    assert cells[0].cell_id == "m04_b02_g000_t000_mun15"
    assert cells[-1].cell_id == "m08_b08_g200_t200_mup15"


def test_machine_shards_are_disjoint_complete_and_use_reserved_worker_ids() -> None:
    cells = coarse_grid()
    wsl = select_shard(cells, "wsl")
    cpu = select_shard(cells, "cpu")
    assert len(wsl) == 135
    assert len(cpu) == 540
    assert {cell.cell_id for cell in wsl}.isdisjoint(
        {cell.cell_id for cell in cpu}
    )
    assert {cell.cell_id for cell in wsl + cpu} == {
        cell.cell_id for cell in cells
    }
    assert {cell.worker_id for cell in wsl} <= set(range(14))
    assert {cell.worker_id for cell in cpu} <= set(range(14, 76))


def test_seed_is_stable_and_separates_worker_identity() -> None:
    assert (
        deterministic_seed(
            "stage3-coarse-20260729",
            "m04_b02_g000_t000_mu-15",
            0,
        )
        == 3026704543
    )
    assert deterministic_seed("exp", "cell", 0) != deterministic_seed(
        "exp", "cell", 1
    )


def _region_rows(
    *,
    g: float,
    t: float,
    mu: float,
    q_by_beta_m: dict[tuple[float, int], float],
    stderr: float,
) -> list[dict[str, float | int]]:
    rows: list[dict[str, float | int]] = []
    for beta in (2.0, 4.0, 8.0):
        for m in (4, 6, 8):
            q_value = q_by_beta_m[(beta, m)]
            rows.append(
                {
                    "m": m,
                    "beta": beta,
                    "g_b_over_g_a": g,
                    "t": t,
                    "mu": mu,
                    "q_combined_mean": q_value,
                    "q_combined_stderr": stderr,
                    "q_a_sq_mean": q_value * 0.9,
                    "q_a_sq_stderr": stderr,
                    "q_b_sq_mean": q_value * 1.1,
                    "q_b_sq_stderr": stderr,
                    "channel_balance_mean": 0.1,
                    "channel_balance_stderr": stderr,
                    "density_mean": 0.5,
                    "direct_sign_mean": 1.0,
                    "weight_log_error_mean": 1.0e-12,
                    "acceptance": 0.6,
                    "measurements": 40,
                    "q_a_sq_tau_int": 1.0,
                }
            )
    return rows


def test_classification_keeps_size_and_temperature_enhancement() -> None:
    enhanced = {
        (2.0, 4): 1.00,
        (2.0, 6): 1.02,
        (2.0, 8): 1.04,
        (4.0, 4): 1.05,
        (4.0, 6): 1.12,
        (4.0, 8): 1.20,
        (8.0, 4): 1.10,
        (8.0, 6): 1.30,
        (8.0, 8): 1.60,
    }
    flat = {
        (beta, m): 1.0 for beta in (2.0, 4.0, 8.0) for m in (4, 6, 8)
    }
    regions = classify_regions(
        _region_rows(
            g=1.0, t=0.5, mu=0.0, q_by_beta_m=enhanced, stderr=0.03
        )
        + _region_rows(
            g=0.25, t=0.25, mu=1.5, q_by_beta_m=flat, stderr=0.08
        )
    )
    by_key = {
        (row["g_b_over_g_a"], row["t"], row["mu"]): row for row in regions
    }
    assert by_key[(1.0, 0.5, 0.0)]["classification"] == "SURVIVE"
    assert "size-and-temperature enhancement" in by_key[
        (1.0, 0.5, 0.0)
    ]["reasons"]
    assert by_key[(0.25, 0.25, 1.5)]["classification"] == "STOP"


def test_unstable_direct_audit_requests_stabilized_retry() -> None:
    healthy = {
        "direct_sign_mean": 1.0,
        "weight_log_error_mean": 1.0e-10,
        "density_mean": 0.5,
    }
    assert not needs_stable_retry(healthy)
    assert needs_stable_retry({**healthy, "direct_sign_mean": -1.0})
    assert needs_stable_retry({**healthy, "weight_log_error_mean": 2.0e-5})
    assert needs_stable_retry(
        {**healthy, "weight_log_error_max": 2.0e-5}
    )
    assert needs_stable_retry({**healthy, "density_max": 1.01})
    assert not needs_stable_retry(
        {
            **healthy,
            "density_min": -5.0e-8,
            "density_max": 1.0 + 5.0e-8,
        }
    )
    assert needs_stable_retry({**healthy, "density_min": -2.0e-6})
    assert needs_stable_retry({**healthy, "density_max": 1.0 + 2.0e-6})


def test_single_channel_and_zero_kinetic_controls_do_not_survive() -> None:
    enhanced = {
        (2.0, 4): 1.00,
        (2.0, 6): 1.02,
        (2.0, 8): 1.04,
        (4.0, 4): 1.05,
        (4.0, 6): 1.12,
        (4.0, 8): 1.20,
        (8.0, 4): 1.10,
        (8.0, 6): 1.30,
        (8.0, 8): 1.60,
    }
    regions = classify_regions(
        _region_rows(
            g=0.0, t=0.5, mu=0.0, q_by_beta_m=enhanced, stderr=0.03
        )
        + _region_rows(
            g=0.5, t=0.0, mu=0.0, q_by_beta_m=enhanced, stderr=0.03
        )
    )
    by_key = {
        (row["g_b_over_g_a"], row["t"], row["mu"]): row for row in regions
    }
    assert by_key[(0.0, 0.5, 0.0)]["classification"] == "STOP"
    assert by_key[(0.5, 0.0, 0.0)]["classification"] == "STOP"


def test_manifest_command_does_not_expose_absolute_home_paths() -> None:
    project = "/home/researcher/code/tensor-square-phase-diagram"
    command = portable_command(
        [
            f"{project}/scripts/run_phase_scan.py",
            "--output-dir",
            f"{project}/results/stage3_coarse_20260729",
            "--machine",
            "cpu",
        ],
        project,
    )
    assert command == [
        "python",
        "scripts/run_phase_scan.py",
        "--output-dir",
        "results/stage3_coarse_20260729",
        "--machine",
        "cpu",
    ]
    assert "/home/" not in " ".join(command)


def test_run_fingerprint_changes_with_schedule_seed_or_source() -> None:
    base = {
        "experiment_id": "stage3",
        "cell_id": "cell-1",
        "seed": 7,
        "warmup_sweeps": 40,
        "measurement_sweeps": 80,
        "measure_every": 2,
        "source_revision": "abc123",
    }
    fingerprint = run_fingerprint(base)
    assert fingerprint == run_fingerprint(dict(reversed(list(base.items()))))
    assert fingerprint != run_fingerprint({**base, "seed": 8})
    assert fingerprint != run_fingerprint(
        {**base, "measurement_sweeps": 160}
    )
    assert fingerprint != run_fingerprint(
        {**base, "source_revision": "def456"}
    )


def test_incompatible_summary_fingerprint_is_refused() -> None:
    validate_run_fingerprint("same", "same")
    try:
        validate_run_fingerprint("old", "new")
    except ValueError as error:
        assert "fingerprint" in str(error)
    else:
        raise AssertionError("mismatched fingerprint was silently reused")


def test_production_scan_requires_clean_known_source_revision() -> None:
    validate_source_revision("abc123", dirty=False)
    for commit, dirty in (("unknown", False), ("abc123", True)):
        try:
            validate_source_revision(commit, dirty=dirty)
        except ValueError as error:
            assert "source revision" in str(error)
        else:
            raise AssertionError("non-reproducible source was accepted")

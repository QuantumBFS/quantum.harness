import numpy as np

from analysis.bootstrap import bootstrap_mc


def test_bootstrap_is_reproducible_and_contains_injected_half_charge():
    blocks, manifest = synthetic_blocks()
    first = bootstrap_mc(blocks, manifest, draws=200, seed=731)
    second = bootstrap_mc(blocks, manifest, draws=200, seed=731)
    np.testing.assert_array_equal(first.g_draws_primary, second.g_draws_primary)
    np.testing.assert_array_equal(
        first.c_draws_primary[6], second.c_draws_primary[6]
    )
    assert first.primary_grid_points == 5
    assert first.nested_grid_points == 3
    low, high = np.percentile(first.c_draws_primary[6], [2.5, 97.5])
    assert low <= 0.5 <= high
    assert first.integration_shift < first.primary_standard_error


def synthetic_blocks():
    widths = [4, 6, 8, 10, 12, 16]
    aspect_ratio = 8
    critical_k = 0.44068679350977147
    grid_intervals = 4
    replicas = 4
    blocks_per_replica = 8
    block_sweeps = 10
    f_infinity = -0.9296953983
    correction = 0.07
    rng = np.random.default_rng(991)
    records = []
    seeds = []
    for width in widths:
        length = aspect_ratio * width
        sites = width * length
        per_site = (
            f_infinity
            - np.pi * 0.5 / (6.0 * width**2)
            + correction / width**4
        )
        target_free_energy = length * width * per_site
        integral = target_free_energy + sites * np.log(2.0)
        for k_index in range(grid_intervals + 1):
            k_value = critical_k * k_index / grid_intervals
            expected_energy = 2.0 * integral * k_value / critical_k**2
            noise = rng.normal(
                0.0,
                0.4,
                size=(replicas, blocks_per_replica),
            )
            noise -= noise.mean()
            for replica in range(replicas):
                seed = width * 1000 + k_index * 10 + replica
                seeds.append(
                    {
                        "l": width,
                        "k_index": k_index,
                        "replica": replica,
                        "seed": seed,
                    }
                )
                for block_index in range(blocks_per_replica):
                    block_mean = expected_energy + noise[replica, block_index]
                    records.append(
                        {
                            "schema_version": 1,
                            "l": width,
                            "m": length,
                            "k_index": k_index,
                            "k": k_value,
                            "replica": replica,
                            "seed": seed,
                            "thermal_sweeps": 20,
                            "measurement_sweeps": blocks_per_replica * block_sweeps,
                            "block_index": block_index,
                            "block_sweeps": block_sweeps,
                            "cluster_updates_per_sweep": 1,
                            "energy_sum": block_mean * block_sweeps,
                            "energy_squared_sum": block_mean**2 * block_sweeps,
                            "measurement_count": block_sweeps,
                            "mean_cluster_size": 1.0,
                            "max_cluster_size": 1,
                            "cumulative_elapsed_s": 0.0,
                        }
                    )
    manifest = {
        "schema_version": 1,
        "config": {
            "widths": widths,
            "aspect_ratio": aspect_ratio,
            "critical_k": critical_k,
            "base_seed": 42,
            "production_gates": False,
            "exact": {
                "max_iterations": 10000,
                "eigenvalue_tolerance": 1.0e-12,
                "residual_tolerance": 1.0e-10,
            },
            "mc": {
                "replicas": replicas,
                "grid_intervals": grid_intervals,
                "thermal_sweeps": 20,
                "measurement_sweeps": blocks_per_replica * block_sweeps,
                "block_sweeps": block_sweeps,
            },
        },
        "seeds": seeds,
    }
    return records, manifest

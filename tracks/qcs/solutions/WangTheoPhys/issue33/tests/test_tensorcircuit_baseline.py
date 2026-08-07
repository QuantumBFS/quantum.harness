import json

import jax
import numpy as np

from vqetape.spec import TFIMVQESpec
from vqetape.tensorcircuit_baseline import (
    build_protocol,
    matched_parameters,
    run_baseline,
)
from vqetape.kernels import unrolled_energy
from vqetape.worker import _parameters
from vqetape.tensorcircuit_baseline_cli import _parser, _write_json_atomic


def test_matched_parameters_equal_vqetape_worker():
    spec = TFIMVQESpec(nqubits=4, depth=2)

    actual = matched_parameters(spec, seed=33)

    assert np.array_equal(actual, _parameters(spec, 33))
    assert actual.dtype == np.float32


def test_matched_parameters_follow_complex128_real_dtype():
    spec = TFIMVQESpec(
        nqubits=3,
        depth=1,
        dtype="complex128",
    )

    actual = matched_parameters(spec, seed=7)

    assert actual.dtype == np.float64


def test_protocol_records_exact_matched_workload():
    protocol = build_protocol(
        TFIMVQESpec(nqubits=10, depth=4),
        seed=33,
    )

    assert protocol["hamiltonian"] == (
        "-sum_i Z_i Z_{i+1} - sum_i X_i"
    )
    assert protocol["boundary"] == "open"
    assert protocol["ansatz"] == "plus_then_rzz_rx"
    assert protocol["parameter_shape"] == [4, 2, 10]
    assert protocol["active_parameter_count"] == 76
    assert protocol["seed"] == 33
    assert protocol["parameter_distribution"] == (
        "numpy.default_rng.normal(loc=0, scale=0.1)"
    )
    assert protocol["comparison_scope"] == (
        "matched_rzz_rx_not_fig2_su4"
    )


def test_greedy_baseline_matches_vqetape_reference(tmp_path):
    spec = TFIMVQESpec(nqubits=3, depth=1)
    theta = matched_parameters(spec, seed=7)
    energy, gradient = jax.value_and_grad(
        lambda values: unrolled_energy(values, spec)
    )(theta)
    reference_path = tmp_path / "reference.json"
    reference_path.write_text(
        json.dumps(
            {
                "candidate": {
                    "energy": float(np.asarray(energy)),
                    "gradient": np.asarray(gradient).tolist(),
                }
            }
        ),
        encoding="utf-8",
    )

    with jax.default_matmul_precision("highest"):
        report = run_baseline(
            spec=spec,
            seed=7,
            warm_repeats=2,
            contractor="greedy",
            reference_path=reference_path,
        )

    assert report["correctness"]["tolerance_passed"]
    assert report["correctness"]["energy_abs_error"] <= 1e-5
    assert (
        report["correctness"]["gradient_relative_l2_error"]
        <= 1e-5
    )
    assert report["timings"]["compile_seconds"] >= 0
    assert report["timings"]["first_execute_seconds"] >= 0
    assert report["timings"]["warm_seconds_median"] > 0
    assert len(report["timings"]["warm_seconds"]) == 2
    assert report["runtime"]["jax_backend"] == "cpu"
    assert report["runtime"]["tensor_network_jax_precision"] == (
        "HIGHEST"
    )
    assert report["result"]["gradient"][-1][0][-1] == 0.0


def test_baseline_cli_defaults_match_gpu_workload(tmp_path):
    output = tmp_path / "baseline.json"

    args = _parser().parse_args(["--output", str(output)])

    assert args.nqubits == 10
    assert args.depth == 4
    assert args.seed == 33
    assert args.warm_repeats == 5
    assert args.expected_steps == 100
    assert args.contractor == "omeco"
    assert args.dtype == "complex64"
    assert args.output == output


def test_atomic_json_writer_leaves_no_predictable_temporary(tmp_path):
    output = tmp_path / "baseline.json"

    _write_json_atomic(output, {"finite": 1.0})

    assert json.loads(output.read_text(encoding="utf-8")) == {
        "finite": 1.0
    }
    assert list(tmp_path.glob(".baseline.json.*.tmp")) == []

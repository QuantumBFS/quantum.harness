import json

import jax
import pytest

from vqetape.tensorcircuit_fig2 import (
    Fig2Spec,
    build_fig2_protocol,
    fig2_cotengra_options,
    protocol_sha256,
    run_fig2_path,
    search_fig2_path,
    validate_path_payload,
)
from vqetape.tensorcircuit_fig2_cli import _parser, main


def test_fig2_spec_matches_paper_parameter_count():
    spec = Fig2Spec()

    assert spec.parameter_shape == (16, 31, 15)
    assert spec.parameter_count == 7440


def test_fig2_protocol_records_paper_score_and_boundary():
    protocol = build_fig2_protocol(Fig2Spec())

    assert protocol["paper"]["arxiv"] == "2602.14167"
    assert protocol["paper"][
        "reported_single_gpu_n32_l16_step_seconds"
    ] == 17.86
    assert protocol["ansatz"]["layout"].startswith("ladder:")
    assert protocol["ansatz"]["parameter_count"] == 7440
    assert protocol["contractor"]["max_repeats"] == 640
    assert protocol["contractor"]["minimize"] == "combo-640"
    assert protocol["contractor"]["score"] == "FLOPS + 640 * WRITE"
    assert protocol["contractor"]["slicing_target_elements"] == 2**29
    assert "40-qubit" in protocol["contractor"]["slicing_boundary"]
    assert "does not state" in protocol["numerics"]["seed_boundary"]


def test_cotengra_options_are_exact_and_validated():
    options = fig2_cotengra_options(
        max_repeats=7,
        target_size=2**12,
        parallel=2,
    )

    assert options == {
        "slicing_reconf_opts": {"target_size": 2**12},
        "max_repeats": 7,
        "minimize": "combo-640",
        "parallel": 2,
        "progbar": False,
    }
    with pytest.raises(ValueError, match="max_repeats"):
        fig2_cotengra_options(max_repeats=0)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"nqubits": 1}, "nqubits"),
        ({"depth": 0}, "depth"),
        ({"dtype": "float32"}, "dtype"),
        ({"parameter_scale": 0.0}, "parameter_scale"),
    ],
)
def test_fig2_spec_rejects_invalid_inputs(kwargs, message):
    with pytest.raises(ValueError, match=message):
        Fig2Spec(**kwargs)


def test_fig2_cli_defaults_are_formal_paper_workload(tmp_path):
    output = tmp_path / "manifest.json"

    args = _parser().parse_args(["manifest", "--output", str(output)])

    assert args.nqubits == 32
    assert args.depth == 16
    assert args.max_repeats == 640
    assert args.target_size_log2 == 29
    assert args.parallel == 1
    assert args.seed == 42


def test_manifest_command_writes_self_verifying_protocol(tmp_path):
    output = tmp_path / "manifest.json"

    assert main(["manifest", "--output", str(output)]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["artifact_type"] == "tensorcircuit_ng_fig2_manifest"
    assert payload["protocol"]["ansatz"]["parameter_count"] == 7440
    assert payload["protocol_sha256"] == protocol_sha256(
        payload["protocol"]
    )


def test_path_validator_rejects_checksum_mismatch():
    protocol = build_fig2_protocol(Fig2Spec(nqubits=3, depth=1))
    payload = {
        "schema_version": 1,
        "artifact_type": "tensorcircuit_ng_fig2_path",
        "protocol": protocol,
        "protocol_sha256": "0" * 64,
        "tree_data": {},
    }

    with pytest.raises(ValueError, match="checksum"):
        validate_path_payload(payload)


def test_small_fig2_json_path_matches_direct_contraction():
    spec = Fig2Spec(nqubits=3, depth=1, seed=7)

    with jax.default_matmul_precision("highest"):
        searched = search_fig2_path(
            spec,
            max_repeats=1,
            target_size=2**8,
            parallel=1,
        )
        # Exercise the real artifact boundary rather than passing the Python
        # object directly between the two stages.
        restored = json.loads(json.dumps(searched, allow_nan=False))
        report = run_fig2_path(
            restored,
            warm_repeats=1,
            verify_direct=True,
        )

    assert report["result"]["gradient_shape"] == [1, 2, 15]
    assert report["correctness"]["tolerance_passed"]
    assert report["correctness"]["energy_abs_error"] <= 1e-5
    assert (
        report["correctness"]["gradient_relative_l2_error"] <= 1e-5
    )

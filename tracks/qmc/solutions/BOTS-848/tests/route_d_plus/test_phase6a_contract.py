from __future__ import annotations

import json
from pathlib import Path

SOLUTION_ROOT = Path(__file__).resolve().parents[2]
ROUTE_D_PLUS_ROOT = SOLUTION_ROOT / "route_d_plus"


def test_phase6a_schema_requires_full_isolated_gate_evidence() -> None:
    schema = json.loads(
        (ROUTE_D_PLUS_ROOT / "phase6a.schema.json").read_text(
            encoding="utf-8"
        )
    )
    properties = schema["properties"]
    assert properties["n_electrons"]["const"] == 6
    assert properties["two_q"]["const"] == 15
    assert properties["continuous_configurations"]["const"] == 2
    assert (
        properties["quadrature"]["properties"]["reconstruction_error"][
            "exclusiveMaximum"
        ]
        == 1.0e-12
    )
    backend = properties["backend_cross_validation"]["properties"]
    assert backend["tolerance"]["const"] == 1.0e-10
    assert backend["records"]["minItems"] == 2
    assert backend["records"]["maxItems"] == 2
    cache = properties["cache_profile"]["properties"]
    assert cache["key_fields"]["prefixItems"] == [
        {"const": "N"},
        {"const": "two_q"},
        {"const": "L"},
        {"const": "M"},
        {"const": "word_id"},
        {"const": "configuration_digest"},
    ]
    delayed = properties["delayed_acceptance"]["properties"]
    assert delayed["correction_acceptance"]["const"] == 1.0
    assert delayed["ess_per_second"]["exclusiveMinimum"] == 0
    evidence = properties["evidence"]
    assert {
        "stdout_sha256",
        "stderr_sha256",
        "slurm_evidence_sha256",
        "slurm_state",
        "slurm_exit_code",
    } <= set(evidence["required"])
    assert properties["passed"]["const"] is True


def test_phase6a_profiler_separates_run_finalize_and_readback() -> None:
    source = (ROUTE_D_PLUS_ROOT / "certify_phase6a.py").read_text(
        encoding="utf-8"
    )
    assert "compact_reproducing_quadrature(TWO_Q)" in source
    assert "scalar_laughlin_amplitudes_kernel" in source
    assert "CoordinateAmplitudeCache" in source
    assert "delayed_acceptance_chain" in source
    assert "ess_per_second" in source
    assert 'subparsers.add_parser("run")' in source
    assert 'subparsers.add_parser("finalize")' in source
    assert 'subparsers.add_parser("verify")' in source
    assert "COMPLETED 0:0" in source
    assert "sha256_file(Path(evidence[" in source
    assert "FORBIDDEN_MODULE_PREFIXES" in source

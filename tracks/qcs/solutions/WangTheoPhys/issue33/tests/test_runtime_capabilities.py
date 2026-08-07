import json

from vqetape.runtime_capabilities import (
    runtime_capabilities,
    write_runtime_capabilities,
)


def test_runtime_capabilities_separate_memory_meanings():
    payload = runtime_capabilities()

    assert payload["jax"]["device_count"] >= 1
    assert payload["memory_evidence"]["process_peak_rss"][
        "meaning"
    ].endswith("not GPU peak memory")
    assert payload["gpu_benchmark"]["status"] in (
        "available",
        "skipped",
    )
    if payload["gpu_benchmark"]["status"] == "skipped":
        assert "no GPU" in payload["gpu_benchmark"]["reason"]
        assert not payload["gpu_benchmark"][
            "peak_memory_measured"
        ]


def test_runtime_capability_report_is_json_round_trippable(
    tmp_path,
):
    output = tmp_path / "runtime.json"
    findings = tmp_path / "runtime.md"

    payload = write_runtime_capabilities(
        output,
        findings,
    )
    restored = json.loads(output.read_text())

    assert restored == payload
    assert findings.read_text().startswith(
        "# VQETape runtime capabilities"
    )

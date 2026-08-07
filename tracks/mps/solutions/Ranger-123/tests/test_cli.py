import json
from pathlib import Path

from heat_valve_fixtures import valid_heat_valve_manifest

from floquet_if_manybody.cli import build_parser, main


def test_quick_baseline_and_audit(tmp_path):
    results = tmp_path / "results"
    figures = tmp_path / "figures"
    assert main(["baselines", "--output", str(results), "--figures", str(figures), "--quick"]) == 0
    assert main(["audit", str(results), "--allow-unconverged"]) == 0
    for path in results.glob("*.json"):
        payload = json.loads(path.read_text())
        assert payload["schema_version"] == 1
        assert payload["config_hash"]
        assert payload["method"]
        assert "environment" in payload
    assert len(list(figures.glob("*.pdf"))) == 4
    assert len(list(figures.glob("*.png"))) == 4


def test_audit_ignores_artifact_provenance(tmp_path) -> None:
    results = tmp_path / "results"
    results.mkdir()
    (results / "ARTIFACT_PROVENANCE.json").write_text(
        json.dumps({"schema_version": 1, "artifacts": []}),
        encoding="utf-8",
    )
    assert (
        main(
            [
                "baselines",
                "--output",
                str(results),
                "--figures",
                str(tmp_path / "figures"),
                "--quick",
            ]
        )
        == 0
    )
    assert main(["audit", str(results), "--allow-unconverged"]) == 0


def test_publication_commands_default_to_uniform_tempo() -> None:
    parser = build_parser()
    for command in ("n3-heat-grid", "error-map", "model-comparison"):
        arguments = parser.parse_args([command])
        assert arguments.exact_backend == "uniform_tempo"
        explicit = parser.parse_args([command, "--exact-backend", "oqupy"])
        assert explicit.exact_backend == "oqupy"


def test_heat_valve_cli_defaults() -> None:
    arguments = build_parser().parse_args(["heat-valve"])
    assert arguments.output == Path("results/heat-valve")
    assert arguments.cache == Path("results/cache/uniform_tempo")
    assert arguments.figures == Path("figures/heat-valve")
    assert not arguments.full


def test_heat_valve_audit_command_accepts_a_valid_manifest(tmp_path) -> None:
    manifest = valid_heat_valve_manifest()
    (tmp_path / "heat_valve_manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    assert main(["heat-valve-audit", str(tmp_path)]) == 0

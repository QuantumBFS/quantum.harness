import argparse

import pytest

from challenge15.cli import _parser, _runtime_attestation_commands


def _parse(*argv: str) -> argparse.Namespace:
    return _parser().parse_args(argv)


@pytest.mark.parametrize(
    ("command", "argv"),
    [
        ("policy", ["--output", "/x", "--create-only"]),
        (
            "source-manifest",
            ["--root", "/r", "--policy", "/p", "--output", "/o", "--require-clean"],
        ),
        (
            "runtime-attest",
            [
                "--role", "training", "--controller", "qdeshell",
                "--profile", "cuda12", "--wheelhouse", "/w",
                "--source-manifest", "/s", "--policy", "/p",
                "--expected-backend", "gpu", "--output-dir", "/o", "--create-only",
            ],
        ),
        (
            "production-orchestrate-size",
            [
                "--particles", "6", "--rank-ladder", "1,2,4,8",
                "--seeds", "0,1,2,3,4", "--base-config", "/b",
                "--policy", "/p", "--source-manifest", "/s",
                "--runtime-set-local", "/rl", "--runtime-set-local-sha256", "a" * 64,
                "--cpu-runtime-set-remote", "/rc", "--cpu-runtime-set-receipt", "/crc",
                "--gpu-runtime-set-remote", "/rg", "--gpu-runtime-set-receipt", "/grc",
                "--cpu-controller", "lasg02", "--gpu-controller", "qdeshell",
                "--cpu-profile", "/cp", "--gpu-profile", "/gp",
                "--cpu-deployment-receipt", "/cd", "--gpu-deployment-receipt", "/gd",
                "--cpu-results-root", "/cr", "--gpu-results-root", "/gr",
                "--state-root-base", "/state", "--state-backup-uri", "ssh://cpu/backup",
                "--transition-action-manifest", "/tam",
                "--create-only",
            ],
        ),
    ],
)
def test_exact_production_contracts_parse(command, argv):
    assert _parse(command, *argv).command == command


def test_vmc_train_requires_provenance_contract():
    with pytest.raises(SystemExit):
        _parse(
            "vmc-train",
            "--base-config", "/b", "--extension", "/e",
            "--owner", "/o", "--destination", "/d", "--create-only",
        )


def test_n7_orchestrator_requires_prerequisite():
    args = _parse(
        "production-orchestrate-size",
        "--particles", "7", "--rank-ladder", "1,2,4,8",
        "--seeds", "0,1,2,3,4", "--base-config", "/b",
        "--policy", "/p", "--source-manifest", "/s",
        "--runtime-set-local", "/rl", "--runtime-set-local-sha256", "a" * 64,
        "--cpu-runtime-set-remote", "/rc", "--cpu-runtime-set-receipt", "/crc",
        "--gpu-runtime-set-remote", "/rg", "--gpu-runtime-set-receipt", "/grc",
        "--cpu-controller", "lasg02", "--gpu-controller", "qdeshell",
        "--cpu-profile", "/cp", "--gpu-profile", "/gp",
        "--cpu-deployment-receipt", "/cd", "--gpu-deployment-receipt", "/gd",
        "--cpu-results-root", "/cr", "--gpu-results-root", "/gr",
        "--state-root-base", "/state", "--state-backup-uri", "ssh://cpu/backup",
        "--transition-action-manifest", "/tam",
        "--create-only",
    )
    with pytest.raises(ValueError, match="prerequisite"):
        args.handler(args)


def test_runtime_attestation_installs_and_tests_supplied_wheelhouse(tmp_path):
    wheelhouse = tmp_path / "wheelhouse"
    environment = tmp_path / "attestation-env"
    commands = _runtime_attestation_commands(
        wheelhouse=wheelhouse,
        environment=environment,
        requirements=tmp_path / "requirements.txt",
    )
    interpreter = str(environment / "bin" / "python")
    assert commands[1][:4] == (interpreter, "-m", "pip", "install")
    assert "--no-index" in commands[1]
    assert "--require-hashes" in commands[1]
    assert str(wheelhouse) in commands[1]
    assert commands[2][:4] == (interpreter, "-m", "pytest", "-m")
    assert "production" in commands[2]

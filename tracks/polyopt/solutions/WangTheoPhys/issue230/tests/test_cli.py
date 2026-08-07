from pathlib import Path
import json
import subprocess


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [".venv/bin/xxzcert", *args], text=True, capture_output=True, check=False
    )


def test_generate_verify_report(tmp_path: Path):
    generated = run_cli(
        "generate",
        "--delta",
        "0,1",
        "--lti-levels",
        "2,3",
        "--block-sizes",
        "2,4",
        "--output",
        str(tmp_path),
    )
    assert generated.returncode == 0, generated.stderr
    verified = run_cli("verify", str(tmp_path))
    assert verified.returncode == 0, verified.stdout + verified.stderr
    assert verified.stdout.count("PASS") == 4
    reported = run_cli("report", str(tmp_path))
    assert reported.returncode == 0
    assert "certified_lower" in reported.stdout
    audit_path = tmp_path.parent / f"{tmp_path.name}-audit.json"
    audited = run_cli(
        "audit", str(tmp_path), "--json", str(audit_path)
    )
    assert audited.returncode == 0, audited.stdout + audited.stderr
    payload = json.loads(audit_path.read_text())
    assert payload["ok"]
    assert len(payload["rows"]) == 4


def test_verify_empty_directory_fails(tmp_path: Path):
    result = run_cli("verify", str(tmp_path))
    assert result.returncode != 0
    assert "no certificate" in result.stdout


def test_proof_level_can_exceed_raw_lti_cap(tmp_path: Path):
    generated = run_cli(
        "generate",
        "--delta",
        "1",
        "--lti-levels",
        "7",
        "--block-sizes",
        "4",
        "--raw-lti-cap",
        "3",
        "--output",
        str(tmp_path),
    )
    assert generated.returncode == 0, generated.stderr
    assert run_cli("verify", str(tmp_path)).returncode == 0

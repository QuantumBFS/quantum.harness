from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
DIRECT = ROOT / "production" / "direct"
PREPARE = DIRECT / "prepare_run.py"
BATCH = DIRECT / "n6_train_qdeshell.sbatch"
SUBMIT = DIRECT / "submit_run.sh"
VERIFY = DIRECT / "verify_download.py"
PROFILE = DIRECT / "qdeshell_profile.json"


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _load_envelope(path: Path) -> dict:
    raw = path.read_bytes()
    document = json.loads(raw)
    assert raw == _canonical(document)
    assert document["payload_sha256"] == hashlib.sha256(
        _canonical(document["payload"])[:-1]
    ).hexdigest()
    return document


def _run(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, **kwargs)


@pytest.fixture
def source_checkout(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    (source / "challenge15").mkdir()
    (source / "challenge15" / "__init__.py").write_text("", encoding="utf-8")
    (source / "challenge15" / "cli.py").write_text(
        """
import json
import os
from pathlib import Path
import sys
import time

assert sys.argv[1] == "train"
output = Path(sys.argv[sys.argv.index("--output") + 1])
seed = sys.argv[sys.argv.index("--seeds") + 1]
log = Path(os.environ["FAKE_TRAIN_LOG"])
with log.open("a", encoding="utf-8") as stream:
    stream.write(json.dumps({
        "argv": sys.argv[1:],
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "mkl_num_threads": os.environ.get("MKL_NUM_THREADS"),
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
        "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS"),
    }, sort_keys=True) + "\\n")
barrier = os.environ.get("FAKE_CONCURRENCY_DIR")
if barrier:
    barrier_path = Path(barrier)
    barrier_path.mkdir(exist_ok=True)
    (barrier_path / seed).write_text(seed + "\\n", encoding="utf-8")
    deadline = time.monotonic() + 3
    while len(list(barrier_path.iterdir())) != 5:
        if time.monotonic() >= deadline:
            raise SystemExit(8)
        time.sleep(0.01)
output.mkdir(parents=True, exist_ok=True)
checkpoint = output / "checkpoint.json"
if os.environ.get("FAKE_FAIL_SEED") == seed and not checkpoint.exists():
    checkpoint.write_text('{"checkpoint":true}\\n', encoding="utf-8")
    raise SystemExit(9)
checkpoint.write_text('{"checkpoint":true}\\n', encoding="utf-8")
(output / "result.json").write_text(
    json.dumps({"seed": int(seed), "production_accepted": False}) + "\\n",
    encoding="utf-8",
)
print(f"seed={seed}")
""".lstrip(),
        encoding="utf-8",
    )
    (source / "smoke.json").write_bytes(
        _canonical(
            {
                "batch_size": 1,
                "depth": 0,
                "fourier_order": 1,
                "hidden_width": 4,
                "projection_block_size": 8,
                "token_width": 2,
            }
        )
    )
    subprocess.run(["git", "init", "-q"], cwd=source, check=True)
    subprocess.run(["git", "add", "."], cwd=source, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Direct Runner Test",
            "-c",
            "user.email=direct@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        cwd=source,
        check=True,
    )
    return source


def _prepare(source: Path, run_dir: Path, output_root: Path):
    interpreter = str(Path(sys.executable).resolve())
    return _run(
        [
            interpreter,
            str(PREPARE),
            "--source-root",
            str(source),
            "--config",
            str(source / "smoke.json"),
            "--interpreter",
            interpreter,
            "--run-dir",
            str(run_dir),
            "--output-root",
            str(output_root),
        ]
    )


def test_prepare_records_clean_source_runtime_command_and_five_immutable_tasks(
    source_checkout: Path, tmp_path: Path
):
    run_dir = tmp_path / "run"
    output_root = tmp_path / "outputs"

    prepared = _prepare(source_checkout, run_dir, output_root)

    assert prepared.returncode == 0, prepared.stderr
    manifest = _load_envelope(run_dir / "run.json")
    payload = manifest["payload"]
    assert payload["source"]["commit"] == _run(
        ["git", "rev-parse", "HEAD"], cwd=source_checkout
    ).stdout.strip()
    assert payload["config"]["canonical_sha256"]
    assert payload["runtime"]["interpreter_sha256"]
    assert payload["runtime"]["identity_sha256"]
    assert payload["particles"] == 6
    assert payload["rank"] == 1
    assert payload["seeds"] == [0, 1, 2, 3, 4]
    assert payload["steps"] == 1
    assert payload["command_template"] == [
        payload["runtime"]["interpreter"],
        "-m",
        "challenge15.cli",
        "train",
        "--config",
        payload["config"]["path"],
        "--particles",
        "6",
        "--ranks",
        "1",
        "--seeds",
        "{seed}",
        "--steps",
        "1",
        "--output",
        "{output_dir}",
        "{resume}",
    ]
    assert len(payload["tasks"]) == 5
    for index, entry in enumerate(payload["tasks"]):
        task_path = run_dir / entry["relative_path"]
        task = _load_envelope(task_path)
        assert task["payload"]["task_id"] == index
        assert task["payload"]["seed"] == index
        assert hashlib.sha256(task_path.read_bytes()).hexdigest() == entry["sha256"]
        assert stat.S_IMODE(task_path.stat().st_mode) == 0o444
    assert stat.S_IMODE((run_dir / "run.json").stat().st_mode) == 0o444


def test_prepare_rejects_dirty_duplicate_traversal_symlink_and_hash_mismatch(
    source_checkout: Path, tmp_path: Path
):
    dirty = source_checkout / "dirty"
    dirty.write_text("x", encoding="utf-8")
    failed = _prepare(source_checkout, tmp_path / "dirty-run", tmp_path / "outputs")
    assert failed.returncode != 0
    assert "clean committed source" in failed.stderr
    dirty.unlink()

    run_dir = tmp_path / "run"
    assert _prepare(source_checkout, run_dir, tmp_path / "outputs").returncode == 0
    duplicate = _prepare(source_checkout, run_dir, tmp_path / "outputs")
    assert duplicate.returncode != 0
    assert "already exists" in duplicate.stderr

    traversal = _run(
        [
            sys.executable,
            str(PREPARE),
            "--source-root",
            str(source_checkout),
            "--config",
            "../smoke.json",
            "--interpreter",
            str(Path(sys.executable).resolve()),
            "--run-dir",
            str(tmp_path / "traversal"),
            "--output-root",
            str(tmp_path / "out2"),
        ]
    )
    assert traversal.returncode != 0

    linked = tmp_path / "linked-config.json"
    linked.symlink_to(source_checkout / "smoke.json")
    symlinked = _run(
        [
            sys.executable,
            str(PREPARE),
            "--source-root",
            str(source_checkout),
            "--config",
            str(linked),
            "--interpreter",
            str(Path(sys.executable).resolve()),
            "--run-dir",
            str(tmp_path / "symlink-run"),
            "--output-root",
            str(tmp_path / "out3"),
        ]
    )
    assert symlinked.returncode != 0
    assert "symlink" in symlinked.stderr

    mismatched = _run(
        [
            sys.executable,
            str(PREPARE),
            "--source-root",
            str(source_checkout),
            "--config",
            str(source_checkout / "smoke.json"),
            "--config-sha256",
            "0" * 64,
            "--interpreter",
            str(Path(sys.executable).resolve()),
            "--run-dir",
            str(tmp_path / "mismatch-run"),
            "--output-root",
            str(tmp_path / "out4"),
        ]
    )
    assert mismatched.returncode != 0
    assert "config SHA256 mismatch" in mismatched.stderr


def _slurm_env(log: Path) -> dict[str, str]:
    return {
        **os.environ,
        "CHALLENGE15_PYTHON": str(Path(sys.executable).resolve()),
        "FAKE_TRAIN_LOG": str(log),
        "SLURM_JOB_ACCOUNT": "giggleliu",
        "SLURM_CPUS_PER_TASK": "64",
        "SLURM_JOB_ID": "1234",
        "SLURM_JOB_PARTITION": "dzagnormal",
        "SLURM_JOB_QOS": "user_jiangweiqi",
    }


def test_batch_has_exact_resources_publishes_done_and_is_idempotent(
    source_checkout: Path, tmp_path: Path
):
    text = BATCH.read_text(encoding="utf-8")
    for directive in (
        "#SBATCH --partition=dzagnormal",
        "#SBATCH --account=giggleliu",
        "#SBATCH --qos=user_jiangweiqi",
        "#SBATCH --nodes=1",
        "#SBATCH --ntasks=1",
        "#SBATCH --cpus-per-task=64",
        "#SBATCH --gres=gpu:NVIDIAA80080GBPCIeLC:8",
        "#SBATCH --mem=480000M",
        "#SBATCH --time=24:00:00",
    ):
        assert directive in text
    assert "#SBATCH --array" not in text
    assert "sbatch" not in text

    run_dir, output_root = tmp_path / "run", tmp_path / "outputs"
    assert _prepare(source_checkout, run_dir, output_root).returncode == 0
    log = tmp_path / "train.log"
    env = {
        **_slurm_env(log),
        "FAKE_CONCURRENCY_DIR": str(tmp_path / "barrier"),
    }
    first = _run(
        ["bash", str(BATCH), str(run_dir / "run.json")],
        env=env,
    )
    assert first.returncode == 0, first.stderr
    for seed in range(5):
        done = _load_envelope(output_root / f"seed-{seed}" / "DONE.json")
        assert done["payload"]["seed"] == seed
        assert {item["relative_path"] for item in done["payload"]["outputs"]} == {
            "checkpoint.json",
            "result.json",
        }
        assert all(item["sha256"] for item in done["payload"]["outputs"])
        assert (run_dir / "logs" / f"seed-{seed}.log").read_text(
            encoding="utf-8"
        ) == f"seed={seed}\n"
    calls = [
        json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()
    ]
    assert len(calls) == 5
    calls.sort(key=lambda item: item["argv"][item["argv"].index("--seeds") + 1])
    for seed, call in enumerate(calls):
        assert call["argv"][call["argv"].index("--seeds") + 1] == str(seed)
        assert call["cuda_visible_devices"] == str(seed)
        assert call["mkl_num_threads"] == "12"
        assert call["omp_num_threads"] == "12"
        assert call["openblas_num_threads"] == "12"
    before = log.read_text(encoding="utf-8")

    restarted = _run(
        ["bash", str(BATCH), str(run_dir / "run.json")],
        env=env,
    )
    assert restarted.returncode == 0, restarted.stderr
    assert log.read_text(encoding="utf-8") == before

    (output_root / "seed-0" / "result.json").write_text("tampered\n", encoding="utf-8")
    ambiguous = _run(
        ["bash", str(BATCH), str(run_dir / "run.json")],
        env=env,
    )
    assert ambiguous.returncode != 0
    assert "DONE" in (run_dir / "logs" / "seed-0.log").read_text(encoding="utf-8")


def test_batch_resumes_checkpoint_but_rejects_ambiguous_output(
    source_checkout: Path, tmp_path: Path
):
    run_dir, output_root = tmp_path / "run", tmp_path / "outputs"
    assert _prepare(source_checkout, run_dir, output_root).returncode == 0
    log = tmp_path / "train.log"
    env = {**_slurm_env(log), "FAKE_FAIL_SEED": "1"}

    failed = _run(["bash", str(BATCH), str(run_dir / "run.json")], env=env)
    assert failed.returncode != 0
    assert not (output_root / "seed-1" / "DONE.json").exists()
    assert all(
        (output_root / f"seed-{seed}" / "DONE.json").is_file()
        for seed in (0, 2, 3, 4)
    )
    resumed = _run(["bash", str(BATCH), str(run_dir / "run.json")], env=env)
    assert resumed.returncode == 0, resumed.stderr
    calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    seed_one_calls = [
        call["argv"]
        for call in calls
        if call["argv"][call["argv"].index("--seeds") + 1] == "1"
    ]
    assert "--resume" not in seed_one_calls[0]
    assert "--resume" in seed_one_calls[1]

    seed_dir = output_root / "seed-2"
    (seed_dir / "DONE.json").unlink()
    (seed_dir / "checkpoint.json").unlink()
    (seed_dir / "result.json").unlink()
    (seed_dir / "unknown").write_text("x", encoding="utf-8")
    rejected = _run(["bash", str(BATCH), str(run_dir / "run.json")], env=env)
    assert rejected.returncode != 0
    assert "ambiguous" in (run_dir / "logs" / "seed-2.log").read_text(
        encoding="utf-8"
    )


def test_submit_calls_fake_sbatch_once_and_receipt_or_claim_prevents_resubmit(
    source_checkout: Path, tmp_path: Path
):
    run_dir, output_root = tmp_path / "run", tmp_path / "outputs"
    assert _prepare(source_checkout, run_dir, output_root).returncode == 0
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    calls = tmp_path / "sbatch.calls"
    sbatch = fake_bin / "sbatch"
    sbatch.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >> "$FAKE_SBATCH_CALLS"\n'
        'printf "7654321\\n"\n',
        encoding="utf-8",
    )
    sbatch.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "FAKE_SBATCH_CALLS": str(calls),
    }

    submitted = _run(
        ["bash", str(SUBMIT), str(run_dir / "run.json")],
        env=env,
    )
    assert submitted.returncode == 0, submitted.stderr
    assert submitted.stdout.strip() == "7654321"
    sbatch_calls = calls.read_text(encoding="utf-8").splitlines()
    assert sbatch_calls == [
        f"--parsable {BATCH} {run_dir / 'run.json'}"
    ]
    assert "--array" not in sbatch_calls[0]
    receipt = _load_envelope(run_dir / "submission" / "receipt.json")
    assert receipt["payload"]["scheduler_job_id"] == "7654321"

    repeated = _run(
        ["bash", str(SUBMIT), str(run_dir / "run.json")],
        env=env,
    )
    assert repeated.returncode == 0, repeated.stderr
    assert repeated.stdout.strip() == "7654321"
    assert len(calls.read_text(encoding="utf-8").splitlines()) == 1

    (run_dir / "submission" / "receipt.json").unlink()
    closed = _run(["bash", str(SUBMIT), str(run_dir / "run.json")], env=env)
    assert closed.returncode != 0
    assert "operator recovery" in closed.stderr
    assert len(calls.read_text(encoding="utf-8").splitlines()) == 1


def test_verify_download_rehashes_done_outputs_and_reports_coverage(
    source_checkout: Path, tmp_path: Path
):
    run_dir, output_root = tmp_path / "run", tmp_path / "outputs"
    assert _prepare(source_checkout, run_dir, output_root).returncode == 0
    log = tmp_path / "train.log"
    completed = _run(
        ["bash", str(BATCH), str(run_dir / "run.json")],
        env=_slurm_env(log),
    )
    assert completed.returncode == 0, completed.stderr

    verified = _run(
        [
            sys.executable,
            str(VERIFY),
            "--manifest",
            str(run_dir / "run.json"),
            "--outputs",
            str(output_root),
        ]
    )
    assert verified.returncode == 0, verified.stderr
    report = json.loads(verified.stdout)
    assert report == {
        "covered_seeds": [0, 1, 2, 3, 4],
        "expected_seeds": [0, 1, 2, 3, 4],
        "missing_seeds": [],
        "scientific_acceptance_claimed": False,
    }

    (output_root / "seed-4" / "checkpoint.json").write_text(
        "tampered\n", encoding="utf-8"
    )
    tampered = _run(
        [
            sys.executable,
            str(VERIFY),
            "--manifest",
            str(run_dir / "run.json"),
            "--outputs",
            str(output_root),
        ]
    )
    assert tampered.returncode != 0
    assert "SHA256 mismatch" in tampered.stderr


def test_direct_profile_is_exact_and_scripts_are_not_orchestrator_coupled():
    profile = _load_envelope(PROFILE)["payload"]
    assert profile == {
        "account": "giggleliu",
        "cpus_per_task": 64,
        "gres": "gpu:NVIDIAA80080GBPCIeLC:8",
        "memory": "480000M",
        "nodes": 1,
        "ntasks": 1,
        "partition": "dzagnormal",
        "qos": "user_jiangweiqi",
        "wall_time": "24:00:00",
    }
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (PREPARE, BATCH, SUBMIT, VERIFY)
    )
    assert "production/orchestrate" not in combined
    assert "orchestrator" not in combined.lower()

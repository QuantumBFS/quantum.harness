from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SLURM = ROOT / "production" / "slurm"
ORCHESTRATE = ROOT / "production" / "orchestrate"


def test_qdeshell_wrapper_has_exact_shape_and_absolute_interpreter():
    text = (SLURM / "train-qdeshell.sbatch").read_text()
    for directive in (
        "#SBATCH --partition=dzagnormal",
        "#SBATCH --account=giggleliu",
        "#SBATCH --qos=user_jiangweiqi",
        "#SBATCH --nodes=1",
        "#SBATCH --ntasks=1",
        "#SBATCH --cpus-per-task=8",
        "#SBATCH --gres=gpu:NVIDIAA80080GBPCIeLC:1",
        "#SBATCH --mem=60000M",
        "#SBATCH --time=24:00:00",
        "#SBATCH --array=0-4%5",
    ):
        assert directive in text
    assert '"$INTERPRETER" -m challenge15.cli' in text
    assert "python3 " not in text


def test_lasg_wrapper_derives_array_from_identity_map():
    text = (SLURM / "exact-lasg02.sbatch").read_text()
    assert "#SBATCH --partition=ihicnormal" in text
    assert "#SBATCH --cpus-per-task=24" in text
    assert "identity-map-count" in text
    assert "%1" in text


def test_scientific_wrappers_verify_execution_inputs_before_work():
    for name, command in (
        ("train-qdeshell.sbatch", "vmc-train"),
        ("coordinate-qdeshell.sbatch", "coordinate-shard"),
        ("oracle-lasg02.sbatch", " oracle "),
        ("exact-lasg02.sbatch", "exact-shard"),
    ):
        text = (SLURM / name).read_text()
        assert "verify-execution-inputs" in text
        assert text.index("verify-execution-inputs") < text.rindex(command)


def test_submit_once_checks_receipt_scheduler_then_submits():
    text = (ORCHESTRATE / "submit_once.sh").read_text()
    assert text.index("submission-receipt") < text.index("squeue")
    assert text.index("squeue") < text.index("sacct")
    assert text.index("sacct") < text.index("sbatch --parsable")
    assert "c15-${CORRELATION_ID:0:24}" in text
    assert "submission claim identity mismatch" in text
    assert "ambiguous scheduler evidence" in text
    assert "MATCHES[0]" in text


def test_transfer_frontends_never_copy_directly():
    for name in ("transfer_bundle.sh", "transfer_bytes.sh"):
        text = (ORCHESTRATE / name).read_text()
        assert "transfer_once.sh" in text
        assert "scp " not in text
        assert "rsync " not in text


def test_transfer_once_checks_promoted_destination_before_claim_failure():
    text = (ORCHESTRATE / "transfer_once.sh").read_text()
    assert text.index('if [[ -e "$DESTINATION"') < text.index(
        'die "transfer claim identity mismatch"'
    )
    assert "ambiguous promoted transfer destinations" in text
    assert "hash_path" in text


def test_deploy_verifies_bundle_and_installs_project_offline():
    text = (ROOT / "production" / "deploy" / "deploy.sh").read_text()
    assert "bundle SHA256 mismatch" in text
    assert "sha256sum -c" in text
    assert '"$INTERPRETER" -m pip install --no-index --no-deps' in text
    assert 'installed_wheel_sha256' in text

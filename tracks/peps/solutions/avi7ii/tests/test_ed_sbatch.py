from pathlib import Path


def test_ed_sbatch_has_ratified_resources_and_no_partition():
    path = (
        Path(__file__).parents[1]
        / "scripts"
        / "issue147-ed.sbatch"
    )
    text = path.read_text(encoding="utf-8")
    assert "#SBATCH --cpus-per-task=32" in text
    assert "#SBATCH --mem=128G" in text
    assert "#SBATCH --time=06:00:00" in text
    assert "#SBATCH --partition" not in text
    assert "#SBATCH --gres" not in text
    assert "PYTHONUNBUFFERED=1" in text
    assert "SLURM_ARRAY_TASK_ID" in text
    assert "python -u -m qh147.run_ed" in text

import pytest

from analysis.data_io import load_run
from analysis.tests.helpers import create_synthetic_run


def test_loader_builds_replica_block_width_tensor_and_verifies_hashes(tmp_path):
    run_dir = create_synthetic_run(tmp_path / "run")
    loaded = load_run(run_dir)
    assert loaded.block_tensor.shape == (4, 8, 6)
    assert loaded.widths.tolist() == [4, 6, 8, 10, 12, 14]
    assert loaded.total_bonds == 400_000

    replica = run_dir / "raw" / "replicas" / "replica-000.json"
    replica.write_text(replica.read_text() + " ")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        load_run(run_dir)

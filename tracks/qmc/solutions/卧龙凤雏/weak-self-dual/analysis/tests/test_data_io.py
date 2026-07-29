import json

import numpy as np
import pytest

from analysis.data_io import load_run
from analysis.tests.helpers import make_synthetic_run


def test_loader_assembles_width_keyed_stream_block_arrays(tmp_path):
    run = make_synthetic_run(tmp_path)
    loaded = load_run(run)
    np.testing.assert_array_equal(loaded.widths, [6, 8, 10])
    assert loaded.gamma_blocks[6].shape == (2, 4)
    assert loaded.electric_counts[8].shape == (2, 4)
    assert loaded.oracle["schema_version"] == 1


def test_loader_rejects_a_tampered_stream(tmp_path):
    run = make_synthetic_run(tmp_path)
    path = run / "raw/streams/stream-L06-000.json"
    artifact = json.loads(path.read_text())
    artifact["estimate"]["blocks"][0]["gamma"] += 1.0
    path.write_text(json.dumps(artifact))
    with pytest.raises(ValueError, match="SHA-256"):
        load_run(run)

from pathlib import Path

from scripts.snapshot_scnet_progress_data import build_manifest


def test_manifest_hashes_inputs(tmp_path: Path) -> None:
    source = tmp_path / "a.dat"
    source.write_bytes(b"abc")
    manifest = build_manifest([source], tmp_path)
    assert manifest["files"][0]["sha256"] == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


from pathlib import Path

import pytest

from challenge15.transfers import (
    copy_bundle_create_only,
    verify_bundle,
    write_sha256sums,
)


def _bundle(root: Path) -> Path:
    root.mkdir()
    (root / "members").mkdir()
    (root / "members" / "a").write_bytes(b"payload")
    write_sha256sums(root)
    return root


def test_create_only_bundle_round_trip(tmp_path):
    source = _bundle(tmp_path / "source")
    destination = tmp_path / "imports" / "bundle"
    copy_bundle_create_only(source, destination, expected_controller_root=tmp_path)
    verify_bundle(destination)
    assert (destination / "members" / "a").read_bytes() == b"payload"


def test_existing_destination_and_corrupt_member_fail_closed(tmp_path):
    source = _bundle(tmp_path / "source")
    destination = tmp_path / "imports" / "bundle"
    destination.mkdir(parents=True)
    with pytest.raises(FileExistsError):
        copy_bundle_create_only(source, destination, expected_controller_root=tmp_path)
    (source / "members" / "a").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="SHA256"):
        verify_bundle(source)

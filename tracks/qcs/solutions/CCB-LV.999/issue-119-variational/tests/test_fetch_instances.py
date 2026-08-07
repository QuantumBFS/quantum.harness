from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.fetch_instances import InstanceSource, fetch_instance


def test_fetch_instance_records_verified_manifest(tmp_path: Path) -> None:
    source_file = tmp_path / "source.FCIDUMP"
    source_file.write_text(
        " &FCI NORB=1,NELEC=0,MS2=0,\n ORBSYM=1,\n ISYM=1,\n &END\n"
        " 0.0 0 0 0 0\n",
        encoding="utf-8",
    )
    checksum = hashlib.sha256(source_file.read_bytes()).hexdigest()
    source = InstanceSource(
        name="tiny",
        filename="tiny.FCIDUMP",
        url=source_file.as_uri(),
        source_commit="deadbeef",
        git_blob="cafebabe",
        sha256=checksum,
        size_bytes=source_file.stat().st_size,
        norb=1,
        nelec=0,
        ms2=0,
    )

    destination = fetch_instance(source, tmp_path / "run")

    assert destination.read_bytes() == source_file.read_bytes()
    manifest = json.loads(
        (tmp_path / "run" / "inputs" / "manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["schema_version"] == 1
    assert manifest["inputs"]["tiny"]["sha256"] == checksum
    assert manifest["inputs"]["tiny"]["source_commit"] == "deadbeef"

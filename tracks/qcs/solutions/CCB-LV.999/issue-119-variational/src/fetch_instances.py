from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import urllib.request
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .fcidump_audit import audit_fcidump


TRACKER_COMMIT = "e2a2488ceb53344668ac1447f7f96b18703f3524"
TRACKER_RAW = (
    "https://raw.githubusercontent.com/quantum-advantage-tracker/"
    "quantum-advantage-tracker.github.io"
)


@dataclass(frozen=True)
class InstanceSource:
    name: str
    filename: str
    url: str
    source_commit: str
    git_blob: str
    sha256: str
    size_bytes: int
    norb: int
    nelec: int
    ms2: int


SOURCES = {
    "2fe2s": InstanceSource(
        name="2fe2s",
        filename="2fe_2s_30e_20o.fcidump",
        url=(
            f"{TRACKER_RAW}/{TRACKER_COMMIT}/data/variational-problems/"
            "hamiltonians/2fe_2s/2fe_2s_30e_20o.fcidump"
        ),
        source_commit=TRACKER_COMMIT,
        git_blob="55e0dbab07d4d1754e042e38f98b34b566921f31",
        sha256="bd6ef31773f7b082171f73faa6c98924948e2c250b6fbec74504d64361c8c6c7",
        size_bytes=959_069,
        norb=20,
        nelec=30,
        ms2=0,
    ),
    "anderson": InstanceSource(
        name="anderson",
        filename="anderson_impurity_model_4i_28b_32e.fcidump",
        url=(
            f"{TRACKER_RAW}/{TRACKER_COMMIT}/data/variational-problems/"
            "hamiltonians/anderson_impurity_model/"
            "anderson_impurity_model_4i_28b_32e.fcidump"
        ),
        source_commit=TRACKER_COMMIT,
        git_blob="fe97b1621e4f3fec821d69c275063d3e18992408",
        sha256="9c8ceb3faa39ccb9cf2c15632cdc748e449cf26197ee1e8251092a6bb49ce4b6",
        size_bytes=149_334,
        norb=32,
        nelec=32,
        ms2=0,
    ),
}


def _manifest_path(run_dir: Path) -> Path:
    return run_dir / "inputs" / "manifest.json"


def _load_manifest(run_dir: Path) -> dict:
    path = _manifest_path(run_dir)
    if not path.exists():
        return {"schema_version": 1, "inputs": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def fetch_instance(source: InstanceSource, run_dir: str | Path) -> Path:
    run_path = Path(run_dir)
    inputs_dir = run_path / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    destination = inputs_dir / source.filename

    if destination.exists():
        audit = audit_fcidump(
            destination,
            expected_norb=source.norb,
            expected_nelec=source.nelec,
            expected_ms2=source.ms2,
            expected_sha256=source.sha256,
        )
    else:
        with tempfile.NamedTemporaryFile(dir=inputs_dir, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            with urllib.request.urlopen(source.url) as response:
                shutil.copyfileobj(response, temporary)
        try:
            audit = audit_fcidump(
                temporary_path,
                expected_norb=source.norb,
                expected_nelec=source.nelec,
                expected_ms2=source.ms2,
                expected_sha256=source.sha256,
            )
            if audit.size_bytes != source.size_bytes:
                raise ValueError(
                    f"size mismatch: expected {source.size_bytes}, got {audit.size_bytes}"
                )
            temporary_path.replace(destination)
        finally:
            temporary_path.unlink(missing_ok=True)

    manifest = _load_manifest(run_path)
    manifest["updated_at_utc"] = datetime.now(UTC).isoformat()
    manifest["inputs"][source.name] = {
        **asdict(source),
        "local_path": str(destination.resolve()),
        "verified_size_bytes": audit.size_bytes,
        "verified_header": asdict(audit.header),
    }
    _write_json(_manifest_path(run_path), manifest)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and verify pinned FCIDUMP inputs")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument(
        "--instance",
        action="append",
        choices=sorted(SOURCES),
        help="instance to fetch; repeatable, defaults to both",
    )
    args = parser.parse_args()
    names = args.instance or sorted(SOURCES)
    for name in names:
        path = fetch_instance(SOURCES[name], args.run_dir)
        print(f"verified {name}: {path}", flush=True)


if __name__ == "__main__":
    main()

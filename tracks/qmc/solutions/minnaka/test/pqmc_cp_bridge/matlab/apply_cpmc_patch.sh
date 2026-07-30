#!/usr/bin/env bash
set -euo pipefail

bridge_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
patch_file="${bridge_root}/patches/cpmc-lab-mixed-diagnostics.patch"
frozen_source_hash="6bd0c736649b78647ec8c8d3908d128e4a438a806b6690bee6d066a9f4b710f9"

source_root=""
destination=""
while (($#)); do
    case "$1" in
        --source)
            source_root="$2"
            shift 2
            ;;
        --destination)
            destination="$2"
            shift 2
            ;;
        *)
            echo "unknown argument: $1" >&2
            exit 2
            ;;
    esac
done
if [[ -z "${source_root}" || -z "${destination}" ]]; then
    echo "--source and --destination are required" >&2
    exit 2
fi
source_root="$(realpath "${source_root}")"
destination_parent="$(realpath -m "$(dirname "${destination}")")"
destination="${destination_parent}/$(basename "${destination}")"
manifest="${destination_parent}/package_manifest.json"

tree_hash() {
    /usr/bin/python3 - "$1" <<'PY'
from pathlib import Path
import hashlib
import sys

root = Path(sys.argv[1])
digest = hashlib.sha256()
for path in sorted(item for item in root.rglob("*") if item.is_file()):
    relative = path.relative_to(root).as_posix().encode()
    content = path.read_bytes()
    digest.update(len(relative).to_bytes(4, "little"))
    digest.update(relative)
    digest.update(len(content).to_bytes(8, "little"))
    digest.update(content)
print(digest.hexdigest())
PY
}

if [[ ! -f "${source_root}/CPMC_Lab.m" ]]; then
    echo "official package root does not contain CPMC_Lab.m" >&2
    exit 1
fi
source_hash="$(tree_hash "${source_root}")"
if [[ "${source_hash}" != "${frozen_source_hash}" ]]; then
    echo "official CPMC-Lab source hash mismatch" >&2
    exit 1
fi
patch_hash="$(sha256sum "${patch_file}" | awk '{print $1}')"

if [[ -e "${destination}" ]]; then
    if [[ ! -f "${manifest}" ]]; then
        echo "existing destination has no package manifest" >&2
        exit 1
    fi
    /usr/bin/python3 - "${manifest}" "${source_hash}" "${patch_hash}" \
        "$(tree_hash "${destination}")" <<'PY'
import json
from pathlib import Path
import sys

manifest = json.loads(Path(sys.argv[1]).read_text())
expected = (sys.argv[2], sys.argv[3], sys.argv[4])
actual = (
    manifest.get("source_tree_sha256"),
    manifest.get("patch_sha256"),
    manifest.get("patched_tree_sha256"),
)
if actual != expected:
    raise SystemExit("existing destination does not match its frozen manifest")
PY
    if [[ ! -f "${destination}/CPMC_BRIDGE_PATCH.txt" \
          || ! -f "${destination}/CPMC_Bridge.m" ]]; then
        echo "existing destination lacks required bridge marker" >&2
        exit 1
    fi
    echo "PASS: reused verified CPMC-Lab package ${destination}"
    exit 0
fi

mkdir -p "${destination_parent}"
temporary="$(mktemp -d "${destination_parent}/package-stage-XXXXXX")"
cleanup() {
    if [[ -d "${temporary}" ]]; then
        rm -rf -- "${temporary}"
    fi
}
trap cleanup EXIT
cp -a "${source_root}/." "${temporary}/"
patch --dry-run --silent -p1 -d "${temporary}" < "${patch_file}"
patch --silent -p1 -d "${temporary}" < "${patch_file}"
if [[ ! -f "${temporary}/CPMC_BRIDGE_PATCH.txt" \
      || ! -f "${temporary}/CPMC_Bridge.m" ]]; then
    echo "patch did not create required bridge files" >&2
    exit 1
fi
patched_hash="$(tree_hash "${temporary}")"

matlab_executable="$(command -v matlab || true)"
if [[ -z "${matlab_executable}" && -x /home/minnaka/.local/bin/matlab ]]; then
    matlab_executable=/home/minnaka/.local/bin/matlab
fi
if [[ -z "${matlab_executable}" ]]; then
    echo "MATLAB executable was not found" >&2
    exit 1
fi
matlab_version="$(
    "${matlab_executable}" -batch "disp(version)" 2>/dev/null | tail -1
)"

mv "${temporary}" "${destination}"
trap - EXIT
/usr/bin/python3 - "${manifest}" "${source_hash}" "${patch_hash}" \
    "${patched_hash}" "${matlab_executable}" "${matlab_version}" \
    "${destination}" <<'PY'
import json
import os
from pathlib import Path
import sys

manifest_path = Path(sys.argv[1])
root = Path(sys.argv[7])
data = {
    "schema_version": 1,
    "source_tree_sha256": sys.argv[2],
    "patch_sha256": sys.argv[3],
    "patched_tree_sha256": sys.argv[4],
    "matlab_executable": sys.argv[5],
    "matlab_version": sys.argv[6],
    "files": [
        path.relative_to(root).as_posix()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    ],
}
temporary = manifest_path.with_name(manifest_path.name + ".tmp")
temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
os.replace(temporary, manifest_path)
PY
if [[ "$(tree_hash "${source_root}")" != "${source_hash}" ]]; then
    echo "official source changed while preparing the package" >&2
    exit 1
fi
echo "PASS: prepared verified CPMC-Lab package ${destination}"

#!/usr/bin/env python3
"""Fail-closed verification for Challenge 15 candidate wheelhouses."""

from __future__ import annotations

import argparse
import errno
import hashlib
import json
import os
import re
import stat
import zipfile
from pathlib import Path
from typing import Literal


_NAME_RE = re.compile(r"[-_.]+")
_INPUT_RE = re.compile(
    r"([A-Za-z0-9_.-]+)(?:\[([A-Za-z0-9_.-]+)\])?==([A-Za-z0-9][A-Za-z0-9.!+_-]*)"
)
_LOCK_RE = re.compile(
    r"([A-Za-z0-9_.-]+)==([A-Za-z0-9][A-Za-z0-9.!+_-]*)"
    r"((?:\s+--hash=sha256:[0-9a-f]{64})+)"
)
_HASH_RE = re.compile(r"--hash=sha256:([0-9a-f]{64})")
_SDIST_SUFFIXES = (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".zip")
_CPU_INPUTS = (
    "jax==0.4.38",
    "jaxlib==0.4.38",
    "flax==0.10.2",
    "optax==0.2.4",
    "numpy==1.26.4",
    "scipy==1.12.0",
    "sympy==1.13.3",
    "h5py==3.10.0",
    "pytest==8.3.4",
)
_APPROVED_INPUT_LINES = {
    "cpu": _CPU_INPUTS,
    "cuda12": (*_CPU_INPUTS, "jax-cuda12-plugin[with-cuda]==0.4.38"),
}


def _normalize(name: str) -> str:
    return _NAME_RE.sub("-", name).lower()


class CandidateLock:
    __slots__ = (
        "profile",
        "python_version",
        "abis",
        "platform",
        "only_binary",
        "packages",
        "hashes",
        "projects",
        "nvidia_projects",
        "requested",
        "sdists",
        "requirements",
    )

    def __init__(
        self,
        *,
        profile: str,
        packages: dict[str, str],
        hashes: dict[str, tuple[str, ...]],
        requested: dict[str, str],
        requirements: Path,
    ) -> None:
        self.profile = profile
        self.python_version = "3.12"
        self.abis = ("cp312", "abi3")
        self.platform = "manylinux2014_x86_64"
        self.only_binary = True
        self.packages = packages
        self.hashes = hashes
        self.projects = tuple(sorted(packages))
        self.nvidia_projects = tuple(
            name for name in self.projects if name.startswith("nvidia-")
        )
        self.requested = requested
        self.sdists: tuple[str, ...] = ()
        self.requirements = requirements


class WheelhouseReport:
    __slots__ = ("profile", "root", "wheel_count", "projects", "wheel_sha256")

    def __init__(
        self,
        profile: str,
        root: Path,
        projects: tuple[str, ...],
        wheel_sha256: dict[str, str],
    ) -> None:
        self.profile = profile
        self.root = root
        self.wheel_count = len(wheel_sha256)
        self.projects = projects
        self.wheel_sha256 = wheel_sha256

    def to_json(self) -> str:
        return json.dumps(
            {
                "profile": self.profile,
                "root": str(self.root),
                "wheel_count": self.wheel_count,
                "projects": list(self.projects),
                "wheel_sha256": self.wheel_sha256,
                "status": "CANDIDATE_OK",
            },
            sort_keys=True,
            separators=(",", ":"),
        )


def _logical_lines(path: Path) -> tuple[str, ...]:
    logical: list[str] = []
    pending = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        pending = f"{pending} {stripped}".strip()
        if pending.endswith("\\"):
            pending = pending[:-1].rstrip()
        else:
            logical.append(pending)
            pending = ""
    if pending:
        raise ValueError(f"unterminated requirement continuation in {path}")
    return tuple(logical)


def _parse_input_requirements(profile: str, input_path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    requested_extras: dict[str, str] = {}
    for line in input_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _INPUT_RE.fullmatch(stripped)
        if match is None:
            raise ValueError(f"requirement is not an exact registry pin: {stripped}")
        name, extra, version = match.groups()
        key = _normalize(name)
        if extra:
            key = f"{key}[{extra}]"
            requested_extras[key] = version
        if key in parsed:
            raise ValueError(f"duplicate normalized input project: {key}")
        parsed[key] = version

    approved: dict[str, str] = {}
    for requirement in _APPROVED_INPUT_LINES[profile]:
        match = _INPUT_RE.fullmatch(requirement)
        assert match is not None
        name, extra, version = match.groups()
        key = _normalize(name)
        if extra:
            key = f"{key}[{extra}]"
        approved[key] = version
    if parsed != approved:
        raise ValueError(
            f"{input_path} does not match the exact approved input set: "
            f"expected {approved!r}, got {parsed!r}"
        )
    return requested_extras


def _parse_lock(requirements: Path) -> tuple[dict[str, str], dict[str, tuple[str, ...]]]:
    lines = _logical_lines(requirements)
    if not lines or lines[0] != "--only-binary :all:":
        raise ValueError(
            f"{requirements} must begin with exactly '--only-binary :all:'"
        )
    if lines.count("--only-binary :all:") != 1:
        raise ValueError(f"duplicate global directive in {requirements}")

    packages: dict[str, str] = {}
    hashes: dict[str, tuple[str, ...]] = {}
    for line in lines[1:]:
        if line.startswith("--"):
            raise ValueError(f"unsupported global directive in {requirements}: {line}")
        match = _LOCK_RE.fullmatch(line)
        if match is None:
            raise ValueError(f"non-exact or malformed lock requirement: {line}")
        name, version, hash_tokens = match.groups()
        normalized = _normalize(name)
        if normalized in packages:
            raise ValueError(f"duplicate normalized lock project: {normalized}")
        project_hashes = tuple(_HASH_RE.findall(hash_tokens))
        if not project_hashes:
            raise ValueError(f"missing hash for locked project: {normalized}")
        packages[normalized] = version
        hashes[normalized] = project_hashes
    if not packages:
        raise ValueError(f"empty requirements lock: {requirements}")
    return packages, hashes


def load_candidate(
    profile: Literal["cpu", "cuda12"], runtime_root: Path | None = None
) -> CandidateLock:
    if profile not in _APPROVED_INPUT_LINES:
        raise ValueError(f"unknown candidate profile: {profile}")
    root = runtime_root or Path(__file__).resolve().parent
    input_path = root / profile / "requirements.in"
    requirements = root / profile / "requirements.txt"
    requested = _parse_input_requirements(profile, input_path)
    packages, hashes = _parse_lock(requirements)
    required: dict[str, str] = {}
    for requirement in _APPROVED_INPUT_LINES[profile]:
        match = _INPUT_RE.fullmatch(requirement)
        assert match is not None
        name, _, version = match.groups()
        required[_normalize(name)] = version
    for name, version in required.items():
        if packages.get(name) != version:
            raise ValueError(f"approved input {name} must be locked at {version}")
    if profile == "cuda12":
        for name in ("jax-cuda12-plugin", "jax-cuda12-pjrt"):
            if packages.get(name) != "0.4.38":
                raise ValueError(f"missing bundled CUDA project {name}==0.4.38")
        if not any(name.startswith("nvidia-") for name in packages):
            raise ValueError("CUDA lock has no bundled NVIDIA runtime wheels")

    return CandidateLock(
        profile=profile,
        packages=packages,
        hashes=hashes,
        requested=requested,
        requirements=requirements,
    )


def _wheel_parts(filename: str) -> tuple[str, str, str, str, str]:
    if not filename.endswith(".whl"):
        raise ValueError(f"not a wheel: {filename}")
    parts = filename[:-4].rsplit("-", 4)
    if len(parts) != 5:
        raise ValueError(f"malformed wheel filename: {filename}")
    return tuple(parts)  # type: ignore[return-value]


def _verify_tags(filename: str, python_tag: str, abi_tag: str, platform_tag: str) -> None:
    python_tags = python_tag.split(".")
    abi_tags = abi_tag.split(".")
    platform_tags = platform_tag.split(".")
    if platform_tags == ["any"]:
        if "py3" not in python_tags and python_tags != ["cp312"]:
            raise ValueError(f"unsupported Python tag in {filename}")
        if abi_tags != ["none"]:
            raise ValueError(f"non-none ABI on universal wheel {filename}")
        return

    if not all(tag.endswith("_x86_64") for tag in platform_tags):
        raise ValueError(f"wheel is not x86_64 Linux compatible: {filename}")
    compatible_floor = False
    for tag in platform_tags:
        prefix = tag.removesuffix("_x86_64")
        if prefix in {"manylinux1", "manylinux2010", "manylinux2014"}:
            compatible_floor = True
            continue
        match = re.fullmatch(r"manylinux_2_(\d+)", prefix)
        if match is not None and int(match.group(1)) <= 17:
            compatible_floor = True
    if not compatible_floor:
        raise ValueError(f"platform is above manylinux2014: {filename}")

    if "abi3" in abi_tags:
        if not all(re.fullmatch(r"cp3(?:[6-9]|1[0-2])", tag) for tag in python_tags):
            raise ValueError(f"unsupported abi3 Python tag in {filename}")
    elif abi_tags == ["none"] and python_tags == ["py3"]:
        pass
    elif abi_tags == ["cp312"] and python_tags == ["cp312"]:
        pass
    else:
        raise ValueError(f"wheel is neither cp312 nor abi3: {filename}")


def _filename_tags(
    python_tag: str, abi_tag: str, platform_tag: str
) -> set[str]:
    return {
        f"{python_name}-{abi_name}-{platform_name}"
        for python_name in python_tag.split(".")
        for abi_name in abi_tag.split(".")
        for platform_name in platform_tag.split(".")
    }


def _open_regular_nofollow(path: Path):
    if path.is_symlink():
        raise ValueError(f"symlinked wheel rejected: {path.name}")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise ValueError(f"symlinked wheel rejected: {path.name}") from error
        raise
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError(f"wheel is not a regular file: {path.name}")
    return os.fdopen(descriptor, "rb")


def _inspect_wheel(
    wheel: Path,
    python_tag: str,
    abi_tag: str,
    platform_tag: str,
) -> tuple[str, str, str]:
    with _open_regular_nofollow(wheel) as wheel_file:
        digest = hashlib.file_digest(wheel_file, "sha256").hexdigest()
        wheel_file.seek(0)
        with zipfile.ZipFile(wheel_file) as archive:
            metadata_names = [
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA") and name.count("/") == 1
            ]
            wheel_names = [
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/WHEEL") and name.count("/") == 1
            ]
            if len(metadata_names) != 1:
                raise ValueError(f"wheel has invalid METADATA count: {wheel.name}")
            if len(wheel_names) != 1:
                raise ValueError(
                    f"wheel has invalid WHEEL metadata count: {wheel.name}"
                )
            metadata = archive.read(metadata_names[0]).decode("utf-8")
            wheel_metadata = archive.read(wheel_names[0]).decode("utf-8")
    name_match = re.search(r"^Name:\s*(\S+)\s*$", metadata, re.MULTILINE)
    version_match = re.search(r"^Version:\s*(\S+)\s*$", metadata, re.MULTILINE)
    if name_match is None or version_match is None:
        raise ValueError(f"wheel metadata lacks name/version: {wheel.name}")
    internal_tags = set(
        re.findall(
            r"^Tag:\s*([A-Za-z0-9_.]+-[A-Za-z0-9_.]+-[A-Za-z0-9_.]+)\s*$",
            wheel_metadata,
            re.MULTILINE,
        )
    )
    expected_tags = _filename_tags(python_tag, abi_tag, platform_tag)
    if internal_tags != expected_tags:
        raise ValueError(
            f"internal WHEEL Tag entries do not match filename tags for {wheel.name}: "
            f"expected {sorted(expected_tags)!r}, got {sorted(internal_tags)!r}"
        )
    return _normalize(name_match.group(1)), version_match.group(1), digest


def verify_wheelhouse(
    profile: Literal["cpu", "cuda12"],
    root: Path,
    *,
    runtime_root: Path | None = None,
) -> WheelhouseReport:
    candidate = load_candidate(profile, runtime_root)
    if root.is_symlink():
        raise ValueError(f"symlinked wheelhouse root rejected: {root}")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"wheelhouse is not a directory: {root}")
    files = sorted(root.iterdir())
    for path in files:
        lower = path.name.lower()
        if path.is_symlink():
            raise ValueError(f"symlinked wheel rejected: {path.name}")
        if lower.endswith(_SDIST_SUFFIXES):
            raise ValueError(f"sdist rejected: {path.name}")
        if not path.is_file() or not lower.endswith(".whl"):
            raise ValueError(f"unlisted non-wheel file rejected: {path.name}")

    seen: dict[str, str] = {}
    wheel_sha256: dict[str, str] = {}
    for wheel in files:
        filename_name, filename_version, python_tag, abi_tag, platform_tag = (
            _wheel_parts(wheel.name)
        )
        _verify_tags(wheel.name, python_tag, abi_tag, platform_tag)
        metadata_name, metadata_version, digest = _inspect_wheel(
            wheel, python_tag, abi_tag, platform_tag
        )
        if metadata_name != _normalize(filename_name) or metadata_version != filename_version:
            raise ValueError(f"wheel filename/metadata mismatch: {wheel.name}")
        if metadata_name in seen:
            raise ValueError(
                f"duplicate normalized project {metadata_name}: "
                f"{seen[metadata_name]}, {wheel.name}"
            )
        if candidate.packages.get(metadata_name) != metadata_version:
            raise ValueError(f"wheel absent from exact lock: {wheel.name}")
        if digest not in candidate.hashes.get(metadata_name, ()):
            raise ValueError(f"wheel hash absent from lock: {wheel.name}")
        seen[metadata_name] = wheel.name
        wheel_sha256[wheel.name] = digest

    missing = sorted(set(candidate.packages) - set(seen))
    if missing:
        raise ValueError(f"wheelhouse is missing locked projects: {missing}")
    return WheelhouseReport(
        profile, root, tuple(sorted(seen)), dict(sorted(wheel_sha256.items()))
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=tuple(_APPROVED_INPUT_LINES), required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    report = verify_wheelhouse(args.profile, args.root)
    print(report.to_json())
    print("CANDIDATE_OK")


if __name__ == "__main__":
    main()

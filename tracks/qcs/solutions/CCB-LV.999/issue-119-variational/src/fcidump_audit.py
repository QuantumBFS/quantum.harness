from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


class FCIDUMPValidationError(ValueError):
    """Base class for input-integrity failures."""


class HeaderMismatchError(FCIDUMPValidationError):
    """The FCIDUMP sector does not match the declared calculation."""


class ChecksumMismatchError(FCIDUMPValidationError):
    """The FCIDUMP bytes do not match the pinned source."""


@dataclass(frozen=True)
class FCIDUMPHeader:
    norb: int
    nelec: int
    ms2: int
    orbsym: tuple[int, ...]
    isym: int


@dataclass(frozen=True)
class FCIDUMPAudit:
    path: Path
    header: FCIDUMPHeader
    sha256: str
    size_bytes: int


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _header_text(path: Path) -> str:
    lines: list[str] = []
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            lines.append(line)
            if re.search(r"&END|^\s*/\s*$", line, flags=re.IGNORECASE):
                break
            if len(lines) > 100:
                raise FCIDUMPValidationError("FCIDUMP header exceeds 100 lines")
    text = "".join(lines)
    if not re.search(r"&FCI", text, flags=re.IGNORECASE):
        raise FCIDUMPValidationError("missing &FCI header")
    if not re.search(r"&END|^\s*/\s*$", text, flags=re.IGNORECASE | re.MULTILINE):
        raise FCIDUMPValidationError("unterminated FCIDUMP header")
    return text


def _required_int(header: str, key: str) -> int:
    match = re.search(
        rf"\b{re.escape(key)}\s*=\s*([+-]?\d+)",
        header,
        flags=re.IGNORECASE,
    )
    if match is None:
        raise FCIDUMPValidationError(f"missing {key} in FCIDUMP header")
    return int(match.group(1))


def parse_fcidump_header(path: str | Path) -> FCIDUMPHeader:
    input_path = Path(path)
    header = _header_text(input_path)
    orbsym_match = re.search(
        r"\bORBSYM\s*=\s*(.*?)(?=,\s*[A-Z][A-Z0-9_]*\s*=|&END|^\s*/\s*$)",
        header,
        flags=re.IGNORECASE | re.DOTALL | re.MULTILINE,
    )
    if orbsym_match is None:
        raise FCIDUMPValidationError("missing ORBSYM in FCIDUMP header")
    orbsym = tuple(int(value) for value in re.findall(r"[+-]?\d+", orbsym_match.group(1)))
    norb = _required_int(header, "NORB")
    if len(orbsym) != norb:
        raise FCIDUMPValidationError(
            f"ORBSYM has {len(orbsym)} entries, expected NORB={norb}"
        )
    return FCIDUMPHeader(
        norb=norb,
        nelec=_required_int(header, "NELEC"),
        ms2=_required_int(header, "MS2"),
        orbsym=orbsym,
        isym=_required_int(header, "ISYM"),
    )


def audit_fcidump(
    path: str | Path,
    *,
    expected_norb: int,
    expected_nelec: int,
    expected_ms2: int,
    expected_sha256: str | None = None,
) -> FCIDUMPAudit:
    input_path = Path(path)
    header = parse_fcidump_header(input_path)
    expected = {
        "NORB": expected_norb,
        "NELEC": expected_nelec,
        "MS2": expected_ms2,
    }
    actual = {
        "NORB": header.norb,
        "NELEC": header.nelec,
        "MS2": header.ms2,
    }
    mismatches = [
        f"{key}: expected {expected[key]}, got {actual[key]}"
        for key in expected
        if expected[key] != actual[key]
    ]
    if mismatches:
        raise HeaderMismatchError("; ".join(mismatches))

    checksum = sha256_file(input_path)
    if expected_sha256 is not None and checksum.lower() != expected_sha256.lower():
        raise ChecksumMismatchError(
            f"SHA-256 mismatch: expected {expected_sha256}, got {checksum}"
        )
    return FCIDUMPAudit(
        path=input_path.resolve(),
        header=header,
        sha256=checksum,
        size_bytes=input_path.stat().st_size,
    )

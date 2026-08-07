from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.fcidump_audit import (
    ChecksumMismatchError,
    HeaderMismatchError,
    audit_fcidump,
    parse_fcidump_header,
)


FIXTURE = Path(__file__).parent / "data" / "hubbard_dimer.FCIDUMP"


def test_parse_multiline_fcidump_header() -> None:
    header = parse_fcidump_header(FIXTURE)

    assert header.norb == 2
    assert header.nelec == 2
    assert header.ms2 == 0
    assert header.orbsym == (1, 1)
    assert header.isym == 1


def test_audit_accepts_expected_sector_and_checksum() -> None:
    checksum = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()

    audit = audit_fcidump(
        FIXTURE,
        expected_norb=2,
        expected_nelec=2,
        expected_ms2=0,
        expected_sha256=checksum,
    )

    assert audit.header.norb == 2
    assert audit.sha256 == checksum
    assert audit.size_bytes == FIXTURE.stat().st_size


def test_audit_rejects_wrong_sector() -> None:
    with pytest.raises(HeaderMismatchError, match="NELEC"):
        audit_fcidump(
            FIXTURE,
            expected_norb=2,
            expected_nelec=4,
            expected_ms2=0,
        )


def test_audit_rejects_wrong_checksum() -> None:
    with pytest.raises(ChecksumMismatchError, match="SHA-256"):
        audit_fcidump(
            FIXTURE,
            expected_norb=2,
            expected_nelec=2,
            expected_ms2=0,
            expected_sha256="0" * 64,
        )

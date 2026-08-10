from decimal import Decimal
from pathlib import Path

import pytest

from xxzcert.audit import AuditError, audit_directory
from xxzcert.intervals import DecimalInterval
from xxzcert.schema import LevelCertificate, Provenance
from xxzcert.verify import VerificationReport


def _write_certificate(
    path: Path, level: int, lower: str, upper: str
) -> None:
    LevelCertificate(
        delta=Decimal("1"),
        level=level,
        block_size=20,
        raw_lti_lower=Decimal(lower),
        raw_block_upper=Decimal(upper),
        certified_lower=Decimal(lower),
        certified_upper=Decimal(upper),
        bethe=DecimalInterval(
            lower=Decimal("-0.443147181"),
            upper=Decimal("-0.443147180"),
        ),
        provenance=Provenance(
            generator="test",
            python_version="test",
            numpy_version="test",
            cvxpy_version="test",
            solver="test",
            git_commit="0" * 40,
        ),
    ).write(path)


def _accept(_path: Path) -> VerificationReport:
    return VerificationReport(True)


def test_audit_sorts_levels_and_computes_monotonicity(tmp_path):
    _write_certificate(tmp_path / "level_5.json", 5, "-0.46", "-0.43")
    _write_certificate(tmp_path / "level_3.json", 3, "-0.47", "-0.42")
    report = audit_directory(tmp_path, verifier=_accept)
    assert [row.level for row in report.rows] == [3, 5]
    assert report.lower_monotone
    assert report.upper_monotone
    assert report.rows[-1].width == Decimal("0.03")
    assert report.rows[-1].lower_error == Decimal("0.016852819")
    assert report.rows[-1].upper_error == Decimal("0.013147180")


def test_audit_rejects_failed_verification(tmp_path):
    path = tmp_path / "level_3.json"
    _write_certificate(path, 3, "-0.47", "-0.42")

    def reject(_path: Path) -> VerificationReport:
        return VerificationReport(False, ("tampered",))

    with pytest.raises(AuditError, match="tampered"):
        audit_directory(tmp_path, verifier=reject)


def test_audit_rejects_duplicate_delta_level(tmp_path):
    _write_certificate(tmp_path / "a.json", 3, "-0.47", "-0.42")
    _write_certificate(tmp_path / "b.json", 3, "-0.47", "-0.42")
    with pytest.raises(AuditError, match="duplicate"):
        audit_directory(tmp_path, verifier=_accept)

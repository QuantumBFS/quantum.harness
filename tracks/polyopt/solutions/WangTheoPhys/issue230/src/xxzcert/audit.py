"""Deterministic aggregation for independently verified certificates."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Callable

from .schema import LevelCertificate
from .verify import VerificationReport, verify_level


class AuditError(RuntimeError):
    """Raised when a release directory cannot support its audit claims."""


@dataclass(frozen=True)
class AuditRow:
    path: str
    delta: Decimal
    level: int
    block_size: int
    certified_lower: Decimal
    bethe_lower: Decimal
    bethe_upper: Decimal
    certified_upper: Decimal
    lower_error: Decimal
    upper_error: Decimal
    width: Decimal

    def as_dict(self) -> dict[str, str | int]:
        return {
            "path": self.path,
            "delta": str(self.delta),
            "level": self.level,
            "block_size": self.block_size,
            "certified_lower": str(self.certified_lower),
            "bethe_lower": str(self.bethe_lower),
            "bethe_upper": str(self.bethe_upper),
            "certified_upper": str(self.certified_upper),
            "lower_error": str(self.lower_error),
            "upper_error": str(self.upper_error),
            "width": str(self.width),
        }


@dataclass(frozen=True)
class AuditReport:
    rows: tuple[AuditRow, ...]
    lower_monotone: bool
    upper_monotone: bool

    @property
    def ok(self) -> bool:
        return self.lower_monotone and self.upper_monotone

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "lower_monotone": self.lower_monotone,
            "upper_monotone": self.upper_monotone,
            "rows": [row.as_dict() for row in self.rows],
        }


def _certificate_paths(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(root.glob("**/*.json"))


def audit_directory(
    root: Path,
    *,
    verifier: Callable[[Path], VerificationReport] = verify_level,
) -> AuditReport:
    """Verify and summarize every certificate below ``root``."""
    paths = _certificate_paths(Path(root))
    if not paths:
        raise AuditError("no certificate files found")
    rows: list[AuditRow] = []
    seen: set[tuple[Decimal, int]] = set()
    for path in paths:
        verification = verifier(path)
        if not verification.ok:
            details = "; ".join(verification.errors)
            raise AuditError(f"{path}: {details}")
        certificate = LevelCertificate.read(path)
        key = (certificate.delta, certificate.level)
        if key in seen:
            raise AuditError(
                f"duplicate delta/level pair {certificate.delta}/{certificate.level}"
            )
        seen.add(key)
        rows.append(
            AuditRow(
                path=str(path),
                delta=certificate.delta,
                level=certificate.level,
                block_size=certificate.block_size,
                certified_lower=certificate.certified_lower,
                bethe_lower=certificate.bethe.lower,
                bethe_upper=certificate.bethe.upper,
                certified_upper=certificate.certified_upper,
                lower_error=(
                    certificate.bethe.lower - certificate.certified_lower
                ),
                upper_error=(
                    certificate.certified_upper - certificate.bethe.upper
                ),
                width=(
                    certificate.certified_upper
                    - certificate.certified_lower
                ),
            )
        )
    rows.sort(key=lambda row: (row.delta, row.level, row.path))
    lower_monotone = True
    upper_monotone = True
    previous: dict[Decimal, AuditRow] = {}
    for row in rows:
        prior = previous.get(row.delta)
        if prior is not None:
            lower_monotone &= row.certified_lower >= prior.certified_lower
            upper_monotone &= row.certified_upper <= prior.certified_upper
        previous[row.delta] = row
    return AuditReport(tuple(rows), lower_monotone, upper_monotone)

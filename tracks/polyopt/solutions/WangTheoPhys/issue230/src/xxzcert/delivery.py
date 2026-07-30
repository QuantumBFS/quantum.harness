"""Deterministic research-delivery summaries for Issue #230 certificates."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal, localcontext
import hashlib
import json
from pathlib import Path

from .schema import LevelCertificate


TARGET_WIDTH = Decimal("0.0003")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class RecordGateSummary:
    lower: Decimal
    upper: Decimal
    width: Decimal
    target: Decimal
    required_lower: Decimal
    required_upper: Decimal
    passes: bool

    def as_dict(self) -> dict[str, str | bool]:
        return {
            "certified_lower": str(self.lower),
            "certified_upper": str(self.upper),
            "certified_width": str(self.width),
            "target_width": str(self.target),
            "required_lower_at_current_upper": str(self.required_lower),
            "required_upper_at_current_lower": str(self.required_upper),
            "passes_record_target": self.passes,
            "frontier_status": "certified_calibration_frontier",
        }


def evaluate_record_gate(
    lower: Decimal, upper: Decimal
) -> RecordGateSummary:
    """Evaluate the strict record-width target without float conversion."""
    if lower > upper:
        raise ValueError("certified lower endpoint exceeds upper endpoint")
    precision = max(
        len(lower.as_tuple().digits),
        len(upper.as_tuple().digits),
        len(TARGET_WIDTH.as_tuple().digits),
    ) + 8
    with localcontext() as context:
        context.prec = precision
        width = upper - lower
        required_lower = upper - TARGET_WIDTH
        required_upper = lower + TARGET_WIDTH
    return RecordGateSummary(
        lower=lower,
        upper=upper,
        width=width,
        target=TARGET_WIDTH,
        required_lower=required_lower,
        required_upper=required_upper,
        passes=width < TARGET_WIDTH,
    )


@dataclass(frozen=True)
class CertificateSummary:
    path: str
    source_role: str
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
    lower_method: str
    upper_method: str
    generator: str
    solver: str
    git_commit: str
    sha256: str
    byte_count: int

    @classmethod
    def from_path(
        cls, path: Path, project_root: Path, source_role: str
    ) -> "CertificateSummary":
        certificate = LevelCertificate.read(path)
        return cls(
            path=path.relative_to(project_root).as_posix(),
            source_role=source_role,
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
            lower_method=certificate.lower_method,
            upper_method=certificate.upper_method,
            generator=certificate.provenance.generator,
            solver=certificate.provenance.solver,
            git_commit=certificate.provenance.git_commit,
            sha256=_sha256(path),
            byte_count=path.stat().st_size,
        )

    def as_dict(self) -> dict[str, str | int]:
        return {
            "path": self.path,
            "source_role": self.source_role,
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
            "lower_method": self.lower_method,
            "upper_method": self.upper_method,
            "generator": self.generator,
            "solver": self.solver,
            "git_commit": self.git_commit,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
        }


@dataclass(frozen=True)
class DeliveryBundle:
    grid_rows: tuple[CertificateSummary, ...]
    strongest_xxx: CertificateSummary

    @property
    def rows(self) -> tuple[CertificateSummary, ...]:
        rows = (*self.grid_rows, self.strongest_xxx)
        return tuple(
            sorted(
                rows,
                key=lambda row: (
                    row.delta,
                    row.level,
                    row.source_role,
                    row.path,
                ),
            )
        )

    @property
    def record_gate(self) -> RecordGateSummary:
        return evaluate_record_gate(
            self.strongest_xxx.certified_lower,
            self.strongest_xxx.certified_upper,
        )


def build_delivery_bundle(project_root: Path) -> DeliveryBundle:
    """Load the compact grid and strongest selected XXX certificate."""
    project_root = Path(project_root).resolve()
    grid_paths = sorted(
        (project_root / "outputs/final/grid").glob("**/*.json")
    )
    strongest_paths = sorted(
        (project_root / "outputs/final/xxx_best").glob("*.json")
    )
    if not grid_paths:
        raise ValueError("selected XXZ grid is empty")
    if not strongest_paths:
        raise ValueError("selected XXX certificate is missing")
    grid_rows = tuple(
        CertificateSummary.from_path(path, project_root, "xxz-grid")
        for path in grid_paths
    )
    strongest_candidates = tuple(
        CertificateSummary.from_path(path, project_root, "xxx-strongest")
        for path in strongest_paths
    )
    strongest_xxx = min(
        (row for row in strongest_candidates if row.delta == Decimal("1")),
        key=lambda row: (row.width, -row.level),
    )
    return DeliveryBundle(grid_rows, strongest_xxx)


def _write_summary_csv(bundle: DeliveryBundle, path: Path) -> None:
    rows = [row.as_dict() for row in bundle.rows]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_record_gate(bundle: DeliveryBundle, path: Path) -> None:
    payload = bundle.record_gate.as_dict()
    payload.update(
        {
            "certificate_path": bundle.strongest_xxx.path,
            "normalization": "h=(XX+YY+ZZ)/4",
            "bethe_reference": "e_B=1/4-log(2)",
        }
    )
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_manifest(
    bundle: DeliveryBundle,
    project_root: Path,
    summary_path: Path,
    gate_path: Path,
    manifest_path: Path,
) -> None:
    lines = [
        "Issue #230 certified-delivery data manifest",
        "===========================================",
        "",
        "Model: spin-1/2 XXZ chain, h_Delta=(XX+YY+Delta ZZ)/4",
        "Trust boundary: Bethe data is used only by independent verification.",
        f"Selected certificate payloads: {len(bundle.rows)}",
        "",
        "SHA256  BYTES  ROLE  PATH",
    ]
    for row in bundle.rows:
        lines.append(
            f"{row.sha256}  {row.byte_count}  "
            f"{row.source_role}  {row.path}"
        )
    for role, path in (
        ("delivery-summary", summary_path),
        ("record-gate", gate_path),
    ):
        try:
            relative = path.relative_to(project_root).as_posix()
        except ValueError:
            relative = path.name
        lines.append(
            f"{_sha256(path)}  {path.stat().st_size}  {role}  {relative}"
        )
    lines.extend(
        [
            "",
            "Reproduce:",
            "  .venv/bin/python scripts/build_delivery_data.py",
            "  .venv/bin/pytest tests/test_delivery.py -q",
            "",
        ]
    )
    manifest_path.write_text("\n".join(lines), encoding="utf-8")


def write_delivery_bundle(
    bundle: DeliveryBundle, project_root: Path, output_dir: Path
) -> tuple[Path, Path, Path]:
    """Write deterministic CSV, record-gate JSON, and checksum manifest."""
    project_root = Path(project_root).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "certificate-summary.csv"
    gate_path = output_dir / "record-gate.json"
    manifest_path = output_dir / "DATA_MANIFEST.txt"
    _write_summary_csv(bundle, summary_path)
    _write_record_gate(bundle, gate_path)
    _write_manifest(
        bundle,
        project_root,
        summary_path,
        gate_path,
        manifest_path,
    )
    return summary_path, gate_path, manifest_path

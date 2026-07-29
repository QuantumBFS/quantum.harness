"""Automated integrity checks for generated HTML and PDF artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from pypdf import PdfReader


SECTION_TITLES = (
    "Executive Summary",
    "Conceptual Foundation",
    "Shared Computational Architecture",
    "Clean Ising Model",
    "Nishimori Random-Bond Ising Model",
    "Weak Self-Dual Majorana Network",
    "Cross-Model Comparison",
    "Error and Sensitivity Analysis",
    "Implementation and Reproducibility",
    "Conclusions",
    "Appendices",
)
HEADLINE_VALUES = ("0.499424", "0.456469", "0.444107")


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    checks: Tuple[str, ...]
    page_count: int = 0


def verify_html(path: Path) -> VerificationResult:
    source = Path(path)
    html = source.read_text(encoding="utf-8")
    visible = re.sub(r"data:image/png;base64,[A-Za-z0-9+/=]+", "", html)
    checks = []
    _require("<!doctype html>" in html.lower(), "HTML5 doctype")
    checks.append("HTML5 doctype")
    image_count = html.count("data:image/png;base64,")
    _require(image_count >= 20, "at least 20 embedded PNG figures")
    checks.append(f"{image_count} embedded PNG figures")
    _require("http://" not in visible and "https://" not in visible, "offline content")
    checks.append("no network dependencies")
    for title in SECTION_TITLES:
        _require(title in visible, f"section {title}")
    checks.append("all required sections")
    for value in HEADLINE_VALUES:
        _require(value in visible, f"headline value {value}")
    checks.append("all headline values")
    _require("TBD" not in visible and "TODO" not in visible, "no placeholders")
    checks.append("no placeholders")
    return VerificationResult(True, tuple(checks))


def verify_pdf(path: Path) -> VerificationResult:
    source = Path(path)
    _require(source.read_bytes()[:5] == b"%PDF-", "PDF signature")
    reader = PdfReader(source)
    page_count = len(reader.pages)
    _require(25 <= page_count <= 35, "PDF page count in [25, 35]")
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    for title in SECTION_TITLES:
        _require(title in text, f"PDF section {title}")
    for value in HEADLINE_VALUES:
        _require(value in text, f"PDF headline value {value}")
    _require("TBD" not in text and "TODO" not in text, "no PDF placeholders")
    image_count = sum(len(page.images) for page in reader.pages)
    _require(image_count >= 20, "at least 20 PDF images")
    checks = (
        "valid PDF signature",
        f"{page_count} A4 report pages",
        "all required sections",
        "all headline values",
        f"{image_count} embedded images",
        "no placeholders",
    )
    return VerificationResult(True, checks, page_count)


def _require(condition: bool, label: str) -> None:
    if not condition:
        raise ValueError(f"output verification failed: {label}")

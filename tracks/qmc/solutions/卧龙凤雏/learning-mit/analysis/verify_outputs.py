"""Structural and cross-language verification for standalone report pairs."""

from __future__ import annotations

from dataclasses import dataclass
import html
import json
from pathlib import Path
import re

from pypdf import PdfReader


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    errors: tuple[str, ...]


def verify_report_pair(run_dir: Path) -> VerificationResult:
    run_dir = Path(run_dir)
    errors: list[str] = []
    html_paths = (run_dir / "report.html", run_dir / "report-zh.html")
    pdf_paths = (run_dir / "report.pdf", run_dir / "report-zh.pdf")
    for path in (*html_paths, *pdf_paths):
        if not path.is_file() or path.stat().st_size < 1000:
            errors.append(f"missing or undersized report: {path.name}")
    if errors:
        return VerificationResult(False, tuple(errors))

    html_texts = [path.read_text(encoding="utf-8") for path in html_paths]
    forbidden = ("TODO", "TBD", "PLACEHOLDER", "turn0search", "example result")
    for path, text in zip(html_paths, html_texts, strict=True):
        visible_text = re.sub(
            r"data:image/png;base64,[A-Za-z0-9+/=]+", "", text, flags=re.DOTALL
        )
        for marker in forbidden:
            if marker.lower() in visible_text.lower():
                errors.append(f"unfinished marker {marker} in {path.name}")
        if "exploratory" not in text.lower() and "探索性" not in text:
            errors.append(f"missing exploratory label in {path.name}")

    facts = []
    for path, text in zip(html_paths, html_texts, strict=True):
        match = re.search(
            r'<script id="numeric-facts" type="application/json">(.*?)</script>',
            text,
            flags=re.DOTALL,
        )
        if not match:
            errors.append(f"numeric facts are absent from {path.name}")
            continue
        facts.append(json.loads(html.unescape(match.group(1))))
    if len(facts) == 2 and facts[0] != facts[1]:
        errors.append("English and Chinese numeric facts differ")
    if len(facts) == 2:
        for item in facts:
            if not item.get("alpha_stable") and item.get("central_charge_published"):
                errors.append("standalone central charge published despite unstable alpha")

    for path in pdf_paths:
        try:
            reader = PdfReader(path)
            if len(reader.pages) < 8:
                errors.append(f"PDF has too few pages: {path.name}")
            metadata = reader.metadata or {}
            if "numeric-facts-sha256=" not in str(metadata.get("/Subject", "")):
                errors.append(f"PDF lacks numeric fact hash: {path.name}")
        except Exception as error:
            errors.append(f"PDF cannot be parsed ({path.name}): {error}")
    if any(label in html_texts[1] for label in ("Contents", "Figure", "Interpretation limit")):
        errors.append("Chinese HTML contains untranslated renderer labels")
    return VerificationResult(not errors, tuple(errors))

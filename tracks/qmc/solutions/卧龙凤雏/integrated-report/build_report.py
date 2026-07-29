#!/usr/bin/env python3
"""Build and verify the integrated HTML and PDF reports."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Tuple

from analysis.comparison_plots import build_comparison_plots
from analysis.html_renderer import render_html
from analysis.pdf_renderer import render_pdf
from analysis.report_model import build_report
from analysis.sources import ModelResult, load_all_models
from analysis.verify_outputs import VerificationResult, verify_html, verify_pdf


PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_REPO_ROOT = PACKAGE_ROOT.parents[4]


@dataclass(frozen=True)
class BuildResult:
    html: Path
    pdf: Path
    html_verification: VerificationResult
    pdf_verification: VerificationResult


def build(repo_root: Path = DEFAULT_REPO_ROOT) -> BuildResult:
    root = Path(repo_root).resolve()
    models = load_all_models(root)
    source_fingerprint = _fingerprint(models)
    build_comparison_plots(models, PACKAGE_ROOT / "generated")
    report = build_report(models)

    html_output = root / "output/html/three-model-central-charge-report.html"
    pdf_output = root / "output/pdf/three-model-central-charge-report.pdf"
    html_output.parent.mkdir(parents=True, exist_ok=True)
    pdf_output.parent.mkdir(parents=True, exist_ok=True)
    html_temporary = html_output.with_name(f".{html_output.name}.tmp")
    pdf_temporary = pdf_output.with_name(f".{pdf_output.name}.tmp")

    try:
        render_html(report, html_temporary)
        render_pdf(report, pdf_temporary)
        html_result = verify_html(html_temporary)
        pdf_result = verify_pdf(pdf_temporary)
        if _fingerprint(load_all_models(root)) != source_fingerprint:
            raise ValueError("frozen source artifacts changed during report generation")
        html_temporary.replace(html_output)
        pdf_temporary.replace(pdf_output)
    finally:
        html_temporary.unlink(missing_ok=True)
        pdf_temporary.unlink(missing_ok=True)

    return BuildResult(html_output, pdf_output, html_result, pdf_result)


def _fingerprint(
    models: Tuple[ModelResult, ...]
) -> Tuple[Tuple[str, Tuple[Tuple[str, str], ...]], ...]:
    return tuple(
        (model.slug, tuple(sorted(model.provenance.items())))
        for model in models
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=DEFAULT_REPO_ROOT,
        help="Quantum Harness repository root",
    )
    args = parser.parse_args()
    result = build(args.repo_root)
    print(f"HTML: {result.html}")
    print(f"PDF:  {result.pdf}")
    print(f"PDF pages: {result.pdf_verification.page_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

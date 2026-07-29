#!/usr/bin/env python3
"""Build and verify the integrated HTML and PDF reports."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Tuple

from analysis.comparison_plots import build_comparison_plots
from analysis.html_renderer import render_html
from analysis.locale import get_locale
from analysis.pdf_renderer import render_pdf
from analysis.report_model import build_report
from analysis.report_model_zh import build_report_zh
from analysis.sources import ModelResult, load_all_models
from analysis.source_plots_zh import build_chinese_source_plots
from analysis.verify_outputs import VerificationResult, verify_html, verify_pdf


PACKAGE_ROOT = Path(__file__).resolve().parent
DEFAULT_REPO_ROOT = PACKAGE_ROOT.parents[4]


@dataclass(frozen=True)
class BuildResult:
    language: str
    html: Path
    pdf: Path
    html_verification: VerificationResult
    pdf_verification: VerificationResult


def build(
    repo_root: Path = DEFAULT_REPO_ROOT,
    language: str = "en",
) -> BuildResult:
    root = Path(repo_root).resolve()
    locale = get_locale(language)
    models = load_all_models(root)
    source_fingerprint = _fingerprint(models)
    if locale.code == "zh":
        plot_dir = PACKAGE_ROOT / "generated" / locale.plot_directory
        build_comparison_plots(models, plot_dir, locale)
        build_chinese_source_plots(root, plot_dir)
        report = build_report_zh(models)
    else:
        build_comparison_plots(models, PACKAGE_ROOT / "generated", locale)
        report = build_report(models)

    stem = f"three-model-central-charge-report{locale.output_suffix}"
    html_output = root / f"output/html/{stem}.html"
    pdf_output = root / f"output/pdf/{stem}.pdf"
    html_output.parent.mkdir(parents=True, exist_ok=True)
    pdf_output.parent.mkdir(parents=True, exist_ok=True)
    html_temporary = html_output.with_name(f".{html_output.name}.tmp")
    pdf_temporary = pdf_output.with_name(f".{pdf_output.name}.tmp")

    try:
        render_html(report, html_temporary, locale)
        render_pdf(report, pdf_temporary, locale)
        html_result = verify_html(html_temporary, locale)
        pdf_result = verify_pdf(pdf_temporary, locale)
        if _fingerprint(load_all_models(root)) != source_fingerprint:
            raise ValueError("frozen source artifacts changed during report generation")
        html_temporary.replace(html_output)
        pdf_temporary.replace(pdf_output)
    finally:
        html_temporary.unlink(missing_ok=True)
        pdf_temporary.unlink(missing_ok=True)

    return BuildResult(
        locale.code,
        html_output,
        pdf_output,
        html_result,
        pdf_result,
    )


def build_all(
    repo_root: Path = DEFAULT_REPO_ROOT,
) -> Tuple[BuildResult, BuildResult]:
    return (
        build(repo_root, language="en"),
        build(repo_root, language="zh"),
    )


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
    parser.add_argument(
        "--language",
        choices=("en", "zh", "all"),
        default="en",
        help="Report language to build; 'all' builds both editions",
    )
    args = parser.parse_args()
    results = (
        build_all(args.repo_root)
        if args.language == "all"
        else (build(args.repo_root, args.language),)
    )
    for result in results:
        print(f"[{result.language}] HTML: {result.html}")
        print(f"[{result.language}] PDF:  {result.pdf}")
        print(f"[{result.language}] PDF pages: {result.pdf_verification.page_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Structural verification for the compiled PRB manuscript."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from pypdf import PdfReader


@dataclass(frozen=True)
class PdfVerification:
    page_count: int
    page_width_points: float
    page_height_points: float
    figure_xobjects: int
    has_embedded_fonts: bool
    text_sha256: str


def extract_text(path: Path | str) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def verify_pdf(path: Path | str) -> PdfVerification:
    pdf_path = Path(path)
    if not pdf_path.is_file():
        raise ValueError(f"PDF is missing: {pdf_path}")
    reader = PdfReader(str(pdf_path))
    if not reader.pages:
        raise ValueError("PDF has no pages")

    widths = [float(page.mediabox.width) for page in reader.pages]
    heights = [float(page.mediabox.height) for page in reader.pages]
    if max(widths) - min(widths) > 0.01 or max(heights) - min(heights) > 0.01:
        raise ValueError("PDF contains inconsistent page geometries")
    if abs(widths[0] - 612.0) > 1.0 or abs(heights[0] - 792.0) > 1.0:
        raise ValueError("PDF is not US-letter sized")

    figures = sum(_figure_xobjects(page) for page in reader.pages)
    fonts = [
        font.get_object()
        for page in reader.pages
        for font in page.get("/Resources", {}).get("/Font", {}).values()
    ]
    embedded = bool(fonts) and all(_font_is_embedded(font) for font in fonts)
    if figures < 8:
        raise ValueError(f"expected at least eight figure objects, found {figures}")
    if not embedded:
        raise ValueError("one or more manuscript fonts are not embedded")

    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    for marker in ("TODO", "TBD", "PLACEHOLDER", "undefined citation"):
        if marker.lower() in text.lower():
            raise ValueError(f"visible placeholder marker in PDF: {marker}")
    for phrase in (
        "Xu Tian",
        "Huidan Tan",
        "arXiv:2502.14034",
    ):
        if phrase not in text:
            raise ValueError(f"required PDF text is missing: {phrase}")

    return PdfVerification(
        page_count=len(reader.pages),
        page_width_points=widths[0],
        page_height_points=heights[0],
        figure_xobjects=figures,
        has_embedded_fonts=embedded,
        text_sha256=sha256(text.encode("utf-8")).hexdigest(),
    )


def _figure_xobjects(page: object) -> int:
    xobjects = page.get("/Resources", {}).get("/XObject", {})
    return sum(
        item.get_object().get("/Subtype") in ("/Image", "/Form")
        for item in xobjects.values()
    )


def _font_is_embedded(font: object) -> bool:
    subtype = font.get("/Subtype")
    if subtype == "/Type0":
        descendants = font.get("/DescendantFonts", [])
        return bool(descendants) and all(
            _font_is_embedded(item.get_object()) for item in descendants
        )
    descriptor = font.get("/FontDescriptor")
    if descriptor is None:
        return False
    descriptor = descriptor.get_object()
    return any(key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    result = verify_pdf(args.pdf)
    print(
        f"verified {result.page_count} pages, "
        f"{result.figure_xobjects} figure objects, embedded fonts; "
        f"text sha256={result.text_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

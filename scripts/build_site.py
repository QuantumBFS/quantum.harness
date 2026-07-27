#!/usr/bin/env python3
"""Regenerate the harness website catalog pages from the .knowledge/ cards.

Writes solvable.html, models.html, methods.html — plus benchmarks.html when
.knowledge/solvable/benchmarks.json exists — into .github/template/
(deployed verbatim by the Pages workflow). Stdlib only; output is
byte-stable run-to-run. Cards are the source of truth — curated text in
sitegen is presentation-only (families, hooks, subtitles).

Usage:  python3 scripts/build_site.py [--out DIR]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sitegen import benchmarks, methods, models, solvable  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / ".github" / "template"


def build_all() -> dict:
    """filename -> rendered HTML for every catalog page."""
    pages = {
        "solvable.html": solvable.build_page(),
        "models.html": models.build_page(),
        "methods.html": methods.build_page(),
    }
    bench = benchmarks.build_page()
    if bench:
        pages["benchmarks.html"] = bench
    return pages


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT_DIR,
                    help="output directory (default: .github/template)")
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, html in build_all().items():
        p = args.out / name
        p.write_text(html, encoding="utf-8")
        print(f"wrote {p} ({len(html)} bytes)")


if __name__ == "__main__":
    main()

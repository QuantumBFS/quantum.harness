#!/usr/bin/env python3
"""Analyze a completed ceffflow run specification."""

from ceffflow.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["analyze", *__import__("sys").argv[1:]]))

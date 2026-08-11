#!/usr/bin/env python3
"""Execute one ceffflow run-spec cell."""

from ceffflow.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["cell", *__import__("sys").argv[1:]]))

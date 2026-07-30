"""Validate destination-local accepted inputs before cross-size submission."""

from __future__ import annotations

import argparse
from pathlib import Path

from challenge15.production_schema import validate_envelope


def main() -> int:
    parser = argparse.ArgumentParser()
    for size in (6, 7, 8):
        parser.add_argument(f"--n{size}-terminal-selection", required=True)
        parser.add_argument(f"--runtime-attestation-set-n{size}", required=True)
    for name in (
        "n8-provisional-finalization",
        "n8-reduction",
        "n8-import-receipt",
        "n8-transfer-receipt",
        "policy",
        "source-manifest",
    ):
        parser.add_argument(f"--{name}", required=True)
    args = parser.parse_args()
    for size in (6, 7, 8):
        terminal = validate_envelope(
            Path(getattr(args, f"n{size}_terminal_selection")),
            "challenge15.terminal-selection.v1",
        )
        if terminal["particles"] != size or terminal["production_accepted"] is not True:
            parser.error(f"N={size} terminal selection is not accepted")
        validate_envelope(
            Path(getattr(args, f"runtime_attestation_set_n{size}")),
            "challenge15.runtime-attestation-set.v1",
        )
    print("validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from trottercert.verify import verify_certificate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("certificate")
    parser.add_argument(
        "--deep",
        action="store_true",
        help="regenerate every local commutator and anticommuting proof term",
    )
    arguments = parser.parse_args()
    print(
        json.dumps(
            verify_certificate(arguments.certificate, deep=arguments.deep),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

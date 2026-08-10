#!/usr/bin/env python3
"""Atomically publish a directory without replacing an existing path."""

from __future__ import annotations

import argparse
import ctypes
import errno
import os
import platform
import sys
from pathlib import Path


_AT_FDCWD = -100
_RENAME_NOREPLACE = 1
_RENAMEAT2_SYSCALLS = {
    "x86_64": 316,
    "amd64": 316,
}


def rename_noreplace(source: Path, destination: Path) -> None:
    """Invoke Linux renameat2(RENAME_NOREPLACE), with no unsafe fallback."""
    if not sys.platform.startswith("linux"):
        raise OSError(errno.ENOSYS, "renameat2 is unsupported off Linux")
    machine = platform.machine().lower()
    syscall_number = _RENAMEAT2_SYSCALLS.get(machine)
    if syscall_number is None:
        raise OSError(
            errno.ENOSYS,
            f"renameat2 syscall number is unsupported on architecture {machine!r}",
        )

    libc = ctypes.CDLL(None, use_errno=True)
    syscall = libc.syscall
    syscall.restype = ctypes.c_long
    result = syscall(
        ctypes.c_long(syscall_number),
        ctypes.c_int(_AT_FDCWD),
        ctypes.c_char_p(os.fsencode(source)),
        ctypes.c_int(_AT_FDCWD),
        ctypes.c_char_p(os.fsencode(destination)),
        ctypes.c_uint(_RENAME_NOREPLACE),
    )
    if result != 0:
        error_number = ctypes.get_errno() or errno.EIO
        raise OSError(
            error_number,
            f"renameat2(RENAME_NOREPLACE) failed: {os.strerror(error_number)}",
            destination,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        rename_noreplace(args.source, args.destination)
    except OSError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

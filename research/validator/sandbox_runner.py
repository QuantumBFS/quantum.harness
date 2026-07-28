#!/usr/bin/env python3
"""Run an untrusted candidate with local I/O and process/network restrictions."""

from __future__ import annotations

import builtins
import os
from pathlib import Path
import runpy
import socket
import subprocess
import sys

candidate, input_dir, output = map(Path, sys.argv[1:4])
allowed = [candidate.resolve(), input_dir.resolve(), output.resolve(), Path(sys.base_prefix).resolve()]
allowed.extend(
    Path(item).resolve()
    for item in sys.path
    if item and ("site-packages" in item or Path(item).resolve() == Path(sys.base_prefix).resolve())
)


def blocked(*_args, **_kwargs):
    raise PermissionError("sandbox blocks network and subprocess access")


def guarded_open(file, *args, **kwargs):
    path = Path(file).resolve()
    if not any(path == root or root in path.parents for root in allowed):
        raise PermissionError(f"sandbox blocks out-of-scope read: {path}")
    return original_open(file, *args, **kwargs)


def guarded_path_open(self, *args, **kwargs):
    return guarded_open(self, *args, **kwargs)


original_open = builtins.open
socket.socket = blocked
socket.create_connection = blocked
subprocess.Popen = blocked
os.system = blocked
os.chdir(candidate)
sys.path.insert(0, str(candidate))
sys.argv = [str(candidate / "run.py"), "--input-dir", str(input_dir), "--output", str(output)]
builtins.open = guarded_open
Path.open = guarded_path_open
Path.read_text = lambda self, *args, **kwargs: guarded_path_open(self, *args, **kwargs).read()
Path.read_bytes = lambda self: guarded_path_open(self, "rb").read()
runpy.run_path(str(candidate / "run.py"), run_name="__main__")

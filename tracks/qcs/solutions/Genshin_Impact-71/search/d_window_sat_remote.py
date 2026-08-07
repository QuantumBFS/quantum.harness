#!/usr/bin/env python3
"""Linux-portable entry point for the independently audited D-window SAT code.

The canonical implementation is kept byte-for-byte in ``d_window_sat.py``.
This loader changes exactly its host-specific module locator before compiling
it, so both direct execution and import by the HPC budget wrapper use the
sibling ``window_search.py`` on t02.
"""

from __future__ import annotations

from pathlib import Path


SOURCE_PATH = Path(__file__).with_name("d_window_sat.py")
MODULE_PATH = Path(__file__).with_name("window_search.py")
source = SOURCE_PATH.read_text(encoding="utf-8")
windows_locator = (
    'MODULE_PATH = Path(r"C:\\tmp\\occam71_d_window\\window_search.py")'
)
portable_locator = 'MODULE_PATH = Path(__file__).with_name("window_search.py")'
if source.count(windows_locator) != 1:
    raise RuntimeError(
        "audited d_window_sat.py no longer has exactly one expected "
        "host-specific MODULE_PATH"
    )
source = source.replace(windows_locator, portable_locator)
exec(compile(source, str(SOURCE_PATH), "exec"), globals(), globals())

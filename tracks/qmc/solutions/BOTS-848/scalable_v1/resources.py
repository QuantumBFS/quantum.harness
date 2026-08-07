from __future__ import annotations

import ctypes
import os
import sys
import time
from dataclasses import dataclass, field


if os.name == "nt":
    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    _GET_CURRENT_PROCESS = ctypes.windll.kernel32.GetCurrentProcess
    _GET_CURRENT_PROCESS.restype = ctypes.c_void_p
    _GET_PROCESS_MEMORY_INFO = ctypes.windll.psapi.GetProcessMemoryInfo
    _GET_PROCESS_MEMORY_INFO.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), ctypes.c_ulong
    ]
    _GET_PROCESS_MEMORY_INFO.restype = ctypes.c_int


def peak_rss_bytes() -> int:
    if os.name == "nt":
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(counters)
        process = _GET_CURRENT_PROCESS()
        ok = _GET_PROCESS_MEMORY_INFO(process, ctypes.byref(counters), counters.cb)
        if not ok:
            raise OSError("GetProcessMemoryInfo failed")
        return int(counters.PeakWorkingSetSize)
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


@dataclass
class RuntimeMeter:
    started: float = field(init=False, default=0.0)
    wall_seconds: float = field(init=False, default=0.0)
    peak_rss_bytes: int = field(init=False, default=0)

    def __enter__(self) -> "RuntimeMeter":
        self.started = time.perf_counter()
        return self

    def __exit__(self, *args: object) -> None:
        self.wall_seconds = time.perf_counter() - self.started
        self.peak_rss_bytes = peak_rss_bytes()

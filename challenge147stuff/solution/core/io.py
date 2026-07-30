"""IO and memory-guard helpers shared by all engines.

The memory guard is the mechanism that enforces the challenge's hard
constraint "prefer lost efficiency over a crash": every numerically heavy
stage calls ``assert_mem_available`` *before* a large allocation, and the
driver catches ``MemoryBudgetExceeded`` to degrade gracefully (smaller
lattice / lower bond dim / fewer samples), recording the actual size in a
JSON manifest.
"""
import json
import csv
import os


class MemoryBudgetExceeded(MemoryError):
    """Raised before an allocation that would exceed the available RAM budget.

    Carries the requesting context and the requested/available GB so the
    driver can log and decide on a degradation strategy.
    """

    def __init__(self, context, requested_gb, available_gb):
        super().__init__(
            f"{context}: need {requested_gb:.3f} GB, only {available_gb:.3f} GB available"
        )
        self.context = context
        self.requested_gb = requested_gb
        self.available_gb = available_gb


def assert_mem_available(needed_gb, context):
    """Raise ``MemoryBudgetExceeded`` if ``needed_gb`` (GB) would exceed 80% of
    the currently available RAM. No-op (never raises) if psutil is missing or
    the read fails — the guard itself must never crash the run.
    """
    try:
        import psutil

        available_gb = psutil.virtual_memory().available / 1e9
    except Exception:
        return
    if needed_gb > 0.8 * available_gb:
        raise MemoryBudgetExceeded(context, needed_gb, available_gb)


def write_manifest(path, manifest):
    """Write a run manifest as indented JSON, creating parent dirs."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)


def write_csv(path, rows, fieldnames):
    """Write ``rows`` (list of dict) to a CSV with the given header, creating
    parent dirs."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def read_csv(path):
    """Read a CSV into a list of dicts (string values)."""
    with open(path) as f:
        return list(csv.DictReader(f))

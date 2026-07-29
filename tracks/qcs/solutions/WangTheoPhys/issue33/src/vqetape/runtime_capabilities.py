"""Machine-readable runtime, device, and memory capability evidence."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import importlib.metadata
import json
import platform
from pathlib import Path
from typing import Any

import jax
import numpy as np


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _device_payload(device) -> dict[str, Any]:
    memory_stats = None
    try:
        memory_stats = device.memory_stats()
    except (AttributeError, RuntimeError):
        pass
    return {
        "id": device.id,
        "platform": device.platform,
        "device_kind": device.device_kind,
        "process_index": device.process_index,
        "memory_stats_available": memory_stats is not None,
        "memory_stats": memory_stats,
    }


def _compiler_memory_probe() -> dict[str, Any]:
    function = jax.jit(lambda value: value * value + 1)
    compiled = function.lower(
        np.ones((8,), dtype=np.float32)
    ).compile()
    if not hasattr(compiled, "memory_analysis"):
        return {
            "available": False,
            "reason": (
                "compiled executable has no memory_analysis"
            ),
        }
    analysis = compiled.memory_analysis()
    if analysis is None:
        return {
            "available": False,
            "reason": (
                "backend returned no compiler memory analysis"
            ),
        }
    fields = {}
    for name in (
        "argument_size_in_bytes",
        "output_size_in_bytes",
        "alias_size_in_bytes",
        "temp_size_in_bytes",
        "generated_code_size_in_bytes",
    ):
        value = getattr(analysis, name, None)
        fields[name] = (
            int(value) if value is not None else None
        )
    return {
        "available": True,
        "fields": fields,
        "meaning": (
            "compiler estimate; not measured device peak"
        ),
    }


def runtime_capabilities() -> dict[str, Any]:
    """Inspect this process without claiming unavailable GPU evidence."""

    devices = jax.devices()
    gpu_devices = [
        device
        for device in devices
        if device.platform in ("gpu", "cuda", "rocm")
    ]
    if gpu_devices:
        gpu_benchmark = {
            "status": "available",
            "reason": None,
            "device_count": len(gpu_devices),
            "peak_memory_measured": False,
            "next_action": (
                "run benchmark workers with XProf or NVML "
                "peak collection"
            ),
        }
    else:
        gpu_benchmark = {
            "status": "skipped",
            "reason": (
                "JAX reports no GPU device; CUDA/ROCm runtime "
                "and genuine GPU peak memory were not measured"
            ),
            "device_count": 0,
            "peak_memory_measured": False,
        }
    profiler_memory_api = hasattr(
        jax.profiler,
        "save_device_memory_profile",
    )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "host": {
            "python": platform.python_version(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        },
        "packages": {
            "jax": jax.__version__,
            "jaxlib": _package_version("jaxlib"),
            "numpy": np.__version__,
            "scipy": _package_version("scipy"),
            "opt_einsum": _package_version("opt_einsum"),
        },
        "jax": {
            "default_backend": jax.default_backend(),
            "x64_enabled": bool(
                jax.config.jax_enable_x64
            ),
            "device_count": len(devices),
            "devices": [
                _device_payload(device)
                for device in devices
            ],
        },
        "memory_evidence": {
            "process_peak_rss": {
                "available": True,
                "meaning": (
                    "host process resident-set peak; not GPU "
                    "peak memory"
                ),
            },
            "compiler_memory_analysis": (
                _compiler_memory_probe()
            ),
            "device_memory_profile_api": {
                "available": profiler_memory_api,
                "meaning": (
                    "profiling API availability does not imply "
                    "a GPU measurement was collected"
                ),
            },
        },
        "gpu_benchmark": gpu_benchmark,
    }


def _write_markdown(
    payload: dict[str, Any],
    destination: Path,
) -> None:
    gpu = payload["gpu_benchmark"]
    compiler = payload["memory_evidence"][
        "compiler_memory_analysis"
    ]
    lines = [
        "# VQETape runtime capabilities",
        "",
        f"- Backend: `{payload['jax']['default_backend']}`.",
        f"- JAX devices: `{payload['jax']['device_count']}`.",
        f"- JAX x64 enabled in probe: "
        f"`{payload['jax']['x64_enabled']}`.",
        f"- GPU benchmark status: `{gpu['status']}`.",
    ]
    if gpu["reason"] is not None:
        lines.append(f"- GPU skip reason: {gpu['reason']}.")
    lines.extend(
        [
            "- Process peak RSS means host resident memory; it "
            "is never reported as GPU peak memory.",
            "- Compiler memory analysis available: "
            f"`{compiler['available']}`.",
            "",
            "## Devices",
            "",
        ]
    )
    for device in payload["jax"]["devices"]:
        lines.append(
            f"- `{device['platform']}:{device['id']}` — "
            f"{device['device_kind']}; device memory stats "
            f"available: `{device['memory_stats_available']}`."
        )
    lines.extend(
        [
            "",
            "No CUDA-specific performance or memory conclusion "
            "is made when the GPU status is skipped.",
            "",
        ]
    )
    destination.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def write_runtime_capabilities(
    output: Path,
    findings: Path,
) -> dict[str, Any]:
    payload = runtime_capabilities()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    findings.parent.mkdir(parents=True, exist_ok=True)
    _write_markdown(payload, findings)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--findings", required=True, type=Path)
    args = parser.parse_args(argv)
    payload = write_runtime_capabilities(
        args.output,
        args.findings,
    )
    print(
        f"backend={payload['jax']['default_backend']} "
        f"gpu={payload['gpu_benchmark']['status']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

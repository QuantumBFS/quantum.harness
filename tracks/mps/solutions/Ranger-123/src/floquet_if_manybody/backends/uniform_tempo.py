"""Pinned UniformTEMPO.jl backend for periodic non-Markovian correlations."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
from numpy.typing import NDArray

from ..config import BathConfig, ModelConfig
from ..correlations import CorrelationResult, coherent_decomposition
from ..operators import ComplexMatrix

METHOD = "uniform_tempo_floquet_multitime"
UNIFORM_TEMPO_REVISION = "b76a018c32e5415989761d902b1b0e95f1a337da"


@dataclass(frozen=True)
class UniformTempoControls:
    """Complete numerical controls passed to the Julia runner."""

    steps_per_period: int
    tolerance: float
    phase_samples: int
    delay_periods: int
    auto_nc: bool = True
    memory_cutoff: int = 100_000
    low_rank_svd: bool = False
    truncation: Literal["rel", "abs"] = "rel"
    cap_rank: int = 100_000
    max_rank: int = 100_000
    pole_count: int = 0
    pole_tolerance: float = 1e-10
    pole_maxiter: int = 2_000

    def __post_init__(self) -> None:
        if self.steps_per_period < 2:
            raise ValueError("steps_per_period must be at least two")
        if not 0 < self.tolerance < 1:
            raise ValueError("tolerance must lie between zero and one")
        if (
            self.phase_samples < 2
            or self.phase_samples > self.steps_per_period
            or self.steps_per_period % self.phase_samples != 0
        ):
            raise ValueError("phase_samples must divide steps_per_period")
        if self.delay_periods < 1:
            raise ValueError("delay_periods must be positive")
        if self.memory_cutoff < 1:
            raise ValueError("memory_cutoff must be positive")
        if self.truncation not in ("rel", "abs"):
            raise ValueError("truncation must be 'rel' or 'abs'")
        if self.cap_rank < 1 or self.max_rank < self.cap_rank:
            raise ValueError("invalid rank limits")
        if isinstance(self.pole_count, bool) or self.pole_count < 0:
            raise ValueError("pole_count must be nonnegative")
        if self.pole_tolerance <= 0:
            raise ValueError("pole_tolerance must be positive")
        if isinstance(self.pole_maxiter, bool) or self.pole_maxiter < 1:
            raise ValueError("pole_maxiter must be positive")

    @property
    def phase_offsets(self) -> tuple[int, ...]:
        stride = self.steps_per_period // self.phase_samples
        return tuple(range(0, self.steps_per_period, stride))

    @property
    def delay_steps(self) -> int:
        return self.delay_periods * self.steps_per_period


@dataclass(frozen=True)
class UniformTempoResult:
    method: str
    floquet_state: ComplexMatrix
    phase_states: NDArray[np.complex128]
    correlation: CorrelationResult
    diagnostics: dict[str, float]
    metadata: dict[str, float | int | str]
    transfer_eigenvalues: NDArray[np.complex128] = field(
        default_factory=lambda: np.empty(0, dtype=np.complex128)
    )
    transfer_eigenpair_residuals: NDArray[np.float64] = field(
        default_factory=lambda: np.empty(0, dtype=np.float64)
    )


def _encode_complex(values: NDArray[np.complex128] | ComplexMatrix) -> dict[str, Any]:
    array = np.asarray(values, dtype=np.complex128)
    return {
        "real": np.real(array).astype(float).tolist(),
        "imag": np.imag(array).astype(float).tolist(),
    }


def _tensor_cache_key(
    coupling: ComplexMatrix,
    model: ModelConfig,
    bath: BathConfig,
    controls: UniformTempoControls,
) -> str:
    """Fingerprint every input that changes the uniform process tensor."""
    payload = {
        "schema": "uniform-process-tensor-v1",
        "uniform_tempo_revision": UNIFORM_TEMPO_REVISION,
        "coupling": _encode_complex(np.asarray(coupling, dtype=np.complex128)),
        "bath": asdict(bath),
        "dt": model.period / controls.steps_per_period,
        "tolerance": controls.tolerance,
        "auto_nc": controls.auto_nc,
        "memory_cutoff": controls.memory_cutoff,
        "low_rank_svd": controls.low_rank_svd,
        "truncation": controls.truncation,
        "cap_rank": controls.cap_rank,
        "max_rank": controls.max_rank,
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _required(payload: dict[str, Any], key: str, context: str = "payload") -> Any:
    if key not in payload:
        raise ValueError(f"{context} is missing required field {key!r}")
    return payload[key]


def _decode_complex(
    payload: dict[str, Any],
    *,
    label: str,
    allow_empty: bool = False,
) -> NDArray[np.complex128]:
    try:
        shape = tuple(int(value) for value in payload["shape"])
        real = np.asarray(payload["real"], dtype=float)
        imag = np.asarray(payload["imag"], dtype=float)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{label} has an invalid complex-array schema") from exc
    expected = int(np.prod(shape, dtype=np.int64))
    if (
        expected < 0
        or (expected == 0 and not allow_empty)
        or real.size != expected
        or imag.size != expected
    ):
        raise ValueError(f"{label} data do not match the declared shape")
    values = real.reshape(-1) + 1j * imag.reshape(-1)
    array = values.reshape(shape, order="F")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{label} contains non-finite values")
    return cast(NDArray[np.complex128], array)


class UniformTempoBackend:
    """Subprocess boundary around the pinned Julia implementation."""

    def __init__(
        self,
        *,
        command_prefix: tuple[str, ...] | None = None,
        timeout_seconds: float = 86_400.0,
        tensor_cache_directory: Path | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        root = Path(__file__).resolve().parents[3]
        if command_prefix is None:
            julia = shutil.which("julia")
            if julia is None:
                raise RuntimeError("UniformTEMPO backend requires Julia on PATH")
            command_prefix = (
                julia,
                f"--project={root / 'julia'}",
                str(root / "julia" / "run_uniform_tempo.jl"),
            )
        if not command_prefix:
            raise ValueError("command_prefix must not be empty")
        self._command_prefix = tuple(command_prefix)
        self._timeout_seconds = timeout_seconds
        self._tensor_cache_directory = (
            None
            if tensor_cache_directory is None
            else Path(tensor_cache_directory).resolve()
        )

    def run_periodic(
        self,
        h0: ComplexMatrix,
        coupling: ComplexMatrix,
        model: ModelConfig,
        bath: BathConfig,
        controls: UniformTempoControls,
        *,
        drive_operator: ComplexMatrix | None = None,
    ) -> UniformTempoResult:
        """Compute the Floquet state and phase-averaged two-time correlation."""
        h0_array = np.asarray(h0, dtype=np.complex128)
        coupling_array = np.asarray(coupling, dtype=np.complex128)
        drive_array = (
            coupling_array
            if drive_operator is None
            else np.asarray(drive_operator, dtype=np.complex128)
        )
        if h0_array.ndim != 2 or h0_array.shape[0] != h0_array.shape[1]:
            raise ValueError("h0 must be a square matrix")
        if coupling_array.shape != h0_array.shape:
            raise ValueError("coupling must match h0")
        if drive_array.shape != h0_array.shape:
            raise ValueError("drive_operator must match h0")
        if not all(
            np.all(np.isfinite(array))
            for array in (h0_array, coupling_array, drive_array)
        ):
            raise ValueError("system operators must contain finite values")
        if not np.allclose(h0_array, h0_array.conj().T, atol=1e-10):
            raise ValueError("h0 must be Hermitian")
        if not np.allclose(coupling_array, coupling_array.conj().T, atol=1e-10):
            raise ValueError("coupling must be Hermitian")
        if not np.allclose(drive_array, drive_array.conj().T, atol=1e-10):
            raise ValueError("drive_operator must be Hermitian")

        request: dict[str, Any] = {
            "h0": _encode_complex(h0_array),
            "coupling": _encode_complex(coupling_array),
            "drive": _encode_complex(drive_array),
            "model": asdict(model),
            "bath": asdict(bath),
            "controls": {
                "steps_per_period": controls.steps_per_period,
                "tolerance": controls.tolerance,
                "phase_offsets": list(controls.phase_offsets),
                "delay_steps": controls.delay_steps,
                "auto_nc": controls.auto_nc,
                "memory_cutoff": controls.memory_cutoff,
                "low_rank_svd": controls.low_rank_svd,
                "truncation": controls.truncation,
                "cap_rank": controls.cap_rank,
                "max_rank": controls.max_rank,
                "pole_count": controls.pole_count,
                "pole_tolerance": controls.pole_tolerance,
                "pole_maxiter": controls.pole_maxiter,
            },
        }
        if self._tensor_cache_directory is not None:
            tensor_key = _tensor_cache_key(
                coupling_array,
                model,
                bath,
                controls,
            )
            self._tensor_cache_directory.mkdir(parents=True, exist_ok=True)
            request["controls"]["process_tensor_cache_key"] = tensor_key
            request["controls"]["process_tensor_cache_path"] = str(
                self._tensor_cache_directory / f"{tensor_key}.jls"
            )
        with tempfile.TemporaryDirectory(prefix="uniform-tempo-") as temporary:
            temporary_path = Path(temporary)
            input_path = temporary_path / "input.json"
            output_path = temporary_path / "output.json"
            input_path.write_text(
                json.dumps(request, sort_keys=True),
                encoding="utf-8",
            )
            try:
                completed = subprocess.run(
                    [*self._command_prefix, str(input_path), str(output_path)],
                    capture_output=True,
                    text=True,
                    timeout=self._timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    f"UniformTEMPO runner exceeded {self._timeout_seconds:g} seconds"
                ) from exc
            if completed.returncode != 0:
                detail = completed.stderr.strip() or completed.stdout.strip()
                raise RuntimeError(
                    f"UniformTEMPO runner failed with exit code "
                    f"{completed.returncode}: {detail}"
                )
            if not output_path.is_file():
                raise RuntimeError("UniformTEMPO runner did not create output JSON")
            try:
                payload = cast(
                    dict[str, Any],
                    json.loads(output_path.read_text(encoding="utf-8")),
                )
            except (json.JSONDecodeError, OSError) as exc:
                raise ValueError("UniformTEMPO runner returned malformed JSON") from exc
        return self._validate_payload(payload, h0_array.shape[0], model, controls)

    @staticmethod
    def _validate_payload(
        payload: dict[str, Any],
        dimension: int,
        model: ModelConfig,
        controls: UniformTempoControls,
    ) -> UniformTempoResult:
        method = str(_required(payload, "method"))
        if method != METHOD:
            raise ValueError(f"unexpected UniformTEMPO method label {method!r}")
        for provenance_key in (
            "julia_version",
            "uniform_tempo_revision",
            "manifest_sha256",
        ):
            if provenance_key not in payload or not str(payload[provenance_key]):
                raise ValueError("UniformTEMPO payload is missing provenance")
        manifest_hash = str(payload["manifest_sha256"])
        if len(manifest_hash) != 64:
            raise ValueError("UniformTEMPO manifest provenance is invalid")

        period_steps = int(_required(payload, "period_steps"))
        if period_steps != controls.steps_per_period:
            raise ValueError("UniformTEMPO period grid does not match the request")
        phase_offsets = tuple(int(value) for value in _required(payload, "phase_offsets"))
        if phase_offsets != controls.phase_offsets:
            raise ValueError("UniformTEMPO phase grid does not match the request")
        dt = float(_required(payload, "dt"))
        if not np.isclose(
            dt,
            model.period / controls.steps_per_period,
            rtol=1e-11,
            atol=1e-13,
        ):
            raise ValueError("UniformTEMPO timestep does not match the model period")

        floquet_state_raw = _decode_complex(
            cast(dict[str, Any], _required(payload, "floquet_state")),
            label="floquet_state",
        )
        if floquet_state_raw.shape != (dimension, dimension):
            raise ValueError("floquet_state has the wrong shape")
        phase_states_raw = _decode_complex(
            cast(dict[str, Any], _required(payload, "phase_states")),
            label="phase_states",
        )
        expected_phase_shape = (
            dimension,
            dimension,
            controls.phase_samples,
        )
        if phase_states_raw.shape != expected_phase_shape:
            raise ValueError("phase_states have the wrong shape")
        phase_states = np.moveaxis(phase_states_raw, 2, 0)

        delay = np.asarray(_required(payload, "delay"), dtype=float)
        if delay.shape != (controls.delay_steps + 1,) or not np.all(np.isfinite(delay)):
            raise ValueError("delay grid has the wrong shape")
        if not np.allclose(delay, np.arange(len(delay)) * dt, atol=1e-12):
            raise ValueError("delay grid is not uniform")
        total = _decode_complex(
            cast(dict[str, Any], _required(payload, "correlation")),
            label="correlation",
        )
        if total.shape != delay.shape:
            raise ValueError("correlation data do not match the delay shape")
        one_point = np.asarray(_required(payload, "one_point"), dtype=float)
        if one_point.shape != (controls.phase_samples,) or not np.all(
            np.isfinite(one_point)
        ):
            raise ValueError("one_point data have the wrong shape")
        coherent, peaks = coherent_decomposition(
            one_point,
            model.drive_frequency,
            delay,
        )
        correlation = CorrelationResult(
            delay,
            total,
            total - coherent,
            coherent,
            peaks,
            METHOD,
            {
                "period_steps": float(period_steps),
                "phase_samples": float(controls.phase_samples),
                "dt": dt,
            },
        )

        diagnostics_payload = cast(
            dict[str, Any],
            _required(payload, "diagnostics"),
        )
        diagnostic_keys = (
            "trace_error",
            "hermiticity_error",
            "minimum_density_eigenvalue",
            "fixed_point_residual",
            "floquet_transfer_residual",
        )
        try:
            diagnostics = {
                key: float(diagnostics_payload[key]) for key in diagnostic_keys
            }
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("UniformTEMPO diagnostics are incomplete") from exc
        if not all(np.isfinite(value) for value in diagnostics.values()):
            raise ValueError("UniformTEMPO diagnostics contain non-finite values")

        transfer_dimension = int(_required(payload, "transfer_dimension"))
        if transfer_dimension < 2:
            raise ValueError("UniformTEMPO transfer dimension is invalid")
        transfer_eigenvalues = _decode_complex(
            cast(dict[str, Any], _required(payload, "transfer_eigenvalues")),
            label="transfer_eigenvalues",
            allow_empty=True,
        )
        if transfer_eigenvalues.ndim != 1:
            raise ValueError("transfer_eigenvalues must be one-dimensional")
        transfer_eigenpair_residuals = np.asarray(
            _required(payload, "transfer_eigenpair_residuals"),
            dtype=float,
        )
        if transfer_eigenpair_residuals.ndim != 1:
            raise ValueError(
                "transfer_eigenpair_residuals must be one-dimensional"
            )
        if transfer_eigenvalues.shape != transfer_eigenpair_residuals.shape:
            raise ValueError(
                "transfer eigenvalues and residuals must have the same length"
            )
        expected_poles = min(controls.pole_count, transfer_dimension - 1)
        if len(transfer_eigenvalues) != expected_poles:
            raise ValueError(
                "UniformTEMPO returned "
                f"{len(transfer_eigenvalues)} poles; expected {expected_poles}"
            )
        if not np.all(np.isfinite(transfer_eigenpair_residuals)):
            raise ValueError("transfer eigenpair residuals contain non-finite values")
        if np.any(transfer_eigenpair_residuals < 0):
            raise ValueError("transfer eigenpair residuals must be nonnegative")

        metadata: dict[str, float | int | str] = {
            "dt": dt,
            "period_steps": period_steps,
            "phase_samples": controls.phase_samples,
            "bond_dimension": int(_required(payload, "bond_dimension")),
            "tolerance": controls.tolerance,
            "julia_version": str(payload["julia_version"]),
            "uniform_tempo_revision": str(payload["uniform_tempo_revision"]),
            "manifest_sha256": manifest_hash,
            "process_tensor_cache_hit": int(
                bool(_required(payload, "process_tensor_cache_hit"))
            ),
            "transfer_dimension": transfer_dimension,
            "pole_count": len(transfer_eigenvalues),
        }
        return UniformTempoResult(
            method,
            floquet_state_raw,
            phase_states,
            correlation,
            diagnostics,
            metadata,
            transfer_eigenvalues,
            transfer_eigenpair_residuals,
        )

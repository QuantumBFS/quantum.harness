"""OQuPy PT-TEMPO backend for controlled non-Markovian calculations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from ..config import BathConfig
from ..operators import ComplexMatrix
from .base import OpenSystemResult


@dataclass(frozen=True)
class PtTempoResult:
    result: OpenSystemResult
    process_tensor: Any
    system: Any
    bath: Any
    initial_density: ComplexMatrix


class PtTempoBackend:
    """Numerically controlled PT-TEMPO process-tensor wrapper.

    OQuPy uses ``J(w)=2*alpha*w*exp(-w/wc)``. This wrapper passes half of the
    project's alpha so both packages implement the same spectral density.
    """

    method = "pt_tempo"

    @staticmethod
    def _oqupy() -> Any:
        try:
            import oqupy
        except ImportError as exc:
            raise RuntimeError(
                "PT-TEMPO requires the 'nonmarkov' optional dependencies"
            ) from exc
        return oqupy

    def run(
        self,
        hamiltonian: Any,
        coupling: ComplexMatrix,
        initial_density: ComplexMatrix,
        bath_config: BathConfig,
        dt: float,
        steps: int,
        memory_steps: int,
        epsrel: float,
    ) -> PtTempoResult:
        if dt <= 0 or steps < 1 or memory_steps < 1 or not 0 < epsrel < 1:
            raise ValueError("invalid PT-TEMPO numerical parameters")
        oqupy = self._oqupy()
        correlations = oqupy.PowerLawSD(
            alpha=bath_config.alpha / 2,
            zeta=1,
            cutoff=bath_config.cutoff,
            cutoff_type="exponential",
            temperature=bath_config.temperature,
        )
        bath = oqupy.Bath(coupling, correlations)
        parameters = oqupy.TempoParameters(
            dt=dt,
            epsrel=epsrel,
            dkmax=memory_steps,
        )
        process_tensor = oqupy.pt_tempo_compute(
            bath=bath,
            start_time=0.0,
            end_time=steps * dt,
            parameters=parameters,
            unique=True,
            progress_type="silent",
        )
        system = oqupy.TimeDependentSystem(hamiltonian)
        dynamics = oqupy.compute_dynamics(
            system=system,
            initial_state=initial_density,
            process_tensor=process_tensor,
            progress_type="silent",
        )
        states = np.asarray(dynamics.states, dtype=np.complex128)
        traces = np.trace(states, axis1=1, axis2=2)
        trace_error = float(np.max(abs(traces - 1)))
        minimum_eigenvalue = float(
            min(np.min(np.linalg.eigvalsh((state + state.conj().T) / 2)) for state in states)
        )
        bond_dimensions = process_tensor.get_bond_dimensions()
        result = OpenSystemResult(
            self.method,
            states,
            np.asarray(dynamics.times, dtype=np.float64),
            trace_error < 5e-3 and minimum_eigenvalue > -5e-3,
            {
                "trace_error": trace_error,
                "minimum_density_eigenvalue": minimum_eigenvalue,
                "maximum_bond_dimension": float(np.max(bond_dimensions)),
            },
            {
                "approximation": "PT-TEMPO: finite dt, dkmax and SVD epsrel",
                "dt": dt,
                "memory_steps": memory_steps,
                "epsrel": epsrel,
                "spectral_density_convention": (
                    "OQuPy alpha divided by two to match J=alpha*w*exp(-w/wc)"
                ),
            },
        )
        return PtTempoResult(result, process_tensor, system, bath, initial_density)

    def period_averaged_correlation(
        self,
        run: PtTempoResult,
        operator: ComplexMatrix,
        phase_start: int,
        period_steps: int,
        delay_steps: int,
        drive_frequency: float,
        phase_offsets: list[int] | None = None,
    ) -> Any:
        """Calculate exact process-tensor insertions and average drive phases."""
        from ..correlations import CorrelationResult, coherent_decomposition

        oqupy = self._oqupy()
        offsets = list(range(period_steps)) if phase_offsets is None else phase_offsets
        if (
            len(offsets) < 2
            or len(set(offsets)) != len(offsets)
            or min(offsets) < 0
            or max(offsets) >= period_steps
        ):
            raise ValueError("phase offsets must be distinct indices in one period")
        initial_indices = [phase_start + offset for offset in offsets]
        final_indices = list(
            range(phase_start, phase_start + period_steps + delay_steps)
        )
        _, matrix = oqupy.compute_correlations(
            system=run.system,
            process_tensor=run.process_tensor,
            operator_a=operator,
            operator_b=operator,
            times_a=initial_indices,
            times_b=final_indices,
            time_order="ordered",
            initial_state=run.initial_density,
            progress_type="silent",
        )
        total = np.empty(delay_steps + 1, dtype=np.complex128)
        for delay in range(delay_steps + 1):
            values = [
                matrix[row, offset + delay]
                for row, offset in enumerate(offsets)
            ]
            total[delay] = np.mean(values)
        dt = float(run.result.times[1] - run.result.times[0])
        delays = np.arange(delay_steps + 1, dtype=np.float64) * dt
        phase_states = run.result.density_matrices[
            [phase_start + offset for offset in offsets]
        ]
        one_point = np.real(
            np.einsum("ij,tji->t", operator, phase_states, optimize=True)
        )
        coherent, peaks = coherent_decomposition(one_point, drive_frequency, delays)
        return CorrelationResult(
            delays,
            total,
            total - coherent,
            coherent,
            peaks,
            "pt_tempo_multitime",
            {
                "period_steps": float(period_steps),
                "phase_samples": float(len(offsets)),
                "dt": dt,
                "phase_start": float(phase_start),
            },
        )
